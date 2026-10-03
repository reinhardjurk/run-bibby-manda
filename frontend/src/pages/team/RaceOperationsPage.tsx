import { useState } from 'react';
import { settingsApi } from '../../api/team';
import { EventSelector, PageHead } from '../../components/EventSelector';
import { Notice } from '../../components/ErrorBox';
import { useAsync } from '../../hooks/useAsync';
import { useT } from '../../i18n';
import { ComputeSection } from './operations/ComputeSection';
import { DeviceTokensSection } from './operations/DeviceTokensSection';
import { InternalResultsSection } from './operations/InternalResultsSection';
import { RegistrationListSection } from './operations/RegistrationListSection';
import { SettingsSection } from './operations/SettingsSection';
import { TimingRecordsSection } from './operations/TimingRecordsSection';
import { UserManagementSection } from './operations/UserManagementSection';
import { useTeam } from './TeamContext';

type Section = 'registrations' | 'timing' | 'compute' | 'results' | 'devices' | 'settings' | 'users';

/** Tab "Special-Admin": race operations, device tokens, settings and (admin only) user management. */
export function RaceOperationsPage() {
  const { slug, me, selectedEventId } = useTeam();
  const t = useT();
  const isAdmin = me.roles.includes('admin');
  const [section, setSection] = useState<Section>('timing');
  const settings = useAsync(() => settingsApi.get(slug), [slug]);
  const threshold = typeof settings.data?.['plausibility_threshold_seconds'] === 'string' ? settings.data['plausibility_threshold_seconds'] : '3';

  const sections: Array<{ key: Section; label: string; needsEvent: boolean; adminOnly?: boolean }> = [
    { key: 'registrations', label: 'Anmeldungen', needsEvent: true },
    { key: 'timing', label: 'Zeiterfassungen', needsEvent: true },
    { key: 'compute', label: 'Berechnung & Plausibilität', needsEvent: true },
    { key: 'results', label: 'Interne Ergebnisliste', needsEvent: true },
    { key: 'devices', label: 'Geräte-Token', needsEvent: false },
    { key: 'settings', label: 'Einstellungen', needsEvent: false },
    { key: 'users', label: 'Benutzer', needsEvent: false, adminOnly: true },
  ];
  const current = sections.find((s) => s.key === section);

  return (
    <div className="stack">
      <PageHead title="Special-Admin">
        <EventSelector />
      </PageHead>
      <div className="subtabs" role="tablist">
        {sections
          .filter((s) => !s.adminOnly || isAdmin)
          .map((s) => (
            <button key={s.key} type="button" role="tab" aria-selected={section === s.key} className={section === s.key ? 'is-active' : ''} onClick={() => setSection(s.key)}>
              {s.label}
            </button>
          ))}
      </div>
      {current?.needsEvent && !selectedEventId && <Notice kind="info">{t('team.noEvent')}</Notice>}
      <div className="card">
        {section === 'registrations' && selectedEventId && <RegistrationListSection slug={slug} eventId={selectedEventId} />}
        {section === 'timing' && selectedEventId && <TimingRecordsSection slug={slug} eventId={selectedEventId} />}
        {section === 'compute' && selectedEventId && <ComputeSection key={threshold} slug={slug} eventId={selectedEventId} defaultThreshold={threshold} />}
        {section === 'results' && selectedEventId && <InternalResultsSection slug={slug} eventId={selectedEventId} />}
        {section === 'devices' && <DeviceTokensSection slug={slug} />}
        {section === 'settings' && <SettingsSection slug={slug} isAdmin={isAdmin} onSaved={(v) => settings.setData(v)} />}
        {section === 'users' && isAdmin && <UserManagementSection slug={slug} selfEmail={me.email} />}
      </div>
    </div>
  );
}
