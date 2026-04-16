import axios from 'axios';

// Use VITE_API_BASE_URL (e.g. http://127.0.0.1:8001) if proxy fails; else uses relative /api/v1
const apiBase = (import.meta.env.VITE_API_BASE_URL as string)?.trim()
  ? `${(import.meta.env.VITE_API_BASE_URL as string).replace(/\/$/, '')}/api/v1`
  : '/api/v1';

/** Default HTTP timeout (ms). Long jobs override per request. */
const DEFAULT_API_TIMEOUT_MS = 120000;
/** Budget initialize: DWH ingest + baseline + all department plans can exceed 2 minutes. */
export const LONG_RUNNING_REQUEST_TIMEOUT_MS = 900000; // 15 minutes

const api = axios.create({
  baseURL: apiBase,
  timeout: DEFAULT_API_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle errors - 401 clears token; for protected routes, notify app to show login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      const isLoginEndpoint = url.includes('/auth/login') || url.includes('/auth/register');
      localStorage.removeItem('access_token');
      if (!isLoginEndpoint) {
        window.dispatchEvent(new CustomEvent('auth:unauthorized'));
      }
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: async (username: string, password: string) => {
    const response = await api.post('/auth/login-simple', { username, password });
    return response.data;
  },

  register: async (userData: any) => {
    const response = await api.post('/auth/register', userData);
    return response.data;
  },

  getCurrentUser: async () => {
    const response = await api.get('/auth/me');
    return response.data;
  }
};

// Budget API
export const budgetAPI = {
  list: async (params?: any) => {
    const response = await api.get('/budgets/', { params });
    return response.data;
  },

  get: async (id: number) => {
    const response = await api.get(`/budgets/${id}`);
    return response.data;
  },

  update: async (id: number, data: { department?: string; branch?: string; description?: string; notes?: string }) => {
    const response = await api.patch(`/budgets/${id}`, data);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/budgets/${id}`);
  },

  createLineItem: async (budgetId: number, data: Record<string, unknown>) => {
    const response = await api.post(`/budgets/${budgetId}/line-items`, data);
    return response.data;
  },

  updateLineItem: async (budgetId: number, itemId: number, data: Record<string, unknown>) => {
    const response = await api.patch(`/budgets/${budgetId}/line-items/${itemId}`, data);
    return response.data;
  },

  deleteLineItem: async (budgetId: number, itemId: number) => {
    await api.delete(`/budgets/${budgetId}/line-items/${itemId}`);
  },

  scaleSection: async (budgetId: number, groupBy: string, groupValue: string, newAmount?: number, newQuantity?: number) => {
    const response = await api.post(`/budgets/${budgetId}/line-items/scale-section`, {
      group_by: groupBy,
      group_value: groupValue,
      new_amount: newAmount,
      new_quantity: newQuantity,
    });
    return response.data;
  },

  batchUpdateLineItems: async (budgetId: number, updates: { id: number; amount?: number; quantity?: number; unit_price?: number }[]) => {
    const response = await api.post(`/budgets/${budgetId}/line-items/batch`, { updates });
    return response.data;
  },

  submit: async (id: number) => {
    const response = await api.post(`/budgets/${id}/submit`);
    return response.data;
  },

  stats: async (id: number) => {
    const response = await api.get(`/budgets/${id}/stats`);
    return response.data;
  },

  downloadTemplate: async () => {
    const response = await api.get('/budgets/template/download', {
      responseType: 'blob'
    });
    return response.data;
  },

  upload: async (file: File, uploadedBy: string) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/budgets/upload', formData, {
      params: { uploaded_by: uploadedBy },
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }
};

// Approvals API (requires auth)
export const approvalsAPI = {
  listPending: async () => {
    const response = await api.get('/approvals/pending');
    return response.data;
  },
  approve: async (budgetId: number, comment?: string) => {
    const response = await api.post(`/approvals/${budgetId}/approve`, { comment });
    return response.data;
  },
  reject: async (budgetId: number, comment?: string) => {
    const response = await api.post(`/approvals/${budgetId}/reject`, { comment });
    return response.data;
  },
  getHistory: async (budgetId: number) => {
    const response = await api.get(`/approvals/${budgetId}/history`);
    return response.data;
  },
};

// DWH Connections API
export const connectionsAPI = {
  list: async () => {
    const response = await api.get('/connections');
    return response.data;
  },
  get: async (id: number) => {
    const response = await api.get(`/connections/${id}`);
    return response.data;
  },
  create: async (data: { name: string; db_type: string; host: string; port?: number; database_name: string; username: string; password: string; schema_name?: string; use_ssl?: boolean; description?: string }) => {
    const response = await api.post('/connections', data);
    return response.data;
  },
  update: async (id: number, data: Record<string, unknown>) => {
    const response = await api.patch(`/connections/${id}`, data);
    return response.data;
  },
  delete: async (id: number) => {
    await api.delete(`/connections/${id}`);
  },
  test: async (id: number, password?: string) => {
    const response = await api.post(`/connections/${id}/test`, { password });
    return response.data;
  },
  testNew: async (data: { name: string; db_type: string; host: string; port?: number; database_name: string; username: string; password: string; schema_name?: string; use_ssl?: boolean }) => {
    const response = await api.post('/connections/test-new', data);
    return response.data;
  },
  getTables: async (connectionId: number) => {
    const response = await api.get(`/connections/${connectionId}/tables`);
    return response.data;
  },
  getColumns: async (connectionId: number, tableName: string, schemaName?: string) => {
    const params = schemaName ? { schema_name: schemaName } : {};
    const response = await api.get(`/connections/${connectionId}/tables/${encodeURIComponent(tableName)}/columns`, { params });
    return response.data;
  },
  listMappings: async (connectionId: number) => {
    const response = await api.get(`/connections/${connectionId}/mappings`);
    return response.data;
  },
  createMapping: async (connectionId: number, data: { source_schema?: string; source_table: string; target_entity: string; target_description?: string; column_mapping?: Record<string, string>; sync_enabled?: boolean }) => {
    const response = await api.post(`/connections/${connectionId}/mappings`, data);
    return response.data;
  },
  updateMapping: async (connectionId: number, mappingId: number, data: Record<string, unknown>) => {
    const response = await api.patch(`/connections/${connectionId}/mappings/${mappingId}`, data);
    return response.data;
  },
  deleteMapping: async (connectionId: number, mappingId: number) => {
    await api.delete(`/connections/${connectionId}/mappings/${mappingId}`);
  },
};

// ETL API
export const etlAPI = {
  getFpnaTables: async () => {
    const response = await api.get('/etl/fpna-tables');
    return response.data;
  },
  listJobs: async () => {
    const response = await api.get('/etl/jobs');
    return response.data;
  },
  getJob: async (id: number) => {
    const response = await api.get(`/etl/jobs/${id}`);
    return response.data;
  },
  createJob: async (data: {
    name: string;
    description?: string;
    source_type: string;
    source_connection_id?: number;
    source_schema?: string;
    source_table: string;
    target_type: string;
    target_connection_id?: number;
    target_schema?: string;
    target_table: string;
    column_mapping?: Record<string, string>;
    create_target_if_missing?: boolean;
    load_mode?: string;
  }) => {
    const response = await api.post('/etl/jobs', data);
    return response.data;
  },
  updateJob: async (id: number, data: Record<string, unknown>) => {
    const response = await api.patch(`/etl/jobs/${id}`, data);
    return response.data;
  },
  deleteJob: async (id: number) => {
    await api.delete(`/etl/jobs/${id}`);
  },
  runJob: async (id: number) => {
    const response = await api.post(`/etl/jobs/${id}/run`);
    return response.data;
  },
  getJobRuns: async (jobId: number, limit?: number) => {
    const response = await api.get(`/etl/jobs/${jobId}/runs`, { params: { limit } });
    return response.data;
  },
};

// Notifications API
export const notificationsAPI = {
  list: async (unreadOnly = false) => {
    const response = await api.get('/notifications/', { params: { unread_only: unreadOnly } });
    return response.data;
  },
  unreadCount: async () => {
    const response = await api.get('/notifications/unread-count');
    return response.data;
  },
  markAsRead: async (id: number) => {
    const response = await api.post(`/notifications/${id}/read`);
    return response.data;
  },
  markAllAsRead: async () => {
    const response = await api.post('/notifications/read-all');
    return response.data;
  },
};

// Universal Budget Upload API
export interface ColumnMapping {
  source_column: string;
  target_field: string;
}

export interface ColumnMappingSuggestion {
  source_column: string;
  suggested_target: string | null;
  confidence: number;
  required: boolean;
}

export interface PreviewResponse {
  success: boolean;
  columns: { name: string; type: string }[];
  data: Record<string, unknown>[];
  row_count: number;
  total_rows?: number;
  message?: string;
  suggested_mappings?: ColumnMappingSuggestion[];
}

export interface HeaderValues {
  fiscal_year: number;
  department?: string;
  branch?: string;
  currency?: string;
  description?: string;
}

export interface DatabaseSourceConfig {
  connection_id: number;
  schema_name?: string;
  table_name: string;
  where_clause?: string;
}

export interface APISourceConfig {
  url: string;
  method?: string;
  headers?: Record<string, string>;
  auth_type?: 'none' | 'basic' | 'bearer' | 'api_key';
  auth_credentials?: Record<string, string>;
  data_path?: string;
  params?: Record<string, unknown>;
  body?: Record<string, unknown>;
}

export interface ImportResponse {
  success: boolean;
  budget_id?: number;
  budget_code?: string;
  message: string;
  summary?: {
    total_items: number;
    total_amount: number;
    categories: string[];
  };
}

export interface TargetSchemaField {
  name: string;
  type: string;
  required: boolean;
  description: string;
  default?: unknown;
}

export const budgetUploadAPI = {
  getTargetSchema: async () => {
    const response = await api.get('/budgets/upload/target-schema');
    return response.data as {
      header_fields: TargetSchemaField[];
      line_item_fields: TargetSchemaField[];
    };
  },

  testConnection: async (sourceType: string, config: { database_config?: DatabaseSourceConfig; api_config?: APISourceConfig }) => {
    const response = await api.post('/budgets/upload/test-connection', {
      source_type: sourceType,
      ...config
    });
    return response.data as { success: boolean; message: string; details?: Record<string, unknown> };
  },

  previewFile: async (file: File, sourceType: 'excel' | 'csv', options?: { sheet_name?: string; delimiter?: string; encoding?: string; rows?: number }) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_type', sourceType);
    if (options?.sheet_name) formData.append('sheet_name', options.sheet_name);
    if (options?.delimiter) formData.append('delimiter', options.delimiter);
    if (options?.encoding) formData.append('encoding', options.encoding);
    if (options?.rows) formData.append('rows', String(options.rows));

    const response = await api.post('/budgets/upload/preview/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data as PreviewResponse;
  },

  previewDatabase: async (sourceType: 'sql_server' | 'postgresql', config: DatabaseSourceConfig, rows?: number) => {
    const response = await api.post('/budgets/upload/preview/database', {
      source_type: sourceType,
      database_config: config,
      rows: rows || 10
    });
    return response.data as PreviewResponse;
  },

  previewAPI: async (config: APISourceConfig, rows?: number) => {
    const response = await api.post('/budgets/upload/preview/api', {
      source_type: 'api',
      api_config: config,
      rows: rows || 10
    });
    return response.data as PreviewResponse;
  },

  validateMapping: async (sourceColumns: string[], mapping: ColumnMapping[], schemaType?: string) => {
    const response = await api.post('/budgets/upload/validate-mapping', {
      source_columns: sourceColumns,
      mapping,
      schema_type: schemaType || 'line_items'
    });
    return response.data as {
      valid: boolean;
      errors: string[];
      warnings: string[];
      mapped_fields: string[];
      missing_required: string[];
      coverage: { required: number; required_total: number; optional: number; optional_total: number };
    };
  },

  importFromFile: async (
    file: File,
    sourceType: 'excel' | 'csv',
    mapping: ColumnMapping[],
    headerValues: HeaderValues,
    uploadedBy?: string,
    options?: { sheet_name?: string; delimiter?: string; encoding?: string }
  ) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_type', sourceType);
    formData.append('mapping', JSON.stringify(mapping));
    formData.append('header_values', JSON.stringify(headerValues));
    formData.append('uploaded_by', uploadedBy || 'system');
    if (options?.sheet_name) formData.append('sheet_name', options.sheet_name);
    if (options?.delimiter) formData.append('delimiter', options.delimiter);
    if (options?.encoding) formData.append('encoding', options.encoding);

    const response = await api.post('/budgets/upload/import/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data as ImportResponse;
  },

  importFromDatabase: async (
    sourceType: 'sql_server' | 'postgresql',
    config: DatabaseSourceConfig,
    mapping: ColumnMapping[],
    headerValues: HeaderValues,
    uploadedBy?: string
  ) => {
    const response = await api.post('/budgets/upload/import/database', {
      source_type: sourceType,
      database_config: config,
      mapping,
      header_values: headerValues,
      uploaded_by: uploadedBy
    });
    return response.data as ImportResponse;
  },

  importFromAPI: async (
    config: APISourceConfig,
    mapping: ColumnMapping[],
    headerValues: HeaderValues,
    uploadedBy?: string
  ) => {
    const response = await api.post('/budgets/upload/import/api', {
      api_config: config,
      mapping,
      header_values: headerValues,
      uploaded_by: uploadedBy
    });
    return response.data as ImportResponse;
  }
};

// ============================================
// FP&A System APIs
// ============================================

// COA (Chart of Accounts) API
export const coaAPI = {
  // Account Classes
  listClasses: async () => {
    const response = await api.get('/coa/classes');
    return response.data;
  },
  createClass: async (data: { code: string; name_en: string; name_uz: string; class_type: string; nature: string; description?: string }) => {
    const response = await api.post('/coa/classes', data);
    return response.data;
  },

  // Account Groups
  listGroups: async (classCode?: string) => {
    const params = classCode ? { class_code: classCode } : {};
    const response = await api.get('/coa/groups', { params });
    return response.data;
  },
  createGroup: async (data: { code: string; class_code: string; name_en: string; name_uz: string; description?: string }) => {
    const response = await api.post('/coa/groups', data);
    return response.data;
  },

  // Account Categories
  listCategories: async (groupCode?: string) => {
    const params = groupCode ? { group_code: groupCode } : {};
    const response = await api.get('/coa/categories', { params });
    return response.data;
  },
  createCategory: async (data: { code: string; group_code: string; name_en: string; name_uz: string; description?: string }) => {
    const response = await api.post('/coa/categories', data);
    return response.data;
  },

  // Accounts
  listAccounts: async (params?: { category_code?: string; is_active?: boolean; limit?: number; offset?: number }) => {
    const response = await api.get('/coa/accounts', { params });
    return response.data;
  },
  createAccount: async (data: { code: string; category_code: string; name_en: string; name_uz: string; description?: string; is_budgetable?: boolean }) => {
    const response = await api.post('/coa/accounts', data);
    return response.data;
  },

  // Hierarchy
  getHierarchy: async () => {
    const response = await api.get('/coa/hierarchy');
    return response.data;
  },

  // Business Units
  listBusinessUnits: async () => {
    const response = await api.get('/coa/business-units');
    return response.data;
  },
  createBusinessUnit: async (data: { code: string; name_en: string; name_uz: string; unit_type: string; parent_id?: number; description?: string }) => {
    const response = await api.post('/coa/business-units', data);
    return response.data;
  },

  // Account Responsibilities
  listResponsibilities: async (businessUnitId?: number, accountId?: number) => {
    const params: Record<string, number> = {};
    if (businessUnitId) params.business_unit_id = businessUnitId;
    if (accountId) params.account_id = accountId;
    const response = await api.get('/coa/responsibilities', { params });
    return response.data;
  },
  createResponsibility: async (data: { account_id: number; business_unit_id: number; is_primary?: boolean; can_budget?: boolean; can_view?: boolean }) => {
    const response = await api.post('/coa/responsibilities', data);
    return response.data;
  },

  seed: async () => {
    const response = await api.post('/coa/seed');
    return response.data;
  },
};

// Currencies API
export const currenciesAPI = {
  list: async (isActive?: boolean) => {
    const params = isActive !== undefined ? { is_active: isActive } : {};
    const response = await api.get('/currencies', { params });
    return response.data;
  },
  create: async (data: { code: string; name_en: string; name_uz: string; symbol?: string; decimal_places?: number; is_base_currency?: boolean }) => {
    const response = await api.post('/currencies', data);
    return response.data;
  },
  update: async (code: string, data: { name_en?: string; name_uz?: string; symbol?: string; is_active?: boolean }) => {
    const response = await api.patch(`/currencies/${code}`, data);
    return response.data;
  },
  seed: async () => {
    const response = await api.post('/currencies/seed');
    return response.data;
  },

  // FX Rates
  listRates: async (params?: { from_currency?: string; to_currency?: string; start_date?: string; end_date?: string; limit?: number }) => {
    const response = await api.get('/currencies/rates', { params });
    return response.data;
  },
  createRate: async (data: { rate_date: string; from_currency: string; to_currency?: string; rate: number; rate_source?: string }) => {
    const response = await api.post('/currencies/rates', data);
    return response.data;
  },
  getLatestRate: async (fromCurrency: string, toCurrency?: string) => {
    const params = toCurrency ? { to_currency: toCurrency } : {};
    const response = await api.get(`/currencies/rates/latest/${fromCurrency}`, { params });
    return response.data;
  },
  getRateHistory: async (fromCurrency: string, params?: { to_currency?: string; start_date?: string; end_date?: string }) => {
    const response = await api.get(`/currencies/rates/history/${fromCurrency}`, { params });
    return response.data;
  },
  convert: async (data: { amount: number; from_currency: string; to_currency?: string; rate_date?: string; use_budget_rate?: boolean; fiscal_year?: number; month?: number }) => {
    const response = await api.post('/currencies/rates/convert', data);
    return response.data;
  },
  seedRates: async () => {
    const response = await api.post('/currencies/rates/seed');
    return response.data;
  },

  // CBU Rate Scraping
  fetchCBURates: async (targetDate?: string) => {
    const params = targetDate ? { target_date: targetDate } : {};
    const response = await api.post('/currencies/rates/fetch-cbu', null, { params });
    return response.data;
  },
  fetchCBURatesRange: async (startDate: string, endDate: string) => {
    const response = await api.post('/currencies/rates/fetch-cbu-range', null, {
      params: { start_date: startDate, end_date: endDate },
    });
    return response.data;
  },

  // Budget FX Rates
  listBudgetRates: async (params?: { fiscal_year?: number; from_currency?: string; month?: number; is_approved?: boolean }) => {
    const response = await api.get('/currencies/budget-rates', { params });
    return response.data;
  },
  createBudgetRate: async (data: { fiscal_year: number; month: number; from_currency: string; to_currency?: string; planned_rate: number; assumption_type?: string; notes?: string }) => {
    const response = await api.post('/currencies/budget-rates', data);
    return response.data;
  },
  generateBudgetRates: async (data: { fiscal_year: number; from_currency: string; to_currency?: string; base_rate: number; assumption_type?: string; growth_rate?: number; notes?: string }) => {
    const response = await api.post('/currencies/budget-rates/generate', null, { params: data });
    return response.data;
  },
  getBudgetRatePlan: async (fiscalYear: number, fromCurrency: string) => {
    const response = await api.get(`/currencies/budget-rates/plan/${fiscalYear}/${fromCurrency}`);
    return response.data;
  },
  approveBudgetRates: async (fiscalYear: number, fromCurrency: string, approvedByUserId: number) => {
    const response = await api.post('/currencies/budget-rates/approve', null, {
      params: { fiscal_year: fiscalYear, from_currency: fromCurrency, approved_by_user_id: approvedByUserId }
    });
    return response.data;
  },
};

// Drivers API
export const driversAPI = {
  list: async (params?: { driver_type?: string; is_active?: boolean; is_system?: boolean }) => {
    const response = await api.get('/drivers', { params });
    return response.data;
  },
  get: async (code: string) => {
    const response = await api.get(`/drivers/${code}`);
    return response.data;
  },
  create: async (data: {
    code: string;
    name_en: string;
    name_uz: string;
    driver_type: string;
    scope?: string;
    source_account_pattern?: string;
    target_account_pattern?: string;
    formula?: string;
    default_value?: number;
    unit?: string;
  }) => {
    const response = await api.post('/drivers', data);
    return response.data;
  },
  update: async (code: string, data: Record<string, unknown>) => {
    const response = await api.patch(`/drivers/${code}`, data);
    return response.data;
  },
  delete: async (code: string) => {
    const response = await api.delete(`/drivers/${code}`);
    return response.data;
  },
  seed: async () => {
    const response = await api.post('/drivers/seed');
    return response.data;
  },

  seedFpnaPlanningDefaults: async () => {
    const response = await api.post('/drivers/seed-fpna-planning');
    return response.data;
  },

  // Driver Values
  listValues: async (params?: { driver_code?: string; fiscal_year?: number; month?: number; account_code?: string; is_approved?: boolean }) => {
    const response = await api.get('/drivers/values', { params });
    return response.data;
  },
  createValue: async (data: { driver_id: number; fiscal_year: number; month?: number; value: number; account_code?: string; business_unit_code?: string; notes?: string }) => {
    const response = await api.post('/drivers/values', data);
    return response.data;
  },
  bulkCreateValues: async (values: Array<{ driver_id: number; fiscal_year: number; month?: number; value: number; value_type?: string; account_code?: string }>) => {
    const response = await api.post('/drivers/values/bulk', { values });
    return response.data;
  },
  getValueMatrix: async (driverCode: string, fiscalYear: number, accountCode?: string) => {
    const params = accountCode ? { account_code: accountCode } : {};
    const response = await api.get(`/drivers/values/matrix/${driverCode}`, { params: { fiscal_year: fiscalYear, ...params } });
    return response.data;
  },
  getActuals: async (driverCode: string, fiscalYear: number) => {
    const response = await api.get(`/drivers/values/actuals/${driverCode}`, { params: { fiscal_year: fiscalYear } });
    return response.data;
  },
  approveValues: async (driverCode: string, fiscalYear: number, approvedByUserId: number) => {
    const response = await api.post('/drivers/values/approve', null, {
      params: { driver_code: driverCode, fiscal_year: fiscalYear, approved_by_user_id: approvedByUserId }
    });
    return response.data;
  },

  // Golden Rules
  listGoldenRules: async (params?: { rule_type?: string; is_active?: boolean }) => {
    const response = await api.get('/drivers/golden-rules', { params });
    return response.data;
  },
  getGoldenRule: async (code: string) => {
    const response = await api.get(`/drivers/golden-rules/${code}`);
    return response.data;
  },
  createGoldenRule: async (data: {
    code: string;
    name_en: string;
    name_uz: string;
    rule_type: string;
    source_account_pattern: string;
    target_account_pattern: string;
    calculation_formula: string;
    driver_code?: string;
    priority?: number;
  }) => {
    const response = await api.post('/drivers/golden-rules', data);
    return response.data;
  },
  updateGoldenRule: async (code: string, data: Record<string, unknown>) => {
    const response = await api.patch(`/drivers/golden-rules/${code}`, data);
    return response.data;
  },
  deleteGoldenRule: async (code: string) => {
    const response = await api.delete(`/drivers/golden-rules/${code}`);
    return response.data;
  },
  seedGoldenRules: async () => {
    const response = await api.post('/drivers/golden-rules/seed');
    return response.data;
  },

  // Calculations
  runCalculations: async (data: { fiscal_year: number; months?: number[]; driver_codes?: string[]; account_codes?: string[]; apply_golden_rules?: boolean }) => {
    const response = await api.post('/drivers/calculations/run', data);
    return response.data;
  },
  listCalculationLogs: async (params?: { batch_id?: string; fiscal_year?: number; status?: string; limit?: number }) => {
    const response = await api.get('/drivers/calculations/logs', { params });
    return response.data;
  },
  validateBalanceEquation: async (fiscalYear: number, month: number) => {
    const response = await api.post('/drivers/calculations/validate', null, {
      params: { fiscal_year: fiscalYear, month }
    });
    return response.data;
  },

  // Driver-Group Assignments
  getDriversForProduct: async (productKey: string) => {
    const response = await api.get(
      `/drivers/group-assignments/by-product/${encodeURIComponent(productKey)}`
    );
    return response.data;
  },

  getDriversForGroup: async (groupId: number) => {
    const response = await api.get(`/drivers/group-assignments/by-group/${groupId}`);
    return response.data;
  },
  listGroupAssignments: async (params?: { budgeting_group_id?: number; driver_id?: number }) => {
    const response = await api.get('/drivers/group-assignments', { params });
    return response.data;
  },
  assignToGroup: async (driverId: number, budgetingGroupId: number, isDefault: boolean = false) => {
    const response = await api.post('/drivers/group-assignments', null, {
      params: { driver_id: driverId, budgeting_group_id: budgetingGroupId, is_default: isDefault }
    });
    return response.data;
  },
  bulkAssignToGroup: async (budgetingGroupId: number, driverIds: number[], defaultDriverId?: number) => {
    const response = await api.post('/drivers/group-assignments/bulk', null, {
      params: { budgeting_group_id: budgetingGroupId, driver_ids: driverIds, default_driver_id: defaultDriverId }
    });
    return response.data;
  },
  removeAssignment: async (assignmentId: number) => {
    const response = await api.delete(`/drivers/group-assignments/${assignmentId}`);
    return response.data;
  },
  setDefaultDriver: async (assignmentId: number) => {
    const response = await api.patch(`/drivers/group-assignments/${assignmentId}/set-default`);
    return response.data;
  },
};

// Templates API
export const templatesAPI = {
  list: async (params?: { template_type?: string; status?: string; fiscal_year?: number; is_active?: boolean }) => {
    const response = await api.get('/templates', { params });
    return response.data;
  },
  get: async (code: string) => {
    const response = await api.get(`/templates/${code}`);
    return response.data;
  },
  create: async (data: {
    code: string;
    name_en: string;
    name_uz: string;
    template_type?: string;
    fiscal_year?: number;
    include_baseline?: boolean;
    include_prior_year?: boolean;
    include_variance?: boolean;
    instructions?: string;
    sections?: Array<{
      code: string;
      name_en: string;
      name_uz: string;
      account_pattern?: string;
      account_codes?: string;
      is_editable?: boolean;
      is_required?: boolean;
    }>;
  }) => {
    const response = await api.post('/templates', data);
    return response.data;
  },
  update: async (code: string, data: Record<string, unknown>) => {
    const response = await api.patch(`/templates/${code}`, data);
    return response.data;
  },
  delete: async (code: string) => {
    const response = await api.delete(`/templates/${code}`);
    return response.data;
  },
  activate: async (code: string) => {
    const response = await api.post(`/templates/${code}/activate`);
    return response.data;
  },
  clone: async (code: string, newCode: string, newFiscalYear?: number) => {
    const params: Record<string, unknown> = { new_code: newCode };
    if (newFiscalYear) params.new_fiscal_year = newFiscalYear;
    const response = await api.post(`/templates/${code}/clone`, null, { params });
    return response.data;
  },
  seed: async () => {
    const response = await api.post('/templates/seed');
    return response.data;
  },

  // Sections
  listSections: async (templateCode?: string) => {
    const params = templateCode ? { template_code: templateCode } : {};
    const response = await api.get('/templates/sections', { params });
    return response.data;
  },
  createSection: async (data: {
    template_id: number;
    code: string;
    name_en: string;
    name_uz: string;
    account_pattern?: string;
    account_codes?: string;
    is_editable?: boolean;
    is_required?: boolean;
    display_order?: number;
  }) => {
    const response = await api.post('/templates/sections', data);
    return response.data;
  },
  updateSection: async (sectionId: number, data: Record<string, unknown>) => {
    const response = await api.patch(`/templates/sections/${sectionId}`, data);
    return response.data;
  },
  deleteSection: async (sectionId: number) => {
    const response = await api.delete(`/templates/sections/${sectionId}`);
    return response.data;
  },

  // Assignments
  listAssignments: async (params?: { template_code?: string; business_unit_code?: string; fiscal_year?: number; status?: string }) => {
    const response = await api.get('/templates/assignments', { params });
    return response.data;
  },
  getAssignment: async (assignmentId: number) => {
    const response = await api.get(`/templates/assignments/${assignmentId}`);
    return response.data;
  },
  createAssignment: async (data: {
    template_id: number;
    business_unit_id: number;
    fiscal_year: number;
    deadline?: string;
    reminder_date?: string;
    notes?: string;
  }) => {
    const response = await api.post('/templates/assignments', data);
    return response.data;
  },
  bulkCreateAssignments: async (assignments: Array<{ template_id: number; business_unit_id: number; fiscal_year: number; deadline?: string }>) => {
    const response = await api.post('/templates/assignments/bulk', { assignments });
    return response.data;
  },
  updateAssignment: async (assignmentId: number, data: Record<string, unknown>) => {
    const response = await api.patch(`/templates/assignments/${assignmentId}`, data);
    return response.data;
  },
  deleteAssignment: async (assignmentId: number) => {
    const response = await api.delete(`/templates/assignments/${assignmentId}`);
    return response.data;
  },
  prefillAssignment: async (assignmentId: number, baselineVersion?: number) => {
    const response = await api.post(`/templates/assignments/${assignmentId}/prefill`, { baseline_version: baselineVersion });
    return response.data;
  },
  submitAssignment: async (assignmentId: number, submittedByUserId: number) => {
    const response = await api.post(`/templates/assignments/${assignmentId}/submit`, { submitted_by_user_id: submittedByUserId });
    return response.data;
  },

  // Line Items
  listLineItems: async (params?: { assignment_id?: number; section_id?: number; account_code?: string }) => {
    const response = await api.get('/templates/line-items', { params });
    return response.data;
  },
  getLineItem: async (lineItemId: number) => {
    const response = await api.get(`/templates/line-items/${lineItemId}`);
    return response.data;
  },
  updateLineItem: async (lineItemId: number, data: {
    adjusted_jan?: number;
    adjusted_feb?: number;
    adjusted_mar?: number;
    adjusted_apr?: number;
    adjusted_may?: number;
    adjusted_jun?: number;
    adjusted_jul?: number;
    adjusted_aug?: number;
    adjusted_sep?: number;
    adjusted_oct?: number;
    adjusted_nov?: number;
    adjusted_dec?: number;
    adjustment_notes?: string;
  }) => {
    const response = await api.patch(`/templates/line-items/${lineItemId}`, data);
    return response.data;
  },
};

// Snapshots API
export const snapshotsAPI = {
  list: async (params?: { account_code?: string; start_date?: string; end_date?: string; currency?: string; limit?: number; offset?: number }) => {
    const response = await api.get('/snapshots', { params });
    return response.data;
  },
  create: async (data: { snapshot_date: string; account_code: string; currency?: string; balance: number; balance_uzs?: number; fx_rate?: number; data_source?: string }) => {
    const response = await api.post('/snapshots', data);
    return response.data;
  },
  bulkCreate: async (snapshots: Array<{ snapshot_date: string; account_code: string; currency?: string; balance: number; balance_uzs?: number; fx_rate?: number }>, dataSource?: string) => {
    const response = await api.post('/snapshots/bulk', { snapshots, data_source: dataSource });
    return response.data;
  },
  getSummary: async (params?: { start_date?: string; end_date?: string }) => {
    const response = await api.get('/snapshots/summary', { params });
    return response.data;
  },
  getTimeSeries: async (accountCode: string, params?: { start_date?: string; end_date?: string; currency?: string }) => {
    const response = await api.get(`/snapshots/timeseries/${accountCode}`, { params });
    return response.data;
  },
  listImportLogs: async (limit?: number) => {
    const response = await api.get('/snapshots/import-logs', { params: { limit } });
    return response.data;
  },
  getImportLog: async (batchId: string) => {
    const response = await api.get(`/snapshots/import-logs/${batchId}`);
    return response.data;
  },

  // Baselines
  listBaselines: async (params: { fiscal_year: number; account_code?: string; is_active?: boolean }) => {
    const response = await api.get('/snapshots/baselines', { params });
    return response.data;
  },
  getBaseline: async (accountCode: string, fiscalYear: number) => {
    const response = await api.get(`/snapshots/baselines/${accountCode}`, { params: { fiscal_year: fiscalYear } });
    return response.data;
  },
  calculateBaselines: async (data: {
    fiscal_year: number;
    method?: string;
    account_class_codes?: string[];
    account_group_codes?: string[];
    account_codes?: string[];
    apply_trend?: boolean;
    apply_seasonality?: boolean;
  }) => {
    const response = await api.post('/snapshots/baselines/calculate', data);
    return response.data;
  },
  getBaselineSummary: async (fiscalYear: number) => {
    const response = await api.get(`/snapshots/baselines/summary/${fiscalYear}`);
    return response.data;
  },
  getAggregatedBaselines: async (fiscalYear: number, level?: string) => {
    const response = await api.get(`/snapshots/baselines/aggregated/${fiscalYear}`, { params: { level } });
    return response.data;
  },
  deactivateBaselines: async (fiscalYear: number) => {
    const response = await api.delete(`/snapshots/baselines/${fiscalYear}`);
    return response.data;
  },
};

// ============================================
// DWH Integration API
// ============================================
export const dwhIntegrationAPI = {
  // DWH Data Preview
  getBalansSummary: async (connectionId: number) => {
    const response = await api.get(`/dwh/connections/${connectionId}/balans-summary`);
    return response.data;
  },

  previewBalansData: async (connectionId: number, params?: {
    snapshot_date?: string;
    account_code?: string;
    limit?: number;
  }) => {
    const response = await api.get(`/dwh/connections/${connectionId}/balans-preview`, { params });
    return response.data;
  },

  // Ingestion (DWH -> Platform)
  ingestSnapshots: async (data: {
    connection_id: number;
    source_table?: string;
    source_schema?: string;
    start_date?: string;
    end_date?: string;
    branch_code?: number;
    aggregate_branches?: boolean;
  }) => {
    const response = await api.post('/dwh/ingest/snapshots', data);
    return response.data;
  },

  ingestActuals: async (data: {
    connection_id: number;
    source_table: string;
    fiscal_year: number;
    month: number;
    column_mapping?: Record<string, string>;
  }) => {
    const response = await api.post('/dwh/ingest/actuals', data);
    return response.data;
  },

  // Baseline Generation
  generateBaselines: async (data: {
    fiscal_year: number;
    method?: string;
    apply_trend?: boolean;
    apply_seasonality?: boolean;
    account_codes?: string[];
  }) => {
    const response = await api.post('/dwh/baselines/generate', data);
    return response.data;
  },

  listBaselines: async (params?: { fiscal_year?: number; account_code?: string }) => {
    const response = await api.get('/dwh/baselines', { params });
    return response.data;
  },

  // Egress (Platform -> DWH)
  exportBudget: async (data: {
    connection_id: number;
    budget_id: number;
    target_table?: string;
    target_schema?: string;
    version_label?: string;
  }) => {
    const response = await api.post('/dwh/export/budget', data);
    return response.data;
  },

  exportScenario: async (data: {
    connection_id: number;
    budget_id: number;
    scenario_type: string;
    adjustment_factor: number;
    target_table?: string;
  }) => {
    const response = await api.post('/dwh/export/scenario', data);
    return response.data;
  },

  // Version Management
  createVersion: async (data: { budget_id: number; version_label: string }) => {
    const response = await api.post('/dwh/versions/create', data);
    return response.data;
  },

  // DWH Exploration
  getDWHTables: async (connectionId: number) => {
    const response = await api.get(`/dwh/connections/${connectionId}/tables`);
    return response.data;
  },

  getTableColumns: async (connectionId: number, tableName: string, schemaName?: string) => {
    const params = schemaName ? { schema_name: schemaName } : {};
    const response = await api.get(`/dwh/connections/${connectionId}/tables/${encodeURIComponent(tableName)}/columns`, { params });
    return response.data;
  },

  previewTableData: async (connectionId: number, tableName: string, schemaName?: string, limit?: number) => {
    const params: Record<string, unknown> = {};
    if (schemaName) params.schema_name = schemaName;
    if (limit) params.limit = limit;
    const response = await api.get(`/dwh/connections/${connectionId}/tables/${encodeURIComponent(tableName)}/preview`, { params });
    return response.data;
  },

  // COA Transformation
  getCOAHierarchy: async (accountCode: string) => {
    const response = await api.get(`/dwh/coa/hierarchy/${accountCode}`);
    return response.data;
  },

  // Alerts
  checkVariances: async (fiscalYear: number, month?: number, department?: string) => {
    const params: Record<string, unknown> = { fiscal_year: fiscalYear };
    if (month) params.month = month;
    if (department) params.department = department;
    const response = await api.post('/dwh/alerts/check', null, { params });
    return response.data;
  },

  getPendingAlerts: async (params?: { department?: string; severity?: string; limit?: number }) => {
    const response = await api.get('/dwh/alerts', { params });
    return response.data;
  },

  getAlertSummary: async (fiscalYear?: number) => {
    const params = fiscalYear ? { fiscal_year: fiscalYear } : {};
    const response = await api.get('/dwh/alerts/summary', { params });
    return response.data;
  },

  acknowledgeAlert: async (alertCode: string, notes?: string) => {
    const response = await api.post('/dwh/alerts/acknowledge', { alert_code: alertCode, notes });
    return response.data;
  },

  resolveAlert: async (alertCode: string, notes: string) => {
    const response = await api.post('/dwh/alerts/resolve', { alert_code: alertCode, notes });
    return response.data;
  },

  // Alert Thresholds
  setAlertThreshold: async (data: {
    department?: string;
    account_code?: string;
    info_threshold?: number;
    warning_threshold?: number;
    critical_threshold?: number;
    notify_department_head?: boolean;
    notify_cfo?: boolean;
  }) => {
    const response = await api.post('/dwh/alerts/thresholds', data);
    return response.data;
  },

  listAlertThresholds: async () => {
    const response = await api.get('/dwh/alerts/thresholds');
    return response.data;
  },

  // Variance Reports
  getVarianceReport: async (fiscalYear: number, month?: number, department?: string) => {
    const params: Record<string, unknown> = { fiscal_year: fiscalYear };
    if (month) params.month = month;
    if (department) params.department = department;
    const response = await api.get('/dwh/reports/variance', { params });
    return response.data;
  },

  // Import History
  getImportHistory: async (params?: { status?: string; skip?: number; limit?: number }) => {
    const response = await api.get('/dwh/imports/history', { params });
    return response.data;
  },

  listSnapshots: async (params?: { start_date?: string; end_date?: string; account_code?: string; skip?: number; limit?: number }) => {
    const response = await api.get('/dwh/snapshots', { params });
    return response.data;
  },

  // Audit Trail
  getAuditTrail: async (params?: { operation?: string; batch_id?: string; skip?: number; limit?: number }) => {
    const response = await api.get('/dwh/audit', { params });
    return response.data;
  },
};

// ============================================
// Data Upload API (Balance Snapshots & Budget Planned)
// ============================================
export const dataUploadAPI = {
  // Balance Snapshot Upload
  uploadBalanceSnapshot: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/data-upload/balance-snapshot/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },

  downloadBalanceSnapshotTemplate: async () => {
    const response = await api.get('/data-upload/balance-snapshot/template', {
      responseType: 'blob'
    });
    return response.data;
  },

  listSnapshotImports: async (skip?: number, limit?: number) => {
    const response = await api.get('/data-upload/balance-snapshot/imports', {
      params: { skip, limit }
    });
    return response.data;
  },

  deleteSnapshotImport: async (batchId: string) => {
    const response = await api.delete(`/data-upload/balance-snapshot/imports/${batchId}`);
    return response.data;
  },

  // Budget Planned Upload
  uploadBudgetPlanned: async (file: File, fiscalYear: number) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/data-upload/budget-planned/upload', formData, {
      params: { fiscal_year: fiscalYear },
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },

  downloadBudgetPlannedTemplate: async (fiscalYear?: number) => {
    const response = await api.get('/data-upload/budget-planned/template', {
      params: { fiscal_year: fiscalYear },
      responseType: 'blob'
    });
    return response.data;
  },

  listBudgetPlanned: async (params?: {
    fiscal_year?: number;
    status?: string;
    department?: string;
    account_code?: string;
    scenario?: string;
    skip?: number;
    limit?: number;
  }) => {
    const response = await api.get('/data-upload/budget-planned/list', { params });
    return response.data;
  },

  getBudgetPlanned: async (budgetId: number) => {
    const response = await api.get(`/data-upload/budget-planned/${budgetId}`);
    return response.data;
  },

  updateBudgetPlanned: async (budgetId: number, updates: Record<string, unknown>) => {
    const response = await api.patch(`/data-upload/budget-planned/${budgetId}`, updates);
    return response.data;
  },

  deleteBudgetPlanned: async (budgetId: number) => {
    const response = await api.delete(`/data-upload/budget-planned/${budgetId}`);
    return response.data;
  },

  submitBudgetPlanned: async (budgetId: number) => {
    const response = await api.post(`/data-upload/budget-planned/${budgetId}/submit`);
    return response.data;
  },

  bulkSubmitBudgetPlanned: async (budgetIds: number[]) => {
    const response = await api.post('/data-upload/budget-planned/bulk-submit', { budget_ids: budgetIds });
    return response.data;
  },

  // Upload Statistics
  getUploadStats: async (fiscalYear?: number) => {
    const response = await api.get('/data-upload/stats', { params: { fiscal_year: fiscalYear } });
    return response.data;
  },
};

// ============================================
// Planned Budget Approvals API
// ============================================
export const plannedApprovalsAPI = {
  listPending: async (params?: {
    fiscal_year?: number;
    department?: string;
    account_code?: string;
  }) => {
    const response = await api.get('/planned-approvals/pending', { params });
    return response.data;
  },

  getStats: async (fiscalYear?: number) => {
    const response = await api.get('/planned-approvals/stats', { params: { fiscal_year: fiscalYear } });
    return response.data;
  },

  approve: async (budgetId: number, comment?: string) => {
    const response = await api.post(`/planned-approvals/${budgetId}/approve`, { comment });
    return response.data;
  },

  reject: async (budgetId: number, comment?: string) => {
    const response = await api.post(`/planned-approvals/${budgetId}/reject`, { comment });
    return response.data;
  },

  submit: async (budgetId: number) => {
    const response = await api.post(`/planned-approvals/${budgetId}/submit`);
    return response.data;
  },

  bulkApprove: async (budgetIds: number[], comment?: string) => {
    const response = await api.post('/planned-approvals/bulk-approve', { budget_ids: budgetIds, comment });
    return response.data;
  },

  bulkReject: async (budgetIds: number[], comment: string) => {
    const response = await api.post('/planned-approvals/bulk-reject', { budget_ids: budgetIds, comment });
    return response.data;
  },

  bulkSubmit: async (budgetIds: number[]) => {
    const response = await api.post('/planned-approvals/bulk-submit', { budget_ids: budgetIds });
    return response.data;
  },

  getBudgetDetails: async (budgetId: number) => {
    const response = await api.get(`/planned-approvals/${budgetId}`);
    return response.data;
  },
};

// Baseline & Budget Planning API
export const baselineAPI = {
  // Step 1: Ingest from DWH
  ingest: async (data: {
    connection_id: number;
    start_year: number;
    end_year: number;
  }) => {
    const response = await api.post('/baseline/ingest', data);
    return response.data;
  },

  getBaselineData: async (params?: {
    fiscal_year?: number;
    account_code?: string;
    skip?: number;
    limit?: number;
  }) => {
    const response = await api.get('/baseline/data', { params });
    return response.data;
  },

  getBaselineDataSummary: async () => {
    const response = await api.get('/baseline/data/summary');
    return response.data;
  },

  // Step 2: Calculate Baselines
  calculate: async (data: {
    fiscal_year: number;
    method?: string;
    source_years?: number[];
  }) => {
    const response = await api.post('/baseline/calculate', data);
    return response.data;
  },

  listBaselines: async (params: {
    fiscal_year: number;
    account_code?: string;
    skip?: number;
    limit?: number;
  }) => {
    const response = await api.get('/baseline/baselines', { params });
    return response.data;
  },

  getBaselineSummary: async (fiscalYear: number) => {
    const response = await api.get('/baseline/baselines/summary', { params: { fiscal_year: fiscalYear } });
    return response.data;
  },

  // Step 3: Create Planned Budgets
  createPlanned: async (data: {
    fiscal_year: number;
    account_code: string;
    driver_adjustment_pct?: number;
    driver_code?: string;
    department?: string;
    scenario?: string;
  }) => {
    const response = await api.post('/baseline/planned', data);
    return response.data;
  },

  bulkCreatePlanned: async (data: {
    fiscal_year: number;
    driver_adjustment_pct?: number;
    driver_code?: string;
    account_codes?: string[];
    scenario?: string;
  }) => {
    const response = await api.post('/baseline/planned/bulk', data);
    return response.data;
  },

  listPlanned: async (params: {
    fiscal_year: number;
    status?: string;
    account_code?: string;
    skip?: number;
    limit?: number;
  }) => {
    const response = await api.get('/baseline/planned', { params });
    return response.data;
  },

  submitPlanned: async (budgetCode: string) => {
    const response = await api.post(`/baseline/planned/${budgetCode}/submit`);
    return response.data;
  },

  approvePlanned: async (budgetCode: string) => {
    const response = await api.post(`/baseline/planned/${budgetCode}/approve`);
    return response.data;
  },

  getPlannedSummary: async (fiscalYear: number) => {
    const response = await api.get('/baseline/planned/summary', { params: { fiscal_year: fiscalYear } });
    return response.data;
  },

  // Step 4: Export to DWH
  exportToDWH: async (data: {
    connection_id: number;
    fiscal_year: number;
    target_table?: string;
    status_filter?: string;
  }) => {
    const response = await api.post('/baseline/export', data);
    return response.data;
  },

  // Workflow Status
  getWorkflowStatus: async (fiscalYear: number) => {
    const response = await api.get(`/baseline/workflow-status/${fiscalYear}`);
    return response.data;
  },
};

// COA Dimension API
export const coaDimensionAPI = {
  // Import COA from Excel
  importFromFile: async (file: File, sheetName: string = 'CBU_2', replaceExisting: boolean = true) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/coa-dimension/import', formData, {
      params: { sheet_name: sheetName, replace_existing: replaceExisting },
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  // Import from uploads folder
  importFromUploads: async (filename: string = 'COA_Dimension.xlsx', sheetName: string = 'CBU_2') => {
    const response = await api.post('/coa-dimension/import-from-uploads', null, {
      params: { filename, sheet_name: sheetName },
    });
    return response.data;
  },

  /** Recompute fpna_product_* on all rows (after DB upgrade or taxonomy rule changes) */
  rebuildFpnaProducts: async () => {
    const response = await api.post('/coa-dimension/rebuild-fpna-products');
    return response.data;
  },

  // Get COA hierarchy for tree view
  getHierarchy: async () => {
    const response = await api.get('/coa-dimension/hierarchy');
    return response.data;
  },

  // List/search accounts
  listAccounts: async (params?: {
    query?: string;
    bs_flag?: number;
    product_key?: string;
    skip?: number;
    limit?: number;
  }) => {
    const response = await api.get('/coa-dimension/accounts', { params });
    return response.data;
  },

  // Get single account details
  getAccount: async (coaCode: string) => {
    const response = await api.get(`/coa-dimension/accounts/${coaCode}`);
    return response.data;
  },

  // List budgeting groups
  listBudgetingGroups: async (category?: string) => {
    const response = await api.get('/coa-dimension/budgeting-groups', { params: { category } });
    return response.data;
  },

  // Alias for getBudgetingGroups
  getBudgetingGroups: async (category?: string) => {
    const response = await api.get('/coa-dimension/budgeting-groups', { params: { category } });
    return response.data;
  },

  // Get accounts by budgeting group
  getAccountsByBudgetingGroup: async (groupId: number) => {
    const response = await api.get(`/coa-dimension/budgeting-groups/${groupId}/accounts`);
    return response.data;
  },

  // List BS classes
  listBSClasses: async () => {
    const response = await api.get('/coa-dimension/bs-classes');
    return response.data;
  },

  // Get COA statistics
  getStats: async () => {
    const response = await api.get('/coa-dimension/stats');
    return response.data;
  },

  /** FP&A product buckets (Loans, Deposits, P&L, etc.) derived from coa_dimension */
  getProductTaxonomy: async () => {
    const response = await api.get('/coa-dimension/product-taxonomy');
    return response.data;
  },

  getProductSummary: async () => {
    const response = await api.get('/coa-dimension/product-summary');
    return response.data;
  },

  listAccountsByProduct: async (productKey: string, params?: { skip?: number; limit?: number }) => {
    const response = await api.get(`/coa-dimension/accounts/by-product/${encodeURIComponent(productKey)}`, {
      params,
    });
    return response.data;
  },
};

// Department API
export const departmentAPI = {
  // List departments
  list: async (includeInactive: boolean = false) => {
    const response = await api.get('/departments/', { params: { include_inactive: includeInactive } });
    return response.data;
  },

  // Create department (product owner — set primary_product_key to FP&A taxonomy key when possible)
  create: async (data: {
    code: string;
    name_en: string;
    name_uz?: string;
    name_ru?: string;
    description?: string;
    parent_id?: number;
    head_user_id?: number;
    manager_user_id?: number;
    is_baseline_only?: boolean;
    display_order?: number;
    dwh_segment_value?: string;
    primary_product_key?: string | null;
  }) => {
    const response = await api.post('/departments/', data);
    return response.data;
  },

  // Get department
  get: async (deptId: number) => {
    const response = await api.get(`/departments/${deptId}`);
    return response.data;
  },

  // Update department
  update: async (deptId: number, data: Partial<{
    name_en: string;
    name_uz: string;
    name_ru: string;
    description: string;
    parent_id: number;
    head_user_id: number;
    manager_user_id: number;
    is_active: boolean;
    is_baseline_only: boolean;
    display_order: number;
    dwh_segment_value: string;
    primary_product_key: string | null;
  }>) => {
    const response = await api.patch(`/departments/${deptId}`, data);
    return response.data;
  },

  /** One department per FP&A product (excludes UNCLASSIFIED); sets access to that product only */
  seedProductOwners: async () => {
    const response = await api.post('/departments/seed-product-owners');
    return response.data;
  },

  // Delete department
  delete: async (deptId: number) => {
    const response = await api.delete(`/departments/${deptId}`);
    return response.data;
  },

  // List department users
  listUsers: async (deptId: number) => {
    const response = await api.get(`/departments/${deptId}/users`);
    return response.data;
  },

  // Assign user to department
  assignUser: async (deptId: number, userId: number, role: string = 'analyst') => {
    const response = await api.post(`/departments/${deptId}/assign`, { user_id: userId, role });
    return response.data;
  },

  // Remove user from department
  removeUser: async (deptId: number, userId: number) => {
    const response = await api.delete(`/departments/${deptId}/users/${userId}`);
    return response.data;
  },

  // Assign budgeting groups
  assignGroups: async (deptId: number, groupIds: number[]) => {
    const response = await api.post(`/departments/${deptId}/assign-groups`, { budgeting_group_ids: groupIds });
    return response.data;
  },

  /** FP&A product buckets (Loans, Deposits, …) — preferred over assignGroups for new plans */
  assignProducts: async (deptId: number, productKeys: string[]) => {
    const response = await api.post(`/departments/${deptId}/assign-products`, { product_keys: productKeys });
    return response.data;
  },

  // Get department groups
  getGroups: async (deptId: number) => {
    const response = await api.get(`/departments/${deptId}/groups`);
    return response.data;
  },
};

// Budget Planning API
export const budgetPlanningAPI = {
  // Initialize budget cycle
  initialize: async (fiscalYear: number, data: {
    connection_id: number;
    source_table?: string;
    source_years?: number[];
    calculation_method?: string;
    column_mapping?: Record<string, string>;
  }) => {
    const response = await api.post(`/budget-planning/initialize/${fiscalYear}`, data, {
      timeout: LONG_RUNNING_REQUEST_TIMEOUT_MS,
    });
    return response.data;
  },

  // Calculate baseline only (preview)
  calculateBaseline: async (fiscalYear: number, params?: {
    source_years?: number[];
    method?: string;
  }) => {
    const response = await api.post(`/budget-planning/calculate-baseline/${fiscalYear}`, null, {
      params,
      timeout: LONG_RUNNING_REQUEST_TIMEOUT_MS,
    });
    return response.data;
  },

  // Assign departments to groups
  assignDepartments: async (assignments: Array<{ department_id: number; budgeting_group_ids: number[] }>) => {
    const response = await api.post('/budget-planning/assign-departments', { assignments });
    return response.data;
  },

  // Get department template
  getDepartmentTemplate: async (deptId: number, fiscalYear: number) => {
    const response = await api.get(`/budget-planning/department/${deptId}/template`, { params: { fiscal_year: fiscalYear } });
    return response.data;
  },

  // Get P&L planning data (COA-level income statement)
  getDepartmentPLData: async (
    deptId: number,
    fiscalYear: number,
    scenario?: string,
    opts?: { seasonality_reference_year?: number }
  ) => {
    const params: Record<string, any> = { fiscal_year: fiscalYear };
    if (scenario) params.scenario = scenario;
    if (opts?.seasonality_reference_year != null) {
      params.seasonality_reference_year = opts.seasonality_reference_year;
    }
    const response = await api.get(`/budget-planning/department/${deptId}/pl-data`, { params });
    return response.data;
  },

  /** Historic YoY from BaselineData → suggested PL_GROWTH / p_l_flag deltas (e.g. FY2026 → 2025 vs 2024) */
  getPlDriverProposals: async (
    fiscalYear: number,
    opts?: { year_old?: number; year_new?: number; segment?: string }
  ) => {
    const params: Record<string, any> = { fiscal_year: fiscalYear };
    if (opts?.year_old != null) params.year_old = opts.year_old;
    if (opts?.year_new != null) params.year_new = opts.year_new;
    if (opts?.segment) params.segment = opts.segment;
    const response = await api.get('/budget-planning/pl-driver-proposals', { params });
    return response.data;
  },

  /** CFO: set baseline-reference P&L group adjusted = baseline × (1 + historic YoY%) per FP&A product */
  applyPlHistoricYoy: async (fiscalYear: number) => {
    const response = await api.post(`/budget-planning/apply-pl-historic-yoy/${fiscalYear}`);
    return response.data;
  },

  // Get group details (drill-down)
  getGroupDetails: async (deptId: number, groupId: number) => {
    const response = await api.get(`/budget-planning/department/${deptId}/group/${groupId}/details`);
    return response.data;
  },

  // Update group adjustment
  updateGroupAdjustment: async (deptId: number, groupId: number, data: {
    driver_code?: string;
    driver_name?: string;
    driver_rate?: number;
    monthly_adjustments?: Record<string, number>;
    notes?: string;
  }) => {
    const response = await api.patch(`/budget-planning/department/${deptId}/group/${groupId}`, data);
    return response.data;
  },

  // Submit plan
  submitPlan: async (deptId: number, fiscalYear: number) => {
    const response = await api.post(`/budget-planning/department/${deptId}/submit`, null, { params: { fiscal_year: fiscalYear } });
    return response.data;
  },

  // Approve plan (dept head)
  approvePlanDept: async (deptId: number, fiscalYear: number, comment?: string) => {
    const response = await api.post(`/budget-planning/department/${deptId}/approve`, { comment }, { params: { fiscal_year: fiscalYear } });
    return response.data;
  },

  // CFO approve all
  cfoApproveAll: async (fiscalYear: number, comment?: string) => {
    const response = await api.post(`/budget-planning/cfo-approve/${fiscalYear}`, { comment });
    return response.data;
  },

  // Reject plan
  rejectPlan: async (deptId: number, fiscalYear: number, reason: string, level: string = 'dept_head') => {
    const response = await api.post(`/budget-planning/department/${deptId}/reject`, { reason }, { params: { fiscal_year: fiscalYear, level } });
    return response.data;
  },

  // Export to DWH
  exportToDWH: async (fiscalYear: number, connectionId: number, targetTable?: string) => {
    const response = await api.post(`/budget-planning/export/${fiscalYear}`, {
      connection_id: connectionId,
      target_table: targetTable || 'fpna_budget_final',
    });
    return response.data;
  },

  // Get workflow status
  getWorkflowStatus: async (fiscalYear: number) => {
    const response = await api.get(`/budget-planning/status/${fiscalYear}`);
    return response.data;
  },

  // List plans
  listPlans: async (fiscalYear: number, statusFilter?: string) => {
    const response = await api.get(`/budget-planning/plans/${fiscalYear}`, { params: { status_filter: statusFilter } });
    return response.data;
  },

  // Get plan detail
  getPlanDetail: async (planId: number) => {
    const response = await api.get(`/budget-planning/plan/${planId}`);
    return response.data;
  },

  // Get plan approvals
  getPlanApprovals: async (planId: number) => {
    const response = await api.get(`/budget-planning/plan/${planId}/approvals`);
    return response.data;
  },

  // CFO Locking
  lockGroup: async (groupId: number, fiscalYear: number, reason?: string) => {
    const response = await api.post(`/budget-planning/lock-group/${groupId}`, null, {
      params: { fiscal_year: fiscalYear, reason }
    });
    return response.data;
  },

  unlockGroup: async (groupId: number, fiscalYear: number) => {
    const response = await api.post(`/budget-planning/unlock-group/${groupId}`, null, {
      params: { fiscal_year: fiscalYear }
    });
    return response.data;
  },

  getLockedGroups: async (fiscalYear: number) => {
    const response = await api.get(`/budget-planning/locked-groups/${fiscalYear}`);
    return response.data;
  },

  getAllBudgetingGroups: async (fiscalYear: number) => {
    const response = await api.get(`/budget-planning/all-groups/${fiscalYear}`);
    return response.data;
  },

  getDriverConfig: async (fiscalYear: number) => {
    const response = await api.get(`/budget-planning/driver-config/${fiscalYear}`);
    return response.data;
  },

  saveDriverConfig: async (fiscalYear: number, configs: Array<{
    budgeting_group_id?: number | null;
    fpna_product_key?: string | null;
    driver_id: number | null;
    rate: number | null;
    monthly_rates?: Record<string, number>;
  }>) => {
    const response = await api.post(`/budget-planning/driver-config/${fiscalYear}`, { configs });
    return response.data;
  },

  applyDriversBulk: async (fiscalYear: number) => {
    const response = await api.post(`/budget-planning/apply-drivers-bulk/${fiscalYear}`);
    return response.data;
  },

  // DWH Source preview
  previewSource: async (connectionId: number, tableName: string, limit: number = 50) => {
    const response = await api.post('/budget-planning/preview-source', {
      connection_id: connectionId,
      table_name: tableName,
      limit,
    });
    return response.data;
  },

  // Compare baselines (all 5 methods)
  compareBaselines: async (fiscalYear: number, sourceYears?: number[]) => {
    const response = await api.post(`/budget-planning/compare-baselines/${fiscalYear}`, null, {
      params: { source_years: sourceYears },
    });
    return response.data;
  },

  // Department assignments v2 (optional: only FP&A product owner departments)
  getDepartmentAssignments: async (fiscalYear: number, productOwnersOnly: boolean = false) => {
    const response = await api.get(`/budget-planning/department-assignments/${fiscalYear}`, {
      params: { product_owners_only: productOwnersOnly },
    });
    return response.data;
  },

  assignDepartmentsV2: async (fiscalYear: number, assignments: Array<{
    department_id: number;
    budgeting_group_ids: number[];
    can_edit: boolean;
    can_submit: boolean;
  }>, notify: boolean = true) => {
    const response = await api.post('/budget-planning/assign-departments-v2', {
      fiscal_year: fiscalYear,
      assignments,
      notify,
    });
    return response.data;
  },

  // CEO Consolidated
  getConsolidatedPlan: async (fiscalYear: number) => {
    const response = await api.get(`/budget-planning/consolidated/${fiscalYear}`);
    return response.data;
  },

  ceoApprove: async (fiscalYear: number, comment?: string) => {
    const response = await api.post(`/budget-planning/ceo-approve/${fiscalYear}`, { comment });
    return response.data;
  },

  ceoReject: async (fiscalYear: number, reason: string) => {
    const response = await api.post(`/budget-planning/ceo-reject/${fiscalYear}`, { reason });
    return response.data;
  },

  // Scenarios
  listScenarios: async (fiscalYear: number) => {
    const response = await api.get(`/budget-planning/scenarios/${fiscalYear}`);
    return response.data;
  },

  createScenario: async (fiscalYear: number, data: { name: string; description?: string; scenario_type?: string }) => {
    const response = await api.post(`/budget-planning/scenarios/${fiscalYear}`, data);
    return response.data;
  },

  updateScenarioAdjustments: async (scenarioId: number, adjustments: Array<{
    budgeting_group_id: number;
    adjustment_type: string;
    value: number;
    notes?: string;
  }>) => {
    const response = await api.put(`/budget-planning/scenarios/${scenarioId}/adjustments`, { adjustments });
    return response.data;
  },

  approveScenario: async (scenarioId: number) => {
    const response = await api.post(`/budget-planning/scenarios/${scenarioId}/approve`);
    return response.data;
  },

  compareScenario: async (scenarioId: number) => {
    const response = await api.get(`/budget-planning/scenarios/${scenarioId}/compare`);
    return response.data;
  },

  // Fact Table (account-level approved budget)
  getFactTable: async (fiscalYear: number, params?: {
    department_code?: string;
    budgeting_group_id?: number;
    month?: number;
    page?: number;
    page_size?: number;
  }) => {
    const response = await api.get(`/budget-planning/fact-table/${fiscalYear}`, { params });
    return response.data;
  },

  getFactTableSummary: async (fiscalYear: number) => {
    const response = await api.get(`/budget-planning/fact-table/${fiscalYear}/summary`);
    return response.data;
  },

  resetFiscalYear: async (fiscalYear: number) => {
    const response = await api.delete(`/budget-planning/reset/${fiscalYear}`);
    return response.data;
  },
};

// ========== Analysis API ==========
export const analysisAPI = {
  getYoYDelta: async (fiscalYear: number) => {
    const response = await api.get(`/analysis/yoy-delta/${fiscalYear}`);
    return response.data;
  },

  getPlanDelta: async (fiscalYear: number) => {
    const response = await api.get(`/analysis/plan-delta/${fiscalYear}`);
    return response.data;
  },

  getMonthlyTrend: async (fiscalYear: number) => {
    const response = await api.get(`/analysis/monthly-trend/${fiscalYear}`);
    return response.data;
  },

  getDashboardKPIs: async (fiscalYear: number) => {
    const response = await api.get(`/analysis/dashboard-kpis/${fiscalYear}`);
    return response.data;
  },
};

// Reporting API
export const reportingAPI = {
  // Power BI workspace config (stored in backend for team-wide config)
  getPowerBIConfig: async () => {
    const response = await api.get('/reporting/powerbi/config');
    return response.data;
  },

  savePowerBIConfig: async (config: { workspace_url?: string; tenant_id?: string; client_id?: string }) => {
    const response = await api.post('/reporting/powerbi/config', config);
    return response.data;
  },

  // Report list from Power BI workspace (requires API auth configured)
  listWorkspaceReports: async () => {
    const response = await api.get('/reporting/powerbi/reports');
    return response.data;
  },

  // Excel ad-hoc exports
  exportBudgetPlan: async (fiscalYear: number, format: 'xlsx' | 'csv' = 'xlsx') => {
    const response = await api.get(`/reporting/export/budget-plan`, {
      params: { fiscal_year: fiscalYear, format },
      responseType: 'blob',
    });
    return response.data;
  },

  exportVarianceReport: async (fiscalYear: number, period?: string) => {
    const response = await api.get('/reporting/export/variance', {
      params: { fiscal_year: fiscalYear, period },
      responseType: 'blob',
    });
    return response.data;
  },

  exportAdHoc: async (params: {
    dataset: string;
    group_by: string;
    period: string;
    fiscal_year: number;
    filters?: Record<string, string>;
  }) => {
    const response = await api.post('/reporting/export/adhoc', params, { responseType: 'blob' });
    return response.data;
  },

  // Paginated report generation (PDF/XLSX)
  generateReport: async (reportId: string, params?: Record<string, unknown>) => {
    const response = await api.post(`/reporting/paginated/${reportId}/generate`, params || {}, { responseType: 'blob' });
    return response.data;
  },

  listGeneratedReports: async () => {
    const response = await api.get('/reporting/paginated/history');
    return response.data;
  },
};

// ── AI Assistant API ───────────────────────────────────────────────────────

export const aiAPI = {
  /** Non-streaming scenario calculation + narrative */
  runScenario: async (fiscalYear: number, adjustments: { label: string; department?: string; change_type: string; value: number }[]) => {
    const response = await api.post('/ai/scenario', { fiscal_year: fiscalYear, adjustments });
    return response.data;
  },

  /** Plan health check (verdict + alerts) */
  healthCheck: async (fiscalYear: number, alertThresholdPct = 10) => {
    const response = await api.post('/ai/health-check', { fiscal_year: fiscalYear, alert_threshold_pct: alertThresholdPct });
    return response.data;
  },

  /** List saved AI projections */
  listProjections: async (fiscalYear: number) => {
    const response = await api.get('/ai/projections', { params: { fiscal_year: fiscalYear } });
    return response.data;
  },

  /** Get detailed projection */
  getProjection: async (scenarioName: string, fiscalYear: number) => {
    const response = await api.get(`/ai/projections/${scenarioName}`, { params: { fiscal_year: fiscalYear } });
    return response.data;
  },

  /** Delete a projection */
  deleteProjection: async (scenarioName: string, fiscalYear: number) => {
    const response = await api.delete(`/ai/projections/${scenarioName}`, { params: { fiscal_year: fiscalYear } });
    return response.data;
  },
};

// ── Real Excel Export API ──────────────────────────────────────────────────

/** Downloads a blob and triggers browser file-save dialog */
function _downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const excelExportAPI = {
  budgetPlan: async (fiscalYear: number) => {
    const response = await api.get('/reports/budget-plan/export', {
      params: { fiscal_year: fiscalYear },
      responseType: 'blob',
    });
    _downloadBlob(response.data, `budget_plan_FY${fiscalYear}.xlsx`);
  },

  variance: async (fiscalYear: number) => {
    const response = await api.get('/reports/variance/export', {
      params: { fiscal_year: fiscalYear },
      responseType: 'blob',
    });
    _downloadBlob(response.data, `variance_FY${fiscalYear}.xlsx`);
  },

  baselineComparison: async (fiscalYear: number) => {
    const response = await api.get('/reports/baseline/export', {
      params: { fiscal_year: fiscalYear },
      responseType: 'blob',
    });
    _downloadBlob(response.data, `baseline_comparison_FY${fiscalYear}.xlsx`);
  },

  adhoc: async (params: { fiscal_year: number; dataset: string; group_by: string; period: string }) => {
    const response = await api.post('/reports/adhoc/export', params, { responseType: 'blob' });
    _downloadBlob(response.data, `adhoc_${params.dataset.replace(/ /g, '_')}_FY${params.fiscal_year}.xlsx`);
  },
};

export default api;