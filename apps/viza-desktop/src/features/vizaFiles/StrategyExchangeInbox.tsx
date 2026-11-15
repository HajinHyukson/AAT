import type { VizaFileRecordResponse } from "./types";

export function StrategyExchangeInbox({ records }: { records: VizaFileRecordResponse[] }) {
  return (
    <section className="strategy-exchange-inbox">
      <h2>Strategy Exchange</h2>
      <ul>
        {records.map((record) => {
          const quarantined = record.imports.some(
            (item) => item.quarantine_status === "quarantined",
          );
          return (
            <li key={record.file_id} data-status={quarantined ? "quarantined" : "available"}>
              <span>{record.file_id}</span>
              <strong>{quarantined ? "quarantined" : "available"}</strong>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
