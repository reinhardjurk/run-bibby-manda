import type { ReactNode } from 'react';
import type { Role } from '../../api/types';
import { useT } from '../../i18n';
import { hasRole } from '../../utils/roles';
import { useTeam } from './TeamContext';

/** Shows the notice instead of the content when the user lacks every required role. */
export function RoleGate({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { me } = useTeam();
  const t = useT();
  if (!hasRole(me.roles, ...roles)) {
    return (
      <div className="notice notice--warn" role="alert">
        {t('team.noRole')}
      </div>
    );
  }
  return <>{children}</>;
}
