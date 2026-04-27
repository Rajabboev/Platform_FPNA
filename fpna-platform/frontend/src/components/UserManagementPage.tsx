import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Check, Loader2, Pencil, Plus, Shield, UserX } from 'lucide-react';
import { usersAPI } from '../services/api';

type AppUser = {
  id: number;
  username: string;
  email: string;
  full_name: string;
  employee_id?: string;
  department?: string;
  branch?: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  roles: string[];
};

type RoleItem = {
  id: number;
  name: string;
  display_name?: string;
  description?: string;
  is_active: boolean;
};

type FormState = {
  username: string;
  email: string;
  full_name: string;
  password: string;
  employee_id: string;
  department: string;
  branch: string;
  is_active: boolean;
  roles: string[];
};

const emptyForm: FormState = {
  username: '',
  email: '',
  full_name: '',
  password: '',
  employee_id: '',
  department: '',
  branch: '',
  is_active: true,
  roles: [],
};

const FALLBACK_ROLES: RoleItem[] = [
  { id: 1, name: 'ADMIN', display_name: 'Administrator', is_active: true },
  { id: 2, name: 'CEO', display_name: 'CEO', is_active: true },
  { id: 3, name: 'CFO', display_name: 'CFO', is_active: true },
  { id: 4, name: 'FINANCE_MANAGER', display_name: 'Finance Manager', is_active: true },
  { id: 5, name: 'DEPARTMENT_MANAGER', display_name: 'Department Manager', is_active: true },
  { id: 6, name: 'BRANCH_MANAGER', display_name: 'Branch Manager', is_active: true },
  { id: 7, name: 'ANALYST', display_name: 'Analyst', is_active: true },
  { id: 8, name: 'DATA_ENTRY', display_name: 'Data Entry', is_active: true },
  { id: 9, name: 'VIEWER', display_name: 'Viewer', is_active: true },
];

