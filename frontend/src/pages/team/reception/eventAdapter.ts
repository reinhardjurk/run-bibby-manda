import type { EventOut, PublicEvent } from '../../../api/types';

/** Maps a team EventOut to the public event shape used by the shared registration form. */
export function toPublicEvent(e: EventOut): PublicEvent {
  return {
    id: e.id,
    name: e.name,
    year: e.year,
    event_date: e.event_date,
    registration_deadline: e.registration_deadline,
    registration_open: true,
    tshirt_options: e.tshirt_options
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean),
    tshirt_included: e.tshirt_included,
    youth_cutoff_date: e.youth_cutoff_date,
    photos_available: false,
    competitions: [...e.competitions]
      .sort((a, b) => a.sort_order - b.sort_order || a.title_de.localeCompare(b.title_de))
      .map((c) => ({
        id: c.id,
        title_de: c.title_de,
        title_en: c.title_en || c.title_de,
        start_time: c.start_time,
        price_adult_cents: c.price_adult_cents,
        price_youth_cents: c.price_youth_cents,
        relay_scoring: c.relay_scoring,
      })),
  };
}
