import type { VizaFileVisualization } from "./types";

export function VizaFileViewer({ visualization }: { visualization: VizaFileVisualization }) {
  const sections = Object.values(visualization.contents_map);
  const readiness = Object.entries(visualization.readiness_checklist ?? {});
  const complianceWarnings =
    visualization.compliance_warnings.length > 0
      ? visualization.compliance_warnings
      : visualization.warnings.filter((warning) => COMPLIANCE_CODES.has(warning.code));
  return (
    <section className="viza-file-viewer">
      <header>
        <h2>{visualization.display_name ?? visualization.file_id}</h2>
        <span className={`viza-visibility-badge ${visualization.visibility}`}>
          {visualization.visibility.replaceAll("_", " ")}
        </span>
        <dl>
          <dt>file</dt>
          <dd>{visualization.file_id}</dd>
          <dt>kind</dt>
          <dd>{visualization.object_kind}</dd>
          <dt>visibility</dt>
          <dd>{visualization.visibility}</dd>
          <dt>schema</dt>
          <dd>{visualization.schema}</dd>
          {visualization.creator.display_name ? (
            <>
              <dt>creator</dt>
              <dd>{String(visualization.creator.display_name)}</dd>
            </>
          ) : null}
        </dl>
      </header>

      <div className="viza-file-grid">
        <section>
          <h3>Contents</h3>
          <ul>
            {sections.map((section) => (
              <li key={section.section_name} data-status={section.status}>
                <span>{section.section_name.replaceAll("_", " ")}</span>
                <strong>{section.status.replaceAll("_", " ")}</strong>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h3>Compatibility</h3>
          <ul>
            {visualization.required_modules.map((module) => (
              <li key={module.module_id} data-status={module.status}>
                <span>{module.module_id}</span>
                <strong>{module.status}</strong>
              </li>
            ))}
            {visualization.compatibility.required_connectors.map((connectorId) => (
              <li key={connectorId}>
                <span>{connectorId}</span>
                <strong>
                  {visualization.compatibility.missing_connectors.includes(connectorId)
                    ? "missing"
                    : "available"}
                </strong>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h3>Actions</h3>
          <div className="viza-file-actions">
            {KNOWN_ACTIONS.map((action) => (
              <button
                disabled={!visualization.available_actions.includes(action)}
                key={action}
                type="button"
              >
                {action.replaceAll("_", " ")}
              </button>
            ))}
          </div>
        </section>
        {complianceWarnings.length > 0 || readiness.length > 0 ? (
          <section>
            <h3>Compliance</h3>
            {complianceWarnings.length > 0 ? (
              <ul>
                {complianceWarnings.map((warning) => (
                  <li key={warning.code} data-status={warning.severity}>
                    <span>{warning.code.replaceAll("_", " ")}</span>
                    <strong>{warning.severity}</strong>
                  </li>
                ))}
              </ul>
            ) : null}
            {readiness.length > 0 ? (
              <ul className="viza-readiness-list">
                {readiness.map(([key, value]) => (
                  <li key={key} data-status={readinessStatus(value)}>
                    <span>{key.replaceAll("_", " ")}</span>
                    <strong>{readinessLabel(value)}</strong>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
        ) : null}
      </div>
    </section>
  );
}

const KNOWN_ACTIONS = [
  "open_without_import",
  "fork_as_new_methodology",
  "run_locally",
  "import_to_project",
  "quarantine",
];

const COMPLIANCE_CODES = new Set([
  "not_investment_advice_missing",
  "performance_claim_unverified",
  "source_data_redistribution_forbidden",
  "rumor_data_unverified",
  "black_box_without_proof",
  "insufficient_out_of_sample_history",
  "lookahead_risk_detected",
]);

function readinessStatus(value: unknown): string {
  if (isRecord(value) && value.passed === true) {
    return "ok";
  }
  return "warning";
}

function readinessLabel(value: unknown): string {
  if (!isRecord(value)) {
    return "review";
  }
  if (typeof value.value === "number") {
    return `${value.value}`;
  }
  if (typeof value.status === "string") {
    return value.status;
  }
  return value.passed === true ? "passed" : "review";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
