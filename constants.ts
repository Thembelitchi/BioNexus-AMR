import { GraphData, NodeType, OrganismData } from './types';

// Mock Knowledge Graph Data simulating clusters of "Superbugs" (CRE, MRSA, C. auris)
export const INITIAL_GRAPH_DATA: GraphData = {
  nodes: [
    // Locations
    { id: 'LOC-ICU', label: 'ICU Ward', type: NodeType.LOCATION, group: 1 },
    { id: 'LOC-BURN', label: 'Burn Unit', type: NodeType.LOCATION, group: 1 },
    { id: 'LOC-ONC', label: 'Oncology', type: NodeType.LOCATION, group: 1 },
    
    // Patients (Cluster 1: MRSA in ICU)
    { id: 'PT-101', label: 'Patient 101', type: NodeType.PATIENT, group: 2 },
    { id: 'PT-102', label: 'Patient 102', type: NodeType.PATIENT, group: 2 },
    
    // Patients (Cluster 2: CRE in Burn Unit)
    { id: 'PT-205', label: 'Patient 205', type: NodeType.PATIENT, group: 2 },
    { id: 'PT-206', label: 'Patient 206', type: NodeType.PATIENT, group: 2 },

    // Patients (Cluster 3: C. auris in Oncology)
    { id: 'PT-309', label: 'Patient 309', type: NodeType.PATIENT, group: 2 },

    // Samples
    { id: 'SMP-A1', label: 'Blood Culture A1', type: NodeType.SAMPLE, group: 3 },
    { id: 'SMP-A2', label: 'Wound Swab A2', type: NodeType.SAMPLE, group: 3 },
    { id: 'SMP-B1', label: 'Sputum B1', type: NodeType.SAMPLE, group: 3 },
    { id: 'SMP-B2', label: 'Urine B2', type: NodeType.SAMPLE, group: 3 },
    { id: 'SMP-C1', label: 'Axillary Swab C1', type: NodeType.SAMPLE, group: 3 },
    
    // Organisms
    { id: 'ORG-MRSA', label: 'S. aureus (MRSA)', type: NodeType.ORGANISM, group: 4 },
    { id: 'ORG-CRE', label: 'K. pneumoniae (CRE)', type: NodeType.ORGANISM, group: 4 },
    { id: 'ORG-CAURIS', label: 'Candida auris', type: NodeType.ORGANISM, group: 4 },

    // Antibiotics
    { id: 'ABX-VAN', label: 'Vancomycin', type: NodeType.ANTIBIOTIC, group: 5 },
    { id: 'ABX-OXA', label: 'Oxacillin', type: NodeType.ANTIBIOTIC, group: 5 },
    { id: 'ABX-MER', label: 'Meropenem', type: NodeType.ANTIBIOTIC, group: 5 },
    { id: 'ABX-CAZ', label: 'Ceftazidime-Avi', type: NodeType.ANTIBIOTIC, group: 5 },
    { id: 'ABX-FLU', label: 'Fluconazole', type: NodeType.ANTIBIOTIC, group: 5 },
    { id: 'ABX-MIC', label: 'Micafungin', type: NodeType.ANTIBIOTIC, group: 5 },
  ],
  links: [
    // Cluster 1: MRSA in ICU
    { source: 'PT-101', target: 'SMP-A1', relationship: 'PROVIDED_SAMPLE' },
    { source: 'SMP-A1', target: 'LOC-ICU', relationship: 'COLLECTED_AT' },
    { source: 'SMP-A1', target: 'ORG-MRSA', relationship: 'IDENTIFIED' },
    
    { source: 'PT-102', target: 'SMP-A2', relationship: 'PROVIDED_SAMPLE' },
    { source: 'SMP-A2', target: 'LOC-ICU', relationship: 'COLLECTED_AT' },
    { source: 'SMP-A2', target: 'ORG-MRSA', relationship: 'IDENTIFIED' },

    { source: 'ORG-MRSA', target: 'ABX-OXA', relationship: 'RESISTANT_TO', details: { mic: '>4', gene: 'mecA' } },
    { source: 'ORG-MRSA', target: 'ABX-VAN', relationship: 'SUSCEPTIBLE_TO', details: { mic: '1.0' } },

    // Cluster 2: CRE (Klebsiella) in Burn Unit
    { source: 'PT-205', target: 'SMP-B1', relationship: 'PROVIDED_SAMPLE' },
    { source: 'SMP-B1', target: 'LOC-BURN', relationship: 'COLLECTED_AT' },
    { source: 'SMP-B1', target: 'ORG-CRE', relationship: 'IDENTIFIED' },

    { source: 'PT-206', target: 'SMP-B2', relationship: 'PROVIDED_SAMPLE' },
    { source: 'SMP-B2', target: 'LOC-BURN', relationship: 'COLLECTED_AT' },
    { source: 'SMP-B2', target: 'ORG-CRE', relationship: 'IDENTIFIED' },
    
    { source: 'ORG-CRE', target: 'ABX-MER', relationship: 'RESISTANT_TO', details: { mic: '>16', gene: 'blaKPC' } },
    { source: 'ORG-CRE', target: 'ABX-CAZ', relationship: 'SUSCEPTIBLE_TO', details: { mic: '2.0' } },

    // Cluster 3: Candida auris in Oncology
    { source: 'PT-309', target: 'SMP-C1', relationship: 'PROVIDED_SAMPLE' },
    { source: 'SMP-C1', target: 'LOC-ONC', relationship: 'COLLECTED_AT' },
    { source: 'SMP-C1', target: 'ORG-CAURIS', relationship: 'IDENTIFIED' },

    { source: 'ORG-CAURIS', target: 'ABX-FLU', relationship: 'RESISTANT_TO', details: { mic: '>256', note: 'Intrinsic' } },
    { source: 'ORG-CAURIS', target: 'ABX-MIC', relationship: 'SUSCEPTIBLE_TO', details: { mic: '0.12' } },
  ]
};

