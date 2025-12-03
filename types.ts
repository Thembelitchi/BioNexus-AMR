import { SimulationNodeDatum, SimulationLinkDatum } from 'd3';

// Data Models
export enum NodeType {
  PATIENT = 'PATIENT',
  SAMPLE = 'SAMPLE',
  ORGANISM = 'ORGANISM',
  ANTIBIOTIC = 'ANTIBIOTIC',
  LOCATION = 'LOCATION'
}

export interface GraphNode extends SimulationNodeDatum {
  id: string;
  label: string;
  type: NodeType;
  group?: number;
  details?: Record<string, any>;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

export interface GraphLink extends SimulationLinkDatum<GraphNode> {
  source: string | GraphNode;
  target: string | GraphNode;
  relationship: string;
  details?: Record<string, any>;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface AntibioticInfo {
  name: string;
  class: string;
  note: string;
  resistanceLikelihood: 'Low' | 'Medium' | 'High' | 'Intrinsic';
}

export interface OrganismData {
  name: string;
  type: 'Bacteria (Gram +)' | 'Bacteria (Gram -)' | 'Fungi' | 'Virus';
  investigations: string[];
  antibiotics: AntibioticInfo[];
  alert?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'model';
  content: string;
  timestamp: Date;
  isThinking?: boolean;
  groundingMetadata?: any; // For Google Search citations
  attachment?: {
    name: string;
    type: string;
    data: string; // Base64
  };
}