import { api, apiBlob } from './client';
import type {
  ManageUpdate,
  ManageView,
  PublicInfo,
  PublicResults,
  PublicSponsor,
  RegistrationCreate,
  RegistrationCreated,
} from './types';

const base = (slug: string) => `/api/public/${encodeURIComponent(slug)}`;

export const publicApi = {
  info: (slug: string) => api<PublicInfo>(`${base(slug)}/info`),
  teamNames: (slug: string, q: string, signal?: AbortSignal) =>
    api<string[]>(`${base(slug)}/team-names`, { query: { q }, signal }),
  register: (slug: string, body: RegistrationCreate) =>
    api<RegistrationCreated>(`${base(slug)}/registrations`, { method: 'POST', body }),
  manage: (slug: string, token: string) => api<ManageView>(`${base(slug)}/manage`, { query: { token } }),
  manageUpdate: (slug: string, token: string, body: ManageUpdate) =>
    api<ManageView>(`${base(slug)}/manage`, { method: 'PATCH', query: { token }, body }),
  manageCheckout: (slug: string, token: string) =>
    api<{ checkout_url: string | null; status: string }>(`${base(slug)}/manage/checkout`, {
      method: 'POST',
      query: { token },
    }),
  manageBibPdf: (slug: string, token: string) => apiBlob(`${base(slug)}/manage/bib.pdf`, { query: { token } }),
  manageCertificatePdf: (slug: string, token: string) =>
    apiBlob(`${base(slug)}/manage/certificate.pdf`, { query: { token } }),
  results: (slug: string, eventId?: string | null) =>
    api<PublicResults>(`${base(slug)}/results`, { query: { event_id: eventId ?? undefined } }),
  sponsors: (slug: string) => api<PublicSponsor[]>(`${base(slug)}/sponsors`),
};
