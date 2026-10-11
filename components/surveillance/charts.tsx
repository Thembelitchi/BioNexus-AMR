import React, { useMemo, useState } from 'react';
import * as d3 from 'd3';
import { Tooltip, useWidth } from './ui';

// --------------------------------------------------------------------------- bar list

export interface BarItem {
  key: string;
  label: React.ReactNode;
  value: number;
  valueLabel: string;
  tooltip?: React.ReactNode;
}

/** Horizontal bars, one series (one color), value labels in ink. */
export function BarList({ items, max, color = 'var(--series-1)' }: { items: BarItem[]; max?: number; color?: string }) {
  const top = max ?? Math.max(1, ...items.map(i => i.value));
  const [hover, setHover] = useState<{ item: BarItem; x: number; y: number } | null>(null);
  return (
    <div className="space-y-1.5">
      {items.map(item => (
        <div
          key={item.key}
          className="grid grid-cols-[minmax(7rem,11rem)_1fr_auto] items-center gap-3 rounded px-1 py-1 hover:bg-hover"
          onMouseMove={e => setHover({ item, x: e.clientX, y: e.clientY })}
          onMouseLeave={() => setHover(null)}
        >
          <div className="text-[13px] text-ink truncate">{item.label}</div>
          <div className="h-2.5 rounded-r bg-transparent relative">
            <div className="absolute inset-y-0 left-0 rounded-r" style={{ width: `${(item.value / top) * 100}%`, background: color, minWidth: item.value > 0 ? 3 : 0 }} />
          </div>
          <div className="text-[12px] text-ink-2 tabular text-right whitespace-nowrap">{item.valueLabel}</div>
        </div>
      ))}
      {hover?.item.tooltip && <Tooltip x={hover.x} y={hover.y}>{hover.item.tooltip}</Tooltip>}
    </div>
  );
}

// --------------------------------------------------------------------------- line chart

export interface LineSeries {
  key: string;
  label: string;
  color: string;
  values: number[];
}

