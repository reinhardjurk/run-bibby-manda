import { api, apiBlob } from './client';
import type {
  CompetitionIn,
  CompetitionOut,
  ComputeResult,
  DeviceTokenIssued,
  DeviceTokenOut,
  DisplaySettings,
  EventImportBody,
  EventIn,
  EventOut,
  EventStats,
  EventTemplate,
  EventUpdate,
  InternalResults,
  MeResponse,
  OfficeRegistrationCreate,
  PagedRegistrations,
  PlausibilityResult,
  RecordOut,
  RegistrationAdminUpdate,
  RegistrationCreated,
  RegistrationDetail,
  ResultsOverview,
  SepaSummary,
  SettingsUpdate,
  SettingsView,
  SponsorOut,
  UserOut,
  VersionInfo,
} from './types';

const root = (slug: string) => `/api/${encodeURIComponent(slug)}`;
const team = (slug: string) => `${root(slug)}/team`;

export const authApi = {
  login: (slug: string, email: string, password: string) =>
    api<MeResponse>(`${root(slug)}/auth/login`, { method: 'POST', body: { email, password } }),
  logout: (slug: string) => api<{ ok: boolean }>(`${root(slug)}/auth/logout`, { method: 'POST' }),
  me: (slug: string) => api<MeResponse>(`${root(slug)}/auth/me`),
  version: () => api<VersionInfo>('/version'),
};

export const eventsApi = {
  list: (slug: string) => api<EventOut[]>(`${team(slug)}/events`),
  get: (slug: string, id: string) => api<EventOut>(`${team(slug)}/events/${id}`),
  create: (slug: string, body: EventIn) => api<EventOut>(`${team(slug)}/events`, { method: 'POST', body }),
  update: (slug: string, id: string, body: EventUpdate) =>
    api<EventOut>(`${team(slug)}/events/${id}`, { method: 'PATCH', body }),
  remove: (slug: string, id: string) => api<void>(`${team(slug)}/events/${id}`, { method: 'DELETE' }),
  addCompetition: (slug: string, eventId: string, body: CompetitionIn) =>
    api<CompetitionOut>(`${team(slug)}/events/${eventId}/competitions`, { method: 'POST', body }),
  updateCompetition: (slug: string, eventId: string, compId: string, body: CompetitionIn) =>
    api<CompetitionOut>(`${team(slug)}/events/${eventId}/competitions/${compId}`, { method: 'PATCH', body }),
  removeCompetition: (slug: string, eventId: string, compId: string) =>
    api<void>(`${team(slug)}/events/${eventId}/competitions/${compId}`, { method: 'DELETE' }),
  template: (slug: string, eventId: string) => api<EventTemplate>(`${team(slug)}/events/${eventId}/template`),
  importTemplate: (slug: string, body: EventImportBody) =>
    api<EventOut>(`${team(slug)}/events/import`, { method: 'POST', body }),
  uploadBackground: (slug: string, eventId: string, kind: 'certificate' | 'bib', file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api<{ ok: boolean }>(`${team(slug)}/events/${eventId}/background/${kind}`, { method: 'POST', form });
  },
  backgroundUrl: (slug: string, eventId: string, kind: 'certificate' | 'bib') =>
    `${team(slug)}/events/${eventId}/background/${kind}`,
};

export const registrationsApi = {
  list: (
    slug: string,
    params: { event_id: string; q?: string; status?: string; page?: number; page_size?: number },
  ) => api<PagedRegistrations>(`${team(slug)}/registrations`, { query: params }),
  get: (slug: string, id: string) => api<RegistrationDetail>(`${team(slug)}/registrations/${id}`),
  byBib: (slug: string, eventId: string, bib: number) =>
    api<RegistrationDetail>(`${team(slug)}/registrations/by-bib/${bib}`, { query: { event_id: eventId } }),
  create: (slug: string, body: OfficeRegistrationCreate) =>
    api<RegistrationCreated>(`${team(slug)}/registrations`, { method: 'POST', body }),
  update: (slug: string, id: string, body: RegistrationAdminUpdate) =>
    api<RegistrationDetail>(`${team(slug)}/registrations/${id}`, { method: 'PATCH', body }),
  remove: (slug: string, id: string) => api<void>(`${team(slug)}/registrations/${id}`, { method: 'DELETE' }),
  markPaid: (slug: string, id: string) =>
    api<RegistrationDetail>(`${team(slug)}/registrations/${id}/mark-paid`, { method: 'POST' }),
  merge: (slug: string, source: string, target: string) =>
    api<{ moved: number }>(`${team(slug)}/registrations/merge-participants`, {
      method: 'POST',
      body: { source_participant_id: source, target_participant_id: target },
    }),
  bibPdf: (slug: string, id: string) => apiBlob(`${team(slug)}/registrations/${id}/bib.pdf`),
};

