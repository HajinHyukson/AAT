import type { VizaEvent } from "./types";

interface EventCardProps {
  event: VizaEvent;
}

export function EventCard({ event }: EventCardProps) {
  return (
    <article className="event-card">
      <header>
        <strong>{event.event_type.replaceAll("_", " ")}</strong>
        <span>{Math.round(event.confidence * 100)}%</span>
      </header>
      <dl>
        <dt>Available</dt>
        <dd>{new Date(event.available_at).toLocaleString()}</dd>
        <dt>Assets</dt>
        <dd>{event.affected_asset_ids.join(", ") || "none"}</dd>
      </dl>
    </article>
  );
}
