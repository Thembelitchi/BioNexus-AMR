import React, { useMemo } from 'react';
import { BarList, LineChart } from './charts';
import { FLAG_MEANING, Isolate, KEY_FLAG, Snapshot, shortSpecies } from './data';
import { Card, FACILITY_COLOR, StatTile } from './ui';

const MONTHS = ['2025-07', '2025-08', '2025-09', '2025-10', '2025-11', '2025-12'];
const MONTH_LABEL: Record<string, string> = { '2025-07': 'Jul', '2025-08': 'Aug', '2025-09': 'Sep', '2025-10': 'Oct', '2025-11': 'Nov', '2025-12': 'Dec' };

function sastMonth(iso: string) {
  const d = new Date(new Date(iso).getTime() + 2 * 3600 * 1000);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

export default function Overview({ snapshot, isolates, facilities, onOpen }: {
  snapshot: Snapshot; isolates: Isolate[]; facilities: string[]; onOpen: (tab: string) => void;
}) {
  const stats = useMemo(() => {
    const patients = new Set(isolates.map(i => i.patient)).size;
    const sequenced = isolates.filter(i => i.genotype !== 'not_sequenced').length;
    const ids = new Set(isolates.map(i => i.id));
    const clusters = snapshot.clusters.filter(c => c.members.some(m => ids.has(m.isolate_id)));
    const priority = new Set(clusters.map(c => `${c.ward}|${c.sequence_type}|${c.first_collected}`)).size;
    const critical = snapshot.alerts.filter(a => a.severity === 'critical' && ids.has(a.isolate_id)).length;
    return { patients, sequenced, clusters: priority, critical };
  }, [isolates, snapshot]);

  const resistance = useMemo(() => {
    const bySpecies = new Map<string, Isolate[]>();
    isolates.forEach(i => bySpecies.set(i.species, [...(bySpecies.get(i.species) ?? []), i]));
    return [...bySpecies.entries()]
      .map(([species, list]) => {
        const flag = KEY_FLAG[species];
        const flagged = list.filter(i => i.labels.includes(flag)).length;
        return { species, flag, flagged, total: list.length, rate: flagged / list.length };
      })
      .sort((a, b) => b.rate - a.rate);
  }, [isolates]);

  const monthly = useMemo(
    () =>
      facilities.map(code => ({
        key: code,
        label: code,
        color: FACILITY_COLOR[code],
        values: MONTHS.map(m => isolates.filter(i => i.facility === code && sastMonth(i.collected) === m).length),
      })),
    [isolates, facilities],
  );

  const carbapenemases = useMemo(() => {
    const counts = new Map<string, Set<string>>();
    isolates.forEach(i => i.genes.filter(g => g.category === 'carbapenemase').forEach(g => counts.set(g.symbol, (counts.get(g.symbol) ?? new Set()).add(i.id))));
    return [...counts.entries()].map(([gene, set]) => ({ gene, n: set.size })).sort((a, b) => b.n - a.n);
  }, [isolates]);
  const sequencedCarbapenemase = new Set(isolates.filter(i => i.genes.some(g => g.category === 'carbapenemase')).map(i => i.id)).size;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <StatTile label="Patients" value={stats.patients.toLocaleString()} note="with a positive culture" />
        <StatTile label="Isolates" value={isolates.length.toLocaleString()} note={`${snapshot.meta.guideline} interpreted`} />
        <StatTile label="Sequenced" value={stats.sequenced.toLocaleString()} note={`${Math.round((100 * stats.sequenced) / Math.max(1, isolates.length))}% of isolates`} />
        <button onClick={() => onOpen('outbreaks')} className="text-left">
          <StatTile label="Outbreak clusters" value={stats.clusters} note={`same ward, ST and gene, ≤${snapshot.meta.windowDays} days apart`} />
        </button>
        <button onClick={() => onOpen('alerts')} className="text-left col-span-2 lg:col-span-1">
          <StatTile label="Critical alerts" value={stats.critical} note="colistin resistance, sentinel genes" />
        </button>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="Key resistance phenotype by organism" subtitle="Share of isolates carrying the laboratory flag clinicians act on">
          <BarList
            max={1}
            items={resistance.map(r => ({
              key: r.species,
              label: (
                <span>
                  <i>{shortSpecies(r.species)}</i> <span className="text-ink-2">{r.flag}</span>
                </span>
              ),
              value: r.rate,
              valueLabel: `${Math.round(r.rate * 100)}% · ${r.flagged}/${r.total}`,
              tooltip: (
                <div>
                  <div className="font-medium"><i>{r.species}</i></div>
                  <div className="text-ink-2">{r.flag}: {FLAG_MEANING[r.flag]}</div>
                  <div className="mt-1 tabular">{r.flagged} of {r.total} isolates</div>
                </div>
              ),
            }))}
          />
        </Card>

        <Card title="Isolates per month" subtitle="Positive cultures by facility, July–December 2025">
          <div className="flex flex-wrap gap-x-4 gap-y-1 mb-2" aria-label="Legend">
            {monthly.map(s => {
              const facility = snapshot.facilities.find(f => f.code === s.key);
              return (
                <span key={s.key} className="inline-flex items-center gap-1.5 text-[12px] text-ink-2">
                  <span className="w-3 h-0.5 rounded" style={{ background: s.color }} />
                  <span className="font-medium text-ink">{s.key}</span> {facility?.name.replace(' (demo)', '')}
                </span>
              );
            })}
          </div>
          <LineChart xLabels={MONTHS.map(m => MONTH_LABEL[m])} series={monthly} yLabel="Isolates per month by facility" />
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="Carbapenemase genes" subtitle={`Isolates carrying each gene (${sequencedCarbapenemase} carbapenemase producers among sequenced isolates)`}>
          {carbapenemases.length ? (
            <BarList
              items={carbapenemases.map(c => ({
                key: c.gene,
                label: <span className="font-mono text-[12px]">{c.gene}</span>,
                value: c.n,
                valueLabel: `${c.n}`,
                tooltip: <div><span className="font-mono">{c.gene}</span>: {c.n} isolates</div>,
              }))}
            />
          ) : (
            <p className="text-[13px] text-ink-2">No carbapenemase genes in the current selection.</p>
          )}
        </Card>
        <Card title="What this snapshot is" subtitle="Read this before drawing conclusions">
          <ul className="text-[13px] text-ink-2 space-y-2 list-disc pl-4">
            <li><b className="text-ink">Synthetic data.</b> 600 generated patients across four fictional hospitals in Gauteng, KwaZulu-Natal and the Western Cape. Patterns follow published South African surveillance; numbers are illustrative.</li>
            <li><b className="text-ink">Real computation.</b> Every cluster, gene-transfer signal, ward ranking and alert was produced by the BioNexus backend on Neo4j {snapshot.meta.neo4j} with Graph Data Science {snapshot.meta.gds}, then exported for this static page.</li>
            <li><b className="text-ink">Verified vocabulary.</b> Taxonomy, genes, drug codes, sequence types and {snapshot.meta.guideline} breakpoints are checked against their sources. <button className="underline text-ink" onClick={() => onOpen('about')}>See provenance</button>.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
