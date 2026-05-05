import Link from "next/link";
import {
  Activity,
  AlertCircle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Info,
  Search,
} from "lucide-react";
import type { UniverseResponse, UniverseStock } from "@/lib/types";

type Params = {
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

const SORT_LABELS: Record<string, string> = {
  ticker: "Ticker",
  company: "Company",
  sector: "Sector",
  latest_run: "Run",
  move: "Move",
  residual: "Residual",
  top_driver: "Top Driver",
  confidence: "Confidence",
};

export function UniverseTable({
  universe,
  params,
  selectedTicker,
}: {
  universe: UniverseResponse;
  params: Params;
  selectedTicker: string;
}) {
  const limit = universe.limit;
  const previousOffset = Math.max(0, universe.offset - limit);
  const nextOffset = universe.offset + limit;
  const canPageBack = universe.offset > 0;
  const canPageForward = nextOffset < universe.total;
  const expanded = params.universe === "open";
  const displayMode = params.display === "usd" ? "usd" : "bps";
  const companyOptions = universe.company_options ?? [];
  const sectorOptions = universe.sector_options ?? [];
  const industryOptions = universe.industry_options ?? [];
  const exchangeOptions = universe.exchange_options ?? [];

  return (
    <section className="border-y border-steel/40 bg-white">
      <div className="border-b border-steel/30 bg-[#eef3f1] px-4 py-3">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Universe Access</h2>
            <p className="text-sm text-steel">Search and filter the model universe.</p>
          </div>
          <Link
            href={queryHref(params, {
              universe: expanded ? undefined : "open",
              offset: String(universe.offset),
            })}
            className="inline-flex h-9 items-center gap-2 border border-steel bg-white px-3 text-sm font-semibold text-steel hover:bg-paper"
          >
            {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            {expanded ? "Collapse" : "Show Rows"}
          </Link>
        </div>
        <form className="grid gap-2 lg:grid-cols-[minmax(180px,1.2fr)_repeat(4,minmax(120px,0.7fr))_auto]">
          <label className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 text-steel" size={15} />
            <input
              name="search"
              list="universe-company-options"
              defaultValue={params.search ?? ""}
              className="h-9 w-full border border-line bg-white pl-9 pr-3 text-sm outline-none focus:border-steel"
              placeholder="Search ticker or company"
            />
          </label>
          <input
            name="sector"
            list="universe-sector-options"
            defaultValue={params.sector ?? ""}
            className="h-9 border border-line bg-white px-3 text-sm outline-none focus:border-steel"
            placeholder="Sector"
          />
          <input
            name="industry"
            list="universe-industry-options"
            defaultValue={params.industry ?? ""}
            className="h-9 border border-line bg-white px-3 text-sm outline-none focus:border-steel"
            placeholder="Industry"
          />
          <input
            name="exchange"
            list="universe-exchange-options"
            defaultValue={params.exchange ?? ""}
            className="h-9 border border-line bg-white px-3 text-sm uppercase outline-none focus:border-steel"
            placeholder="Exchange"
          />
          <select
            name="status"
            defaultValue={params.status ?? ""}
            className="h-9 border border-line bg-white px-3 text-sm outline-none focus:border-steel"
          >
            <option value="">All runs</option>
            <option value="available">Available</option>
            <option value="missing">Missing</option>
          </select>
          <input type="hidden" name="sort" value={params.sort ?? "ticker"} />
          <input type="hidden" name="order" value={params.order ?? "asc"} />
          <input type="hidden" name="limit" value={String(limit)} />
          <input type="hidden" name="universe" value={params.universe ?? ""} />
          <input type="hidden" name="display" value={params.display ?? ""} />
          <button className="h-9 border border-steel bg-steel px-4 text-sm font-semibold text-white">
            Apply
          </button>
          <datalist id="universe-company-options">
            {companyOptions.map((option) => (
              <option
                key={option.ticker}
                value={option.ticker}
                label={`${option.ticker} - ${option.company_name}`}
              />
            ))}
          </datalist>
          <datalist id="universe-sector-options">
            {sectorOptions.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>
          <datalist id="universe-industry-options">
            {industryOptions.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>
          <datalist id="universe-exchange-options">
            {exchangeOptions.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>
        </form>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-steel/20 pt-3">
          <span className="text-xs uppercase text-steel">Display stock row values as</span>
          <div className="inline-flex border border-line bg-white text-sm">
            <DisplayLink active={displayMode === "bps"} href={queryHref(params, { display: undefined })}>
              Basis points
            </DisplayLink>
            <DisplayLink active={displayMode === "usd"} href={queryHref(params, { display: "usd" })}>
              USD
            </DisplayLink>
          </div>
        </div>
      </div>

      {expanded ? (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] border-collapse text-sm">
              <thead className="bg-white text-left text-xs uppercase text-steel">
                <tr className="border-b border-line">
                  {Object.entries(SORT_LABELS).map(([key, label]) => (
                    <th key={key} className="h-10 px-4">
                      <Link
                        href={queryHref(params, {
                          sort: key,
                          order: params.sort === key && params.order !== "desc" ? "desc" : "asc",
                          offset: "0",
                        })}
                        className="inline-flex items-center gap-1 hover:text-ink"
                      >
                        {label}
                        {key === "move" ? (
                          <Info
                            size={13}
                            aria-label="Observed stock return over the latest attribution window."
                          >
                            <title>Observed stock return over the latest attribution window.</title>
                          </Info>
                        ) : null}
                        {key === "residual" ? (
                          <Info
                            size={13}
                            aria-label="Portion of the move not explained by modeled drivers."
                          >
                            <title>Portion of the move not explained by modeled drivers.</title>
                          </Info>
                        ) : null}
                        {params.sort === key ? (
                          params.order === "desc" ? <ArrowDown size={12} /> : <ArrowUp size={12} />
                        ) : null}
                      </Link>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {universe.rows.map((stock, index) => (
                  <UniverseRow
                    key={`${stock.security_id}-${stock.ticker}-${index}`}
                    stock={stock}
                    selected={stock.ticker === selectedTicker}
                    displayMode={displayMode}
                    href={queryHref(params, {
                      ticker: stock.ticker,
                      runId: undefined,
                      offset: String(universe.offset),
                    })}
                  />
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm text-steel">
            <span>
              Showing {universe.total === 0 ? 0 : universe.offset + 1}-
              {Math.min(universe.offset + universe.rows.length, universe.total)} of {universe.total}
            </span>
            <div className="flex gap-2">
              <PageLink disabled={!canPageBack} href={queryHref(params, { offset: String(previousOffset) })}>
                Previous
              </PageLink>
              <PageLink disabled={!canPageForward} href={queryHref(params, { offset: String(nextOffset) })}>
                Next
              </PageLink>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}

function UniverseRow({
  stock,
  selected,
  href,
  displayMode,
}: {
  stock: UniverseStock;
  selected: boolean;
  href: string;
  displayMode: "bps" | "usd";
}) {
  const moveClass =
    stock.latest_observed_return_bps === null
      ? "text-steel"
      : stock.latest_observed_return_bps < 0
        ? "text-signal"
        : "text-moss";
  const residualClass =
    stock.latest_residual_bps === null
      ? "text-steel"
      : Math.abs(stock.latest_residual_bps) > 50
        ? "text-signal"
        : "text-ink";

  return (
    <tr className={`border-b border-line last:border-b-0 ${selected ? "bg-paper" : "hover:bg-paper"}`}>
      <td className="px-4 py-3">
        <Link href={href} className="font-semibold text-ink hover:text-steel">
          {stock.ticker}
        </Link>
        <div className="mt-1 flex items-center gap-1 text-xs text-steel">
          {stock.run_status === "available" ? (
            <CheckCircle2 size={13} className="text-moss" />
          ) : (
            <AlertCircle size={13} className="text-signal" />
          )}
          {stock.run_status}
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="max-w-[220px] truncate font-medium">{stock.company_name}</div>
        <div className="text-xs text-steel">{stock.exchange}</div>
      </td>
      <td className="px-4 py-3 text-steel">{stock.sector ?? "n/a"}</td>
      <td className="px-4 py-3 text-steel">{formatDate(stock.latest_window_end)}</td>
      <td className={`px-4 py-3 font-semibold ${moveClass}`}>
        {formatValue({
          mode: displayMode,
          bps: stock.latest_observed_return_bps,
          usd: stock.latest_price_change_usd,
        })}
      </td>
      <td className={`px-4 py-3 font-semibold ${residualClass}`}>
        {formatValue({
          mode: displayMode,
          bps: stock.latest_residual_bps,
          usd: stock.latest_residual_usd,
        })}
      </td>
      <td className="px-4 py-3">
        <div className="max-w-[180px] truncate">{stock.top_driver ?? "n/a"}</div>
        <div className="text-xs text-steel">
          {stock.has_evidence ? (
            <span className="inline-flex items-center gap-1">
              <Activity size={12} />
              evidence
            </span>
          ) : (
            "no evidence"
          )}
        </div>
      </td>
      <td className="px-4 py-3">
        <span className="inline-flex h-7 items-center border border-line px-2 text-xs text-steel">
          {stock.top_driver_confidence ?? "n/a"}
        </span>
      </td>
    </tr>
  );
}

function DisplayLink({ active, href, children }: { active: boolean; href: string; children: string }) {
  return (
    <Link
      href={href}
      className={`px-3 py-1.5 font-semibold ${
        active ? "bg-steel text-white" : "text-steel hover:bg-paper hover:text-ink"
      }`}
    >
      {children}
    </Link>
  );
}

function PageLink({ disabled, href, children }: { disabled: boolean; href: string; children: string }) {
  if (disabled) {
    return <span className="border border-line px-3 py-1 text-line">{children}</span>;
  }
  return (
    <Link className="border border-line px-3 py-1 hover:border-steel hover:text-ink" href={href}>
      {children}
    </Link>
  );
}

function queryHref(params: Params, patch: Partial<Params>) {
  const next = new URLSearchParams();
  for (const [key, value] of Object.entries({ ...params, ...patch })) {
    if (value !== undefined && value !== null && value !== "") {
      next.set(key, String(value));
    }
  }
  return `/?${next.toString()}`;
}

function formatDate(value: string | null) {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toLocaleDateString();
}

function formatValue({
  mode,
  bps,
  usd,
}: {
  mode: "bps" | "usd";
  bps: number | null;
  usd: number | null;
}) {
  if (mode === "usd") {
    return formatUsd(usd);
  }
  if (bps === null) {
    return "n/a";
  }
  return `${bps.toFixed(1)} bp`;
}

function formatUsd(value: number | null) {
  if (value === null) {
    return "n/a";
  }
  const absolute = Math.abs(value);
  const formatted = absolute.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return value < 0 ? `-$${formatted}` : `$${formatted}`;
}
