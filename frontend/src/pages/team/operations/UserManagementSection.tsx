import { useState } from 'react';
import { errorMessage } from '../../../api/client';
import { usersApi } from '../../../api/team';
import { ALL_ROLES, type Role, type UserOut } from '../../../api/types';
import { ErrorBox } from '../../../components/ErrorBox';
import { Field } from '../../../components/Field';
import { Loading } from '../../../components/Loading';
import { Modal } from '../../../components/Modal';
import { useAsync } from '../../../hooks/useAsync';
import { useToast } from '../../../hooks/useToast';
import { ROLE_LABELS } from '../../../utils/roles';

function RolePicker({ value, onChange }: { value: string[]; onChange: (roles: string[]) => void }) {
  return (
    <div className="chip-list" role="group" aria-label="Rollen">
      {ALL_ROLES.map((r: Role) => (
        <label key={r} className="checkbox" style={{ alignItems: 'center' }}>
          <input
            type="checkbox"
            checked={value.includes(r)}
            onChange={(e) => onChange(e.target.checked ? [...value, r] : value.filter((x) => x !== r))}
          />
          <span>{ROLE_LABELS[r]}</span>
        </label>
      ))}
    </div>
  );
}

function UserModal({
  slug,
  user,
  onClose,
  onSaved,
}: {
  slug: string;
  user: UserOut | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [email, setEmail] = useState(user?.email ?? '');
  const [name, setName] = useState(user?.display_name ?? '');
  const [password, setPassword] = useState('');
  const [roles, setRoles] = useState<string[]>(user?.roles ?? ['race_office']);
  const [active, setActive] = useState(user?.is_active ?? true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      if (user) {
        await usersApi.update(slug, user.id, {
          display_name: name,
          roles,
          is_active: active,
          ...(password ? { password } : {}),
        });
      } else {
        await usersApi.create(slug, { email: email.trim(), display_name: name, password, roles });
      }
      toast.success('Benutzer gespeichert.');
      onSaved();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      title={user ? `Benutzer bearbeiten · ${user.email}` : 'Benutzer anlegen'}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn--ghost" onClick={onClose} disabled={busy}>
            Abbrechen
          </button>
          <button type="button" className="btn btn--primary" onClick={save} disabled={busy || (!user && (!email || password.length < 10))}>
            Speichern
          </button>
        </>
      }
    >
      <div className="stack">
        {!user && (
          <Field label="E-Mail" required>
            {(id) => <input id={id} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" />}
          </Field>
        )}
        <Field label="Anzeigename">{(id) => <input id={id} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
        <Field label={user ? 'Neues Passwort (leer = unverändert)' : 'Passwort'} hint="Mindestens 10 Zeichen." required={!user}>
          {(id) => <input id={id} type="password" value={password} autoComplete="new-password" onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <div className="field">
          <span className="field__label">Rollen</span>
          <RolePicker value={roles} onChange={setRoles} />
        </div>
        {user && (
          <label className="checkbox">
            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
            <span>Konto aktiv</span>
          </label>
        )}
        <ErrorBox message={error} />
      </div>
    </Modal>
  );
}

/** Org user management (admin only). */
export function UserManagementSection({ slug, selfEmail }: { slug: string; selfEmail: string }) {
  const toast = useToast();
  const users = useAsync(() => usersApi.list(slug), [slug]);
  const [editing, setEditing] = useState<UserOut | null | 'new'>(null);

  const remove = async (u: UserOut) => {
    if (!window.confirm(`Benutzer ${u.email} löschen?`)) return;
    try {
      await usersApi.remove(slug, u.id);
      toast.success('Benutzer gelöscht.');
      users.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  return (
    <div className="stack">
      <div className="row row--end">
        <button type="button" className="btn btn--primary" onClick={() => setEditing('new')}>
          + Benutzer
        </button>
      </div>
      {users.loading && !users.data && <Loading />}
      <ErrorBox message={users.error} onRetry={users.reload} />
      {users.data && (
        <div className="table-wrap">
          <table className="table--compact">
            <thead>
              <tr>
                <th>E-Mail</th>
                <th>Name</th>
                <th>Rollen</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.data.map((u) => (
                <tr key={u.id}>
                  <td>
                    {u.email}
                    {u.email === selfEmail && <span className="badge badge--primary"> Sie</span>}
                  </td>
                  <td>{u.display_name}</td>
                  <td>
                    <div className="chip-list">
                      {u.roles.map((r) => (
                        <span key={r} className="badge">
                          {ROLE_LABELS[r as Role] ?? r}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>{u.is_active ? <span className="badge badge--ok">aktiv</span> : <span className="badge badge--danger">deaktiviert</span>}</td>
                  <td className="nowrap">
                    <button type="button" className="btn btn--small btn--ghost" onClick={() => setEditing(u)}>
                      Bearbeiten
                    </button>
                    {u.email !== selfEmail && (
                      <button type="button" className="btn btn--small btn--ghost" onClick={() => void remove(u)}>
                        Löschen
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing !== null && (
        <UserModal slug={slug} user={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={users.reload} />
      )}
    </div>
  );
}
