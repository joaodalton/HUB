import { apiRequest } from './apiClient';

export type DatabaseProvider = 'google_drive' | 'sql';

export type DatabaseConfig = {
  provider: DatabaseProvider;
  googleDrive: {
    configured: boolean;
    credentialsFile: string;
    rootFolderId: string;
    dataFile: string;
    credentialsFound: boolean;
  };
  sql: {
    configured: boolean;
    driver: string;
    host: string;
    port: string;
    database: string;
    user: string;
    passwordConfigured: boolean;
  };
};

type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
};

export async function getDatabaseConfig(): Promise<DatabaseConfig> {
  const response = await apiRequest<ApiResponse<DatabaseConfig>>('/config/database');
  return response.data;
}

export async function saveDatabaseProvider(provider: DatabaseProvider): Promise<DatabaseConfig> {
  const response = await apiRequest<ApiResponse<DatabaseConfig>>('/config/database/provider', {
    method: 'POST',
    body: { provider }
  });

  return response.data;
}

export async function saveGoogleDriveConfig(data: {
  credentialsFile: string;
  rootFolderId: string;
  dataFile: string;
}): Promise<DatabaseConfig> {
  const response = await apiRequest<ApiResponse<DatabaseConfig>>('/config/database/google-drive', {
    method: 'POST',
    body: data
  });

  return response.data;
}

export async function saveSqlConfig(data: {
  driver: string;
  host: string;
  port: string;
  database: string;
  user: string;
  password: string;
}): Promise<DatabaseConfig> {
  const response = await apiRequest<ApiResponse<DatabaseConfig>>('/config/database/sql', {
    method: 'POST',
    body: data
  });

  return response.data;
}

export async function testDatabaseConnection(provider: DatabaseProvider): Promise<string> {
  const response = await apiRequest<ApiResponse<{ ok: boolean }>>('/config/database/test', {
    method: 'POST',
    body: { provider }
  });

  return response.message;
}
