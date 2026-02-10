import axios from 'axios';

// Use VITE_API_BASE_URL (e.g. http://127.0.0.1:8000) if proxy fails; else uses relative /api/v1
const apiBase = (import.meta.env.VITE_API_BASE_URL as string)?.trim()
  ? `${(import.meta.env.VITE_API_BASE_URL as string).replace(/\/$/, '')}/api/v1`
  : '/api/v1';

const api = axios.create({
  baseURL: apiBase,
  timeout: 15000,
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

export default api;