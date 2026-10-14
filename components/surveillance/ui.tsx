import React, { useEffect, useRef, useState } from 'react';
import { AlertOctagon, AlertTriangle } from 'lucide-react';
import { SIR } from './data';

// Color follows the entity: each facility keeps its slot under every filter.
export const FACILITY_COLOR: Record<string, string> = {
  GAH: 'var(--series-1)',
  GDH: 'var(--series-2)',
  KRH: 'var(--series-3)',
  WTH: 'var(--series-4)',
};
export const facilityColor = (code: string | null | undefined) => (code && FACILITY_COLOR[code]) || 'var(--ink-muted)';

export function Card({ title, subtitle, actions, children, className = '' }: {
  title?: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={`bg-surface border border-line rounded-xl p-4 sm:p-5 min-w-0 ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="text-[13px] text-ink-2 mt-0.5">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function StatTile({ label, value, note }: { label: string; value: React.ReactNode; note?: React.ReactNode }) {
  return (
    <div className="h-full bg-surface border border-line rounded-xl px-4 py-3 min-w-0">
      <div className="text-[12px] text-ink-2">{label}</div>
      <div className="text-[28px] leading-9 font-semibold text-ink mt-1">{value}</div>
      {note && <div className="text-[12px] text-muted mt-0.5">{note}</div>}
    </div>
  );
}

export function Chips<T extends string>({ options, value, onChange, label }: {
  options: { value: T; label: string; count?: number; color?: string }[]; value: T; onChange: (v: T) => void; label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-1.5">
      {options.map(o => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={`inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full text-[12px] border transition-colors ${
              active ? 'border-accent text-ink bg-hover font-medium' : 'border-line text-ink-2 hover:bg-hover'
            }`}
          >
            {o.color && <span className="w-2 h-2 rounded-full" style={{ background: o.color }} />}
            {o.label}
            {o.count !== undefined && <span className="text-muted tabular">{o.count}</span>}
          </button>
        );
      })}
    </div>
  );
}

const SIR_STYLE: Record<SIR, { bg: string; label: string }> = {
  S: { bg: 'var(--status-good)', label: 'Susceptible' },
  SDD: { bg: 'var(--status-warning)', label: 'Susceptible-dose-dependent' },
  I: { bg: 'var(--status-warning)', label: 'Intermediate' },
  R: { bg: 'var(--status-critical)', label: 'Resistant' },
};

export function SirBadge({ sir }: { sir: SIR }) {
  const style = SIR_STYLE[sir];
  return (
    <span title={style.label} className="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink">
      <span className="w-2 h-2 rounded-sm" style={{ background: style.bg }} aria-hidden />
      {sir}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: 'critical' | 'high' }) {
  const Icon = severity === 'critical' ? AlertOctagon : AlertTriangle;
  const color = severity === 'critical' ? 'var(--status-critical)' : 'var(--status-serious)';
  return (
    <span className="inline-flex items-center gap-1 text-[12px] font-medium text-ink whitespace-nowrap">
      <Icon className="w-3.5 h-3.5" style={{ color }} aria-hidden />
      {severity === 'critical' ? 'Critical' : 'High'}
    </span>
  );
}

const AWARE_STYLE: Record<string, string> = {
  Access: 'var(--status-good)',
  Watch: 'var(--status-warning)',
  Reserve: 'var(--status-critical)',
};

/** WHO AWaRe group, always shown as text with a colour cue. */
export function AwareTag({ group }: { group: string | null | undefined }) {
  if (!group) return <span className="text-[11px] text-muted" title="Not classified">—</span>;
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-ink-2 whitespace-nowrap" title={`WHO AWaRe: ${group}`}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: AWARE_STYLE[group] }} aria-hidden />
      {group}
    </span>
  );
}

export function Tag({ children, color }: { children: React.ReactNode; color?: string }) {
  return (
    <span className="inline-flex items-center gap-1 h-5 px-1.5 rounded text-[11px] font-medium border border-line text-ink-2 whitespace-nowrap">
      {color && <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />}
      {children}
    </span>
  );
}

export function FacilityDot({ code }: { code: string | null }) {
  return <span className="inline-block w-2 h-2 rounded-full shrink-0" style={{ background: facilityColor(code) }} aria-hidden />;
}

// Floating tooltip positioned near the pointer, kept inside the viewport.
export function Tooltip({ x, y, children }: { x: number; y: number; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: x + 14, top: y + 14 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    const left = x + 14 + width > window.innerWidth - 8 ? x - width - 14 : x + 14;
    const top = y + 14 + height > window.innerHeight - 8 ? y - height - 14 : y + 14;
    setPos({ left: Math.max(8, left), top: Math.max(8, top) });
  }, [x, y]);
  return (
    <div
      ref={ref}
      role="tooltip"
      style={{ position: 'fixed', left: pos.left, top: pos.top, zIndex: 50 }}
      className="pointer-events-none bg-raised border border-line rounded-lg shadow-lg px-3 py-2 text-[12px] text-ink max-w-xs"
    >
      {children}
    </div>
  );
}

export function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const observer = new ResizeObserver(entries => setWidth(entries[0].contentRect.width));
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

export function Table({ head, children, dense = false }: { head: React.ReactNode[]; children: React.ReactNode; dense?: boolean }) {
  return (
    <div className="overflow-x-auto -mx-1">
      <table className="w-full text-[13px] border-collapse">
        <thead>
          <tr className="text-left text-ink-2 border-b border-line">
            {head.map((h, i) => (
              <th key={i} className={`font-medium px-1 ${dense ? 'py-1.5' : 'py-2'} whitespace-nowrap`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="tabular">{children}</tbody>
      </table>
    </div>
  );
}
