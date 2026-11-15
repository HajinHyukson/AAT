export interface UnknownNodePlaceholderProps {
  moduleId: string;
  nodeType: string;
  rawConfig?: Record<string, unknown>;
}

export function UnknownNodePlaceholder({
  moduleId,
  nodeType,
  rawConfig = {},
}: UnknownNodePlaceholderProps) {
  return (
    <div className="unknown-node-placeholder" aria-label="Unknown Module Node">
      <div className="unknown-node-title">Unknown Module Node</div>
      <dl>
        <dt>module</dt>
        <dd>{moduleId}</dd>
        <dt>node type</dt>
        <dd>{nodeType}</dd>
        <dt>status</dt>
        <dd>module not installed</dd>
      </dl>
      <pre>{JSON.stringify(rawConfig, null, 2)}</pre>
    </div>
  );
}
