import type { VizaStrategyProfile } from "./types";

interface StrategyProfileInspectorProps {
  profile: VizaStrategyProfile | null;
}

export function StrategyProfileInspector({ profile }: StrategyProfileInspectorProps) {
  if (!profile) {
    return <section className="strategy-profile-inspector" />;
  }

  return (
    <section className="strategy-profile-inspector">
      <header>
        <h3>{profile.display_name}</h3>
        <span>{profile.module_id}</span>
      </header>
      <dl>
        <dt>Holding period</dt>
        <dd>
          {profile.holding_period.min} - {profile.holding_period.max}
        </dd>
        <dt>Indicators</dt>
        <dd>{profile.preferred_indicators.join(", ")}</dd>
        <dt>Evidence</dt>
        <dd>{Object.keys(profile.evidence_requirements).join(", ")}</dd>
      </dl>
    </section>
  );
}
