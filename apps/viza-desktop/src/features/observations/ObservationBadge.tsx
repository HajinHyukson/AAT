interface ObservationBadgeProps {
  observationId?: string | null;
  pitStatus?: string | null;
  isPrototype?: boolean;
  missingReason?: string | null;
}

export function ObservationBadge({
  observationId,
  pitStatus,
  isPrototype,
  missingReason,
}: ObservationBadgeProps) {
  const label = observationId
    ? "source-backed"
    : isPrototype
      ? "prototype"
      : pitStatus || "PIT";

  return (
    <span className="observation-badge" title={missingReason || observationId || pitStatus || ""}>
      {label}
    </span>
  );
}
