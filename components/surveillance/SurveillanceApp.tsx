import React, { useEffect, useMemo, useState } from 'react';
import { Activity, Bell, Dna, FlaskConical, Info, LayoutDashboard, Moon, Network, Pill } from 'lucide-react';
import { Snapshot, loadSnapshot } from './data';
import Overview from './Overview';
import Outbreaks from './Outbreaks';
import Networks from './Networks';
import { About, Alerts, GeneTransfer, Isolates, Stewardship } from './Findings';
import { Chips, FACILITY_COLOR } from './ui';

const TABS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'outbreaks', label: 'Outbreaks', icon: Activity },
  { id: 'networks', label: 'Networks', icon: Network },
  { id: 'hgt', label: 'Gene transfer', icon: Dna },
  { id: 'alerts', label: 'Alerts', icon: Bell },
  { id: 'stewardship', label: 'Stewardship', icon: Pill },
  { id: 'isolates', label: 'Isolates', icon: FlaskConical },
  { id: 'about', label: 'Provenance', icon: Info },
] as const;
type TabId = (typeof TABS)[number]['id'];

function initialTab(): TabId {
  const hash = window.location.hash.replace('#', '');
  return (TABS.find(t => t.id === hash)?.id ?? 'overview') as TabId;
}

function useTheme(): [string | null, () => void] {
  const [theme, setTheme] = useState<string | null>(() => {
    try { return localStorage.getItem('bionexus-theme'); } catch { return null; }
  });
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
  }, [theme]);
  const toggle = () => {
    const dark = theme ? theme === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    const next = dark ? 'light' : 'dark';
    setTheme(next);
    try { localStorage.setItem('bionexus-theme', next); } catch { /* storage unavailable */ }
  };
  return [theme, toggle];
}

export default function SurveillanceApp() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>(initialTab);
  const [facility, setFacility] = useState<string>('all');
  const [, toggleTheme] = useTheme();

  useEffect(() => {
    loadSnapshot().then(setSnapshot).catch(e => setError(String(e)));
  }, []);
  useEffect(() => {
    if (window.location.hash !== `#${tab}`) window.history.pushState(null, '', `#${tab}`);
  }, [tab]);
  // Follow back/forward navigation and links that change only the hash.
  useEffect(() => {
    const onHashChange = () => setTab(initialTab());
    window.addEventListener('hashchange', onHashChange);
    window.addEventListener('popstate', onHashChange);
    return () => {
      window.removeEventListener('hashchange', onHashChange);
      window.removeEventListener('popstate', onHashChange);
    };
  }, []);

  const isolates = useMemo(
    () => (snapshot ? snapshot.isolates.filter(i => facility === 'all' || i.facility === facility) : []),
    [snapshot, facility],
  );

  if (error) {
    return <div className="p-8 text-[14px]"><b>Could not load the snapshot.</b> <span className="text-ink-2">{error}</span></div>;
  }
  if (!snapshot) {
    return <div className="p-8 text-[14px] text-ink-2">Loading surveillance snapshot…</div>;
  }

  const facilityCodes = snapshot.facilities.map(f => f.code);
  const shown = facility === 'all' ? facilityCodes : [facility];

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-surface">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 pt-4">
          <div className="flex flex-wrap items-center gap-3 justify-between">
            <div className="min-w-0">
              <h1 className="text-[18px] font-semibold text-ink">BioNexus AMR · Surveillance</h1>
              <p className="text-[12px] text-ink-2">
                South African hospital network · Jul–Dec 2025 ·{' '}
                <span className="font-medium text-ink">synthetic demonstration data</span>
              </p>
            </div>
            <button onClick={toggleTheme} aria-label="Toggle light or dark theme" title="Toggle theme"
              className="w-8 h-8 grid place-items-center rounded-md border border-line text-ink-2 hover:text-ink">
              <Moon className="w-4 h-4" />
            </button>
          </div>
          <nav className="flex gap-1 mt-3 overflow-x-auto" aria-label="Sections">
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)} aria-current={tab === t.id ? 'page' : undefined}
                className={`inline-flex items-center gap-1.5 px-3 h-9 text-[13px] border-b-2 whitespace-nowrap ${
                  tab === t.id ? 'border-accent text-ink font-medium' : 'border-transparent text-ink-2 hover:text-ink'}`}>
                <t.icon className="w-4 h-4" aria-hidden /> {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-[1440px] mx-auto px-4 sm:px-6 py-4 space-y-4">
        {tab !== 'about' && tab !== 'hgt' && tab !== 'networks' && (
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-[12px] text-ink-2">Facility</span>
            <Chips
              label="Facility"
              value={facility}
              onChange={setFacility}
              options={[
                { value: 'all', label: 'All facilities', count: snapshot.isolates.length },
                ...snapshot.facilities.map(f => ({
                  value: f.code,
                  label: `${f.code} · ${f.province}`,
                  color: FACILITY_COLOR[f.code],
                  count: snapshot.isolates.filter(i => i.facility === f.code).length,
                })),
              ]}
            />
          </div>
        )}
        {tab === 'overview' && <Overview snapshot={snapshot} isolates={isolates} facilities={shown} onOpen={t => setTab(t as TabId)} />}
        {tab === 'outbreaks' && <Outbreaks snapshot={snapshot} isolates={isolates} />}
        {tab === 'networks' && <Networks snapshot={snapshot} isolates={snapshot.isolates} />}
        {tab === 'hgt' && <GeneTransfer snapshot={snapshot} />}
        {tab === 'alerts' && <Alerts snapshot={snapshot} isolates={isolates} />}
        {tab === 'stewardship' && <Stewardship snapshot={snapshot} facility={facility} />}
        {tab === 'isolates' && <Isolates isolates={isolates} />}
        {tab === 'about' && <About snapshot={snapshot} />}
      </main>
      <footer className="max-w-[1440px] mx-auto px-4 sm:px-6 py-6 text-[12px] text-muted">
        Snapshot generated {new Date(snapshot.meta.generatedAt).toLocaleString('en-ZA')} from the BioNexus backend · {snapshot.meta.guideline} · synthetic data, not for clinical use.
      </footer>
    </div>
  );
}
