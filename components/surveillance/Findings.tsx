import React, { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { Alert, Isolate, Snapshot, formatDate, formatMic, shortSpecies, wardLabel } from './data';
import { Card, Chips, FacilityDot, SeverityBadge, SirBadge, StatTile, Table, Tag } from './ui';

// --------------------------------------------------------------------------- gene transfer

export function GeneTransfer({ snapshot }: { snapshot: Snapshot }) {
  const [level, setLevel] = useState<'species' | 'genus'>('genus');
  const signals = snapshot.hgt[level];
  return (
    <Card
      title="Horizontal gene transfer signals"
      subtitle="The same resistance-gene variant (one CARD accession) in different taxa points at a shared plasmid or transposon rather than one spreading clone. A shared replicon strengthens the signal."
      actions={<Chips<'species' | 'genus'> label="Taxonomic level" value={level} onChange={setLevel} options={[{ value: 'genus', label: 'Across genera' }, { value: 'species', label: 'Across species' }]} />}
    >
      <Table head={['Gene', 'Taxa', 'Shared carrier', 'Isolates', 'Wards', 'Seen']}>
        {signals.map(s => (
          <tr key={s.gene_aro_id} className="border-b border-line last:border-0 align-top">
            <td className="px-1 py-2"><div className="font-mono text-[12px]">{s.gene}</div><div className="text-[11px] text-muted">{s.gene_aro_id}</div></td>
            <td className="px-1 py-2"><div className="flex flex-wrap gap-1">{s.taxa.map(t => <Tag key={t}><i>{t}</i></Tag>)}</div></td>
            <td className="px-1 py-2">{s.replicons.length ? s.replicons.map(r => <div key={r}>{r.replace(':', ' ')}</div>) : <span className="text-muted">not resolved</span>}</td>
            <td className="px-1 py-2">{s.isolate_count}</td>
            <td className="px-1 py-2 text-[12px] text-ink-2 max-w-[18rem]">{s.wards.map(wardLabel).join(', ')}</td>
            <td className="px-1 py-2 whitespace-nowrap text-ink-2">{formatDate(s.first_collected)} – {formatDate(s.last_collected)}</td>
          </tr>
        ))}
      </Table>
      <p className="text-[12px] text-muted mt-3">
        Interpretation: <span className="font-mono">blaCTX-M-15</span> is expected across Enterobacterales, so its signal is background. The planted
        NDM-5 scenario (S3) appears as one gene in three genera on a shared IncX3 plasmid.
      </p>
    </Card>
  );
}

// --------------------------------------------------------------------------- alerts

export function Alerts({ snapshot, isolates }: { snapshot: Snapshot; isolates: Isolate[] }) {
  const visible = useMemo(() => new Set(isolates.map(i => i.id)), [isolates]);
  const alerts = snapshot.alerts.filter(a => visible.has(a.isolate_id));
  const [rule, setRule] = useState<string>('all');
  const [limit, setLimit] = useState(40);
  const counts = (r: string) => alerts.filter(a => a.rule === r).length;
  const shown = rule === 'all' ? alerts : alerts.filter(a => a.rule === rule);
  const rules = Object.entries(snapshot.alertRules);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {rules.map(([key, r]) => (
          <button key={key} onClick={() => setRule(rule === key ? 'all' : key)} className={`text-left rounded-xl ${rule === key ? 'ring-2 ring-accent' : ''}`}>
            <StatTile label={r.title} value={counts(key)} note={<SeverityBadge severity={r.severity} />} />
          </button>
        ))}
      </div>
      <Card
        title="Clinical alerts"
        subtitle="Rules evaluated by the backend over the graph. Treatment is recorded per admission, so a drug applies to all of that admission's cultures."
        actions={
          <Chips label="Rule" value={rule} onChange={setRule}
            options={[{ value: 'all', label: 'All', count: alerts.length }, ...rules.map(([key, r]) => ({ value: key, label: r.title.split(' (')[0], count: counts(key) }))]} />
        }
      >
        <AlertTable alerts={shown.slice(0, limit)} />
        <ShowMore shown={Math.min(limit, shown.length)} total={shown.length} onMore={() => setLimit(l => l + 40)} />
      </Card>
    </div>
  );
}

