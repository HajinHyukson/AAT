interface StrategyFitBadgeProps {
  score?: number | null;
  action?: string | null;
}

export function StrategyFitBadge({ score, action }: StrategyFitBadgeProps) {
  const label = typeof score === "number" ? `${Math.round(score * 100)}%` : "n/a";
  return (
    <span className="strategy-fit-badge" title={action ?? ""}>
      {label}
    </span>
  );
}