// Knowledge Base for Smart Select - Updated with Superbugs
export const ORGANISM_KB: Record<string, OrganismData> = {
  "Staphylococcus aureus": {
    name: "Staphylococcus aureus",
    type: "Bacteria (Gram +)",
    investigations: ["Coagulase Test", "PCR (mecA gene)", "Latex Agglutination"],
    antibiotics: [
      { name: "Vancomycin", class: "Glycopeptide", note: "First-line for MRSA", resistanceLikelihood: "Low" },
      { name: "Linezolid", class: "Oxazolidinone", note: "Oral option for resistant strains", resistanceLikelihood: "Low" },
      { name: "Oxacillin", class: "Penicillin", note: "Marker for MRSA resistance", resistanceLikelihood: "High" },
      { name: "Daptomycin", class: "Lipopeptide", note: "Alternative for bacteremia", resistanceLikelihood: "Low" }
    ],
    alert: "High risk of MRSA. Check mecA gene status."
  },
  "Pseudomonas aeruginosa": {
    name: "Pseudomonas aeruginosa",
    type: "Bacteria (Gram -)",
    investigations: ["Oxidase Test", "Pigment Production", "Biofilm Assay"],
    antibiotics: [
      { name: "Piperacillin-Tazobactam", class: "Beta-lactam", note: "Standard anti-pseudomonal", resistanceLikelihood: "Medium" },
      { name: "Ceftazidime", class: "Cephalosporin", note: "Watch for ESBLs", resistanceLikelihood: "Medium" },
      { name: "Colistin", class: "Polymyxin", note: "Reserve for MDR strains", resistanceLikelihood: "Low" },
      { name: "Ampicillin", class: "Penicillin", note: "Intrinsic Resistance", resistanceLikelihood: "Intrinsic" }
    ],
    alert: "Intrinsic resistance to many standard antibiotics."
  },
  "Klebsiella pneumoniae": {
    name: "Klebsiella pneumoniae",
    type: "Bacteria (Gram -)",
    investigations: ["String Test (Hypermucoviscosity)", "Modified Hodge Test", "CarbaNP"],
    antibiotics: [
      { name: "Meropenem", class: "Carbapenem", note: "Key indicator for CRE", resistanceLikelihood: "High" },
      { name: "Ceftazidime-Avibactam", class: "BL/BLI", note: "Effective against KPC producers", resistanceLikelihood: "Low" },
      { name: "Colistin", class: "Polymyxin", note: "Last-resort for NDM strains", resistanceLikelihood: "Low" },
      { name: "Tigecycline", class: "Glycylcycline", note: "Tissue infections only", resistanceLikelihood: "Medium" }
    ],
    alert: "CRITICAL: Potential CRE (Carbapenem-Resistant Enterobacterales)."
  },
  "Neisseria gonorrhoeae": {
    name: "Neisseria gonorrhoeae",
    type: "Bacteria (Gram -)",
    investigations: ["NAAT", "Gram Stain (Diplococci)", "Sugar Utilization"],
    antibiotics: [
      { name: "Ceftriaxone", class: "Cephalosporin", note: "Primary therapy", resistanceLikelihood: "Medium" },
      { name: "Azithromycin", class: "Macrolide", note: "Dual therapy partner", resistanceLikelihood: "High" },
      { name: "Ciprofloxacin", class: "Fluoroquinolone", note: "High resistance rates", resistanceLikelihood: "High" }
    ],
    alert: "Monitor for Ceftriaxone 'Alert' values (MIC > 0.125)."
  },
  "Candida auris": {
    name: "Candida auris",
    type: "Fungi",
    investigations: ["MALDI-TOF", "D1/D2 Sequencing", "Germ Tube (Negative)"],
    antibiotics: [
      { name: "Fluconazole", class: "Azole", note: "Intrinsic Resistance likely", resistanceLikelihood: "Intrinsic" },
      { name: "Micafungin", class: "Echinocandin", note: "First-line recommendation", resistanceLikelihood: "Low" },
      { name: "Amphotericin B", class: "Polyene", note: "Nephrotoxic; variable susceptibility", resistanceLikelihood: "Medium" }
    ],
    alert: "GLOBAL THREAT: Often multidrug resistant and persistent in environments."
  }
};
