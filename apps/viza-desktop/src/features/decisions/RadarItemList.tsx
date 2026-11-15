// Phase 34. Renders a RadarItem[] by dispatching each item to the right
// card per its `render_component` discriminator. The dispatch is a small
// switch rather than a registry so the language-gate test can statically
// see which components own which command labels.

import { BlockedCommandCard } from "./BlockedCommandCard";
import { DecisionCommandCard } from "./DecisionCommandCard";
import { WatchCommandCard } from "./WatchCommandCard";
import type { RadarItem } from "./radarTypes";

interface RadarItemListProps {
  items: RadarItem[];
}

export function RadarItemList({ items }: RadarItemListProps) {
  if (items.length === 0) {
    return (
      <div className="radar-item-list radar-item-list-empty">
        No items returned for the current radar mode.
      </div>
    );
  }

  const grouped = new Map<string, RadarItem[]>();
  for (const item of items) {
    const bucket = grouped.get(item.display_group) ?? [];
    bucket.push(item);
    grouped.set(item.display_group, bucket);
  }

  return (
    <div className="radar-item-list">
      {Array.from(grouped.entries()).map(([group, bucket]) => (
        <section
          key={group}
          className="radar-item-list-group"
          data-radar-group={group}
        >
          <h3 className="radar-item-list-group-header">{group}</h3>
          <ol className="radar-item-list-items">
            {bucket.map((item) => (
              <li key={item.radar_item_id} className="radar-item-list-row">
                <RadarItemRow item={item} />
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

RadarItemList.displayName = "RadarItemList";

function RadarItemRow({ item }: { item: RadarItem }) {
  const command = item.command;
  switch (item.render_component) {
    case "DecisionCommandCard":
      if (!command) {
        return <RankingFallbackRow item={item} />;
      }
      return (
        <DecisionCommandCard
          command={command}
          mode={inferMode(item)}
          cutoffTimestamp={pickString(item.pit_state, "cutoff_timestamp") ?? "—"}
          runId={item.source_run_id ?? "—"}
          evidenceChecksumPrefix={
            pickString(item.validation_state, "evidence_checksum")?.slice(0, 12) ?? "—"
          }
        />
      );
    case "BlockedCommandCard":
      if (!command) {
        return <RankingFallbackRow item={item} />;
      }
      return <BlockedCommandCard command={command} />;
    case "WatchCommandCard":
      if (!command) {
        return <RankingFallbackRow item={item} />;
      }
      return <WatchCommandCard command={command} />;
    default:
      return <RankingFallbackRow item={item} />;
  }
}

function RankingFallbackRow({ item }: { item: RadarItem }) {
  const score = item.radar_score.toFixed(2);
  const label =
    item.ranking_row?.ticker ?? item.asset_id ?? item.entity_id ?? "—";
  return (
    <div className="ranking-card">
      <span className="ranking-card-rank">#{item.ranking_row?.rank ?? "?"}</span>
      <span className="ranking-card-label">{label}</span>
      <span className="ranking-card-score">{score}</span>
    </div>
  );
}

function inferMode(item: RadarItem): "sandbox_replay" | "live" {
  const audit = item.audit_chain;
  const mode = pickString(audit, "mode") ?? pickString(item.pit_state, "mode");
  return mode === "live" ? "live" : "sandbox_replay";
}

function pickString(record: Record<string, unknown>, key: string): string | null {
  const value = record[key];
  return typeof value === "string" ? value : null;
}
