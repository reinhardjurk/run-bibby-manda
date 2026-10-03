import type { Role } from '../api/types';

/** Admin implicitly has every role (mirrors Principal.has_role in the backend). */
export function hasRole(roles: string[] | undefined, ...required: Role[]): boolean {
  if (!roles) return false;
  if (roles.includes('admin')) return true;
  return required.some((r) => roles.includes(r));
}

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Admin',
  race_office: 'Wettkampfbüro',
  timing: 'Zeitnahme',
  sponsor_management: 'Sponsoren',
  sepa: 'SEPA',
  viewer: 'Betrachter',
};
