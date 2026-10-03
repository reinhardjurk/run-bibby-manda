import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, errorMessage } from '../../api/client';
import { platformApi } from '../../api/platform';
import type { OrganizationOut, PlatformMe } from '../../api/types';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { ErrorBox, Notice } from '../../components/ErrorBox';
import { Field } from '../../components/Field';
import { Loading } from '../../components/Loading';
import { Modal } from '../../components/Modal';
import { useAsync } from '../../hooks/useAsync';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import { useToast } from '../../hooks/useToast';
import { bytes, formatDateTime } from '../../utils/format';
import { ROLE_LABELS } from '../../utils/roles';
import type { Role } from '../../api/types';

function LoginForm({ onLogin }: { onLogin: (me: PlatformMe) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onLogin(await platformApi.login(email.trim(), password));
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? 'Anmeldung fehlgeschlagen.' : errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="login-page">
      <form className="card login-card stack" onSubmit={submit}>
        <h1>Plattform-Verwaltung</h1>
        <Field label="E-Mail" required>{(id) => <input id={id} type="email" value={email} required autoComplete="username" onChange={(e) => setEmail(e.target.value)} />}</Field>
        <Field label="Passwort" required>
          {(id) => <input id={id} type="password" value={password} required autoComplete="current-password" onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <ErrorBox message={error} />
        <button type="submit" className="btn btn--primary btn--block" disabled={busy}>
          Anmelden
        </button>
        <div className="small center">
          <Link to="/">Bibby</Link>
        </div>
      </form>
    </div>
  );
}

function OverviewSection() {
  const ov = useAsync(() => platformApi.overview(), []);
  if (ov.loading) return <Loading />;
  if (ov.error) return <ErrorBox message={ov.error} onRetry={ov.reload} />;
  if (!ov.data) return null;
  return (
    <div className="grid grid--4">
      <div className="stat">
        <div className="stat__label">Organisationen</div>
        <div className="stat__value">{ov.data.organizations}</div>
      </div>
      <div className="stat">
        <div className="stat__label">Veranstaltungen</div>
        <div className="stat__value">{ov.data.events}</div>
      </div>
      <div className="stat">
        <div className="stat__label">Anmeldungen</div>
        <div className="stat__value">{ov.data.registrations}</div>
      </div>
      <div className="stat">
        <div className="stat__label">Speicher</div>
        <div className="stat__value">{bytes(ov.data.storage_bytes)}</div>
        <div className="stat__sub">DB gesamt {bytes(ov.data.db_size_bytes)}</div>
      </div>
    </div>
  );
}

function OrgUsersModal({ org, onClose }: { org: OrganizationOut; onClose: () => void }) {
  const toast = useToast();
  const users = useAsync(() => platformApi.orgUsers(org.id), [org.id]);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [resetFor, setResetFor] = useState<string | null>(null);
  const [resetPw, setResetPw] = useState('');
  const [busy, setBusy] = useState(false);

  const createAdmin = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await platformApi.createOrgAdmin(org.id, { email: email.trim(), password, display_name: name });
      toast.success('Org-Admin angelegt.');
      setEmail('');
      setPassword('');
      setName('');
      users.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const reset = async () => {
    if (!resetFor) return;
    setBusy(true);
    try {
      await platformApi.resetPassword(org.id, resetFor, resetPw);
      toast.success('Passwort zurückgesetzt (bestehende Sitzungen beendet).');
      setResetFor(null);
      setResetPw('');
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={`Benutzer · ${org.name}`} onClose={onClose} wide>
      <div className="stack stack--lg">
        {users.loading && <Loading />}
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
                {users.data.length === 0 && (
                  <tr>
                    <td colSpan={5} className="muted center">
                      Keine Benutzer.
                    </td>
                  </tr>
                )}
                {users.data.map((u) => (
                  <tr key={u.id}>
                    <td>{u.email}</td>
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
                    <td>
                      <button type="button" className="btn btn--small btn--ghost" onClick={() => setResetFor(u.id)}>
                        Passwort zurücksetzen
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {resetFor && (
          <div className="card card--flat inline-form">
            <Field label="Neues Passwort (min. 10 Zeichen)">
              {(id) => <input id={id} type="password" value={resetPw} autoComplete="new-password" onChange={(e) => setResetPw(e.target.value)} />}
            </Field>
            <button type="button" className="btn btn--primary" onClick={() => void reset()} disabled={busy || resetPw.length < 10}>
              Zurücksetzen
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setResetFor(null)}>
              Abbrechen
            </button>
          </div>
        )}
        <form className="inline-form" onSubmit={(e) => void createAdmin(e)}>
          <Field label="Neuer Org-Admin: E-Mail">{(id) => <input id={id} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
          <Field label="Anzeigename">{(id) => <input id={id} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
          <Field label="Passwort (min. 10)">
            {(id) => <input id={id} type="password" required minLength={10} value={password} autoComplete="new-password" onChange={(e) => setPassword(e.target.value)} />}
          </Field>
          <button type="submit" className="btn btn--primary" disabled={busy}>
            Org-Admin anlegen
          </button>
        </form>
      </div>
    </Modal>
  );
}

function OrganizationsSection({ me, onMe }: { me: PlatformMe; onMe: (m: PlatformMe) => void }) {
  const toast = useToast();
  const orgs = useAsync(() => platformApi.organizations(), []);
  const [form, setForm] = useState({ slug: '', name: '', contact_email: '', admin_email: '', admin_password: '' });
  const [busy, setBusy] = useState(false);
  const [usersFor, setUsersFor] = useState<OrganizationOut | null>(null);
  const [deleteFor, setDeleteFor] = useState<OrganizationOut | null>(null);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await platformApi.createOrganization({
        slug: form.slug.trim(),
        name: form.name.trim(),
        contact_email: form.contact_email.trim() || null,
        admin_email: form.admin_email.trim() || null,
        admin_password: form.admin_password || null,
      });
      toast.success('Organisation angelegt.');
      setForm({ slug: '', name: '', contact_email: '', admin_email: '', admin_password: '' });
      orgs.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const setStatus = async (o: OrganizationOut, status: 'active' | 'suspended') => {
    if (status === 'suspended' && !window.confirm(`Organisation „${o.name}“ sperren? Alle Team-Sitzungen werden beendet.`)) return;
    try {
      await platformApi.updateOrganization(o.id, { status });
      toast.success(status === 'suspended' ? 'Organisation gesperrt.' : 'Organisation aktiviert.');
      orgs.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const enter = async (o: OrganizationOut) => {
    try {
      const res = await platformApi.enter(o.id);
      onMe({ ...me, acting_organization: res.acting_organization });
      toast.success(`Sie handeln jetzt als „${o.name}“.`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const leave = async () => {
    try {
      await platformApi.leave();
      onMe({ ...me, acting_organization: null });
      toast.success('Organisationskontext verlassen.');
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  return (
    <div className="stack stack--lg">
      {me.acting_organization && (
        <Notice kind="warn">
          <span>
            Aktiv als Organisation <strong>{me.acting_organization.name}</strong> (wird protokolliert).
          </span>
          <span className="row">
            <Link className="btn btn--small btn--primary" to={`/${me.acting_organization.slug}/team`}>
              Team-Bereich öffnen
            </Link>
            <button type="button" className="btn btn--small" onClick={() => void leave()}>
              Verlassen
            </button>
          </span>
        </Notice>
      )}
      {orgs.loading && !orgs.data && <Loading />}
      <ErrorBox message={orgs.error} onRetry={orgs.reload} />
      {orgs.data && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Slug</th>
                <th>Name</th>
                <th>Kontakt</th>
                <th>Status</th>
                <th className="num">Events</th>
                <th className="num">Anm.</th>
                <th className="num">Benutzer</th>
                <th className="num">Speicher</th>
                <th>Angelegt</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {orgs.data.map((o) => (
                <tr key={o.id}>
                  <td className="mono">{o.slug}</td>
                  <td>{o.name}</td>
                  <td className="small">{o.contact_email ?? '–'}</td>
                  <td>{o.status === 'active' ? <span className="badge badge--ok">aktiv</span> : <span className="badge badge--danger">gesperrt</span>}</td>
                  <td className="num">{o.events}</td>
                  <td className="num">{o.registrations}</td>
                  <td className="num">{o.users}</td>
                  <td className="num">{bytes(o.storage_bytes)}</td>
                  <td className="small nowrap">{formatDateTime(o.created_at)}</td>
                  <td className="nowrap">
                    <button type="button" className="btn btn--small btn--ghost" onClick={() => setUsersFor(o)}>
                      Benutzer
                    </button>
                    <button type="button" className="btn btn--small btn--ghost" onClick={() => void enter(o)}>
                      Als Organisation handeln
                    </button>
                    {o.status === 'active' ? (
                      <button type="button" className="btn btn--small btn--ghost" onClick={() => void setStatus(o, 'suspended')}>
                        Sperren
                      </button>
                    ) : (
                      <button type="button" className="btn btn--small btn--ghost" onClick={() => void setStatus(o, 'active')}>
                        Aktivieren
                      </button>
                    )}
                    <button type="button" className="btn btn--small btn--ghost" onClick={() => setDeleteFor(o)}>
                      Löschen
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form className="card stack" onSubmit={(e) => void create(e)}>
        <h2>Organisation anlegen</h2>
        <div className="grid grid--3">
          <Field label="Slug" required hint="Kleinbuchstaben, Ziffern, Bindestriche – Teil der URL.">
            {(id) => <input id={id} value={form.slug} required pattern="^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$" minLength={2} maxLength={64} onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))} />}
          </Field>
          <Field label="Name" required>{(id) => <input id={id} value={form.name} required maxLength={200} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />}</Field>
          <Field label="Kontakt-E-Mail">{(id) => <input id={id} type="email" value={form.contact_email} onChange={(e) => setForm((f) => ({ ...f, contact_email: e.target.value }))} />}</Field>
          <Field label="Erster Admin: E-Mail (optional)">
            {(id) => <input id={id} type="email" value={form.admin_email} onChange={(e) => setForm((f) => ({ ...f, admin_email: e.target.value }))} />}
          </Field>
          <Field label="Erster Admin: Passwort (min. 10)">
            {(id) => <input id={id} type="password" value={form.admin_password} minLength={10} autoComplete="new-password" onChange={(e) => setForm((f) => ({ ...f, admin_password: e.target.value }))} />}
          </Field>
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn--primary" disabled={busy}>
            Anlegen
          </button>
        </div>
      </form>
      {usersFor && <OrgUsersModal org={usersFor} onClose={() => setUsersFor(null)} />}
      {deleteFor && (
        <ConfirmDialog
          title="Organisation löschen"
          danger
          confirmLabel="Endgültig löschen"
          requireText={deleteFor.slug}
          message={
            <>
              <strong>{deleteFor.name}</strong> mit allen Veranstaltungen, Anmeldungen, Benutzern und Dateien unwiderruflich löschen?
            </>
          }
          onConfirm={async () => {
            try {
              await platformApi.deleteOrganization(deleteFor.id, deleteFor.slug);
              toast.success('Organisation gelöscht.');
              setDeleteFor(null);
              orgs.reload();
            } catch (err) {
              toast.error(errorMessage(err));
            }
          }}
          onCancel={() => setDeleteFor(null)}
        />
      )}
    </div>
  );
}

function AuditSection() {
  const [limit, setLimit] = useState(200);
  const audit = useAsync(() => platformApi.audit(limit), [limit]);
  return (
    <div className="stack">
      <div className="row row--between">
        <h2 style={{ margin: 0 }}>Audit-Log</h2>
        <div className="row">
          <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} aria-label="Anzahl" style={{ width: 'auto' }}>
            {[50, 200, 500, 1000].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <button type="button" className="btn btn--small" onClick={audit.reload}>
            Aktualisieren
          </button>
        </div>
      </div>
      {audit.loading && !audit.data && <Loading />}
      <ErrorBox message={audit.error} onRetry={audit.reload} />
      {audit.data && (
        <div className="table-wrap">
          <table className="table--compact">
            <thead>
              <tr>
                <th>Zeit</th>
                <th>Admin</th>
                <th>Aktion</th>
                <th>Pfad</th>
                <th>Organisation</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {audit.data.map((a) => (
                <tr key={a.id}>
                  <td className="nowrap small">{formatDateTime(a.created_at)}</td>
                  <td className="small">{a.admin ?? '–'}</td>
                  <td>
                    <code>{a.action}</code>
                  </td>
                  <td className="small mono">
                    {a.method} {a.path}
                  </td>
                  <td className="small mono">{a.organization_id ?? '–'}</td>
                  <td className="small mono">{a.detail ? JSON.stringify(a.detail) : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function AdminsSection() {
  const toast = useToast();
  const admins = useAsync(() => platformApi.admins(), []);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const create = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await platformApi.createAdmin(email.trim(), password);
      toast.success('Super-Admin angelegt.');
      setEmail('');
      setPassword('');
      admins.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const remove = async (id: string, mail: string) => {
    if (!window.confirm(`Super-Admin ${mail} löschen?`)) return;
    try {
      await platformApi.deleteAdmin(id);
      toast.success('Super-Admin gelöscht.');
      admins.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };
  return (
    <div className="stack">
      <h2>Super-Admins</h2>
      {admins.loading && !admins.data && <Loading />}
      <ErrorBox message={admins.error} onRetry={admins.reload} />
      {admins.data && (
        <div className="table-wrap">
          <table className="table--compact">
            <thead>
              <tr>
                <th>E-Mail</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {admins.data.map((a) => (
                <tr key={a.id}>
                  <td>
                    {a.email} {a.is_self && <span className="badge badge--primary">Sie</span>}
                  </td>
                  <td>{a.is_active ? <span className="badge badge--ok">aktiv</span> : <span className="badge badge--danger">inaktiv</span>}</td>
                  <td>
                    {!a.is_self && (
                      <button type="button" className="btn btn--small btn--ghost" onClick={() => void remove(a.id, a.email)}>
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
      <form className="inline-form" onSubmit={(e) => void create(e)}>
        <Field label="E-Mail">{(id) => <input id={id} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
        <Field label="Passwort (min. 12)">
          {(id) => <input id={id} type="password" required minLength={12} value={password} autoComplete="new-password" onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <button type="submit" className="btn btn--primary" disabled={busy}>
          Anlegen
        </button>
      </form>
    </div>
  );
}

function SettingsSection() {
  const s = useAsync(() => platformApi.settings(), []);
  if (s.loading) return <Loading />;
  if (s.error) return <ErrorBox message={s.error} onRetry={s.reload} />;
  if (!s.data) return null;
  return (
    <div className="stack">
      <h2>Plattform-Einstellungen (nur lesend)</h2>
      <dl className="kv">
        {Object.entries(s.data).map(([k, v]) => (
          <div key={k} style={{ display: 'contents' }}>
            <dt>{k}</dt>
            <dd className="mono">{v === null ? '–' : typeof v === 'boolean' ? (v ? 'ja' : 'nein') : String(v)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

type Section = 'overview' | 'organizations' | 'audit' | 'admins' | 'settings';

/** `/platform`: super-admin console. */
export function PlatformAdminPage() {
  useDocumentTitle('Plattform');
  const [me, setMe] = useState<PlatformMe | null>(null);
  const [checking, setChecking] = useState(true);
  const [section, setSection] = useState<Section>('overview');
  const toast = useToast();

  useEffect(() => {
    platformApi
      .me()
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setChecking(false));
  }, []);

  const logout = async () => {
    try {
      await platformApi.logout();
    } finally {
      setMe(null);
      toast.info('Abgemeldet.');
    }
  };

  if (checking) return <Loading />;
  if (!me) return <LoginForm onLogin={setMe} />;

  const sections: Array<{ key: Section; label: string }> = [
    { key: 'overview', label: 'Übersicht' },
    { key: 'organizations', label: 'Organisationen' },
    { key: 'audit', label: 'Audit-Log' },
    { key: 'admins', label: 'Super-Admins' },
    { key: 'settings', label: 'Einstellungen' },
  ];

  return (
    <div className="team">
      <header className="team__header">
        <div className="team__bar">
          <div>
            <div className="team__org">Bibby · Plattform-Verwaltung</div>
            <div className="team__user">{me.email}</div>
          </div>
          <div className="row">
            <Link className="btn btn--small btn--ghost" to="/">
              Start
            </Link>
            <button type="button" className="btn btn--small" onClick={() => void logout()}>
              Abmelden
            </button>
          </div>
        </div>
        <nav className="tabs" aria-label="Bereiche">
          {sections.map((s) => (
            <a key={s.key} href={`#${s.key}`} className={section === s.key ? 'active' : ''} onClick={(e) => { e.preventDefault(); setSection(s.key); }}>
              {s.label}
            </a>
          ))}
        </nav>
      </header>
      <main className="team__main container container--wide">
        {section === 'overview' && <OverviewSection />}
        {section === 'organizations' && <OrganizationsSection me={me} onMe={setMe} />}
        {section === 'audit' && <AuditSection />}
        {section === 'admins' && <AdminsSection />}
        {section === 'settings' && <SettingsSection />}
      </main>
      <footer className="team__footer">Frontend {__BUILD__}</footer>
    </div>
  );
}
