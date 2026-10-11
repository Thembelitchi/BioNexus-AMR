import React, { useCallback, useMemo, useState } from 'react';
import NetworkCanvas, { NetLink, NetNode } from './NetworkCanvas';
import { Isolate, Snapshot, formatDate, shortSpecies, wardLabel } from './data';
import { Card, Chips, FacilityDot, Table, facilityColor } from './ui';

// --------------------------------------------------------------------------- ward network

function WardNetwork({ snapshot }: { snapshot: Snapshot }) {
  const net = snapshot.wardNetwork;
  const [selected, setSelected] = useState<string | null>(null);
  const onSelect = useCallback((id: string | null) => setSelected(id), []);
  const maxRank = Math.max(...net.wards.map(w => w.pagerank));

  const { nodes, links } = useMemo(() => {
    const nodes: NetNode[] = net.wards.map(w => ({
      id: w.ward,
      label: wardLabel(w.ward),
      color: facilityColor(w.facility),
      shape: 'circle',
      radius: 6 + 14 * Math.sqrt(w.pagerank / maxRank),
      showLabel: true,
      group: w.facility ?? '',
      tooltip: (
        <div>
          <div className="font-medium">{wardLabel(w.ward)}</div>
          <div className="tabular text-ink-2">PageRank {w.pagerank.toFixed(2)} · betweenness {w.betweenness.toFixed(1)}</div>
          <div className="tabular text-ink-2">{w.isolates} isolates · link weight {w.weighted_degree}</div>
        </div>
      ),
    }));
    const links: NetLink[] = net.links.map(l => ({
      source: l.source,
      target: l.target,
      width: Math.min(8, 1 + Math.sqrt(l.transfers + l.genomic) / 2),
      tooltip: (
        <div>
          <div className="font-medium">{wardLabel(l.source)} ↔ {wardLabel(l.target)}</div>
          <div className="tabular text-ink-2">{l.transfers} patient transfers · {l.genomic} genomic links</div>
        </div>
      ),
    }));
    return { nodes, links };
  }, [net, maxRank]);

  const ranked = [...net.wards].sort((a, b) => b.pagerank - a.pagerank);
  return (
    <div className="grid xl:grid-cols-[1fr_380px] gap-4">
      <Card
        title="Ward transmission network"
        subtitle={`Edges join wards linked by ${net.transfer_links} patient transfers and ${net.genomic_links} genomic links (same ST and gene within ${net.window_days} days). Node size is GDS PageRank.`}
      >
        <div className="flex flex-wrap gap-x-4 gap-y-1 mb-2 text-[12px] text-ink-2" aria-label="Legend">
          {snapshot.facilities.map(f => (
            <span key={f.code} className="inline-flex items-center gap-1.5"><FacilityDot code={f.code} /><b className="text-ink">{f.code}</b> {f.name.replace(' (demo)', '')}</span>
          ))}
        </div>
        <NetworkCanvas nodes={nodes} links={links} groupForce selectedId={selected} onSelect={onSelect} ariaLabel="Ward network coloured by facility" />
      </Card>
      <Card title="Epicentre ranking" subtitle="Computed by Neo4j Graph Data Science">
        <Table dense head={['Ward', 'PageRank', 'Betw.', 'Isolates']}>
          {ranked.map(w => (
            <tr key={w.ward} onClick={() => setSelected(w.ward)}
              className={`border-b border-line last:border-0 cursor-pointer ${selected === w.ward ? 'bg-hover' : 'hover:bg-hover'}`}>
              <td className="px-1 py-1.5"><span className="inline-flex items-center gap-1.5"><FacilityDot code={w.facility} />{wardLabel(w.ward)}</span></td>
              <td className="px-1 py-1.5">{w.pagerank.toFixed(2)}</td>
              <td className="px-1 py-1.5">{w.betweenness.toFixed(1)}</td>
              <td className="px-1 py-1.5">{w.isolates}</td>
            </tr>
          ))}
        </Table>
      </Card>
    </div>
  );
}

// --------------------------------------------------------------------------- genomic graph

type Focus = 'all' | string;

