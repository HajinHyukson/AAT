"use client";

import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { AlertTriangle, ChevronDown, ChevronRight, Download } from "lucide-react";
import { Fragment, useMemo, useState } from "react";
import type { AttributionRun, Contribution } from "@/lib/types";
import { submitAnalystFeedback } from "@/lib/api";

type Feedback = "correct" | "partially_correct" | "wrong" | "missing_driver";
const FEEDBACK_LABELS: Record<Feedback, string> = {
  correct: "Correct",
  partially_correct: "Partial",
  wrong: "Wrong",
  missing_driver: "Missing",
};
const DRIVER_FILTERS = [
  "all",
  "market",
  "sector",
  "peer",
  "style",
  "macro",
  "positioning",
  "event",
  "unexplained_residual",
];

export function DriverTable({ run }: { run: AttributionRun }) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "contribution_bps", desc: true },
  ]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [feedback, setFeedback] = useState<Record<string, Feedback>>({});
  const [driverFilter, setDriverFilter] = useState("all");
  const [status, setStatus] = useState<string>("");
  const observedAbs = Math.abs(run.observed_return_bps);
  const filteredContributions = useMemo(
    () =>
      driverFilter === "all"
        ? run.contributions
        : run.contributions.filter((item) => item.driver === driverFilter),
    [driverFilter, run.contributions],
  );

  const columns = useMemo<ColumnDef<Contribution>[]>(
    () => [
      {
        accessorKey: "name",
        header: "Driver",
        cell: ({ row }) => {
          const contribution = row.original;
          const key = row.id;
          const isResidual = contribution.driver === "unexplained_residual";
          const residualIsLarge =
            isResidual && Math.abs(contribution.contribution_bps) > observedAbs * 0.5;
          return (
            <button
              className="flex min-h-10 w-full items-center gap-2 text-left"
              onClick={() => setExpanded((state) => ({ ...state, [key]: !state[key] }))}
            >
              {expanded[key] ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              <span className={residualIsLarge ? "font-semibold text-signal" : "font-medium"}>
                {contribution.name}
              </span>
              {contribution.contribution_stage !== "production" ? (
                <span className="rounded border border-line px-2 py-0.5 text-xs uppercase text-steel">
                  {contribution.contribution_stage.replace("_", " ")}
                </span>
              ) : null}
              {residualIsLarge ? <AlertTriangle size={16} className="text-signal" /> : null}
            </button>
          );
        },
      },
      {
        accessorKey: "contribution_bps",
        header: "Bps",
        cell: ({ row }) => (
          <span className={row.original.contribution_bps < 0 ? "text-signal" : "text-moss"}>
            {row.original.contribution_bps.toFixed(2)}
          </span>
        ),
      },
      {
        accessorKey: "share_of_move",
        header: "Share",
        cell: ({ row }) =>
          row.original.share_of_move === null
            ? "n/a"
            : `${(row.original.share_of_move * 100).toFixed(1)}%`,
      },
      {
        accessorKey: "confidence",
        header: "Confidence",
        cell: ({ row }) => <ConfidencePill confidence={row.original.confidence} />,
      },
      {
        id: "feedback",
        header: "Feedback",
        cell: ({ row }) => (
          <div className="grid grid-cols-4 gap-1">
            {(["correct", "partially_correct", "wrong", "missing_driver"] as Feedback[]).map((item) => (
              <button
                key={item}
                className={`h-8 rounded border px-2 text-xs ${
                  feedback[row.id] === item
                    ? "border-steel bg-steel text-white"
                    : "border-line bg-white text-ink hover:border-steel"
                }`}
                onClick={() => submitFeedback(row.original, row.id, item)}
              >
                {FEEDBACK_LABELS[item]}
              </button>
            ))}
          </div>
        ),
      },
    ],
    [expanded, feedback, observedAbs],
  );

  const table = useReactTable({
    data: filteredContributions,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="overflow-hidden border-y border-line bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-white px-4 py-3">
        <div className="flex flex-wrap gap-2">
          {DRIVER_FILTERS.map((driver) => (
            <button
              key={driver}
              className={`h-8 rounded border px-3 text-xs capitalize ${
                driverFilter === driver
                  ? "border-steel bg-steel text-white"
                  : "border-line bg-white text-ink hover:border-steel"
              }`}
              onClick={() => setDriverFilter(driver)}
            >
              {driver.replace("_", " ")}
            </button>
          ))}
        </div>
        <button
          className="inline-flex h-8 items-center gap-2 rounded border border-line px-3 text-xs text-ink hover:border-steel"
          onClick={() => exportCsv(run)}
        >
          <Download size={14} />
          CSV
        </button>
      </div>
      {run.narrative ? (
        <div className="border-b border-line bg-paper px-4 py-3 text-sm text-ink">
          {run.narrative}
        </div>
      ) : null}
      {status ? <div className="border-b border-line px-4 py-2 text-xs text-steel">{status}</div> : null}
      <table className="w-full border-collapse text-sm">
        <thead className="bg-paper text-left text-xs uppercase text-steel">
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th key={header.id} className="h-11 px-4">
                  {header.isPlaceholder
                    ? null
                    : flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <Fragment key={row.id}>
              <tr key={row.id} className="border-t border-line">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-4 py-3 align-middle">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
              {expanded[row.id] ? (
                <tr className="border-t border-line bg-paper">
                  <td colSpan={columns.length} className="px-4 py-3 text-sm text-steel">
                    <Evidence contribution={row.original} />
                  </td>
                </tr>
              ) : null}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );

  async function submitFeedback(contribution: Contribution, rowId: string, value: Feedback) {
    const missingName =
      value === "missing_driver" ? window.prompt("Missing driver name") ?? "" : null;
    if (value === "missing_driver" && !missingName) {
      return;
    }
    setFeedback((state) => ({ ...state, [rowId]: value }));
    try {
      await submitAnalystFeedback({
        attribution_run_id: run.attribution_run_id,
        attribution_contribution_id:
          value === "missing_driver" ? null : contribution.attribution_contribution_id,
        feedback: value,
        missing_driver_name: missingName,
      });
      setStatus("Feedback saved.");
    } catch {
      setStatus("Feedback could not be saved.");
    }
  }
}

function ConfidencePill({ confidence }: { confidence: string }) {
  const className =
    confidence === "High" || confidence === "Medium-High"
      ? "border-moss text-moss"
      : confidence === "Medium"
        ? "border-steel text-steel"
        : "border-signal text-signal";
  return (
    <span className={`inline-flex h-7 items-center rounded border px-2 text-xs ${className}`}>
      {confidence}
    </span>
  );
}

function Evidence({ contribution }: { contribution: Contribution }) {
  const payloadEntries = Object.entries(contribution.evidence_payload ?? {});
  return (
    <div className="grid gap-3">
      {contribution.evidence.length ? (
        <div className="flex flex-wrap gap-2">
          {contribution.evidence.map((item, index) => (
            <span key={index} className="rounded border border-line bg-white px-2 py-1 text-xs">
              {String(item)}
            </span>
          ))}
        </div>
      ) : null}
      {payloadEntries.length ? (
        <dl className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
          {payloadEntries.map(([key, value]) => (
            <div key={key} className="rounded border border-line bg-white p-2">
              <dt className="text-xs uppercase text-steel">{key.replaceAll("_", " ")}</dt>
              <dd className="mt-1 break-words text-xs text-ink">{formatValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : contribution.evidence.length ? null : (
        <span>No evidence rows attached yet.</span>
      )}
    </div>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "n/a";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function exportCsv(run: AttributionRun) {
  const headers = [
    "driver",
    "name",
    "contribution_bps",
    "share_of_move",
    "confidence",
    "stage",
    "evidence",
    "evidence_payload",
  ];
  const rows = run.contributions.map((item) =>
    [
      item.driver,
      item.name,
      item.contribution_bps,
      item.share_of_move ?? "",
      item.confidence,
      item.contribution_stage,
      JSON.stringify(item.evidence),
      JSON.stringify(item.evidence_payload ?? {}),
    ].map(csvCell),
  );
  const csv = [headers, ...rows].map((row) => row.join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${run.ticker}_${run.attribution_run_id}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function csvCell(value: unknown): string {
  const text = String(value).replaceAll('"', '""');
  return `"${text}"`;
}
