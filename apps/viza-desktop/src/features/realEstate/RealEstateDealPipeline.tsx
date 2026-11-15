interface DealPipelineRow {
  property_id: string;
  property_name: string;
  market: string;
  deal_score: number;
  dscr: number;
  cap_rate: number;
  passes_dscr: boolean;
}

export function RealEstateDealPipeline({ rows }: { rows: DealPipelineRow[] }) {
  return (
    <section className="real-estate-pipeline">
      <div className="result-label">Deal Pipeline</div>
      <table>
        <thead>
          <tr>
            <th>Property</th>
            <th>Market</th>
            <th>Score</th>
            <th>DSCR</th>
            <th>Cap Rate</th>
            <th>Gate</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.property_id}>
              <td>{row.property_name}</td>
              <td>{row.market}</td>
              <td>{row.deal_score.toFixed(3)}</td>
              <td>{row.dscr.toFixed(2)}</td>
              <td>{(row.cap_rate * 100).toFixed(1)}%</td>
              <td>{row.passes_dscr ? "pass" : "review"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
