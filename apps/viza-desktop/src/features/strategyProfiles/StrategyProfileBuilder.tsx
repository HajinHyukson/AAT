import { useState } from "react";
import { createStrategyProfile } from "./profileClient";
import type { StrategyProfileCreateRequest, VizaStrategyProfile } from "./types";

interface StrategyProfileBuilderProps {
  template?: StrategyProfileCreateRequest;
  onSaved?: (profile: VizaStrategyProfile) => void;
}

export function StrategyProfileBuilder({ template, onSaved }: StrategyProfileBuilderProps) {
  const [displayName, setDisplayName] = useState(
    template?.display_name ?? "RSI Swing + Catalyst Confirmation",
  );
  const [holdingMin, setHoldingMin] = useState(template?.holding_period?.min ?? "2d");
  const [holdingMax, setHoldingMax] = useState(template?.holding_period?.max ?? "3w");
  const [saving, setSaving] = useState(false);

  async function saveProfile() {
    setSaving(true);
    try {
      const profile = await createStrategyProfile({
        ...template,
        display_name: displayName,
        holding_period: { min: holdingMin, max: holdingMax },
      });
      onSaved?.(profile);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="strategy-profile-builder">
      <label>
        Name
        <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
      </label>
      <label>
        Min holding
        <input value={holdingMin} onChange={(event) => setHoldingMin(event.target.value)} />
      </label>
      <label>
        Max holding
        <input value={holdingMax} onChange={(event) => setHoldingMax(event.target.value)} />
      </label>
      <button type="button" onClick={saveProfile} disabled={saving}>
        Save profile
      </button>
    </section>
  );
}
