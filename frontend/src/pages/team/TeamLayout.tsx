import { useCallback, useEffect, useMemo, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { platformApi } from '../../api/platform';
import { authApi, eventsApi } from '../../api/team';
import type { EventOut, MeResponse, Role, VersionInfo } from '../../api/types';
import { ErrorBox } from '../../components/ErrorBox';
import { LanguageSwitch } from '../../components/LanguageSwitch';
import { Loading } from '../../components/Loading';
import { useLocalStorage } from '../../hooks/useLocalStorage';
import { useT, type TranslationKey } from '../../i18n';
import { hasRole } from '../../utils/roles';
import { TeamContext, type TeamContextValue } from './TeamContext';

export interface TabDef {
  path: string;
  labelKey: TranslationKey;
  roles: Role[];
}

/** Tab order is fixed by the product spec; admin sees everything. */
export const TEAM_TABS: TabDef[] = [
  { path: 'admin', labelKey: 'team.tab.admin', roles: ['race_office'] },
  { path: 'ergebnisdruck', labelKey: 'team.tab.certificates', roles: ['race_office'] },
  { path: 'zeiterfassung', labelKey: 'team.tab.timing', roles: ['timing', 'race_office'] },
  { path: 'special-admin', labelKey: 'team.tab.operations', roles: ['race_office'] },
  { path: 'sponsoren', labelKey: 'team.tab.sponsors', roles: ['sponsor_management'] },
  { path: 'events', labelKey: 'team.tab.events', roles: ['race_office'] },
  { path: 'statistiken', labelKey: 'team.tab.stats', roles: ['viewer', 'race_office'] },
  { path: 'sepa', labelKey: 'team.tab.sepa', roles: ['sepa'] },
];

export function TeamLayout() {
  const { slug = '' } = useParams();
  const t = useT();
  const navigate = useNavigate();
  const location = useLocation();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [meError, setMeError] = useState<string | null>(null);
  const [events, setEvents] = useState<EventOut[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsTick, setEventsTick] = useState(0);
  const [version, setVersion] = useState<VersionInfo | null>(null);
  const [selectedEventId, setSelectedEventId] = useLocalStorage<string>(`bibby_event_${slug}`, '');

  // Session check → redirect to login on 401.
  useEffect(() => {
    let active = true;
    authApi
      .me(slug)
      .then((m) => active && setMe(m))
      .catch((err: unknown) => {
        if (!active) return;
        if (err instanceof ApiError && err.status === 401) {
          navigate(`/${slug}/team/login`, { replace: true, state: { from: location.pathname } });
        } else {
          setMeError(err instanceof ApiError ? err.detail : 'Fehler beim Laden.');
        }
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  useEffect(() => {
    if (!me) return;
    let active = true;
    setEventsLoading(true);
    eventsApi
      .list(slug)
      .then((list) => {
        if (!active) return;
        setEvents(list);
        setEventsLoading(false);
      })
      .catch(() => active && setEventsLoading(false));
    return () => {
      active = false;
    };
  }, [me, slug, eventsTick]);

  useEffect(() => {
    authApi
      .version()
      .then(setVersion)
      .catch(() => setVersion(null));
  }, []);

  // Keep the selection valid; default to the newest event.
  useEffect(() => {
    if (events.length === 0) return;
    if (!events.some((e) => e.id === selectedEventId)) setSelectedEventId(events[0]?.id ?? '');
  }, [events, selectedEventId, setSelectedEventId]);

  const logout = useCallback(async () => {
    if (me?.is_platform_admin) {
      try {
        await platformApi.leave();
      } finally {
        navigate('/platform', { replace: true });
      }
      return;
    }
    try {
      await authApi.logout(slug);
    } finally {
      navigate(`/${slug}/team/login`, { replace: true });
    }
  }, [slug, navigate, me]);

  const reloadEvents = useCallback(() => setEventsTick((n) => n + 1), []);

  const value = useMemo<TeamContextValue | null>(
    () =>
      me
        ? {
            slug,
            me,
            events,
            eventsLoading,
            reloadEvents,
            selectedEventId,
            setSelectedEventId,
            selectedEvent: events.find((e) => e.id === selectedEventId) ?? null,
            logout,
          }
        : null,
    [slug, me, events, eventsLoading, reloadEvents, selectedEventId, setSelectedEventId, logout],
  );

  if (meError) {
    return (
      <div className="container" style={{ paddingTop: '2rem' }}>
        <ErrorBox message={meError} />
      </div>
    );
  }
  if (!value || !me) {
    return (
      <div className="container">
        <Loading />
      </div>
    );
  }

  const visibleTabs = TEAM_TABS.filter((tab) => hasRole(me.roles, ...tab.roles));
  const wide = location.pathname.endsWith('/events');

  return (
    <TeamContext.Provider value={value}>
      <div className="team">
        <header className="team__header">
          {me.is_platform_admin && <div className="super-admin-banner">{t('team.superAdmin')}</div>}
          <div className="team__bar">
            <div>
              <div className="team__org">{me.organization.name}</div>
              <div className="team__user">
                {me.display_name || me.email} · {me.roles.join(', ')}
              </div>
            </div>
            <div className="row">
              <LanguageSwitch />
              <button type="button" className="btn btn--small" onClick={() => void logout()}>
                {t('team.logout')}
              </button>
            </div>
          </div>
          <nav className="tabs" aria-label="Bereiche">
            {visibleTabs.map((tab) => (
              <NavLink key={tab.path} to={tab.path} className={({ isActive }) => (isActive ? 'active' : '')}>
                {t(tab.labelKey)}
              </NavLink>
            ))}
          </nav>
        </header>
        <main className={`team__main container${wide ? ' container--wide' : ''}`}>
          <Outlet />
        </main>
        <footer className="team__footer">
          Frontend {__BUILD__} · Backend {version?.backend ?? '–'} · DB {version?.db_schema ?? '–'}
        </footer>
      </div>
    </TeamContext.Provider>
  );
}
