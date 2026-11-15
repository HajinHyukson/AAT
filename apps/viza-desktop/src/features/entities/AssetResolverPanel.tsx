import type { AssetResolveResult, EntityResolveResult } from "./types";

export function AssetResolverPanel({
  entityResult,
  assetResult,
}: {
  entityResult: EntityResolveResult | null;
  assetResult: AssetResolveResult | null;
}) {
  return (
    <section className="asset-resolver-panel">
      <h3>Identity</h3>
      <dl>
        <dt>entity</dt>
        <dd>{entityResult?.entity?.entity_id ?? "unresolved"}</dd>
        <dt>asset</dt>
        <dd>{assetResult?.asset?.asset_id ?? "unresolved"}</dd>
        <dt>symbol</dt>
        <dd>{assetResult?.asset?.primary_symbol ?? entityResult?.query.ticker ?? ""}</dd>
      </dl>
      {[...(entityResult?.warnings ?? []), ...(assetResult?.warnings ?? [])].map((warning) => (
        <p key={warning} className="resolver-warning">
          {warning.replaceAll("_", " ")}
        </p>
      ))}
    </section>
  );
}
