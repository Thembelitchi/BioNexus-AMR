import React, { useMemo, useState } from 'react';
import { Timeline } from './charts';
import { Isolate, Snapshot, formatDate, formatMic, shortSpecies, wardLabel } from './data';
import { Card, Chips, FacilityDot, SirBadge, Table, Tag, facilityColor } from './ui';

type Basis = 'phenotypic' | 'genomic';

interface Outbreak {
  key: string;
  ward: string;
  facility: string | null;
  species: string;
  heading: string;
  evidence: React.ReactNode;
  members: { isolate_id: string; patient_id: string; collected: string; sequence_type?: string | null }[];
  first: string;
  last: string;
  scenario: string | null;
}

const CARBAPENEMS = ['Ertapenem', 'Meropenem', 'Imipenem'];
const KEY_TESTS: Record<string, string[]> = {
  CRE: CARBAPENEMS, CRAB: ['Meropenem', 'Imipenem'], CRPA: ['Meropenem', 'Imipenem'],
  MRSA: ['Oxacillin', 'Cefoxitin', 'Vancomycin'], VRE: ['Vancomycin', 'Linezolid'],
};
const stNumber = (key: string) => `ST${key.split(':ST')[1]}`;

export default function Outbreaks({ snapshot, isolates }: { snapshot: Snapshot; isolates: Isolate[] }) {
  const [basis, setBasis] = useState<Basis>('phenotypic');
  const byId = useMemo(() => new Map(snapshot.isolates.map(i => [i.id, i])), [snapshot]);
  const visible = useMemo(() => new Set(isolates.map(i => i.id)), [isolates]);

  const scenarioFor = (ward: string, test: (expect: Record<string, any>) => boolean) =>
    Object.entries(snapshot.scenarios).find(([, s]) => {
      const want = s.expect.cluster;
      return want && (want.ward ? want.ward === ward : ward.endsWith(want.ward_suffix)) && test(want);
    })?.[0] ?? null;

  const outbreaks = useMemo<Outbreak[]>(() => {
    if (basis === 'phenotypic') {
      return snapshot.phenotypicClusters
        .filter(c => c.members.some(m => visible.has(m.isolate_id)))
        .map(c => ({
          key: `${c.ward}|${c.species}|${c.phenotype}|${c.first_collected}`,
          ward: c.ward,
          facility: c.facility,
          species: c.species,
          heading: c.phenotype,
          evidence: c.sequenced
            ? `${c.sequenced}/${c.size} sequenced · ${c.sequence_types.map(stNumber).join(', ')}`
            : 'none sequenced',
          members: c.members,
          first: c.first_collected,
          last: c.last_collected,
          scenario: scenarioFor(c.ward, want => c.members.some(m => m.sequence_type === want.sequence_type)),
        }));
    }
    // Genomic: one outbreak per member set (the backend reports a cluster per gene).
    const merged = new Map<string, Outbreak & { genes: string[] }>();
    for (const c of snapshot.clusters) {
      if (!c.members.some(m => visible.has(m.isolate_id))) continue;
      const key = `${c.ward}|${c.sequence_type}|${c.members.map(m => m.isolate_id).sort().join(',')}`;
      const existing = merged.get(key);
      if (existing) {
        existing.genes.push(c.gene);
        existing.evidence = existing.genes.join(', ');
        continue;
      }
      merged.set(key, {
        key, ward: c.ward, facility: c.facility, species: byId.get(c.members[0].isolate_id)?.species ?? '',
        heading: `${stNumber(c.sequence_type)}${c.clone_designation ? ` (${c.clone_designation})` : ''}`,
        genes: [c.gene], evidence: c.gene, members: c.members, first: c.first_collected, last: c.last_collected,
        scenario: scenarioFor(c.ward, want => want.sequence_type === c.sequence_type && want.gene === c.gene),
      });
    }
    return [...merged.values()];
  }, [basis, snapshot, byId, visible]);

  const sorted = useMemo(() => [...outbreaks].sort((a, b) => b.members.length - a.members.length || a.first.localeCompare(b.first)), [outbreaks]);
  const [selected, setSelected] = useState<string | null>(null);
  const current = sorted.find(o => o.key === selected) ?? sorted[0];
  const tests = current ? (basis === 'phenotypic' ? KEY_TESTS[current.heading] ?? CARBAPENEMS : CARBAPENEMS) : [];

  return (
    <div className="space-y-4">
      <Card
        title="Outbreak detection"
        subtitle={
          basis === 'phenotypic'
            ? `Same species with the same priority resistance phenotype on one ward, each case within ${snapshot.meta.windowDays} days of the next. Needs only laboratory results, so it covers unsequenced isolates.`
            : `Same sequence type and acquired resistance gene on one ward, each within ${snapshot.meta.windowDays} days of the next. Confirms which phenotype clusters are one strain.`
        }
        actions={
          <Chips<Basis>
            label="Detection basis"
            value={basis}
            onChange={v => { setBasis(v); setSelected(null); }}
            options={[
              { value: 'phenotypic', label: 'Lab phenotype', count: snapshot.phenotypicClusters.length },
              { value: 'genomic', label: 'Genomic', count: new Set(snapshot.clusters.map(c => `${c.ward}|${c.sequence_type}|${c.first_collected}`)).size },
            ]}
          />
        }
      >
        {sorted.length === 0 ? (
          <p className="text-[13px] text-ink-2">No clusters in the current selection.</p>
        ) : (
          <Timeline
            domain={[new Date('2025-07-01T00:00:00+02:00'), new Date('2026-01-01T00:00:00+02:00')]}
            selected={current?.key}
            onSelect={setSelected}
            rows={sorted.map(o => ({
              key: o.key,
              color: facilityColor(o.facility),
              label: (
                <span className="flex items-center gap-1.5 min-w-0">
                  <FacilityDot code={o.facility} />
                  <span className="truncate">
                    <span className="font-medium">{wardLabel(o.ward)}</span>{' '}
                    <i className="text-ink-2">{shortSpecies(o.species)}</i> <span className="text-ink-2">{o.heading}</span>
                  </span>
                  <span className="ml-auto tabular text-ink-2 pr-1">{o.members.length}</span>
                </span>
              ),
              points: o.members.map(m => ({
                id: m.isolate_id,
                date: new Date(m.collected),
                tooltip: (
                  <div>
                    <div className="font-medium tabular">{m.isolate_id}</div>
                    <div className="text-ink-2">{formatDate(m.collected)} · {byId.get(m.isolate_id)?.specimen}</div>
                    <div className="text-ink-2">{m.sequence_type ? stNumber(m.sequence_type) : byId.get(m.isolate_id)?.st ? stNumber(byId.get(m.isolate_id)!.st!) : 'not sequenced'}</div>
                  </div>
                ),
              })),
            }))}
          />
        )}
      </Card>

      {current && (
        <Card
          title={
            <span className="flex flex-wrap items-center gap-2">
              <FacilityDot code={current.facility} /> {wardLabel(current.ward)}: <i>{current.species}</i> {current.heading}
              {current.scenario && <Tag>Planted scenario {current.scenario}</Tag>}
            </span>
          }
          subtitle={<span>{current.members.length} cases, {formatDate(current.first)} – {formatDate(current.last)} · {current.evidence}</span>}
        >
          <Table head={['Isolate', 'Collected', 'Patient', 'Specimen', 'Sequence type', 'Treatment', ...tests]}>
            {current.members.map(m => {
              const iso = byId.get(m.isolate_id);
              return (
                <tr key={m.isolate_id} className="border-b border-line last:border-0">
                  <td className="px-1 py-1.5 font-mono text-[12px]">{m.isolate_id}</td>
                  <td className="px-1 py-1.5 whitespace-nowrap">{formatDate(m.collected)}</td>
                  <td className="px-1 py-1.5 font-mono text-[12px]">{m.patient_id}</td>
                  <td className="px-1 py-1.5">{iso?.specimen}</td>
                  <td className="px-1 py-1.5">{iso?.st ? stNumber(iso.st) : <span className="text-muted">not sequenced</span>}</td>
                  <td className="px-1 py-1.5">{iso?.treatments.join(', ') || '—'}</td>
                  {tests.map(drug => {
                    const t = iso?.ast.find(a => a.drug === drug);
                    return (
                      <td key={drug} className="px-1 py-1.5 whitespace-nowrap">
                        {t ? <span className="inline-flex items-center gap-1.5"><SirBadge sir={t.sir} /> <span className="text-ink-2">{formatMic(t)}</span></span> : <span className="text-muted">—</span>}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </Table>
        </Card>
      )}
    </div>
  );
}
