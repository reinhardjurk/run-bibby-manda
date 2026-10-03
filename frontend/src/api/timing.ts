import { api } from './client';
import type { RecordIn, TimingContext } from './types';

const base = (slug: string) => `/api/${encodeURIComponent(slug)}/timing`;

export const timingApi = {
  context: (slug: string, deviceToken?: string | null) =>
    api<TimingContext>(`${base(slug)}/context`, { deviceToken }),
  upload: (slug: string, eventId: string, records: RecordIn[], deviceToken?: string | null) =>
    api<{ inserted: number; duplicates: number }>(`${base(slug)}/records`, {
      method: 'POST',
      body: { event_id: eventId, records },
      deviceToken,
    }),
};