/** Multi-series line chart over categorical x labels with a crosshair tooltip. */
export function LineChart({ xLabels, series, height = 220, yLabel }: { xLabels: string[]; series: LineSeries[]; height?: number; yLabel: string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [pointer, setPointer] = useState({ x: 0, y: 0 });
  const margin = { top: 12, right: 64, bottom: 28, left: 36 };
  const innerW = Math.max(0, width - margin.left - margin.right);
  const innerH = height - margin.top - margin.bottom;
  const x = d3.scalePoint<number>().domain(xLabels.map((_, i) => i)).range([0, innerW]);
  const yMax = Math.max(1, ...series.flatMap(s => s.values));
  const y = d3.scaleLinear().domain([0, yMax]).nice(4).range([innerH, 0]);
  const line = d3.line<number>().x((_, i) => x(i) ?? 0).y(v => y(v));

  // Direct end labels, nudged apart so they never overlap.
  const endLabels = useMemo(() => {
    const placed = series
      .map(s => ({ s, y: y(s.values[s.values.length - 1] ?? 0) }))
      .sort((a, b) => a.y - b.y);
    for (let i = 1; i < placed.length; i++) placed[i].y = Math.max(placed[i].y, placed[i - 1].y + 13);
    return placed;
  }, [series, y]);

  return (
    <div ref={ref} className="relative w-full">
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={yLabel}>
          <g transform={`translate(${margin.left},${margin.top})`}>
            {y.ticks(4).map(t => (
              <g key={t} transform={`translate(0,${y(t)})`}>
                <line x2={innerW} stroke="var(--grid)" strokeWidth={1} />
                <text x={-8} dy="0.32em" textAnchor="end" fontSize={11} fill="var(--ink-muted)" className="tabular">{t}</text>
              </g>
            ))}
            <line y1={innerH} y2={innerH} x2={innerW} stroke="var(--axis)" />
            {xLabels.map((label, i) => (
              <text key={label} x={x(i)} y={innerH + 18} textAnchor="middle" fontSize={11} fill="var(--ink-muted)">{label}</text>
            ))}
            {hoverIndex !== null && <line x1={x(hoverIndex)} x2={x(hoverIndex)} y2={innerH} stroke="var(--axis)" />}
            {series.map(s => (
              <path key={s.key} d={line(s.values) ?? ''} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            ))}
            {hoverIndex !== null && series.map(s => (
              <circle key={s.key} cx={x(hoverIndex)} cy={y(s.values[hoverIndex])} r={4} fill={s.color} stroke="var(--surface)" strokeWidth={2} />
            ))}
            {endLabels.map(({ s, y: ly }) => (
              <text key={s.key} x={innerW + 8} y={ly} dy="0.32em" fontSize={11} fill="var(--ink-2)">{s.label}</text>
            ))}
            <rect
              width={innerW}
              height={innerH}
              fill="transparent"
              onMouseMove={e => {
                const [mx] = d3.pointer(e);
                const step = innerW / Math.max(1, xLabels.length - 1);
                setHoverIndex(Math.max(0, Math.min(xLabels.length - 1, Math.round(mx / step))));
                setPointer({ x: e.clientX, y: e.clientY });
              }}
              onMouseLeave={() => setHoverIndex(null)}
            />
          </g>
        </svg>
      )}
      {hoverIndex !== null && (
        <Tooltip x={pointer.x} y={pointer.y}>
          <div className="font-medium mb-1">{xLabels[hoverIndex]}</div>
          {[...series].sort((a, b) => b.values[hoverIndex] - a.values[hoverIndex]).map(s => (
            <div key={s.key} className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ background: s.color }} />
              <span className="text-ink-2 flex-1">{s.label}</span>
              <span className="tabular">{s.values[hoverIndex]}</span>
            </div>
          ))}
        </Tooltip>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- timeline

export interface TimelineRow {
  key: string;
  label: React.ReactNode;
  color: string;
  points: { id: string; date: Date; tooltip: React.ReactNode }[];
}

/** One row per cluster: a hairline span from first to last case, a dot per case. */
export function Timeline({ rows, domain, selected, onSelect }: {
  rows: TimelineRow[]; domain: [Date, Date]; selected?: string | null; onSelect?: (key: string) => void;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<{ content: React.ReactNode; x: number; y: number } | null>(null);
  const labelW = Math.min(260, Math.max(150, width * 0.34));
  const trackW = Math.max(0, width - labelW - 16);
  const x = d3.scaleTime().domain(domain).range([6, trackW - 6]);
  const rowH = 30;
  const months = d3.timeMonth.range(d3.timeMonth.ceil(domain[0]), domain[1]);
  return (
    <div ref={ref} className="w-full">
      {width > 0 && (
        <>
          <div className="relative" style={{ height: 20, marginLeft: labelW + 16 }}>
            {months.map(m => (
              <span key={m.toISOString()} className="absolute text-[11px] text-muted -translate-x-1/2" style={{ left: x(m) }}>
                {d3.timeFormat('%b')(m)}
              </span>
            ))}
          </div>
          {rows.map(row => {
            const dates = row.points.map(p => p.date.getTime());
            const x0 = x(new Date(Math.min(...dates)));
            const x1 = x(new Date(Math.max(...dates)));
            const active = selected === row.key;
            return (
              <div
                key={row.key}
                role="button"
                tabIndex={0}
                onClick={() => onSelect?.(row.key)}
                onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onSelect?.(row.key)}
                className={`flex items-center gap-4 rounded cursor-pointer ${active ? 'bg-hover ring-1 ring-accent' : 'hover:bg-hover'}`}
                style={{ height: rowH }}
              >
                <div className="text-[12px] text-ink truncate pl-1" style={{ width: labelW }}>{row.label}</div>
                <svg width={trackW} height={rowH} className="shrink-0">
                  {months.map(m => <line key={m.toISOString()} x1={x(m)} x2={x(m)} y2={rowH} stroke="var(--grid)" />)}
                  <line x1={x0} x2={x1} y1={rowH / 2} y2={rowH / 2} stroke={row.color} strokeWidth={2} strokeLinecap="round" />
                  {row.points.map(p => (
                    <g key={p.id} onMouseMove={e => setHover({ content: p.tooltip, x: e.clientX, y: e.clientY })} onMouseLeave={() => setHover(null)}>
                      <circle cx={x(p.date)} cy={rowH / 2} r={4} fill={row.color} stroke="var(--surface)" strokeWidth={2} />
                      {/* Hit target larger than the mark. */}
                      <circle cx={x(p.date)} cy={rowH / 2} r={9} fill="transparent" />
                    </g>
                  ))}
                </svg>
              </div>
            );
          })}
        </>
      )}
      {hover && <Tooltip x={hover.x} y={hover.y}>{hover.content}</Tooltip>}
    </div>
  );
}
