import { Activity, Database, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { AttributionChart } from "@/components/attribution-chart";
import { DriverTable } from "@/components/driver-table";
import { ExposureDecisions } from "@/components/exposure-decisions";
import { RunHistory } from "@/components/run-history";
import { UniverseTable } from "@/components/universe-table";
import {
  getAttributionRunById,
  getAttributionRuns,
  getAttributionChart,
  getExposureUpdateDecisions,
  getLatestAttribution,
  getUniverse,
} from "@/lib/api";
import type { AttributionChartResponse, AttributionRun, ExposureUpdateDecision } from "@/lib/types";

type SearchParams = {
  ticker?: string;
  runId?: string;
  search?: string;
  sector?: string;
  industry?: string;
  exchange?: string;
  status?: string;
  sort?: string;
  order?: string;
  limit?: string;
  offset?: string;
  universe?: string;
  display?: string;
};

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const universe = await getUniverse({
    search: params.search,
    sector: params.sector,
    industry: params.industry,
    exchange: params.exchange,
    status: params.status,
    sort: params.sort ?? "ticker",
    order: params.order ?? "asc",
    limit: numberParam(params.limit, 50),
    offset: numberParam(params.offset, 0),
  });
  const defaultStock =
    universe.rows.find((stock) => stock.run_status === "available") ?? universe.rows[0] ?? null;
  const selectedTicker = (params.ticker ?? defaultStock?.ticker ?? "").toUpperCase();
  const selectedUniverseStock = universe.rows.find((stock) => stock.ticker === selectedTicker);

  const run = selectedTicker
    ? await optionalRun(
        params.runId ? getAttributionRunById(params.runId) : getLatestAttribution(selectedTicker),
      )
    : null;
  const [runHistory, exposureDecisions, chart] =
    run && selectedTicker
      ? await Promise.all([
          optionalList(getAttributionRuns(selectedTicker, 20)),
          optionalList(getExposureUpdateDecisions(selectedTicker)),
          optionalRun(getAttributionChart(selectedTicker, "1m")),
        ])
      : [[], [], null];

  return (
    <main className="min-h-screen bg-paper text-ink">
      <section className="mx-auto flex max-w-[96rem] flex-col gap-5 px-4 py-5">
        <header className="border-b border-line pb-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center bg-ink text-sm font-semibold text-white">
                AAT
              </div>
              <div>
                <h1 className="text-xl font-semibold tracking-normal">Attribution Universe</h1>
                <p className="text-sm text-steel">
                  Search, filter, and drill into every active stock in the model universe.
                </p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-right md:grid-cols-4">
              <Metric icon={<Database size={15} />} label="Universe" value={`${universe.total}`} />
              <Metric icon={<Activity size={15} />} label="Page" value={`${universe.rows.length}`} />
              <Metric label="Selected" value={selectedTicker || "n/a"} />
              <Metric
                icon={<RefreshCw size={15} />}
                label="Last Updated"
                value={universe.latest_run_date ? new Date(universe.latest_run_date).toLocaleDateString() : "n/a"}
              />
            </div>
          </div>
        </header>

        <div className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(680px,1fr)_minmax(460px,0.7fr)]">
          <div className="flex min-w-0 flex-col gap-3">
            <UniverseTable universe={universe} params={params} selectedTicker={selectedTicker} />
          </div>

          <aside className="flex min-w-0 flex-col gap-5 2xl:border-l 2xl:border-steel/30 2xl:pl-5">
            {run ? (
              <AttributionWorkspace
                run={run}
                runHistory={runHistory}
                exposureDecisions={exposureDecisions}
                chart={chart}
              />
            ) : (
              <EmptyDetail ticker={selectedTicker} companyName={selectedUniverseStock?.company_name} />
            )}
          </aside>
        </div>
      </section>
    </main>
  );
}

function AttributionWorkspace({
  run,
  runHistory,
  exposureDecisions,
  chart,
}: {
  run: AttributionRun;
  runHistory: AttributionRun[];
  exposureDecisions: ExposureUpdateDecision[];
  chart: AttributionChartResponse | null;
}) {
  return (
    <>
      <section className="border-y border-line bg-white">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line bg-paper px-4 py-3">
          <div>
            <h2 className="text-xl font-semibold">{run.ticker}</h2>
            <p className="mt-1 text-sm text-steel">
              {new Date(run.window_start).toLocaleDateString()} to{" "}
              {new Date(run.window_end).toLocaleDateString()}
            </p>
          </div>
          <div className="grid grid-cols-4 gap-4 text-right">
            <Metric label="Move" value={`${run.observed_return_bps.toFixed(2)} bps`} />
            <Metric label="Residual" value={`${run.unexplained_residual_bps.toFixed(2)} bps`} />
            <Metric label="Cadence" value={run.cadence} />
            <Metric label="Model" value={run.model_version} />
          </div>
        </div>
      </section>
      <AttributionChart ticker={run.ticker} initialChart={chart} />
      <DriverTable run={run} />
      <RunHistory ticker={run.ticker} runs={runHistory} activeRunId={run.attribution_run_id} />
      <section className="flex flex-col gap-2">
        <h2 className="text-base font-semibold">Exposure Review</h2>
        <ExposureDecisions decisions={exposureDecisions} />
      </section>
    </>
  );
}

function EmptyDetail({ ticker, companyName }: { ticker: string; companyName?: string }) {
  return (
    <section className="border-y border-line bg-white px-4 py-6">
      <h2 className="text-lg font-semibold">{ticker || "No ticker selected"}</h2>
      {companyName ? <p className="mt-1 text-sm text-steel">{companyName}</p> : null}
      <p className="mt-4 text-sm text-steel">
        No attribution run is available for this stock yet. It remains accessible in the universe,
        and the detail panel will populate after a successful attribution run is persisted.
      </p>
    </section>
  );
}

function Metric({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon?: ReactNode;
}) {
  return (
    <div className="min-w-24">
      <div className="flex justify-end gap-1 text-xs uppercase text-steel">
        {icon}
        {label}
      </div>
      <div className="mt-1 text-sm font-semibold">{value}</div>
    </div>
  );
}

async function optionalRun<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise;
  } catch {
    return null;
  }
}

async function optionalList<T>(promise: Promise<T[]>): Promise<T[]> {
  try {
    return await promise;
  } catch {
    return [];
  }
}

function numberParam(value: string | undefined, fallback: number) {
  if (!value) {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}
