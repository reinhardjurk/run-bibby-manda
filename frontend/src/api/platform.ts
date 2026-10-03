import { api } from './client';
import type {
  AuditEntry,
  OrganizationOut,
  PlatformAdminOut,
  PlatformMe,
  PlatformOverview,
  PlatformSettings,
  UserOut,
} from './types';

const base = '/api/platform';

export const platformApi = {
  login: (email: string, password: string) =>
    api<PlatformMe>(`${base}/auth/login`, { method: 'POST', body: { email, password } }),
  logout: () => api<{ ok: boolean }>(`${base}/auth/logout`, { method: 'POST' }),
  me: () => api<PlatformMe>(`${base}/auth/me`),
  overview: () => api<PlatformOverview>(`${base}/overview`),
  organizations: () => api<OrganizationOut[]>(`${base}/organizations`),
  createOrganization: (body: {
    slug: string;
    name: string;
    contact_email?: string | null;
    admin_email?: string | null;
    admin_password?: string | null;
  }) => api<OrganizationOut>(`${base}/organizations`, { method: 'POST', body }),
  updateOrganization: (id: string, body: { name?: string; contact_email?: string; status?: 'active' | 'suspended' }) =>
    api<OrganizationOut>(`${base}/organizations/${id}`, { method: 'PATCH', body }),
  deleteOrganization: (id: string, confirmSlug: string) =>
    api<void>(`${base}/organizations/${id}`, { method: 'DELETE', query: { confirm_slug: confirmSlug } }),
  orgUsers: (id: string) => api<UserOut[]>(`${base}/organizations/${id}/users`),
  createOrgAdmin: (id: string, body: { email: string; password: string; display_name?: string }) =>
    api<{ id: string; email: string; roles: string[] }>(`${base}/organizations/${id}/admins`, {
      method: 'POST',
      body,
    }),
  resetPassword: (id: string, userId: string, password: string) =>
    api<{ ok: boolean }>(`${base}/organizations/${id}/reset-password`, {
      method: 'POST',
      body: { user_id: userId, password },
    }),
  enter: (id: string) =>
    api<{ acting_organization: { id: string; slug: string; name: string } }>(`${base}/organizations/${id}/enter`, {
      method: 'POST',
    }),
  leave: () => api<{ acting_organization: null }>(`${base}/leave`, { method: 'POST' }),
  audit: (limit = 200, organizationId?: string) =>
    api<AuditEntry[]>(`${base}/audit`, { query: { limit, organization_id: organizationId } }),
  admins: () => api<PlatformAdminOut[]>(`${base}/admins`),
  createAdmin: (email: string, password: string) =>
    api<{ id: string; email: string }>(`${base}/admins`, { method: 'POST', body: { email, password } }),
  deleteAdmin: (id: string) => api<void>(`${base}/admins/${id}`, { method: 'DELETE' }),
  settings: () => api<PlatformSettings>(`${base}/settings`),
};
