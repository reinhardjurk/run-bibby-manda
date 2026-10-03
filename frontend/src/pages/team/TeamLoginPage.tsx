import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ApiError, errorMessage } from '../../api/client';
import { authApi } from '../../api/team';
import { ErrorBox } from '../../components/ErrorBox';
import { Field } from '../../components/Field';
import { LanguageSwitch } from '../../components/LanguageSwitch';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import { useT } from '../../i18n';

export function TeamLoginPage() {
  const { slug = '' } = useParams();
  const t = useT();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useDocumentTitle(t('login.title'));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await authApi.login(slug, email.trim(), password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from.startsWith(`/${slug}/team`) ? from : `/${slug}/team`, { replace: true });
    } catch (err) {
      // Generic message on 401/429 – never reveal whether the account exists.
      if (err instanceof ApiError && (err.status === 401 || err.status === 429)) {
        setError(err.status === 429 ? err.detail : t('login.failed'));
      } else {
        setError(errorMessage(err));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-page">
      <form className="card login-card stack" onSubmit={submit}>
        <div className="row row--between">
          <h1 style={{ margin: 0 }}>{t('login.title')}</h1>
          <LanguageSwitch />
        </div>
        <div className="muted small">{slug}</div>
        <Field label={t('login.email')} required>
          {(id) => (
            <input
              id={id}
              type="email"
              value={email}
              required
              autoComplete="username"
              autoFocus
              onChange={(e) => setEmail(e.target.value)}
            />
          )}
        </Field>
        <Field label={t('login.password')} required>
          {(id) => (
            <input
              id={id}
              type="password"
              value={password}
              required
              autoComplete="current-password"
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </Field>
        <ErrorBox message={error} />
        <button type="submit" className="btn btn--primary btn--block" disabled={busy}>
          {t('login.submit')}
        </button>
        <div className="small center">
          <Link to={`/${slug}/teilnahme`}>Anmeldung</Link> · <Link to={`/${slug}/ergebnisse`}>Ergebnisse</Link>
        </div>
      </form>
    </div>
  );
}
