import React, { useMemo, useState } from 'react';
import { Timeline } from './charts';
import { Cluster, Isolate, Snapshot, formatDate, formatMic, shortSpecies, wardLabel } from './data';
import { Card, FacilityDot, SirBadge, Table, Tag, facilityColor } from './ui';

interface Outbreak {
  key: string;
  ward: string;
  facility: string | null;
  sequenceType: string;
  clone: string | null;
  genes: string[];
  members: Cluster['members'];
  first: string;
  last: string;
  species: string;
  scenario: string | null;
}

const CARBAPENEMS = ['Ertapenem', 'Meropenem', 'Imipenem'];

export default function Outbreaks({ snapshot, isolates }: { snapshot: Snapshot; isolates: Isolate[] }) {
  const byId = useMemo(() => new Map(snapshot.isolates.map(i => [i.id, i])), [snapshot]);
  const visible = useMemo(() => new Set(isolates.map(i => i.id)), [isolates]);

  // One outbreak per member set: the backend reports a cluster per gene.
  const outbreaks = useMemo(() => {
    const merged = new Map<string, Outbreak>();
    for (const c of snapshot.clusters) {
      if (!c.members.some(m => visible.has(m.isolate_id))) continue;
      const key = `${c.ward}|${c.sequence_type}|${c.members.map(m => m.isolate_id).sort().join(',')}`;
      const existing = merged.get(key);
      if (existing) {
        existing.genes.push(c.gene);
        continue;
      }
      const species = byId.get(c.members[0].isolate_id)?.species ?? '';
      const scenario = Object.entries(snapshot.scenarios).find(([, s]) => {
        const want = s.expect.cluster;
        return want && (want.ward ? want.ward === c.ward : c.ward.endsWith(want.ward_suffix)) && want.sequence_type === c.sequence_type && want.gene === c.gene;
      })?.[0] ?? null;
      merged.set(key, {
        key, ward: c.ward, facility: c.facility, sequenceType: c.sequence_type, clone: c.clone_designation, genes: [c.gene],
        members: c.members, first: c.first_collected, last: c.last_collected, species, scenario,
      });
    }
    return [...merged.values()].sort((a, b) => b.members.length - a.members.length || a.first.localeCompare(b.first));
  }, [snapshot, byId, visible]);

  const [selected, setSelected] = useState<string | null>(null);
  const current = outbreaks.find(o => o.key === selected) ?? outbreaks[0];

  const stLabel = (o: Outbreak) => `ST${o.sequenceType.split(':ST')[1]}${o.clone ? ` (${o.clone})` : ''}`;

  return (
    <div className="space-y-4">
      <Card
        title="Spatiotemporal clusters"
        subtitle={`Isolates on the same ward sharing sequence type and an acquired resistance gene, each within ${snapshot.meta.windowDays} days of the next. Click a row for its cases.`}
      >
        {outbreaks.length === 0 ? (
          <p className="text-[13px] text-ink-2">No clusters in the current selection.</p>
        ) : (
          <Timeline
            domain={[new Date('2025-07-01T00:00:00+02:00'), new Date('2026-01-01T00:00:00+02:00')]}
            selected={current?.key}
            onSelect={setSelected}
            rows={outbreaks.map(o => ({
              key: o.key,
              color: facilityColor(o.facility),
              label: (
                <span className="flex items-center gap-1.5 min-w-0">
                  <FacilityDot code={o.facility} />
                  <span className="truncate">
                    <span className="font-medium">{wardLabel(o.ward)}</span>{' '}
                    <i className="text-ink-2">{shortSpecies(o.species)}</i> <span className="text-ink-2">{stLabel(o)}</span>
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
                    <div className="text-ink-2">{formatDate(m.collected)} · {m.patient_id}</div>
                    <div className="text-ink-2">{byId.get(m.isolate_id)?.specimen}</div>
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
              <FacilityDot code={current.facility} /> {wardLabel(current.ward)}: <i>{current.species}</i> {stLabel(current)}
              {current.scenario && <Tag>Planted scenario {current.scenario}</Tag>}
            </span>
          }
          subtitle={
            <span>
              {current.members.length} cases, {formatDate(current.first)} – {formatDate(current.last)} · genes{' '}
              {current.genes.map(g => <span key={g} className="font-mono text-[12px] mr-1">{g}</span>)}
            </span>
          }
        >
          <Table head={['Isolate', 'Collected', 'Patient', 'Specimen', 'Treatment', ...CARBAPENEMS.map(d => `${d} (MIC)`)]}>
            {current.members.map(m => {
              const iso = byId.get(m.isolate_id);
              return (
                <tr key={m.isolate_id} className="border-b border-line last:border-0">
                  <td className="px-1 py-1.5 font-mono text-[12px]">{m.isolate_id}</td>
                  <td className="px-1 py-1.5 whitespace-nowrap">{formatDate(m.collected)}</td>
                  <td className="px-1 py-1.5">{m.patient_id}</td>
                  <td className="px-1 py-1.5">{iso?.specimen}</td>
                  <td className="px-1 py-1.5">{iso?.treatments.join(', ') || '—'}</td>
                  {CARBAPENEMS.map(drug => {
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
