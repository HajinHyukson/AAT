import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { ExposureUpdateDecision } from "@/lib/types";

export function ExposureDecisions({ decisions }: { decisions: ExposureUpdateDecision[] }) {
  return (
    <section className="border-y border-line bg-white">
      <div className="grid grid-cols-[1.4fr_1fr_2fr] gap-3 border-b border-line bg-paper px-4 py-3 text-xs uppercase text-steel">
        <div>Exposure</div>
        <div>Decision</div>
        <div>Rationale</div>
      </div>
      {decisions.map((decision, index) => (
        <div
          key={`${decision.exposure_update_decision_id}-${decision.exposure_name}-${index}`}
          className="grid grid-cols-[1.4fr_1fr_2fr] gap-3 border-b border-line px-4 py-3 text-sm last:border-b-0"
        >
          <div className="font-medium">{formatExposure(decision.exposure_name)}</div>
          <div className="flex items-center gap-2">
            {decision.review_required ? (
              <AlertTriangle size={16} className="text-signal" />
            ) : (
              <CheckCircle2 size={16} className="text-moss" />
            )}
            <span className={decision.review_required ? "text-signal" : "text-moss"}>
              {decision.decision.replace("_", " ")}
            </span>
          </div>
          <div className="text-steel">{decision.rationale}</div>
        </div>
      ))}
      {decisions.length === 0 ? (
        <div className="px-4 py-6 text-sm text-steel">No exposure decisions available.</div>
      ) : null}
    </section>
  );
}

function formatExposure(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