export const timingTeamApi = {
  devices: (slug: string) => api<DeviceTokenOut[]>(`${team(slug)}/timing/devices`),
  createDevice: (slug: string, label: string, offset: number) =>
    api<DeviceTokenIssued>(`${team(slug)}/timing/devices`, {
      method: 'POST',
      body: { label, time_offset_seconds: offset },
    }),
  reissueDevice: (slug: string, id: string) =>
    api<DeviceTokenIssued>(`${team(slug)}/timing/devices/${id}/reissue`, { method: 'POST' }),
  updateDevice: (
    slug: string,
    id: string,
    body: { is_active?: boolean; time_offset_seconds?: number; label?: string },
  ) => api<DeviceTokenOut>(`${team(slug)}/timing/devices/${id}`, { method: 'PATCH', body }),
  removeDevice: (slug: string, id: string) => api<void>(`${team(slug)}/timing/devices/${id}`, { method: 'DELETE' }),
  records: (slug: string, eventId: string, bib?: number | null, limit?: number) =>
    api<RecordOut[]>(`${team(slug)}/timing/records`, {
      query: { event_id: eventId, bib_number: bib ?? undefined, limit },
    }),
  addManual: (slug: string, eventId: string, bib: number, absoluteTime: string) =>
    api<RecordOut>(`${team(slug)}/timing/records/manual`, {
      method: 'POST',
      body: { event_id: eventId, bib_number: bib, absolute_time: absoluteTime },
    }),
  updateRecord: (
    slug: string,
    id: string,
    body: { bib_number?: number; absolute_time?: string; status?: string },
  ) => api<RecordOut>(`${team(slug)}/timing/records/${id}`, { method: 'PATCH', body }),
  removeRecord: (slug: string, id: string) => api<void>(`${team(slug)}/timing/records/${id}`, { method: 'DELETE' }),
  compute: (slug: string, eventId: string) =>
    api<ComputeResult>(`${team(slug)}/timing/compute`, { method: 'POST', query: { event_id: eventId } }),
  plausibility: (slug: string, eventId: string, threshold?: number | null) =>
    api<PlausibilityResult>(`${team(slug)}/timing/plausibility`, {
      query: { event_id: eventId, threshold_seconds: threshold ?? undefined },
    }),
  internalResults: (slug: string, eventId: string) =>
    api<InternalResults>(`${team(slug)}/timing/internal-results`, { query: { event_id: eventId } }),
};

export const resultsApi = {
  overview: (slug: string, eventId: string) =>
    api<ResultsOverview>(`${team(slug)}/results/overview`, { query: { event_id: eventId } }),
  certificate: (slug: string, eventId: string, bib: number, printBackground: boolean) =>
    apiBlob(`${team(slug)}/results/certificate.pdf`, {
      query: { event_id: eventId, bib_number: bib, print_background: printBackground },
    }),
  certificates: (
    slug: string,
    params: { event_id: string; competition_id: string; age_class?: string; gender?: string; print_background: boolean },
  ) => apiBlob(`${team(slug)}/results/certificates.pdf`, { query: params }),
};

export const sponsorsApi = {
  list: (slug: string) => api<SponsorOut[]>(`${team(slug)}/sponsors`),
  upload: (slug: string, file: File, tier: number, name: string, url: string) => {
    const form = new FormData();
    form.append('file', file);
    form.append('tier', String(tier));
    form.append('name', name);
    form.append('url', url);
    return api<SponsorOut>(`${team(slug)}/sponsors`, { method: 'POST', form });
  },
  update: (slug: string, id: string, body: { tier?: number; name?: string; url?: string }) =>
    api<SponsorOut>(`${team(slug)}/sponsors/${id}`, { method: 'PATCH', body }),
  remove: (slug: string, id: string) => api<void>(`${team(slug)}/sponsors/${id}`, { method: 'DELETE' }),
  display: (slug: string) => api<DisplaySettings>(`${team(slug)}/sponsors/display`),
  setDisplay: (
    slug: string,
    body: {
      sponsor_mode?: string;
      sponsor_marquee_seconds?: number;
      sponsor_bucket_url?: string;
      sponsor_tier_weights?: string;
    },
  ) => api<DisplaySettings>(`${team(slug)}/sponsors/display`, { method: 'PUT', body }),
};

export const statsApi = {
  get: (slug: string, eventId: string) => api<EventStats>(`${team(slug)}/stats`, { query: { event_id: eventId } }),
};

export const sepaApi = {
  summary: (slug: string, eventId: string) =>
    api<SepaSummary>(`${team(slug)}/sepa/summary`, { query: { event_id: eventId } }),
  exportCsv: (slug: string, eventId: string, includeExported: boolean) =>
    apiBlob(`${team(slug)}/sepa/export.csv`, {
      method: 'POST',
      query: { event_id: eventId, include_exported: includeExported },
    }),
};

export const settingsApi = {
  get: (slug: string) => api<SettingsView>(`${team(slug)}/settings`),
  update: (slug: string, body: SettingsUpdate) => api<SettingsView>(`${team(slug)}/settings`, { method: 'PUT', body }),
  clearSecret: (slug: string, key: string) =>
    api<SettingsView>(`${team(slug)}/settings/secret/${key}`, { method: 'DELETE' }),
  uploadLogo: (slug: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api<{ ok: boolean }>(`${team(slug)}/settings/logo`, { method: 'POST', form });
  },
  deleteLogo: (slug: string) => api<void>(`${team(slug)}/settings/logo`, { method: 'DELETE' }),
  logoUrl: (slug: string) => `/api/public/${encodeURIComponent(slug)}/assets/logo`,
};

export const usersApi = {
  list: (slug: string) => api<UserOut[]>(`${team(slug)}/users`),
  create: (slug: string, body: { email: string; display_name: string; password: string; roles: string[] }) =>
    api<UserOut>(`${team(slug)}/users`, { method: 'POST', body }),
  update: (
    slug: string,
    id: string,
    body: { display_name?: string; password?: string; roles?: string[]; is_active?: boolean },
  ) => api<UserOut>(`${team(slug)}/users/${id}`, { method: 'PATCH', body }),
  remove: (slug: string, id: string) => api<void>(`${team(slug)}/users/${id}`, { method: 'DELETE' }),
};
