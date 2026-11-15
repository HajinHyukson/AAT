"use client";

import { Activity, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { AttributionChart } from "@/components/attribution-chart";
import { DriverTable } from "@/components/driver-table";
import { ExposureDecisions } from "@/components/exposure-decisions";
import { RunHistory } from "@/components/run-history";
import {
  ensureLatestAttribution,
  getAttributionChart,
  getAttributionJob,
  getAttributionRunById,
  getAttributionRuns,
  getExposureUpdateDecisions,
} from "@/lib/api";
import type { AttributionChartResponse, AttributionRun, ExposureUpdateDecision } from "@/lib/types";

type DetailState = {
  run: AttributionRun | null;
  runHistory: AttributionRun[];
  exposureDecisions: ExposureUpdateDecision[];
  chart: AttributionChartResponse | null;
  loading: boolean;
  status: string;
};

const EMPTY_RUN_HISTORY: AttributionRun[] = [];
const EMPTY_EXPOSURE_DECISIONS: ExposureUpdateDecision[] = [];

export function AttributionDetailLoader({
  ticker,
  companyName,
  methodology,
  selectedRunId,
  initialRun,
  initialRunHistory,
  initialExposureDecisions,
  initialChart,
}: {
  ticker: string;
  companyName?: string;
  methodology: string;
  selectedRunId?: string;
  initialRun: AttributionRun | null;
  initialRunHistory: AttributionRun[];
  initialExposureDecisions: ExposureUpdateDecision[];
  initialChart: AttributionChartResponse | null;
}) {
  const selectedRunMatches =
    Boolean(selectedRunId) &&
    initialRun?.ticker.toUpperCase() === ticker.toUpperCase() &&
    initialRun.methodology === methodology;
  const safeInitialRun = selectedRunId && !selectedRunMatches ? null : initialRun;
  const safeInitialRunHistory =
    selectedRunId && !selectedRunMatches ? EMPTY_RUN_HISTORY : initialRunHistory;
  const safeInitialExposureDecisions =
    selectedRunId && !selectedRunMatches ? EMPTY_EXPOSURE_DECISIONS : initialExposureDecisions;
  const safeInitialChart = selectedRunId && !selectedRunMatches ? null : initialChart;
  const [state, setState] = useState<DetailState>({
    run: safeInitialRun,
    runHistory: safeInitialRunHistory,
    exposureDecisions: safeInitialExposureDecisions,
    chart: safeInitialChart,
    loading: !selectedRunMatches,
    status: "",
  });

  useEffect(() => {
    let cancelled = false;

    async function loadSelectedRun() {
      setState({
        run: safeInitialRun,
        runHistory: safeInitialRunHistory,
        exposureDecisions: safeInitialExposureDecisions,
        chart: safeInitialChart,
        loading: false,
        status: "",
      });
    }

    async function ensureLatest() {
      setState((current) => ({
        ...current,
        run: safeInitialRun,
        runHistory: safeInitialRunHistory,
        exposureDecisions: safeInitialExposureDecisions,
        chart: safeInitialChart,
        loading: true,
        status: "Loading attribution",
      }));
      try {
        const ensured = await ensureLatestAttribution({ ticker, methodology, cadence: "daily", range: "1m" });
        if (cancelled) {
          return;
        }
        if (ensured.status === "fresh" && ensured.run) {
          await loadRunBundle(ensured.run);
          return;
        }
        if (ensured.job_id) {
          setState((current) => ({
            ...current,
            loading: true,
            status: ensured.status === "running" ? "Running attribution" : "Queued attribution",
          }));
          const run = await pollJobForRun(ensured.job_id, () => cancelled);
          if (!cancelled && run) {
            await loadRunBundle(run);
            return;
          }
        }
        if (!cancelled) {
          setState((current) => ({
            ...current,
            loading: false,
            status: "Attribution is not available",
          }));
        }
      } catch {
        if (!cancelled) {
          setState((current) => ({
            ...current,
            loading: false,
            status: "Attribution could not be loaded",
          }));
        }
      }
    }

    async function loadRunBundle(run: AttributionRun) {
      const [runHistory, exposureDecisions, chart] = await Promise.all([
        optionalList(getAttributionRuns(ticker, 20, methodology)),
        optionalList(getExposureUpdateDecisions(ticker)),
        optionalRun(getAttributionChart(ticker, "1m", methodology)),
      ]);
      if (!cancelled) {
        setState({
          run,
          runHistory,
          exposureDecisions,
          chart,
          loading: false,
          status: "",
        });
      }
    }

    if (!ticker) {
      return;
    }
    if (selectedRunMatches) {
      void loadSelectedRun();
    } else {
      void ensureLatest();
    }

    return () => {
      cancelled = true;
    };
  }, [
    ticker,
    methodology,
    selectedRunId,
    selectedRunMatches,
    safeInitialRun,
    safeInitialRunHistory,
    safeInitialExposureDecisions,
    safeInitialChart,
  ]);

  if (state.run) {
    return (
      <AttributionWorkspace
        run={state.run}
        methodology={methodology}
        runHistory={state.runHistory}
        exposureDecisions={state.exposureDecisions}
        chart={state.chart}
        loading={state.loading}
        status={state.status}
      />
    );
  }

  return (
    <section className="border-y border-line bg-white px-4 py-6">
      <h2 className="text-lg font-semibold">{ticker || "No ticker selected"}</h2>
      {companyName ? <p className="mt-1 text-sm text-steel">{companyName}</p> : null}
      <div className="mt-4 flex items-center gap-2 text-sm text-steel">
        {state.loading ? <Loader2 size={16} className="animate-spin" /> : <Activity size={16} />}
        <span>{state.status || "No attribution run is available."}</span>
      </div>
    </section>
  );
}

function AttributionWorkspace({
  run,
  methodology,
  runHistory,
  exposureDecisions,
  chart,
  loading,
  status,
}: {
  run: AttributionRun;
  methodology: string;
  runHistory: AttributionRun[];
  exposureDecisions: ExposureUpdateDecision[];
  chart: AttributionChartResponse | null;
  loading: boolean;
  status: string;
}) {
  return (
    <>
      <section className="border-y border-line bg-white">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line bg-paper px-4 py-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-semibold">{run.ticker}</h2>
              {loading ? <Loader2 size={16} className="animate-spin text-steel" /> : null}
            </div>
            <p className="mt-1 text-sm text-steel">
              {new Date(run.window_start).toLocaleDateString()} to{" "}
              {new Date(run.window_end).toLocaleDateString()}
            </p>
            {status ? <p className="mt-1 text-xs text-steel">{status}</p> : null}
          </div>
          <div className="grid grid-cols-4 gap-4 text-right">
            <Metric label="Move" value={`${run.observed_return_bps.toFixed(2)} bps`} />
            <Metric label="Residual" value={`${run.unexplained_residual_bps.toFixed(2)} bps`} />
            <Metric label="Cadence" value={run.cadence} />
            <Metric label="Method" value={run.methodology} />
          </div>
        </div>
      </section>
      <AttributionChart
        key={`${run.ticker}-${methodology}`}
        ticker={run.ticker}
        methodology={methodology}
        initialChart={chart}
      />
      <DriverTable run={run} />
      <RunHistory
        ticker={run.ticker}
        methodology={methodology}
        runs={runHistory}
        activeRunId={run.attribution_run_id}
      />
      <section className="flex flex-col gap-2">
        <h2 className="text-base font-semibold">Exposure Review</h2>
        <ExposureDecisions decisions={exposureDecisions} />
      </section>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-24">
      <div className="flex justify-end gap-1 text-xs uppercase text-steel">{label}</div>
      <div className="mt-1 text-sm font-semibold">{value}</div>
    </div>
  );
}

async function pollJobForRun(jobId: string, isCancelled: () => boolean) {
  for (let attempt = 0; attempt < 90; attempt += 1) {
    if (isCancelled()) {
      return null;
    }
    await sleep(1500);
    const job = await getAttributionJob(jobId);
    if (job.status === "completed") {
      if (job.run) {
        return job.run;
      }
      if (job.latest_run_id) {
        return getAttributionRunById(job.latest_run_id);
      }
      return null;
    }
    if (job.status === "failed" || job.status === "skipped") {
      return null;
    }
  }
  return null;
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

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
