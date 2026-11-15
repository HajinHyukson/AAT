import type { VizaMethodologyGraph } from "../../vizaGraph";
import type { VizaFileExportRequest } from "./types";
import { useState } from "react";

export interface VizaExportWizardProps {
  graph: VizaMethodologyGraph;
  targetPath: string;
  projectId?: string | null;
  onExport: (request: VizaFileExportRequest) => void;
}

export function VizaExportWizard({
  graph,
  targetPath,
  projectId = null,
  onExport,
}: VizaExportWizardProps) {
  const [visibility, setVisibility] =
    useState<NonNullable<VizaFileExportRequest["visibility"]>>("white_box");
  const [purpose, setPurpose] =
    useState<NonNullable<VizaFileExportRequest["purpose"]>>("collaboration");
  const [includeValidationProof, setIncludeValidationProof] = useState(false);
  const [includeSignalOutputs, setIncludeSignalOutputs] = useState(false);
  const [redactParameters, setRedactParameters] = useState(false);
  const [lockGraph, setLockGraph] = useState(false);
  const [creatorDisplayName, setCreatorDisplayName] = useState("");
  const [notInvestmentAdvice, setNotInvestmentAdvice] = useState(false);
  const implications = visibilityImplications[visibility ?? "white_box"];
  const isMarketplaceDraft = purpose === "marketplace_draft";

  const submit = () => {
    onExport({
      graph,
      target_path: targetPath,
      project_id: projectId,
      purpose,
      visibility,
      include_sections: ["methodology_graph"],
      include_validation_proof: includeValidationProof,
      include_signal_outputs: includeSignalOutputs,
      include_sample_outputs: visibility === "preview_only",
      lock_sections: lockGraph ? ["methodology_graph"] : [],
      redact_parameters: redactParameters || visibility === "gray_box",
      creator_display_name: isMarketplaceDraft ? creatorDisplayName || null : null,
      not_investment_advice_acknowledged: isMarketplaceDraft ? notInvestmentAdvice : false,
    });
  };

  return (
    <section className="viza-export-wizard">
      <h2>Export</h2>
      <div className="viza-export-controls">
        <label>
          <span>purpose</span>
          <select
            value={purpose}
            onChange={(event) =>
              setPurpose(event.target.value as NonNullable<VizaFileExportRequest["purpose"]>)
            }
          >
            <option value="collaboration">collaboration</option>
            <option value="marketplace_draft">marketplace draft</option>
          </select>
        </label>
        <label>
          <span>visibility</span>
          <select
            value={visibility}
            onChange={(event) =>
              setVisibility(
                event.target.value as NonNullable<VizaFileExportRequest["visibility"]>,
              )
            }
          >
            <option value="white_box">white box</option>
            <option value="gray_box">gray box</option>
            <option value="black_box">black box</option>
            <option value="output_only">output only</option>
            <option value="preview_only">preview only</option>
          </select>
        </label>
        <label>
          <input
            checked={includeValidationProof}
            type="checkbox"
            onChange={(event) => setIncludeValidationProof(event.target.checked)}
          />
          <span>validation proof</span>
        </label>
        <label>
          <input
            checked={includeSignalOutputs}
            type="checkbox"
            onChange={(event) => setIncludeSignalOutputs(event.target.checked)}
          />
          <span>signal outputs</span>
        </label>
        <label>
          <input
            checked={redactParameters}
            type="checkbox"
            onChange={(event) => setRedactParameters(event.target.checked)}
          />
          <span>redact parameters</span>
        </label>
        <label>
          <input
            checked={lockGraph}
            type="checkbox"
            onChange={(event) => setLockGraph(event.target.checked)}
          />
          <span>lock graph</span>
        </label>
        {isMarketplaceDraft ? (
          <>
            <label>
              <span>creator</span>
              <input
                type="text"
                value={creatorDisplayName}
                onChange={(event) => setCreatorDisplayName(event.target.value)}
              />
            </label>
            <label>
              <input
                checked={notInvestmentAdvice}
                type="checkbox"
                onChange={(event) => setNotInvestmentAdvice(event.target.checked)}
              />
              <span>not investment advice</span>
            </label>
          </>
        ) : null}
      </div>
      {isMarketplaceDraft ? (
        <ul className="viza-compliance-checklist">
          <li data-status={notInvestmentAdvice ? "ok" : "warning"}>
            <span>advice label</span>
            <strong>{notInvestmentAdvice ? "acknowledged" : "missing"}</strong>
          </li>
          <li data-status={includeValidationProof ? "ok" : "warning"}>
            <span>validation proof</span>
            <strong>{includeValidationProof ? "requested" : "warning"}</strong>
          </li>
          <li data-status="ok">
            <span>source rights</span>
            <strong>checked on export</strong>
          </li>
          <li data-status="ok">
            <span>monetization</span>
            <strong>disabled</strong>
          </li>
        </ul>
      ) : null}
      <dl>
        <dt>purpose</dt>
        <dd>{purpose.replaceAll("_", " ")}</dd>
        <dt>visibility</dt>
        <dd>{visibility?.replaceAll("_", " ")}</dd>
        <dt>graph</dt>
        <dd>{implications.graph}</dd>
        <dt>parameters</dt>
        <dd>{implications.parameters}</dd>
        <dt>outputs</dt>
        <dd>{implications.outputs}</dd>
        <dt>permissions</dt>
        <dd>{implications.permissions}</dd>
      </dl>
      <button type="button" onClick={submit}>
        Export
      </button>
    </section>
  );
}

const visibilityImplications: Record<
  NonNullable<VizaFileExportRequest["visibility"]>,
  {
    graph: string;
    outputs: string;
    parameters: string;
    permissions: string;
  }
> = {
  white_box: {
    graph: "included",
    outputs: "optional",
    parameters: "included",
    permissions: "run, fork, export",
  },
  gray_box: {
    graph: "included",
    outputs: "optional",
    parameters: "redacted",
    permissions: "run only",
  },
  black_box: {
    graph: "redacted",
    outputs: "included",
    parameters: "redacted",
    permissions: "inspect only",
  },
  output_only: {
    graph: "absent",
    outputs: "included",
    parameters: "redacted",
    permissions: "inspect only",
  },
  preview_only: {
    graph: "absent",
    outputs: "sample",
    parameters: "redacted",
    permissions: "inspect only",
  },
};
