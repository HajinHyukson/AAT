// Phase 34. Small select component for choosing the radar mode.
// The three modes mirror viza.radar.OutputRadarConfig.

import type { RadarMode } from "./radarTypes";

interface RadarModeSelectorProps {
  mode: RadarMode;
  onChange: (mode: RadarMode) => void;
  disabled?: boolean;
}

const RADAR_MODE_OPTIONS: Array<{ value: RadarMode; label: string; help: string }> = [
  {
    value: "ranking_only",
    label: "Top rankings",
    help: "Show the ranked candidate table only.",
  },
  {
    value: "decisions_only",
    label: "Strategy decisions",
    help: "Show only structured strategy decisions emitted by user-authored rules.",
  },
  {
    value: "mixed",
    label: "Mixed",
    help: "Show rankings and strategy decisions in one radar.",
  },
];

export function RadarModeSelector({ mode, onChange, disabled }: RadarModeSelectorProps) {
  const helpText =
    RADAR_MODE_OPTIONS.find((option) => option.value === mode)?.help ?? "";
  return (
    <div className="radar-mode-selector">
      <label className="radar-mode-selector-label" htmlFor="radar-mode-select">
        Radar mode
      </label>
      <select
        id="radar-mode-select"
        className="radar-mode-selector-select"
        value={mode}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value as RadarMode)}
      >
        {RADAR_MODE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <p className="radar-mode-selector-help">{helpText}</p>
    </div>
  );
}

RadarModeSelector.displayName = "RadarModeSelector";
