export function InvestmentMemoView({
  markdown,
  summary,
}: {
  markdown: string;
  summary?: string | null;
}) {
  return (
    <section className="real-estate-memo">
      <div className="result-label">Investment Memo</div>
      {summary && <p>{summary}</p>}
      <pre>{markdown}</pre>
    </section>
  );
}