function AlertTable({ alerts }: { alerts: Alert[] }) {
  return (
    <Table head={['Severity', 'Alert', 'Detail', 'Organism', 'Ward', 'Collected', 'Isolate']}>
      {alerts.map((a, n) => (
        <tr key={`${a.rule}-${a.isolate_id}-${n}`} className="border-b border-line last:border-0 align-top">
          <td className="px-1 py-1.5"><SeverityBadge severity={a.severity} /></td>
          <td className="px-1 py-1.5 whitespace-nowrap">{a.title}</td>
          <td className="px-1 py-1.5 text-ink-2">{a.detail}</td>
          <td className="px-1 py-1.5 whitespace-nowrap"><i>{shortSpecies(a.species)}</i></td>
          <td className="px-1 py-1.5 whitespace-nowrap"><span className="inline-flex items-center gap-1.5"><FacilityDot code={a.facility} />{wardLabel(a.ward)}</span></td>
          <td className="px-1 py-1.5 whitespace-nowrap">{formatDate(a.collected)}</td>
          <td className="px-1 py-1.5 font-mono text-[12px]">{a.isolate_id}</td>
        </tr>
      ))}
    </Table>
  );
}

function ShowMore({ shown, total, onMore }: { shown: number; total: number; onMore: () => void }) {
  if (shown >= total) return null;
  return (
    <div className="flex items-center gap-3 mt-3 text-[12px] text-ink-2">
      Showing {shown} of {total}
      <button onClick={onMore} className="h-7 px-3 rounded-md border border-line text-ink hover:bg-hover">Show more</button>
    </div>
  );
}

// --------------------------------------------------------------------------- isolates

export function Isolates({ isolates }: { isolates: Isolate[] }) {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const [limit, setLimit] = useState(50);
  const q = query.trim().toLowerCase();
  const matches = useMemo(
    () =>
      isolates.filter(i =>
        !q || [i.id, i.patient, i.species, i.ward, i.st ?? '', ...i.labels, ...i.genes.map(g => g.symbol)].some(v => v.toLowerCase().includes(q)),
      ),
    [isolates, q],
  );
  const current = isolates.find(i => i.id === selected) ?? null;
  return (
    <div className="grid xl:grid-cols-[1fr_420px] gap-4 items-start">
      <Card
        title="Isolate explorer"
        subtitle={`${matches.length} of ${isolates.length} isolates. Search by isolate, patient, organism, ward, flag (CRE, MRSA…), ST or gene.`}
        actions={
          <label className="relative block">
            <Search className="w-4 h-4 text-muted absolute left-2.5 top-2" aria-hidden />
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="e.g. blaOXA-181, ST307, CRAB"
              className="h-8 w-64 max-w-full pl-8 pr-3 rounded-md border border-line bg-raised text-[13px] text-ink placeholder:text-muted outline-none focus:border-accent" />
          </label>
        }
      >
        <Table dense head={['Isolate', 'Collected', 'Organism', 'Flags', 'Ward', 'ST', 'Genes']}>
          {matches.slice(0, limit).map(i => (
            <tr key={i.id} onClick={() => setSelected(i.id)}
              className={`border-b border-line last:border-0 cursor-pointer ${selected === i.id ? 'bg-hover' : 'hover:bg-hover'}`}>
              <td className="px-1 py-1.5 font-mono text-[12px]">{i.id}</td>
              <td className="px-1 py-1.5 whitespace-nowrap">{formatDate(i.collected)}</td>
              <td className="px-1 py-1.5 whitespace-nowrap"><i>{shortSpecies(i.species)}</i></td>
              <td className="px-1 py-1.5">{i.labels.map(l => <Tag key={l}>{l}</Tag>)}</td>
              <td className="px-1 py-1.5 whitespace-nowrap"><span className="inline-flex items-center gap-1.5"><FacilityDot code={i.facility} />{wardLabel(i.ward)}</span></td>
              <td className="px-1 py-1.5">{i.st ? `ST${i.st.split(':ST')[1]}` : <span className="text-muted">{i.genotype === 'not_sequenced' ? '—' : 'n/a'}</span>}</td>
              <td className="px-1 py-1.5 font-mono text-[11px] text-ink-2">{i.genes.map(g => g.symbol).join(', ')}</td>
            </tr>
          ))}
        </Table>
        <ShowMore shown={Math.min(limit, matches.length)} total={matches.length} onMore={() => setLimit(l => l + 50)} />
      </Card>
      <div className="xl:sticky xl:top-4">
        {current ? <IsolateDetail isolate={current} /> : <Card title="Antibiogram"><p className="text-[13px] text-ink-2">Select an isolate to see its susceptibility results, genotype and clinical context.</p></Card>}
      </div>
    </div>
  );
}

