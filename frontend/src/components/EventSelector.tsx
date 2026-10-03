import { useT } from '../i18n';
import { useTeam } from '../pages/team/TeamContext';

/** Shared event selector for team pages (selection is remembered per organization). */
export function EventSelector() {
  const { events, eventsLoading, selectedEventId, setSelectedEventId } = useTeam();
  const t = useT();
  return (
    <div className="event-selector">
      <label className="field__label" htmlFor="event-selector">
        {t('team.event')}
      </label>
      <select
        id="event-selector"
        value={selectedEventId}
        onChange={(e) => setSelectedEventId(e.target.value)}
        disabled={eventsLoading || events.length === 0}
      >
        {events.length === 0 && <option value="">{eventsLoading ? t('common.loading') : t('team.noEvents')}</option>}
        {events.map((e) => (
          <option key={e.id} value={e.id}>
            {e.name} {e.year}
            {e.registration_count ? ` (${e.registration_count})` : ''}
          </option>
        ))}
      </select>
    </div>
  );
}

export function PageHead({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="page-head">
      <h1>{title}</h1>
      <div className="row">{children}</div>
    </div>
  );
}