function GenomicGraph({ snapshot, isolates }: { snapshot: Snapshot; isolates: Isolate[] }) {
  const [focus, setFocus] = useState<Focus>('S1');
  const [selected, setSelected] = useState<string | null>(null);
  const onSelect = useCallback((id: string | null) => setSelected(id), []);
  const scenarioKeys = Object.keys(snapshot.scenarios).filter(k => snapshot.scenarios[k].ward !== '*:Adult ICU').sort();

  const shown = useMemo(() => {
    const sequenced = isolates.filter(i => i.genotype === 'determinants_detected');
    if (focus === 'all') return sequenced;
    const s = snapshot.scenarios[focus];
    // Scenario periods are SAST calendar days.
    const from = new Date(`${s.period[0]}T00:00:00+02:00`).getTime();
    const to = new Date(`${s.period[1]}T23:59:59+02:00`).getTime();
    const signatures = [s.expect.cluster?.gene, s.expect.hgt?.gene, s.expect.gene_present].filter(Boolean);
    return sequenced.filter(i => {
      const t = new Date(i.collected).getTime();
      return t >= from && t <= to && i.ward === s.ward && i.genes.some(g => signatures.includes(g.symbol));
    });
  }, [focus, isolates, snapshot]);

  const { nodes, links } = useMemo(() => {
    const nodes = new Map<string, NetNode>();
    const links: NetLink[] = [];
    for (const i of shown) {
      nodes.set(i.id, {
        id: i.id, label: i.id, color: 'var(--series-1)', shape: 'circle', radius: 5, showLabel: false, group: i.ward,
        tooltip: (
          <div>
            <div className="font-medium tabular">{i.id}</div>
            <div><i>{i.species}</i> {i.st ? `ST${i.st.split(':ST')[1]}` : ''}</div>
            <div className="text-ink-2">{wardLabel(i.ward)} · {formatDate(i.collected)}</div>
            <div className="text-ink-2 font-mono text-[11px]">{i.genes.map(g => g.symbol).join(', ')}</div>
          </div>
        ),
      });
      const wardId = `ward:${i.ward}`;
      if (!nodes.has(wardId)) {
        nodes.set(wardId, { id: wardId, label: wardLabel(i.ward), color: 'var(--ink-muted)', shape: 'square', radius: 8, showLabel: true, tooltip: <div className="font-medium">{wardLabel(i.ward)}</div> });
      }
      links.push({ source: i.id, target: wardId, width: 1 });
      if (i.st) {
        const stId = `st:${i.st}`;
        if (!nodes.has(stId)) {
          nodes.set(stId, { id: stId, label: `${shortSpecies(i.species)} ST${i.st.split(':ST')[1]}`, color: 'var(--series-3)', shape: 'diamond', radius: 8, showLabel: true,
            tooltip: <div><div className="font-medium">Sequence type {i.st}</div><div className="text-ink-2"><i>{i.species}</i></div></div> });
        }
        links.push({ source: i.id, target: stId, width: 1 });
      }
      for (const g of i.genes) {
        const geneId = `gene:${g.symbol}`;
        if (!nodes.has(geneId)) {
          nodes.set(geneId, { id: geneId, label: g.symbol, color: 'var(--series-2)', shape: 'circle', radius: 8, showLabel: true,
            tooltip: <div><div className="font-medium font-mono">{g.symbol}</div><div className="text-ink-2">{g.aro} · {g.category}</div></div> });
        }
        links.push({ source: i.id, target: geneId, width: 1, tooltip: <div className="text-ink-2">{g.carrier ? `on ${g.carrier.replace(':', ' ')}` : 'carrier not resolved'}</div> });
      }
    }
    return { nodes: [...nodes.values()], links };
  }, [shown]);

  const tooMany = focus === 'all' && nodes.length > 400;
  return (
    <Card
      title="Genomic knowledge graph"
      subtitle="Sequenced isolates (blue circles) linked to their ward (grey squares), sequence type (green diamonds) and resistance genes (orange circles). Hover for details; drag to rearrange."
      actions={
        <Chips
          label="Focus"
          value={focus}
          onChange={v => { setFocus(v); setSelected(null); }}
          options={[...scenarioKeys.map(k => ({ value: k, label: k })), { value: 'all', label: 'All sequenced' }]}
        />
      }
    >
      {focus !== 'all' && <p className="text-[13px] text-ink-2 mb-3"><b className="text-ink">{focus}:</b> {snapshot.scenarios[focus].title}</p>}
      {tooMany && <p className="text-[13px] text-ink-2 mb-3">Showing {shown.length} isolates; zoom in to read labels.</p>}
      {nodes.length ? (
        <NetworkCanvas nodes={nodes} links={links} selectedId={selected} onSelect={onSelect} height={560} ariaLabel="Genomic knowledge graph" />
      ) : (
        <p className="text-[13px] text-ink-2">No sequenced isolates match this focus in the current facility selection.</p>
      )}
    </Card>
  );
}

export default function Networks({ snapshot, isolates }: { snapshot: Snapshot; isolates: Isolate[] }) {
  return (
    <div className="space-y-4">
      <WardNetwork snapshot={snapshot} />
      <GenomicGraph snapshot={snapshot} isolates={isolates} />
    </div>
  );
}
