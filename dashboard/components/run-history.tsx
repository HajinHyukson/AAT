import Link from "next/link";
import type { AttributionRun } from "@/lib/types";

export function RunHistory({
  ticker,
  runs,
  activeRunId,
}: {
  ticker: string;
  runs: AttributionRun[];
  activeRunId: string;
}) {
  return (
    <aside className="border-y border-line bg-white">
      <div className="border-b border-line bg-paper px-4 py-3 text-xs uppercase text-steel">
        Recent Runs
      </div>
      <div className="max-h-[420px] overflow-y-auto">
        {runs.map((run, index) => {
          const active = run.attribution_run_id === activeRunId;
          return (
            <Link
              key={`${run.attribution_run_id}-${index}`}
              href={`/?ticker=${ticker}&runId=${run.attribution_run_id}`}
              className={`grid grid-cols-[1fr_auto] gap-2 border-b border-line px-4 py-3 text-sm last:border-b-0 ${
                active ? "bg-paper" : "bg-white hover:bg-paper"
              }`}
            >
              <span>
                <span className="mr-2 uppercase text-steel">{run.cadence}</span>
                {new Date(run.window_start).toLocaleDateString()} to {new Date(run.window_end).toLocaleDateString()}
              </span>
              <span className={run.observed_return_bps < 0 ? "text-signal" : "text-moss"}>
                {run.observed_return_bps.toFixed(1)}
              </span>
            </Link>
          );
        })}
      </div>
    </aside>
  );
}