const UserManagementPage: React.FC<{
  currentUserId?: number;
  currentUser?: {
    id?: number;
    username?: string;
    full_name?: string;
    email?: string;
    department?: string;
    branch?: string;
    roles?: string[];
  } | null;
  canManageUsers: boolean;
}> = ({ currentUserId, currentUser, canManageUsers }) => {
  const [users, setUsers] = useState<AppUser[]>([]);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState<AppUser | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);

  const buildCurrentUserFallback = (): AppUser[] => {
    if (!currentUser?.id) return [];
    return [
      {
        id: currentUser.id,
        username: currentUser.username || 'user',
        email: currentUser.email || '',
        full_name: currentUser.full_name || currentUser.username || 'Current User',
        employee_id: undefined,
        department: currentUser.department,
        branch: currentUser.branch,
        is_active: true,
        is_verified: true,
        created_at: new Date().toISOString(),
        roles: Array.isArray(currentUser.roles) ? currentUser.roles : [],
      },
    ];
  };

  const loadData = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const [usersRes, rolesRes] = await Promise.allSettled([usersAPI.list(), usersAPI.listRoles()]);

      const userRows = usersRes.status === 'fulfilled' ? usersRes.value : null;
      const roleRows = rolesRes.status === 'fulfilled' ? rolesRes.value : null;

      const normalizedUsers = Array.isArray(userRows)
        ? userRows
        : Array.isArray((userRows as any)?.users)
        ? (userRows as any).users
        : [];
      const normalizedRoles = Array.isArray(roleRows)
        ? roleRows
        : Array.isArray((roleRows as any)?.roles)
        ? (roleRows as any).roles
        : [];

      if (normalizedUsers.length === 0) {
        setUsers(buildCurrentUserFallback());
      } else {
        setUsers(normalizedUsers);
      }

      setRoles(normalizedRoles.length > 0 ? normalizedRoles : FALLBACK_ROLES);

      if (usersRes.status === 'rejected') {
        const msg = usersRes.reason?.response?.data?.detail || usersRes.reason?.message || 'Users endpoint unavailable';
        setError(`Users API unavailable (${msg}). Showing current user only.`);
      }
    } catch (err: any) {
      setUsers(buildCurrentUserFallback());
      setRoles(FALLBACK_ROLES);
      setError(err?.response?.data?.detail || err?.message || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (canManageUsers) {
      loadData();
    } else {
      setLoading(false);
      setError('Only CFO or Admin can manage users.');
    }
  }, [canManageUsers]);

  const filteredUsers = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return users;
    return users.filter((u) =>
      [u.username, u.full_name, u.email, ...(u.roles || [])].join(' ').toLowerCase().includes(q)
    );
  }, [users, query]);

  const openCreate = () => {
    setError(null);
    setEditingUser(null);
    setForm({ ...emptyForm, roles: roles.length ? [roles[0].name] : [] });
    setShowModal(true);
  };

  const openEdit = (u: AppUser) => {
    setError(null);
    setEditingUser(u);
    setForm({
      username: u.username,
      email: u.email || '',
      full_name: u.full_name || '',
      password: '',
      employee_id: u.employee_id || '',
      department: u.department || '',
      branch: u.branch || '',
      is_active: u.is_active,
      roles: u.roles || [],
    });
    setShowModal(true);
  };

  const toggleRole = (roleName: string) => {
    setForm((prev) => {
      const has = prev.roles.includes(roleName);
      const next = has ? prev.roles.filter((r) => r !== roleName) : [...prev.roles, roleName];
      return { ...prev, roles: next };
    });
  };

  const handleSave = async () => {
    setError(null);
    setSuccess(null);
    if (!form.full_name.trim() || !form.email.trim()) {
      setError('Full name and email are required.');
      return;
    }
    if (!editingUser && (!form.username.trim() || !form.password.trim())) {
      setError('Username and password are required for new users.');
      return;
    }
    if (form.roles.length === 0) {
      setError('Select at least one role.');
      return;
    }

    setSaving(true);
    try {
      if (editingUser) {
        await usersAPI.update(editingUser.id, {
          email: form.email.trim(),
          full_name: form.full_name.trim(),
          password: form.password.trim() || undefined,
          employee_id: form.employee_id.trim() || undefined,
          department: form.department.trim() || undefined,
          branch: form.branch.trim() || undefined,
          is_active: form.is_active,
          roles: form.roles,
        });
        setSuccess(`Updated ${form.full_name}.`);
      } else {
        await usersAPI.create({
          username: form.username.trim(),
          email: form.email.trim(),
          full_name: form.full_name.trim(),
          password: form.password.trim(),
          employee_id: form.employee_id.trim() || undefined,
          department: form.department.trim() || undefined,
          branch: form.branch.trim() || undefined,
          is_active: form.is_active,
          roles: form.roles,
        });
        setSuccess(`Created ${form.full_name}.`);
      }
      setShowModal(false);
      await loadData();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to save user');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (u: AppUser) => {
    setError(null);
    setSuccess(null);
    setSaving(true);
    try {
      await usersAPI.update(u.id, { is_active: !u.is_active });
      setSuccess(`${u.full_name} is now ${u.is_active ? 'inactive' : 'active'}.`);
      await loadData();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to update status');
    } finally {
      setSaving(false);
    }
  };

  if (!canManageUsers) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center">
            <Shield className="w-6 h-6 text-red-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
            <p className="text-gray-600">Only CFO or Admin can access this section.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
            <p className="text-gray-600">Create, edit roles, and manage active users.</p>
          </div>
          <button
            onClick={openCreate}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            <Plus className="w-4 h-4" /> Add User
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 text-red-700 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" /> {error}
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-center gap-2 text-green-700 text-sm">
          <Check className="w-4 h-4 shrink-0" /> {success}
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between gap-3">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name, username, email, role"
            className="w-full max-w-md border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />
          <button
            onClick={loadData}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
          >
            Refresh
          </button>
        </div>

        {loading ? (
          <div className="h-48 flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-primary-600 animate-spin" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-semibold text-gray-700">User</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-700">Email</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-700">Roles</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-700">Department</th>
                  <th className="text-center px-4 py-3 font-semibold text-gray-700">Status</th>
                  <th className="text-center px-4 py-3 font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredUsers.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{u.full_name}</div>
                      <div className="text-xs text-gray-500">
                        @{u.username} {u.id === currentUserId ? '• You' : ''}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{u.email}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {(u.roles || []).map((r) => (
                          <span key={r} className="px-2 py-0.5 rounded bg-primary-50 text-primary-700 text-xs font-medium">
                            {r}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{u.department || '—'}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${u.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => openEdit(u)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 border border-gray-300 rounded text-xs text-gray-700 hover:bg-gray-50"
                        >
                          <Pencil className="w-3.5 h-3.5" /> Edit
                        </button>
                        <button
                          onClick={() => handleToggleActive(u)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 border border-gray-300 rounded text-xs text-gray-700 hover:bg-gray-50"
                        >
                          <UserX className="w-3.5 h-3.5" /> {u.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredUsers.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-10 text-center text-gray-500">No users found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl">
            <div className="p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">{editingUser ? `Edit ${editingUser.full_name}` : 'Create User'}</h3>
            </div>
            <div className="p-4 space-y-4 max-h-[70vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Username {editingUser ? '' : '*'}</label>
                  <input
                    value={form.username}
                    disabled={!!editingUser}
                    onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm disabled:bg-gray-100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email *</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Full Name *</label>
                  <input
                    value={form.full_name}
                    onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Password {editingUser ? '(optional)' : '*'}
                  </label>
                  <input
                    type="password"
                    value={form.password}
                    onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Employee ID</label>
                  <input
                    value={form.employee_id}
                    onChange={(e) => setForm((f) => ({ ...f, employee_id: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
                  <input
                    value={form.department}
                    onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Branch</label>
                  <input
                    value={form.branch}
                    onChange={(e) => setForm((f) => ({ ...f, branch: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Roles *</label>
                <div className="grid grid-cols-2 gap-2">
                  {roles.map((r) => (
                    <label key={r.id} className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2 text-sm">
                      <input
                        type="checkbox"
                        checked={form.roles.includes(r.name)}
                        onChange={() => toggleRole(r.name)}
                        className="w-4 h-4"
                      />
                      <span className="font-medium text-gray-800">{r.name}</span>
                      {r.display_name && <span className="text-gray-500">({r.display_name})</span>}
                    </label>
                  ))}
                </div>
              </div>

              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                  className="w-4 h-4"
                />
                Active account
              </label>
            </div>
            <div className="p-4 border-t border-gray-200 bg-gray-50 rounded-b-xl flex justify-end gap-2">
              <button onClick={() => setShowModal(false)} className="px-4 py-2 text-gray-700 rounded-lg hover:bg-gray-100">
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                {editingUser ? 'Update User' : 'Create User'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagementPage;
