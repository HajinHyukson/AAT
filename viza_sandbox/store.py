from __future__ import annotations

import hashlib
import secrets
from collections.abc import Collection
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

ALLOWED_RUN_STATUSES = {"queued", "running", "completed", "failed", "timed_out"}


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SandboxUser(Base):
    __tablename__ = "sandbox_user"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SandboxRun(Base):
    __tablename__ = "sandbox_run"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sandbox_user.user_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    code_text: Mapped[str] = mapped_column(Text, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request: Mapped[dict] = mapped_column(JSON, nullable=False)
    data_manifest: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    limits: Mapped[dict] = mapped_column(JSON, nullable=False)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stderr: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    result_path: Mapped[str | None] = mapped_column(String, nullable=True)
    evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    """Create the directory of a SQLite database file; SQLite will not create it."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return
    database = url.database
    if not database or database == ":memory:" or database.startswith("file:"):
        return
    Path(database).parent.mkdir(parents=True, exist_ok=True)


class SandboxStore:
    def __init__(self, database_url: str) -> None:
        _ensure_sqlite_parent_dir(database_url)
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        self._session_factory: sessionmaker[Session] = sessionmaker(
            bind=self._engine, expire_on_commit=False
        )

    def create_schema(self) -> None:
        Base.metadata.create_all(self._engine)

    def create_user(self, name: str, *, is_owner: bool = False) -> tuple[SandboxUser, str]:
        token = secrets.token_urlsafe(32)
        user = SandboxUser(
            user_id=str(uuid4()),
            name=name,
            token_hash=hash_token(token),
            created_at=_utcnow(),
            is_owner=is_owner,
        )
        with self._session_factory() as session:
            session.add(user)
            session.commit()
        return user, token

    def user_for_token(self, token: str) -> SandboxUser | None:
        with self._session_factory() as session:
            return (
                session.query(SandboxUser)
                .filter(SandboxUser.token_hash == hash_token(token))
                .one_or_none()
            )

    def create_run(
        self, user_id: str, code_text: str, request: dict, limits: dict
    ) -> SandboxRun:
        run = SandboxRun(
            run_id=str(uuid4()),
            user_id=user_id,
            status="queued",
            code_text=code_text,
            code_hash=hashlib.sha256(code_text.encode("utf-8")).hexdigest(),
            request=request,
            data_manifest=None,
            limits=limits,
            exit_code=None,
            stdout="",
            stderr="",
            result_kind=None,
            result_path=None,
            evaluation=None,
            error=None,
            created_at=_utcnow(),
            started_at=None,
            finished_at=None,
        )
        with self._session_factory() as session:
            session.add(run)
            session.commit()
        return run

    def get_run(self, run_id: str) -> SandboxRun | None:
        with self._session_factory() as session:
            return session.get(SandboxRun, run_id)

    def update_run(self, run_id: str, **fields) -> SandboxRun:
        with self._session_factory() as session:
            run = session.get(SandboxRun, run_id)
            if run is None:
                raise KeyError(run_id)

            status = fields.get("status")
            if status is not None and status not in ALLOWED_RUN_STATUSES:
                raise ValueError(f"invalid run status: {status!r}")

            for key, value in fields.items():
                if not hasattr(SandboxRun, key):
                    raise AttributeError(key)
                setattr(run, key, value)
            session.commit()
            session.refresh(run)
            return run

    def list_runs(self, user_id: str) -> list[SandboxRun]:
        with self._session_factory() as session:
            return (
                session.query(SandboxRun)
                .filter(SandboxRun.user_id == user_id)
                .order_by(SandboxRun.created_at)
                .all()
            )

    def list_runs_by_status(self, statuses: Collection[str]) -> list[SandboxRun]:
        with self._session_factory() as session:
            return (
                session.query(SandboxRun)
                .filter(SandboxRun.status.in_(list(statuses)))
                .order_by(SandboxRun.created_at)
                .all()
            )