function IsolateDetail({ isolate: i }: { isolate: Isolate }) {
  return (
    <Card
      title={<span className="font-mono">{i.id}</span>}
      subtitle={<span><i>{i.species}</i> · {i.specimen} · {formatDate(i.collected)}</span>}
    >
      <dl className="grid grid-cols-[7rem_1fr] gap-y-1 text-[13px] mb-4">
        <dt className="text-ink-2">Patient</dt><dd>{i.patient} · {i.sex ?? '?'} · {i.age === null ? 'age unknown' : i.age < 1 ? `${Math.round(i.age * 365.25)} days` : `${i.age} years`}</dd>
        <dt className="text-ink-2">Ward</dt><dd className="inline-flex items-center gap-1.5"><FacilityDot code={i.facility} />{wardLabel(i.ward)}</dd>
        <dt className="text-ink-2">Treatment</dt><dd>{i.treatments.join(', ') || '—'}</dd>
        <dt className="text-ink-2">Flags</dt><dd className="flex gap-1 flex-wrap">{i.labels.length ? i.labels.map(l => <Tag key={l}>{l}</Tag>) : '—'}</dd>
        <dt className="text-ink-2">Genotype</dt>
        <dd>
          {i.genotype === 'not_sequenced' ? 'Not sequenced' : i.genotype === 'no_determinant_detected' ? 'Sequenced, no acquired determinant' : (
            <div className="space-y-0.5">
              {i.st && <div>{i.st.replace(':', ' ')}{i.clone ? ` (${i.clone})` : ''}</div>}
              {i.genes.map(g => (
                <div key={g.symbol}><span className="font-mono text-[12px]">{g.symbol}</span> <span className="text-ink-2 text-[12px]">{g.carrier ? `on ${g.carrier.replace(':', ' ')}` : g.context}</span></div>
              ))}
            </div>
          )}
        </dd>
      </dl>
      <Table dense head={['Antimicrobial', 'MIC (mg/L)', 'Result']}>
        {i.ast.map(t => (
          <tr key={t.drug} className="border-b border-line last:border-0">
            <td className="px-1 py-1">{t.drug}</td>
            <td className="px-1 py-1">{formatMic(t)}</td>
            <td className="px-1 py-1"><SirBadge sir={t.sir} /></td>
          </tr>
        ))}
      </Table>
    </Card>
  );
}

// --------------------------------------------------------------------------- about

export function About({ snapshot }: { snapshot: Snapshot }) {
  const m = snapshot.meta;
  return (
    <div className="grid lg:grid-cols-2 gap-4 items-start">
      <Card title="Planted scenarios" subtitle="Ground truth the analytics are tested against (backend/data/demo/scenarios.json)">
        <Table head={['', 'Scenario', 'Where', 'Period']}>
          {Object.entries(snapshot.scenarios).sort().map(([key, s]) => (
            <tr key={key} className="border-b border-line last:border-0 align-top">
              <td className="px-1 py-1.5 font-medium">{key}</td>
              <td className="px-1 py-1.5">{s.title}</td>
              <td className="px-1 py-1.5 whitespace-nowrap">{s.ward === '*:Adult ICU' ? 'All adult ICUs' : wardLabel(s.ward)}</td>
              <td className="px-1 py-1.5 whitespace-nowrap text-ink-2">{s.period[0] === s.period[1] ? s.period[0] : `${s.period[0]} → ${s.period[1]}`}</td>
            </tr>
          ))}
        </Table>
      </Card>
      <div className="space-y-4">
        <Card title="Vocabulary verification" subtitle="tools/verify_vocabulary.py checks every identifier against its authoritative source">
          <Table dense head={['Check', 'Verified']}>
            {snapshot.verification.map(v => (
              <tr key={v.title} className="border-b border-line last:border-0">
                <td className="px-1 py-1.5">{v.title}</td>
                <td className="px-1 py-1.5 whitespace-nowrap">{v.verified}/{v.total} {v.verified === v.total ? '✓' : '✗'}</td>
              </tr>
            ))}
          </Table>
        </Card>
        <Card title="About this page">
          <ul className="text-[13px] text-ink-2 space-y-2 list-disc pl-4">
            <li><b className="text-ink">Static snapshot.</b> Generated {formatDate(m.generatedAt)} by <span className="font-mono text-[12px]">backend/tools/export_site_snapshot.py</span> from Neo4j {m.neo4j} with Graph Data Science {m.gds}. Nothing is computed in the browser except filtering and totals.</li>
            <li><b className="text-ink">Synthetic data.</b> {m.dataset}. Facilities are fictional; do not use for clinical decisions.</li>
            <li><b className="text-ink">Not included here.</b> CSV upload and the AI agent need the backend (and a server-held API key), so they are not part of the static site. Run the full stack with <span className="font-mono text-[12px]">docker compose up</span> in <span className="font-mono text-[12px]">backend/</span>.</li>
            <li>MICs are interpreted with {m.guideline}; clusters use a {m.windowDays}-day linkage window.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
