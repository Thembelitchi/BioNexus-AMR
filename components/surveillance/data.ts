// Snapshot of the backend's output (backend/tools/export_site_snapshot.py).

export type SIR = 'S' | 'I' | 'SDD' | 'R';

export type Aware = 'Access' | 'Watch' | 'Reserve';

export interface AstResult {
  drug: string;
  atc: string;
  aware: Aware | null;
  sir: SIR;
  method: 'MIC' | 'DISK' | null;
  mic: number | null;
  q: '=' | '<' | '<=' | '>' | '>=' | null;
  zone: number | null;
}

export interface GeneCall {
  symbol: string;
  category: string;
  aro: string;
  carrier: string | null;
  context: string;
}

export interface Isolate {
  id: string;
  patient: string;
  sex: 'F' | 'M' | 'U' | null;
  age: number | null;
  ageBand: string | null;
  encounter: string;
  collected: string;
  facility: string | null;
  ward: string;
  wardName: string;
  specimen: string;
  species: string;
  taxid: number;
  labels: string[];
  genotype: 'not_sequenced' | 'no_determinant_detected' | 'determinants_detected';
  st: string | null;
  clone: string | null;
  treatments: string[];
  treatmentAware: (Aware | null)[];
  ast: AstResult[];
  genes: GeneCall[];
}

export interface Cluster {
  ward: string;
  facility: string | null;
  sequence_type: string;
  clone_designation: string | null;
  gene_aro_id: string;
  gene: string;
  size: number;
  first_collected: string;
  last_collected: string;
  members: { isolate_id: string; patient_id: string; collected: string }[];
}

export interface PhenotypicCluster {
  ward: string;
  facility: string | null;
  species: string;
  phenotype: string;
  size: number;
  sequenced: number;
  sequence_types: string[];
  first_collected: string;
  last_collected: string;
  members: { isolate_id: string; patient_id: string; collected: string; sequence_type: string | null }[];
}

export interface PrescribingRow {
  facility: string | null;
  drug: string;
  atc_code: string;
  aware: Aware | null;
  encounters: number;
  resistant_encounters: number;
}

export interface HgtSignal {
  gene_aro_id: string;
  gene: string;
  level: 'species' | 'genus';
  taxa: string[];
  isolate_count: number;
  wards: string[];
  replicons: string[];
  first_collected: string;
  last_collected: string;
}

export interface WardCentrality {
  ward: string;
  facility: string | null;
  pagerank: number;
  betweenness: number;
  weighted_degree: number;
  isolates: number;
}

export interface WardEdge {
  source: string;
  target: string;
  transfers: number;
  genomic: number;
}

export interface Alert {
  rule: string;
  severity: 'critical' | 'high';
  title: string;
  detail: string;
  isolate_id: string;
  patient_id: string;
  ward: string;
  facility: string | null;
  collected: string;
  species: string;
}

export interface Scenario {
  title: string;
  facility: string;
  ward: string;
  period: [string, string];
  patients: number | null;
  expect: Record<string, any>;
}

export interface Facility {
  code: string;
  name: string;
  province: string;
  wards: { key: string; name: string }[];
}

export interface Snapshot {
  meta: { title: string; generatedAt: string; dataset: string; guideline: string; windowDays: number; neo4j: string | null; gds: string | null; pseudonymised: boolean };
  facilities: Facility[];
  isolates: Isolate[];
  clusters: Cluster[];
  phenotypicClusters: PhenotypicCluster[];
  phenotypeRules: { flag: string; meaning: string }[];
  prescribing: PrescribingRow[];
  hgt: { species: HgtSignal[]; genus: HgtSignal[] };
  wardNetwork: { window_days: number; edges: number; transfer_links: number; genomic_links: number; wards: WardCentrality[]; links: WardEdge[] };
  alerts: Alert[];
  alertRules: Record<string, { severity: 'critical' | 'high'; title: string }>;
  scenarios: Record<string, Scenario>;
  verification: { title: string; verified: number; total: number }[];
}

export async function loadSnapshot(): Promise<Snapshot> {
  // Relative to the page so the site works under any GitHub Pages path.
  const response = await fetch(new URL('data/snapshot.json', document.baseURI));
  if (!response.ok) throw new Error(`could not load data/snapshot.json (${response.status})`);
  return response.json();
}

// --------------------------------------------------------------------------- helpers

export const shortSpecies = (species: string) => {
  const [genus, epithet] = species.split(' ');
  return `${genus[0]}. ${epithet}`;
};

export const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-ZA', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Africa/Johannesburg' });

export const formatMic = (t: AstResult) => {
  if (t.mic !== null) return `${t.q && t.q !== '=' ? t.q : ''}${t.mic} mg/L`;
  if (t.zone !== null) return `${t.zone} mm`;
  return '—';
};

export const formatAge = (i: Isolate) => {
  if (i.age !== null) return i.age < 1 ? `${Math.round(i.age * 365.25)} days` : `${i.age} years`;
  return i.ageBand ?? 'age unknown';
};

export const monthKey = (iso: string) => {
  const d = new Date(iso);
  const sast = new Date(d.getTime() + 2 * 3600 * 1000);
  return `${sast.getUTCFullYear()}-${String(sast.getUTCMonth() + 1).padStart(2, '0')}`;
};

// The flag a clinician reads first for each organism, as the laboratory reports it.
export const KEY_FLAG: Record<string, string> = {
  'Klebsiella pneumoniae': 'CRE',
  'Escherichia coli': 'CRE',
  'Enterobacter cloacae': 'CRE',
  'Acinetobacter baumannii': 'CRAB',
  'Pseudomonas aeruginosa': 'CRPA',
  'Staphylococcus aureus': 'MRSA',
  'Enterococcus faecium': 'VRE',
};

export const FLAG_MEANING: Record<string, string> = {
  CRE: 'carbapenem-resistant Enterobacterales',
  CRAB: 'carbapenem-resistant A. baumannii',
  CRPA: 'carbapenem-resistant P. aeruginosa',
  MRSA: 'methicillin-resistant S. aureus',
  VRE: 'vancomycin-resistant enterococci',
  ESBL: 'extended-spectrum beta-lactamase phenotype',
};

export const wardLabel = (key: string) => key.replace(':', ' · ');
