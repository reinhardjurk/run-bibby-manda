import { type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { publicApi } from '../api/public';
import type { SponsorDisplay } from '../api/types';
import { useAsync } from '../hooks/useAsync';
import { LanguageSwitch } from './LanguageSwitch';
import { SponsorBar, useSponsorBodyPadding } from './SponsorBars';

interface Props {
  slug: string;
  orgName?: string | null;
  logoUrl?: string | null;
  sponsorDisplay?: SponsorDisplay | null;
  title?: string;
  children: ReactNode;
}

/** Shared chrome for public pages: header with org name, language switch and sponsor bars. */
export function PublicLayout({ slug, orgName, logoUrl, sponsorDisplay, title, children }: Props) {
  const sponsors = useAsync(() => publicApi.sponsors(slug), [slug]);
  const list = sponsors.data ?? [];
  useSponsorBodyPadding(list.length > 0);

  return (
    <div className="public">
      <SponsorBar sponsors={list} display={sponsorDisplay} position="top" />
      <header className="public__header">
        <div className="public__brand">
          {logoUrl && <img src={logoUrl} alt="" className="public__logo" />}
          <div>
            <div className="public__org">{orgName ?? slug}</div>
            {title && <h1 className="public__title">{title}</h1>}
          </div>
        </div>
        <nav className="public__nav" aria-label="Seiten">
          <Link to={`/${slug}/teilnahme`}>Anmeldung</Link>
          <Link to={`/${slug}/ergebnisse`}>Ergebnisse</Link>
          <LanguageSwitch />
        </nav>
      </header>
      <main className="public__main container">{children}</main>
      <footer className="public__footer">
        <span>Bibby</span>
      </footer>
      <SponsorBar sponsors={list} display={sponsorDisplay} position="bottom" />
    </div>
  );
}
