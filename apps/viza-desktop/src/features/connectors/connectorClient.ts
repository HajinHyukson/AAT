import { VIZA_ENGINE_BASE_URL } from "../../vizaEngineClient";
import type {
  ConnectorConfigurationRecord,
  ConnectorConfigurationRequest,
  CredentialSetRequest,
  CredentialStatus,
} from "./types";

export function fetchConnectorCredentials(connectorId: string): Promise<CredentialStatus[]> {
  return connectorRequestJson<CredentialStatus[]>(
    `/viza/connectors/${encodeURIComponent(connectorId)}/credentials`,
  );
}

export function setConnectorCredential(
  connectorId: string,
  request: CredentialSetRequest,
): Promise<CredentialStatus> {
  return connectorRequestJson<CredentialStatus>(
    `/viza/connectors/${encodeURIComponent(connectorId)}/credentials`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
    },
  );
}

export function deleteConnectorCredential(
  connectorId: string,
  key: string,
): Promise<CredentialStatus[]> {
  return connectorRequestJson<CredentialStatus[]>(
    `/viza/connectors/${encodeURIComponent(connectorId)}/credentials/${encodeURIComponent(key)}`,
    { method: "DELETE" },
  );
}

export function configureConnector(
  connectorId: string,
  request: ConnectorConfigurationRequest,
): Promise<ConnectorConfigurationRecord> {
  return connectorRequestJson<ConnectorConfigurationRecord>(
    `/viza/connectors/${encodeURIComponent(connectorId)}/configure`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
    },
  );
}

async function connectorRequestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const status = window.vizaDesktop ? await window.vizaDesktop.desktopStatus() : null;
  const headers = new Headers(init?.headers);
  if (status?.engineToken) {
    headers.set("x-viza-engine-token", status.engineToken);
  }
  const response = await fetch(`${status?.engineBaseUrl || VIZA_ENGINE_BASE_URL}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`VIZA connector API ${response.status}: ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}
