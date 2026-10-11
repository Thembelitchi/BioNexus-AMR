import React, { useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { Maximize, ZoomIn, ZoomOut } from 'lucide-react';
import { Tooltip, useWidth } from './ui';

export interface NetNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  color: string;
  shape: 'circle' | 'square' | 'diamond';
  radius: number;
  showLabel: boolean;
  tooltip: React.ReactNode;
  group?: string;
}

export interface NetLink extends d3.SimulationLinkDatum<NetNode> {
  source: string | NetNode;
  target: string | NetNode;
  width: number;
  tooltip?: React.ReactNode;
}

/**
 * Force-directed network with zoom/pan, hover tooltips and click selection.
 * Shapes give a second channel besides color, and important nodes are
 * labelled directly, so identity never rests on color alone.
 */
export default function NetworkCanvas({ nodes, links, height = 520, onSelect, selectedId, groupForce = false, ariaLabel }: {
  nodes: NetNode[]; links: NetLink[]; height?: number; onSelect?: (id: string | null) => void; selectedId?: string | null;
  groupForce?: boolean; ariaLabel: string;
}) {
  const [wrapRef, width] = useWidth<HTMLDivElement>();
  const svgRef = useRef<SVGSVGElement>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const fitRef = useRef<(() => d3.ZoomTransform) | null>(null);
  const nodeSelection = useRef<d3.Selection<SVGPathElement, NetNode, SVGGElement, unknown> | null>(null);
  const selectedRef = useRef(selectedId);
  selectedRef.current = selectedId;
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const [hover, setHover] = useState<{ content: React.ReactNode; x: number; y: number } | null>(null);

  // Copy so the simulation's mutation never leaks into props.
  const graph = useMemo(
    () => ({ nodes: nodes.map(n => ({ ...n })), links: links.map(l => ({ ...l })) }),
    [nodes, links],
  );

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || width === 0) return;
    const root = d3.select(svg);
    root.selectAll('*').remove();
    const container = root.append('g');

    // Labels keep a constant on-screen size while the graph zooms.
    const zoom = d3.zoom<SVGSVGElement, unknown>().scaleExtent([0.2, 6]).on('zoom', e => {
      container.attr('transform', e.transform);
      container.selectAll<SVGTextElement, NetNode>('text')
        .attr('font-size', 11 / e.transform.k)
        .attr('stroke-width', 3 / e.transform.k)
        .attr('dx', d => d.radius + 4 / e.transform.k);
    });
    root.call(zoom).on('dblclick.zoom', null);
    zoomRef.current = zoom;

    const groups = Array.from(new Set(graph.nodes.map(n => n.group ?? '')));
    const groupX = d3.scalePoint<string>().domain(groups).range([width * 0.2, width * 0.8]);

    // Labelled hubs repel strongly and reserve room for their label; leaf
    // nodes stay compact around the hubs they attach to.
    const simulation = d3
      .forceSimulation<NetNode>(graph.nodes)
      .force('link', d3.forceLink<NetNode, NetLink>(graph.links).id(d => d.id).distance(l => (groupForce ? 140 : 80) + 20 / Math.max(1, l.width)).strength(groupForce ? 0.3 : 0.5))
      .force('charge', d3.forceManyBody<NetNode>().strength(d => (d.showLabel ? -900 : -90)))
      .force('collide', d3.forceCollide<NetNode>(d => d.radius + (d.showLabel ? 42 : 5)).iterations(3))
      .force('x', d3.forceX<NetNode>(d => (groupForce ? groupX(d.group ?? '') ?? width / 2 : width / 2)).strength(groupForce ? 0.08 : 0.04))
      .force('y', d3.forceY(height / 2).strength(0.06))
      .stop();
    // Settle the layout up front so the first paint is already readable.
    simulation.tick(Math.ceil(Math.log(simulation.alphaMin()) / Math.log(1 - simulation.alphaDecay())));

    const link = container
      .append('g')
      .selectAll('line')
      .data(graph.links)
      .join('line')
      .attr('stroke', 'var(--axis)')
      .attr('stroke-opacity', 0.9)
      .attr('stroke-width', d => d.width)
      .attr('stroke-linecap', 'round')
      .on('mousemove', (e, d) => d.tooltip && setHover({ content: d.tooltip, x: e.clientX, y: e.clientY }))
      .on('mouseleave', () => setHover(null));

    const symbol = (d: NetNode) =>
      d3.symbol().type(d.shape === 'square' ? d3.symbolSquare : d.shape === 'diamond' ? d3.symbolDiamond : d3.symbolCircle)
        .size(Math.PI * d.radius * d.radius * (d.shape === 'circle' ? 1 : 1.25))();

    const node = container
      .append('g')
      .selectAll<SVGPathElement, NetNode>('path')
      .data(graph.nodes)
      .join('path')
      .attr('d', symbol)
      .attr('fill', d => d.color)
      .attr('stroke', d => (d.id === selectedRef.current ? 'var(--ink)' : 'var(--surface)'))
      .attr('stroke-width', d => (d.id === selectedRef.current ? 2.5 : 2))
      .style('cursor', 'pointer')
      .on('mousemove', (e, d) => setHover({ content: d.tooltip, x: e.clientX, y: e.clientY }))
      .on('mouseleave', () => setHover(null))
      .on('click', (e, d) => {
        e.stopPropagation();
        onSelectRef.current?.(d.id === selectedRef.current ? null : d.id);
      })
      .call(
        d3.drag<SVGPathElement, NetNode>()
          .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.25).restart(); d.fx = d.x; d.fy = d.y; })
          .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
          .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }),
      );

    const label = container
      .append('g')
      .selectAll('text')
      .data(graph.nodes.filter(n => n.showLabel))
      .join('text')
      .text(d => d.label)
      .attr('font-size', 11)
      .attr('fill', 'var(--ink-2)')
      .attr('paint-order', 'stroke')
      .attr('stroke', 'var(--surface)')
      .attr('stroke-width', 3)
      .attr('stroke-linejoin', 'round')
      .attr('dx', d => d.radius + 4)
      .attr('dy', '0.32em')
      .style('pointer-events', 'none');

    nodeSelection.current = node;
    root.on('click', () => onSelectRef.current?.(null));

    const draw = () => {
      link
        .attr('x1', d => (d.source as NetNode).x ?? 0)
        .attr('y1', d => (d.source as NetNode).y ?? 0)
        .attr('x2', d => (d.target as NetNode).x ?? 0)
        .attr('y2', d => (d.target as NetNode).y ?? 0);
      node.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`);
      label.attr('x', d => d.x ?? 0).attr('y', d => d.y ?? 0);
    };
    simulation.on('tick', draw);
    draw();

    // Fit the settled layout (labels included) into the viewport.
    const fit = () => {
      const xs = graph.nodes.map(n => n.x ?? 0);
      const ys = graph.nodes.map(n => n.y ?? 0);
      const labelRoom = 120;
      const [x0, x1] = [Math.min(...xs) - 20, Math.max(...xs) + labelRoom];
      const [y0, y1] = [Math.min(...ys) - 20, Math.max(...ys) + 20];
      // Cap the zoom so a small graph is not blown up to oversized labels.
      const k = Math.min(1.25, 0.92 * Math.min(width / (x1 - x0), height / (y1 - y0)));
      return d3.zoomIdentity.translate(width / 2 - (k * (x0 + x1)) / 2, height / 2 - (k * (y0 + y1)) / 2).scale(k);
    };
    fitRef.current = fit;
    root.call(zoom.transform, fit());
    return () => {
      simulation.stop();
    };
  }, [graph, width, height, groupForce]);

  // Selection only restyles nodes; it never restarts the layout.
  useEffect(() => {
    nodeSelection.current
      ?.attr('stroke', d => (d.id === selectedId ? 'var(--ink)' : 'var(--surface)'))
      .attr('stroke-width', d => (d.id === selectedId ? 2.5 : 2));
  }, [selectedId]);

  const zoomBy = (k: number) => svgRef.current && zoomRef.current && d3.select(svgRef.current).transition().duration(250).call(zoomRef.current.scaleBy, k);
  const reset = () =>
    svgRef.current && zoomRef.current && d3.select(svgRef.current).transition().duration(400).call(zoomRef.current.transform, fitRef.current?.() ?? d3.zoomIdentity);

  return (
    <div ref={wrapRef} className="relative w-full rounded-lg border border-line bg-page overflow-hidden" style={{ height }}>
      <svg ref={svgRef} width={width} height={height} role="img" aria-label={ariaLabel} className="cursor-grab active:cursor-grabbing" />
      <div className="absolute top-2 right-2 flex flex-col gap-1">
        {[
          { icon: ZoomIn, label: 'Zoom in', onClick: () => zoomBy(1.3) },
          { icon: ZoomOut, label: 'Zoom out', onClick: () => zoomBy(1 / 1.3) },
          { icon: Maximize, label: 'Reset view', onClick: reset },
        ].map(b => (
          <button key={b.label} onClick={b.onClick} title={b.label} aria-label={b.label}
            className="w-8 h-8 grid place-items-center rounded-md bg-raised border border-line text-ink-2 hover:text-ink">
            <b.icon className="w-4 h-4" />
          </button>
        ))}
      </div>
      {hover && <Tooltip x={hover.x} y={hover.y}>{hover.content}</Tooltip>}
    </div>
  );
}
