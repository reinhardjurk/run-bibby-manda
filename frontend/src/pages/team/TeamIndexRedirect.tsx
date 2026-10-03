import { Navigate } from 'react-router-dom';
import { useT } from '../../i18n';
import { hasRole } from '../../utils/roles';
import { TEAM_TABS } from './TeamLayout';
import { useTeam } from './TeamContext';

/** `/:slug/team` → first tab the user may use. */
export function TeamIndexRedirect() {
  const { me } = useTeam();
  const t = useT();
  const first = TEAM_TABS.find((tab) => hasRole(me.roles, ...tab.roles));
  if (!first) return <div className="notice notice--warn">{t('team.noRole')}</div>;
  return <Navigate to={first.path} replace />;
}
