interface AttributeSourceBadgeProps {
  isPrototype?: boolean | null;
  observationId?: string | null;
  exportAllowed?: boolean | null;
  source?: string | null;
}

export function AttributeSourceBadge({
  exportAllowed,
  isPrototype,
  observationId,
  source,
}: AttributeSourceBadgeProps) {
  const label = observationId ? "source-backed" : isPrototype ? "prototype" : "evidence-only";
  const restriction = exportAllowed === false ? "restricted export" : "exportable";
  return (
    <span className={`attribute-source-badge ${label.replace("-", "_")}`} title={source ?? ""}>
      {label} / {restriction}
    </span>
  );
}
