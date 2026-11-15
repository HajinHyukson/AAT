export interface CredentialStatus {
  connector_id: string;
  key: string;
  configured: boolean;
  storage: string;
  credential_mode: string;
  reference: string | null;
  env_var: string | null;
  warning: string | null;
  updated_at: string | null;
}

export interface CredentialSetRequest {
  key: string;
  value: string;
}

export interface ConnectorConfigurationRequest {
  settings: Record<string, unknown>;
  credentials: Record<string, string>;
  project_id?: string | null;
}

export interface ConnectorConfigurationRecord {
  connector_id: string;
  project_id: string | null;
  settings: Record<string, unknown>;
  credential_refs: Array<{
    connector_id: string;
    key: string;
    storage: string;
    reference: string;
    created_at: string;
  }>;
  credential_status: CredentialStatus[];
  updated_at: string;
}
