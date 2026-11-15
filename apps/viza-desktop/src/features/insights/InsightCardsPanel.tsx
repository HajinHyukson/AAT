import { useMemo } from "react";

import { InsightCard } from "./InsightCard";
import type {
  MethodologyRunResult,
  VizaInsight,
  VizaRadarRow,
  VizaRelationshipEdge,
  VizaTranslation,
} from "../../vizaGraph";

interface InsightCardsPanelProps {
  result: MethodologyRunResult | null;
  row: VizaRadarRow | null;
  selectedEvidenceRef?: string | null;
  onEvidenceSelect?: (evidenceRef: string | null) => void;
}

export function InsightCardsPanel({
  result,
  row,
  selectedEvidenceRef,
  onEvidenceSelect,
}: InsightCardsPanelProps) {
  const cards = useMemo(() => {
    if (!result || !row) {
      return [];
    }
    const translationsByInsight = new Map(
      result.translations.map((translation) => [translation.insight_id, translation]),
    );
    const relationships = [...result.relationships, ...result.insight_relationships];
    return result.insights
      .filter((insight) => insightMatchesRow(insight, row))
      .map((insight) => ({
        insight,
        relationships,
        translation: translationsByInsight.get(insight.insight_id) ?? null,
      }))
      .sort((left, right) => {
        const leftScore = left.translation?.fit_score ?? left.insight.confidence;
        const rightScore = right.translation?.fit_score ?? right.insight.confidence;
        return rightScore - leftScore;
      });
  }, [result, row]);

  return (
    <section className="insight-cards-panel">
      <div className="result-label">Insight Cards</div>
      {row ? (
        <div className="insight-card-panel-header">
          <strong>{row.ticker}</strong>
          <span>{row.translated_summary ?? "No translated summary"}</span>
        </div>
      ) : null}
      {result && row && cards.length ? (
        <div className="insight-cards-list">
          {cards.map(({ insight, relationships, translation }) => (
            <InsightCard
              insight={insight}
              key={insight.insight_id}
              relationships={relationships}
              result={result}
              row={row}
              selectedEvidenceRef={selectedEvidenceRef}
              translation={translation}
              onEvidenceSelect={onEvidenceSelect}
            />
          ))}
        </div>
      ) : (
        <div className="result-empty">
          {result && row ? "No translated insights for this row." : "Run a strategy to inspect insights."}
        </div>
      )}
    </section>
  );
}

function insightMatchesRow(insight: VizaInsight, row: VizaRadarRow): boolean {
  if (row.entity_id && insight.entity_id === row.entity_id) {
    return true;
  }
  if (row.asset_id && insight.asset_id === row.asset_id) {
    return true;
  }
  const rowEvidenceRefs = new Set(row.evidence_refs);
  return insight.evidence_refs.some((evidenceRef) => rowEvidenceRefs.has(evidenceRef));
}

export function buildInsightCardPayloadForRow(
  result: MethodologyRunResult,
  row: VizaRadarRow,
): Array<{
  insight: VizaInsight;
  relationships: VizaRelationshipEdge[];
  translation: VizaTranslation | null;
}> {
  const translationsByInsight = new Map(
    result.translations.map((translation) => [translation.insight_id, translation]),
  );
  const relationships = [...result.relationships, ...result.insight_relationships];
  return result.insights
    .filter((insight) => insightMatchesRow(insight, row))
    .map((insight) => ({
      insight,
      relationships,
      translation: translationsByInsight.get(insight.insight_id) ?? null,
    }));
}
