import { useState } from "react";
import type { VizaConnectorDefinition } from "../../vizaGraph";
import {
  configureConnector,
  fetchConnectorCredentials,
  setConnectorCredential,
} from "./connectorClient";
import type { CredentialStatus } from "./types";

interface ConnectorSettingsPanelProps {
  connector: VizaConnectorDefinition;
}

export function ConnectorSettingsPanel({ connector }: ConnectorSettingsPanelProps) {
  const firstRequirement = connector.credential_requirements[0];
  const [credentialKey, setCredentialKey] = useState(firstRequirement?.key ?? "");
  const [credentialValue, setCredentialValue] = useState("");
  const [localPath, setLocalPath] = useState("");
  const [statuses, setStatuses] = useState<CredentialStatus[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  async function refreshCredentials() {
    const nextStatuses = await fetchConnectorCredentials(connector.connector_id);
    setStatuses(nextStatuses);
  }

  async function saveCredential() {
    if (!credentialKey || !credentialValue) {
      return;
    }
    const status = await setConnectorCredential(connector.connector_id, {
      key: credentialKey,
      value: credentialValue,
    });
    setCredentialValue("");
    setStatuses((current) => [
      ...current.filter((existing) => existing.key !== status.key),
      status,
    ]);
    setMessage("Credential status updated.");
  }

  async function saveSettings() {
    await configureConnector(connector.connector_id, {
      settings: localPath ? { path: localPath } : {},
      credentials: {},
    });
    setMessage("Connector settings saved.");
  }

  const visibleStatuses = statuses.length > 0 ? statuses : [];
  const devOnly = visibleStatuses.some((status) => status.credential_mode === "env_var_dev");

  return (
    <section className="connector-settings-panel">
      <header>
        <h3>{connector.display_name}</h3>
        <button type="button" onClick={refreshCredentials}>
          Test connector
        </button>
      </header>
      <label>
        Credential key
        <input
          value={credentialKey}
          onChange={(event) => setCredentialKey(event.target.value)}
          placeholder={firstRequirement?.key ?? "credential key"}
        />
      </label>
      <label>
        Secret value
        <input
          type="password"
          value={credentialValue}
          onChange={(event) => setCredentialValue(event.target.value)}
        />
      </label>
      <button type="button" onClick={saveCredential}>
        Save credential
      </button>
      <label>
        Local path
        <input value={localPath} onChange={(event) => setLocalPath(event.target.value)} />
      </label>
      <button type="button" onClick={saveSettings}>
        Save settings
      </button>
      {devOnly && <p className="warning-text">Credential storage is using dev-only env vars.</p>}
      {message && <p>{message}</p>}
      <ul>
        {visibleStatuses.map((status) => (
          <li key={status.key}>
            <span>{status.key}</span>
            <strong>{status.configured ? "configured" : "unconfigured"}</strong>
          </li>
        ))}
      </ul>
    </section>
  );
}
