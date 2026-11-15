import { Activity, Database, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { AttributionDetailLoader } from "@/components/attribution-detail-loader";
import { UniverseTable } from "@/components/universe-table";
import {
  getAttributionRunById,
  getAttributionRuns,
  getAttributionChart,
  getAttributionMethodologies,
  getExposureUpdateDecisions,
  getLatestAttribution,
  getUniverse,
} from "@/lib/api";
import type { AttributionMethodology, UniverseResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

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
  methodology?: string;
};

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  let methodologies: AttributionMethodology[];
  let selectedMethodology: string;
  let universe: UniverseResponse;
  try {
    methodologies = await getAttributionMethodologies();
    selectedMethodology = selectedMethodologyId(methodologies, params.methodology);
    universe = await getUniverse({
      search: params.search,
      sector: params.sector,
      industry: params.industry,
      exchange: params.exchange,
      status: params.status,
      sort: params.sort ?? "ticker",
      order: params.order ?? "asc",
      limit: numberParam(params.limit, 50),
      offset: numberParam(params.offset, 0),
      methodology: selectedMethodology,
    });
  } catch (error) {
    return (
      <ApiUnavailable message={error instanceof Error ? error.message : String(error)} />
    );
  }
  const defaultStock =
    universe.rows.find((stock) => stock.run_status === "available") ?? universe.rows[0] ?? null;
  const selectedTicker = (params.ticker ?? defaultStock?.ticker ?? "").toUpperCase();
  const selectedUniverseStock = universe.rows.find((stock) => stock.ticker === selectedTicker);
  const paramsWithMethodology = { ...params, methodology: selectedMethodology };

  const requestedRun = selectedTicker && params.runId
    ? await optionalRun(getAttributionRunById(params.runId))
    : null;
  const selectedRun =
    requestedRun && runMatchesSelection(requestedRun, selectedTicker, selectedMethodology)
      ? requestedRun
      : null;
  const run = selectedTicker
    ? selectedRun ?? await optionalRun(getLatestAttribution(selectedTicker, selectedMethodology))
    : null;
  const selectedRunId = selectedRun ? params.runId : undefined;
  const [runHistory, exposureDecisions, chart] =
    run && selectedTicker
      ? await Promise.all([
          optionalList(getAttributionRuns(selectedTicker, 20, selectedMethodology)),
          optionalList(getExposureUpdateDecisions(selectedTicker)),
          optionalRun(getAttributionChart(selectedTicker, "1m", selectedMethodology)),
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
          <MethodologySelector
            methodologies={methodologies}
            selectedMethodology={selectedMethodology}
            params={params}
          />
        </header>

        <div className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(680px,1fr)_minmax(460px,0.7fr)]">
          <div className="flex min-w-0 flex-col gap-3">
            <UniverseTable universe={universe} params={paramsWithMethodology} selectedTicker={selectedTicker} />
          </div>

          <aside className="flex min-w-0 flex-col gap-5 2xl:border-l 2xl:border-steel/30 2xl:pl-5">
            <AttributionDetailLoader
              ticker={selectedTicker}
              companyName={selectedUniverseStock?.company_name}
              methodology={selectedMethodology}
              selectedRunId={selectedRunId}
              initialRun={run}
              initialRunHistory={runHistory}
              initialExposureDecisions={exposureDecisions}
              initialChart={chart}
            />
          </aside>
        </div>
      </section>
    </main>
  );
}

function MethodologySelector({
  methodologies,
  selectedMethodology,
  params,
}: {
  methodologies: AttributionMethodology[];
  selectedMethodology: string;
  params: SearchParams;
}) {
  return (
    <form className="mt-4 flex flex-wrap items-center gap-2">
      <label className="text-xs uppercase text-steel" htmlFor="methodology">
        Methodology
      </label>
      <select
        id="methodology"
        name="methodology"
        defaultValue={selectedMethodology}
        className="h-9 border border-line bg-white px-3 text-sm outline-none focus:border-steel"
      >
        {methodologies.map((item) => (
          <option key={item.methodology} value={item.methodology}>
            {item.display_name}
            {item.status === "archived" ? " (archived)" : ""}
          </option>
        ))}
      </select>
      <input type="hidden" name="ticker" value={params.ticker ?? ""} />
      <input type="hidden" name="search" value={params.search ?? ""} />
      <input type="hidden" name="sector" value={params.sector ?? ""} />
      <input type="hidden" name="industry" value={params.industry ?? ""} />
      <input type="hidden" name="exchange" value={params.exchange ?? ""} />
      <input type="hidden" name="status" value={params.status ?? ""} />
      <input type="hidden" name="sort" value={params.sort ?? "ticker"} />
      <input type="hidden" name="order" value={params.order ?? "asc"} />
      <input type="hidden" name="limit" value={params.limit ?? "50"} />
      <input type="hidden" name="offset" value="0" />
      <input type="hidden" name="universe" value={params.universe ?? ""} />
      <input type="hidden" name="display" value={params.display ?? ""} />
      <button className="h-9 border border-steel bg-white px-3 text-sm font-semibold text-steel hover:bg-paper">
        Apply
      </button>
    </form>
  );
}

function ApiUnavailable({ message }: { message: string }) {
  return (
    <main className="min-h-screen bg-paper text-ink">
      <section className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-16">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center bg-ink text-sm font-semibold text-white">
            AAT
          </div>
          <h1 className="text-xl font-semibold">Attribution data is unreachable</h1>
        </div>
        <div className="border-y border-line bg-white px-4 py-6 text-sm text-steel">
          <p>
            The dashboard could not reach the attribution API. This usually means the API
            server or its tunnel is down, or <code>AAT_API_BASE_URL</code> is not configured
            for this deployment.
          </p>
          <p className="mt-3 font-mono text-xs">{message}</p>
          <p className="mt-3">Reload the page once the API is back.</p>
        </div>
      </section>
    </main>
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

function runMatchesSelection(run: { ticker: string; methodology: string }, ticker: string, methodology: string) {
  return run.ticker.toUpperCase() === ticker.toUpperCase() && run.methodology === methodology;
}

function selectedMethodologyId(methodologies: AttributionMethodology[], requested?: string) {
  if (requested && methodologies.some((item) => item.methodology === requested)) {
    return requested;
  }
  return (
    methodologies.find((item) => item.is_default)?.methodology ??
    methodologies.find((item) => item.status === "active")?.methodology ??
    "residual_safety_v1"
  );
}

function numberParam(value: string | undefined, fallback: number) {
  if (!value) {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}
