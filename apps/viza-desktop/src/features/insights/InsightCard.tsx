import { AlertTriangle, CheckCircle2, FileText, GitBranch, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import { StrategyFitBadge } from "../translations/StrategyFitBadge";
import type {
  MethodologyRunResult,
  VizaInsight,
  VizaRadarRow,
  VizaRelationshipEdge,
  VizaTranslation,
} from "../../vizaGraph";

interface InsightCardProps {
  insight: VizaInsight;
  translation?: VizaTranslation | null;
  row?: VizaRadarRow | null;
  result: MethodologyRunResult;
  relationships: VizaRelationshipEdge[];
  selectedEvidenceRef?: string | null | undefined;
  onEvidenceSelect?: ((evidenceRef: string | null) => void) | undefined;
}

export function InsightCard({
  insight,
  translation,
  row,
  result,
  relationships,
  selectedEvidenceRef,
  onEvidenceSelect,
}: InsightCardProps) {
  const evidenceRefs = translation?.evidence_refs.length
    ? translation.evidence_refs
    : insight.evidence_refs;
  const evidenceRows = evidenceRefs.map((evidenceRef) => evidenceSummary(evidenceRef, result, insight));
  const relatedRelationships = relationshipsForInsight(insight, relationships);
  const fitScore = translation?.fit_score ?? row?.strategy_fit_score ?? null;
  const missingConfirmations =
    translation?.missing_confirmations.length || !row?.missing_confirmations?.length
      ? translation?.missing_confirmations ?? []
      : row.missing_confirmations;
  const invalidationConditions =
    translation?.invalidation_conditions.length || !row?.invalidation_conditions?.length
      ? translation?.invalidation_conditions ?? insight.invalidation_conditions
      : row.invalidation_conditions;
  const riskFactors =
    translation?.risk_factors.length || !row?.risk_flags?.length
      ? translation?.risk_factors ?? insight.risk_factors
      : row.risk_flags;

  return (
    <article className="insight-card">
      <header className="insight-card-header">
        <div>
          <strong>{readableLabel(insight.insight_type)}</strong>
          <span>
            {entityLabel(row, insight)} / {readableLabel(insight.direction)}
          </span>
        </div>
        <div className="insight-card-metrics">
          <span>{Math.round(insight.confidence * 100)}%</span>
          <StrategyFitBadge
            action={translation?.suggested_research_action ?? null}
            score={fitScore}
          />
        </div>
      </header>

      <p className="insight-card-summary">
        {translation?.translated_summary ?? row?.translated_summary ?? readableLabel(insight.direction)}
      </p>

      <div className="insight-card-grid">
        <InsightSection
          icon={<CheckCircle2 size={14} />}
          items={translation?.strategy_fit_reasons ?? []}
          title="Fit"
          empty="No fit reasons"
        />
        <InsightSection
          icon={<AlertTriangle size={14} />}
          items={missingConfirmations}
          title="Missing"
          empty="No missing confirmations"
        />
        <InsightSection
          icon={<ShieldCheck size={14} />}
          items={invalidationConditions}
          title="Invalidation"
          empty="No invalidation rules"
        />
        <InsightSection
          icon={<AlertTriangle size={14} />}
          items={riskFactors}
          title="Risk"
          empty="No risk flags"
        />
      </div>

      {translation?.suggested_research_action && (
        <div className="insight-action-label">{translation.suggested_research_action}</div>
      )}

      <section className="insight-evidence-section">
        <div className="insight-section-title">
          <FileText size={14} />
          <span>Evidence</span>
        </div>
        <div className="insight-evidence-list">
          {evidenceRows.length ? (
            evidenceRows.map((evidence) => (
              <button
                className={selectedEvidenceRef === evidence.evidenceRef ? "selected" : ""}
                key={evidence.evidenceRef}
                type="button"
                onClick={() => onEvidenceSelect?.(evidence.evidenceRef)}
              >
                <span>
                  <strong>{evidence.evidenceRef}</strong>
                  <small>{evidence.source}</small>
                </span>
                <span>
                  <strong>{evidence.exportStatus}</strong>
                  <small>{evidence.availableAt}</small>
                </span>
              </button>
            ))
          ) : (
            <div className="result-empty">No evidence refs.</div>
          )}
        </div>
      </section>

      <section className="insight-card-audit">
        <div>
          <span>Run</span>
          <strong>{shortId(result.run_id)}</strong>
        </div>
        <div>
          <span>Graph</span>
          <strong>{shortId(result.graph_hash)}</strong>
        </div>
        <div>
          <span>Profile</span>
          <strong>{shortId(translation?.strategy_profile_id ?? "")}</strong>
        </div>
        <div>
          <span>Evidence</span>
          <strong>{shortId(readString(result.manifest.evidence_checksum))}</strong>
        </div>
        <div>
          <span>Result</span>
          <strong>{shortId(result.result_checksum)}</strong>
        </div>
      </section>

      <section className="insight-relationship-strip">
        <div className="insight-section-title">
          <GitBranch size={14} />
          <span>Relationships</span>
        </div>
        {relatedRelationships.length ? (
          relatedRelationships.slice(0, 6).map((relationship) => (
            <span key={`${relationship.source}-${relationship.target}-${relationship.relationship_type}`}>
              {readableLabel(relationship.family || relationship.relationship_family)} /{" "}
              {readableLabel(relationship.relationship_type)}
            </span>
          ))
        ) : (
          <span>No related edges</span>
        )}
      </section>
    </article>
  );
}

function InsightSection({
  empty,
  icon,
  items,
  title,
}: {
  empty: string;
  icon: ReactNode;
  items: string[];
  title: string;
}) {
  return (
    <section className="insight-mini-section">
      <div className="insight-section-title">
        {icon}
        <span>{title}</span>
      </div>
      {items.length ? (
        <ul>
          {items.slice(0, 4).map((item) => (
            <li key={item}>{readableLabel(item)}</li>
          ))}
        </ul>
      ) : (
        <span>{empty}</span>
      )}
    </section>
  );
}

function relationshipsForInsight(
  insight: VizaInsight,
  relationships: VizaRelationshipEdge[],
): VizaRelationshipEdge[] {
  const relatedIds = new Set([
    insight.insight_id,
    insight.entity_id,
    insight.asset_id ?? "",
    ...insight.evidence_refs,
  ]);
  relatedIds.delete("");
  return relationships.filter(
    (relationship) => relatedIds.has(relationship.source) || relatedIds.has(relationship.target),
  );
}

function evidenceSummary(
  evidenceRef: string,
  result: MethodologyRunResult,
  insight: VizaInsight,
): {
  availableAt: string;
  evidenceRef: string;
  exportStatus: string;
  source: string;
} {
  const record = readRecord(result.evidence[evidenceRef]);
  const entitlement = readRecord(record.entitlement);
  const exportAllowed = typeof entitlement.export_allowed === "boolean" ? entitlement.export_allowed : true;
  const sourcePolicy = readRecord(insight.source_policy);
  return {
    availableAt: readString(record.timestamp_available) || readString(record.available_at) || "PIT n/a",
    evidenceRef,
    exportStatus: exportAllowed ? "exportable" : "redacted",
    source:
      readString(record.source) ||
      readString(record.source_id) ||
      readString(sourcePolicy.source_id) ||
      "unknown",
  };
}

function entityLabel(row: VizaRadarRow | null | undefined, insight: VizaInsight): string {
  if (row?.ticker) {
    return row.company_name ? `${row.ticker} ${row.company_name}` : row.ticker;
  }
  return insight.asset_id ?? insight.entity_id;
}

function readableLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortId(value: string): string {
  return value ? value.slice(0, 12) : "-";
}

function readString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function readRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
