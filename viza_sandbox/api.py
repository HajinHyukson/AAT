"""HTTP API for the quant sandbox."""

from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.encoders import jsonable_encoder

from viza_sandbox.canonical import PostgresCanonicalSource
from viza_sandbox.config import SandboxSettings
from viza_sandbox.runner import DockerRunner, LocalProcessRunner
from viza_sandbox.runs import RunRequest, SandboxService, result_header
from viza_sandbox.store import SandboxRun, SandboxStore, SandboxUser

_HIDDEN_RUN_COLUMNS = {"result_path"}


def create_app(service: SandboxService, store: SandboxStore) -> FastAPI:
    # Runs a previous process left queued or running can never finish; fail them now.
    service.fail_interrupted_runs()
    app = FastAPI(title="VIZA Sandbox")

    def current_user(authorization: Annotated[str | None, Header()] = None) -> SandboxUser:
        scheme, _, token = (authorization or "").partition(" ")
        user = store.user_for_token(token.strip()) if scheme.lower() == "bearer" else None
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid sandbox token.")
        return user

    def owned_run(run_id: str, user: SandboxUser) -> SandboxRun:
        run = store.get_run(run_id)
        if run is None or run.user_id != user.user_id:
            raise HTTPException(status_code=404, detail="Run not found.")
        return run

    @app.get("/sandbox/health")
    def health() -> dict:
        return {"status": "ok", "service": "viza-sandbox"}

    @app.post("/sandbox/runs", status_code=202)
    def create_run(
        body: RunRequest,
        background: BackgroundTasks,
        user: Annotated[SandboxUser, Depends(current_user)],
    ) -> dict:
        run = service.submit(user, body)
        background.add_task(service.execute, run.run_id)
        return {"run_id": run.run_id, "status": "queued"}

    @app.get("/sandbox/runs/{run_id}")
    def get_run(run_id: str, user: Annotated[SandboxUser, Depends(current_user)]) -> dict:
        run = owned_run(run_id, user)
        # result_path is an absolute host path; it stays server-side.
        columns = {
            c.name: getattr(run, c.name)
            for c in SandboxRun.__table__.columns
            if c.name not in _HIDDEN_RUN_COLUMNS
        }
        return jsonable_encoder({"run": columns, "header": service.result_header(run)})

    @app.get("/sandbox/runs/{run_id}/result")
    def get_result(run_id: str, user: Annotated[SandboxUser, Depends(current_user)]) -> dict:
        run = owned_run(run_id, user)
        if run.status != "completed":
            raise HTTPException(status_code=409, detail="Run is not completed.")
        evaluation = run.evaluation or {}
        return jsonable_encoder(
            {
                "header": service.result_header(run),
                "evaluation": evaluation,
                "warnings": evaluation.get("warnings", []),
            }
        )

    return app


def build_default_app() -> FastAPI:
    settings = SandboxSettings()
    if not settings.canonical_database_url:
        raise RuntimeError("VIZA_SANDBOX_CANONICAL_DATABASE_URL is required")
    store = SandboxStore(settings.database_url)
    store.create_schema()
    runner = (
        DockerRunner(settings.docker_image) if settings.runner == "docker" else LocalProcessRunner()
    )
    source = PostgresCanonicalSource(settings.canonical_database_url)
    return create_app(SandboxService(settings, store, source, runner), store)


_app: FastAPI | None = None


def __getattr__(name: str) -> FastAPI:
    """Lazy module-level ``app`` so importing never needs the canonical URL (uvicorn-compatible)."""
    global _app
    if name == "app":
        if _app is None:
            _app = build_default_app()
        return _app
    raise AttributeError(name)
