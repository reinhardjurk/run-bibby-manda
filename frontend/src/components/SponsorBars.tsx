import { useEffect, useMemo, useState } from 'react';
import type { PublicSponsor, SponsorDisplay } from '../api/types';
import { useT } from '../i18n';

interface Props {
  sponsors: PublicSponsor[];
  display: SponsorDisplay | null | undefined;
  position: 'top' | 'bottom';
}

/** "5,3,2,1,1" → seconds per tier 1..5 (defaults when missing/invalid). */
export function parseTierWeights(raw: string | null | undefined): number[] {
  const fallback = [5, 3, 2, 1, 1];
  if (!raw) return fallback;
  const parts = raw.split(',').map((p) => Number(p.trim()));
  if (parts.length !== 5 || parts.some((n) => !Number.isFinite(n) || n <= 0)) return fallback;
  return parts;
}

function Logo({ s }: { s: PublicSponsor }) {
  const img = <img src={s.image_url} alt={s.name ?? 'Sponsor'} loading="lazy" />;
  return s.url ? (
    <a href={s.url} target="_blank" rel="noopener noreferrer sponsored" title={s.name ?? undefined}>
      {img}
    </a>
  ) : (
    <span title={s.name ?? undefined}>{img}</span>
  );
}

function Rotation({ sponsors, weights }: { sponsors: PublicSponsor[]; weights: number[] }) {
  const [index, setIndex] = useState(0);
  const current = sponsors[index % sponsors.length];

  useEffect(() => {
    if (sponsors.length <= 1) return;
    const tier = Math.min(Math.max(current?.tier ?? 3, 1), 5);
    const seconds = weights[tier - 1] ?? 1;
    const id = window.setTimeout(() => setIndex((i) => (i + 1) % sponsors.length), seconds * 1000);
    return () => window.clearTimeout(id);
  }, [index, sponsors.length, current, weights]);

  if (!current) return null;
  return (
    <div className="sponsor-bar__rotation" key={index}>
      <Logo s={current} />
    </div>
  );
}

function Marquee({ sponsors, seconds }: { sponsors: PublicSponsor[]; seconds: number }) {
  // Duplicate the list so the track can loop seamlessly (translateX -50%).
  const track = [...sponsors, ...sponsors];
  return (
    <div className="sponsor-bar__marquee">
      <div className="sponsor-bar__track" style={{ animationDuration: `${Math.max(5, Math.min(300, seconds))}s` }}>
        {track.map((s, i) => (
          <div className="sponsor-bar__item" key={`${s.image_url}-${i}`}>
            <Logo s={s} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function SponsorBar({ sponsors, display, position }: Props) {
  const t = useT();
  const weights = useMemo(() => parseTierWeights(display?.tier_weights), [display?.tier_weights]);
  const sorted = useMemo(() => [...sponsors].sort((a, b) => a.tier - b.tier), [sponsors]);
  if (sorted.length === 0) return null;
  const mode = display?.mode === 'marquee' ? 'marquee' : 'rotation';
  return (
    <aside className={`sponsor-bar sponsor-bar--${position}`} aria-label={t('sponsors.title')}>
      {mode === 'marquee' ? (
        <Marquee sponsors={sorted} seconds={display?.marquee_seconds ?? 30} />
      ) : (
        <Rotation sponsors={sorted} weights={weights} />
      )}
    </aside>
  );
}

/** Adds body classes so the page content gets padding for the fixed mobile bars. */
export function useSponsorBodyPadding(active: boolean) {
  useEffect(() => {
    if (!active) return;
    document.body.classList.add('has-sponsor-bars');
    return () => document.body.classList.remove('has-sponsor-bars');
  }, [active]);
}
