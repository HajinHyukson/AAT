import type { VizaInsight } from "./types";

interface InsightListProps {
  insights: VizaInsight[];
}

export function InsightList({ insights }: InsightListProps) {
  return (
    <section className="insight-list">
      {insights.map((insight) => (
        <article key={insight.insight_id} className="insight-card">
          <header>
            <strong>{insight.insight_type.replaceAll("_", " ")}</strong>
            <span>{Math.round(insight.confidence * 100)}%</span>
          </header>
          <p>{insight.direction}</p>
        </article>
      ))}
    </section>
  );
}
