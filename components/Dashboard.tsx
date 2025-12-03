
import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Cell,
  LineChart, Line, PieChart, Pie, Legend
} from 'recharts';
import { 
    Activity, ShieldAlert, Users, LayoutDashboard, Network, UploadCloud, 
    Link as LinkIcon, ArrowRight, ArrowLeft, Microscope, Search, Dna, 
    Pill, ScanEye, CheckCircle2, FileText, AlertTriangle, RefreshCw, FileUp
} from 'lucide-react';
import KnowledgeGraph from './KnowledgeGraph';
import SmartSelect from './SmartSelect';
import AgentInterface from './AgentInterface';
import GenomicPredictor from './GenomicPredictor';
import { INITIAL_GRAPH_DATA, INITIAL_GENOMIC_DATA } from '../constants';
import { GraphNode, GraphData, NodeType, GenomicData, SurveillanceData } from '../types';

const Dashboard: React.FC = () => {
  type TabType = 'surveillance' | 'graph' | 'visual_dx' | 'genomics' | 'stewardship';
  const [activeTab, setActiveTab] = useState<TabType>('surveillance');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [graphData, setGraphData] = useState<GraphData>(INITIAL_GRAPH_DATA);
  const [genomicData, setGenomicData] = useState<GenomicData[]>(INITIAL_GENOMIC_DATA);
  const [surveillanceData, setSurveillanceData] = useState<SurveillanceData[] | null>(null);
  const [showToast, setShowToast] = useState<{message: string, type: 'success' | 'info'} | null>(null);
  
  const labInputRef = useRef<HTMLInputElement>(null);
  const geneInputRef = useRef<HTMLInputElement>(null);
  const surveillanceInputRef = useRef<HTMLInputElement>(null);

  // Auto-hide toast
  useEffect(() => {
    if (showToast) {
      const timer = setTimeout(() => setShowToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [showToast]);

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
  }, []);

  const triggerToast = (message: string, type: 'success' | 'info' = 'success') => {
    setShowToast({ message, type });
  };

  // --- DATA INGESTION HANDLERS ---

  const handleLabUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (event) => {
        const text = event.target?.result as string;
        processLabCSV(text);
    };
    reader.readAsText(file);
    e.target.value = ''; // Reset
  };

  const handleGenomicUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
        const text = event.target?.result as string;
        processGenomicCSV(text);
    };
    reader.readAsText(file);
    e.target.value = ''; // Reset
  };

  const handleSurveillanceUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
        const text = event.target?.result as string;
        processSurveillanceCSV(text);
    };
    reader.readAsText(file);
    e.target.value = ''; // Reset
  };

  const handleResetData = () => {
    setSurveillanceData(null);
    if (surveillanceInputRef.current) surveillanceInputRef.current.value = '';
    triggerToast("Data Cleared. Ready for new upload.", 'info');
  };

  const processSurveillanceCSV = (csvText: string) => {
    try {
      const lines = csvText.split('\n');
      const headers = lines[0].split(',').map(h => h.trim());
      const data: SurveillanceData[] = [];

      for (let i = 1; i < lines.length; i++) {
        const currentLine = lines[i].split(',');
        if (currentLine.length === headers.length) {
          const row: any = {};
          headers.forEach((header, index) => {
            row[header] = currentLine[index].trim();
          });
          data.push(row as SurveillanceData);
        }
      }
      setSurveillanceData(data);
      triggerToast(`Loaded ${data.length} records successfully! ✅`, 'success');
    } catch (e) {
      console.error(e);
      triggerToast("Error parsing CSV file.", 'info');
    }
  };

  const processLabCSV = (csvText: string) => {
      // Logic for Graph Data (Nodes/Links)
      try {
        triggerToast("Lab Data Ingested into Graph! ✅", 'success');
        // In a real app, this would parse into nodes/links. 
        // For this demo, we assume the user might also want to populate the Surveillance dashboard
        if (!surveillanceData) {
            processSurveillanceCSV(csvText);
        }
      } catch (e) {
        console.error(e);
      }
  };

  const processGenomicCSV = (csvText: string) => {
    try {
        const lines = csvText.split('\n');
        const newGenomicRecords: GenomicData[] = [];
        
        // Skip header
        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;
            const [sampleId, geneDetected, mechanism, clinicalImpact] = line.split(',').map(s => s.trim());
            
            if (sampleId && geneDetected) {
                newGenomicRecords.push({ sampleId, geneDetected, mechanism, clinicalImpact });
                
                // --- GRAPH MERGE LOGIC ---
                setGraphData(prev => {
                    const newNodes = [...prev.nodes];
                    const newLinks = [...prev.links];
                    
                    // 1. Find Sample Node
                    const sampleNode = newNodes.find(n => n.id === sampleId);
                    
                    if (sampleNode) {
                        // 2. Create Gene Node
                        const geneId = `GENE-${geneDetected}`;
                        if (!newNodes.some(n => n.id === geneId)) {
                            newNodes.push({
                                id: geneId,
                                label: geneDetected,
                                type: NodeType.GENE,
                                group: 6,
                                details: { mechanism, clinicalImpact }
                            });
                        }
                        
                        // 3. Link Sample to Gene
                        if (!newLinks.some(l => 
                            ((l.source as GraphNode).id === sampleId || l.source === sampleId) && 
                            ((l.target as GraphNode).id === geneId || l.target === geneId)
                        )) {
                            newLinks.push({
                                source: sampleId,
                                target: geneId,
                                relationship: 'DETECTED_GENE'
                            });
                        }
                    }
                    return { nodes: newNodes, links: newLinks };
                });
            }
        }
        
        setGenomicData(prev => [...prev, ...newGenomicRecords]);
        triggerToast("Genomic Sequences Indexed! ✅", 'success');
    } catch (e) {
        console.error(e);
        alert("Failed to parse Genomic CSV");
    }
  };

  // --- ANALYTICS CALCULATIONS ---

  const analytics = useMemo(() => {
    if (!surveillanceData) return null;

    const totalCases = new Set(surveillanceData.map(d => d.PatientID)).size;
    
    // Critical Alerts: High risk phenotypes
    const criticalPhenotypes = ['CRE', 'MRSA', 'VRE', 'Candida auris', 'Pan-Resistant', 'KPC-Producer', 'NDM-1'];
    const criticalCount = surveillanceData.filter(d => 
        criticalPhenotypes.some(p => d.Phenotype && d.Phenotype.includes(p))
    ).length;

    const activeWards = new Set(surveillanceData.map(d => d.Ward)).size;
    
    const totalTests = surveillanceData.length;
    const resistantTests = surveillanceData.filter(d => d.Result === 'R').length;
    const resistanceRate = totalTests ? Math.round((resistantTests / totalTests) * 100) : 0;

    // Chart 1: Trends (Group by Date)
    const trendsMap = new Map<string, number>();
    surveillanceData.forEach(d => {
        if (d.Result === 'R') {
            const date = d.Date; // Assuming YYYY-MM-DD
            trendsMap.set(date, (trendsMap.get(date) || 0) + 1);
        }
    });
    const trendsData = Array.from(trendsMap.entries())
        .map(([date, count]) => ({ date, resistantCases: count }))
        .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

    // Chart 2: Organism Distribution
    const orgMap = new Map<string, number>();
    surveillanceData.forEach(d => {
        orgMap.set(d.Organism, (orgMap.get(d.Organism) || 0) + 1);
    });
    const orgData = Array.from(orgMap.entries())
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value);

    // Chart 3: Ward Burden
    const wardMap = new Map<string, number>();
    surveillanceData.forEach(d => {
        wardMap.set(d.Ward, (wardMap.get(d.Ward) || 0) + 1);
    });
    const wardData = Array.from(wardMap.entries())
        .map(([name, cases]) => ({ name, cases }))
        .sort((a, b) => b.cases - a.cases);

    // Chart 4: Heatmap Matrix (Organism vs Antibiotic % Resistance)
    // Structure: { organism: "E.coli", "Amoxicillin": 80, "Cipro": 20 ... }
    const matrixMap = new Map<string, { total: number, abx: Map<string, {total: number, r: number}> }>();
    
    surveillanceData.forEach(d => {
        if (!matrixMap.has(d.Organism)) {
            matrixMap.set(d.Organism, { total: 0, abx: new Map() });
        }
        const orgEntry = matrixMap.get(d.Organism)!;
        orgEntry.total++;

        if (!orgEntry.abx.has(d.Antibiotic)) {
            orgEntry.abx.set(d.Antibiotic, { total: 0, r: 0 });
        }
        const abxEntry = orgEntry.abx.get(d.Antibiotic)!;
        abxEntry.total++;
        if (d.Result === 'R') abxEntry.r++;
    });

    const heatmapData: any[] = [];
    const antibioticsList = new Set<string>();

    matrixMap.forEach((data, org) => {
        const row: any = { name: org };
        data.abx.forEach((stats, abx) => {
            row[abx] = Math.round((stats.r / stats.total) * 100);
            antibioticsList.add(abx);
        });
        heatmapData.push(row);
    });

    return {
        totalCases,
        criticalCount,
        activeWards,
        resistanceRate,
        trendsData,
        orgData,
        wardData,
        heatmapData,
        antibioticsList: Array.from(antibioticsList).sort()
    };

  }, [surveillanceData]);

  // --- RENDERING HELPERS ---

  const getNeighbors = (node: GraphNode) => {
    return graphData.links
      .filter(link => {
        const sourceId = typeof link.source === 'object' ? (link.source as GraphNode).id : link.source;
        const targetId = typeof link.target === 'object' ? (link.target as GraphNode).id : link.target;
        return sourceId === node.id || targetId === node.id;
      })
      .map(link => {
        const sourceId = typeof link.source === 'object' ? (link.source as GraphNode).id : link.source;
        const targetId = typeof link.target === 'object' ? (link.target as GraphNode).id : link.target;
        const isSource = sourceId === node.id;
        const neighborId = isSource ? targetId : sourceId;
        const neighborNode = graphData.nodes.find(n => n.id === neighborId);
        
        return {
          relationship: link.relationship,
          direction: isSource ? 'outgoing' : 'incoming',
          neighbor: neighborNode
        };
      });
  };

  const neighbors = selectedNode ? getNeighbors(selectedNode) : [];

  const getNodeProperties = (node: GraphNode) => {
    const ignoredKeys = ['index', 'x', 'y', 'vx', 'vy', 'fx', 'fy', 'group', 'label', 'type'];
    return Object.entries(node).filter(([key]) => !ignoredKeys.includes(key) && key !== 'details')
      .concat(node.details ? Object.entries(node.details) : []);
  };

  const COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#ec4899'];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row font-sans">
      
      {/* TOAST NOTIFICATION */}
      {showToast && (
        <div className="fixed top-5 right-5 z-[100] animate-fade-in-up">
            <div className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg border-l-4 ${
                showToast.type === 'success' ? 'bg-white border-emerald-500 text-slate-800' : 'bg-blue-600 text-white border-blue-800'
            }`}>
                {showToast.type === 'success' ? <CheckCircle2 className="w-5 h-5 text-emerald-500" /> : <Activity className="w-5 h-5" />}
                <span className="font-medium text-sm">{showToast.message}</span>
            </div>
        </div>
      )}

      {/* SIDEBAR */}
      <aside className="w-full md:w-64 bg-slate-900 text-slate-300 flex-shrink-0 flex flex-col h-auto md:h-screen sticky top-0 z-50">
        <div className="p-6 border-b border-slate-800">
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Dna className="text-violet-500 w-6 h-6" />
            BioNexus 2026
          </h1>
          <p className="text-[10px] text-slate-500 mt-1 uppercase tracking-widest">Genomic Surveillance Engine</p>
        </div>
        
        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          <div className="text-xs font-bold text-slate-500 uppercase px-4 mb-2 mt-2">Core Modules</div>
          <button onClick={() => setActiveTab('surveillance')} className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors text-sm ${activeTab === 'surveillance' ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30' : 'hover:bg-slate-800'}`}>
            <LayoutDashboard className="w-4 h-4" /> Surveillance
          </button>
          <button onClick={() => setActiveTab('graph')} className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors text-sm ${activeTab === 'graph' ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30' : 'hover:bg-slate-800'}`}>
            <Network className="w-4 h-4" /> Graph Explorer
          </button>

          <div className="text-xs font-bold text-slate-500 uppercase px-4 mb-2 mt-6">2026 Upgrades</div>
          <button onClick={() => setActiveTab('visual_dx')} className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors text-sm ${activeTab === 'visual_dx' ? 'bg-violet-600/20 text-violet-400 border border-violet-600/30' : 'hover:bg-slate-800'}`}>
            <ScanEye className="w-4 h-4" /> Visual Diagnostics
          </button>
          <button onClick={() => setActiveTab('genomics')} className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors text-sm ${activeTab === 'genomics' ? 'bg-violet-600/20 text-violet-400 border border-violet-600/30' : 'hover:bg-slate-800'}`}>
            <Dna className="w-4 h-4" /> Genotype Predictor
          </button>
          <button onClick={() => setActiveTab('stewardship')} className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors text-sm ${activeTab === 'stewardship' ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-600/30' : 'hover:bg-slate-800'}`}>
            <Pill className="w-4 h-4" /> Stewardship AI
          </button>
        </nav>

        {/* Data Ingestion Section */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/50">
           <h4 className="text-xs font-bold text-slate-500 uppercase mb-3 flex items-center gap-2">
              <UploadCloud className="w-3 h-3" /> Data Ingestion
           </h4>
           
           <div className="space-y-3">
              {/* Lab Upload */}
              <div className="relative group cursor-pointer" onClick={() => labInputRef.current?.click()}>
                 <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 hover:border-blue-500 transition-colors flex items-center justify-between">
                    <div>
                        <p className="text-xs font-bold text-slate-300">Phenotypic Data</p>
                        <p className="text-[10px] text-slate-500">Upload CSV</p>
                    </div>
                    {graphData.nodes.length > INITIAL_GRAPH_DATA.nodes.length ? <CheckCircle2 className="w-4 h-4 text-emerald-500" /> : <div className="w-2 h-2 rounded-full bg-slate-600" />}
                 </div>
                 <input type="file" ref={labInputRef} onChange={handleLabUpload} accept=".csv" className="hidden" />
              </div>

              {/* Genomic Upload */}
              <div className="relative group cursor-pointer" onClick={() => geneInputRef.current?.click()}>
                 <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 hover:border-violet-500 transition-colors flex items-center justify-between">
                    <div>
                        <p className="text-xs font-bold text-slate-300">Genomic Data</p>
                        <p className="text-[10px] text-slate-500">Upload CSV</p>
                    </div>
                    {genomicData.length > INITIAL_GENOMIC_DATA.length ? <CheckCircle2 className="w-4 h-4 text-emerald-500" /> : <div className="w-2 h-2 rounded-full bg-slate-600" />}
                 </div>
                 <input type="file" ref={geneInputRef} onChange={handleGenomicUpload} accept=".csv" className="hidden" />
              </div>
           </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-4 md:p-8 overflow-y-auto overflow-x-hidden h-screen bg-slate-50/50">
        
        {/* SURVEILLANCE */}
        {activeTab === 'surveillance' && (
          <div className="space-y-6 animate-fade-in">
            <header className="flex justify-between items-center mb-6">
              <div>
                <h2 className="text-2xl font-bold text-slate-800">Live Surveillance Hub</h2>
                <p className="text-slate-500">Real-time monitoring of phenotypic and genotypic trends.</p>
              </div>
              {analytics && (
                <button 
                  onClick={handleResetData}
                  className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 text-slate-600 rounded-lg hover:bg-slate-50 hover:text-blue-600 transition-colors shadow-sm text-sm"
                >
                  <RefreshCw className="w-4 h-4" /> Refresh Data
                </button>
              )}
            </header>

            {!analytics ? (
              // Empty State
              <div className="flex flex-col items-center justify-center h-[60vh] bg-white rounded-xl border-2 border-dashed border-slate-200">
                <div className="bg-blue-50 p-6 rounded-full mb-4">
                  <FileUp className="w-12 h-12 text-blue-500" />
                </div>
                <h3 className="text-xl font-bold text-slate-800">No Surveillance Data Loaded</h3>
                <p className="text-slate-500 max-w-md text-center mt-2 mb-6">
                  Upload a <code>patient_data.csv</code> file to generate live analytics, trends, and resistance heatmaps.
                </p>
                <div className="relative">
                  <button 
                    onClick={() => surveillanceInputRef.current?.click()}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 rounded-xl font-medium shadow-lg shadow-blue-200 transition-all flex items-center gap-2"
                  >
                    <UploadCloud className="w-5 h-5" /> Upload CSV Data
                  </button>
                  <input 
                    type="file" 
                    ref={surveillanceInputRef} 
                    onChange={handleSurveillanceUpload} 
                    accept=".csv" 
                    className="hidden" 
                  />
                </div>
                <p className="text-xs text-slate-400 mt-4">Supported Format: CSV (PatientID, Organism, Antibiotic, Result...)</p>
              </div>
            ) : (
              // Dashboard Content
              <>
                {/* Row 1: KPI Cards */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                  <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                     <div className="flex items-center justify-between mb-2">
                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Active Cases</h3>
                        <Users className="w-5 h-5 text-blue-500" />
                     </div>
                     <p className="text-3xl font-bold text-slate-800">{analytics.totalCases}</p>
                     <p className="text-xs text-slate-500 mt-1">Unique Patients</p>
                  </div>
                  <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                     <div className="flex items-center justify-between mb-2">
                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Critical Alerts</h3>
                        <ShieldAlert className="w-5 h-5 text-rose-500" />
                     </div>
                     <p className="text-3xl font-bold text-slate-800">{analytics.criticalCount}</p>
                     <p className="text-xs text-slate-500 mt-1">High-Risk Phenotypes</p>
                  </div>
                  <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                     <div className="flex items-center justify-between mb-2">
                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Active Wards</h3>
                        <LayoutDashboard className="w-5 h-5 text-amber-500" />
                     </div>
                     <p className="text-3xl font-bold text-slate-800">{analytics.activeWards}</p>
                     <p className="text-xs text-slate-500 mt-1">Reporting Locations</p>
                  </div>
                  <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                     <div className="flex items-center justify-between mb-2">
                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Resistance Rate</h3>
                        <Activity className="w-5 h-5 text-violet-500" />
                     </div>
                     <p className="text-3xl font-bold text-slate-800">{analytics.resistanceRate}%</p>
                     <p className="text-xs text-slate-500 mt-1">Overall Positivity</p>
                  </div>
                </div>

                {/* Row 2: Trends & Distribution */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  <div className="lg:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 className="text-lg font-bold text-slate-800 mb-6">Resistance Trends Over Time</h3>
                    <div className="h-72">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={analytics.trendsData}>
                           <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                           <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{fill: '#94a3b8', fontSize: 12}} />
                           <YAxis axisLine={false} tickLine={false} tick={{fill: '#94a3b8', fontSize: 12}} />
                           <RechartsTooltip contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}} />
                           <Line type="monotone" dataKey="resistantCases" stroke="#3b82f6" strokeWidth={3} dot={{fill: '#3b82f6', r: 4}} activeDot={{r: 6}} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                  
                  <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 className="text-lg font-bold text-slate-800 mb-6">Pathogen Distribution</h3>
                    <div className="h-72">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie 
                            data={analytics.orgData} 
                            dataKey="value" 
                            nameKey="name" 
                            cx="50%" 
                            cy="50%" 
                            innerRadius={60} 
                            outerRadius={80} 
                            paddingAngle={5}
                          >
                            {analytics.orgData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <RechartsTooltip />
                          <Legend verticalAlign="bottom" height={36} iconType="circle" />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>

                {/* Row 3: Heatmap & Ward Burden */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                   {/* Custom Heatmap Table */}
                   <div className="lg:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-slate-200 overflow-x-auto">
                      <h3 className="text-lg font-bold text-slate-800 mb-4">Antibiotic Resistance Matrix (%)</h3>
                      <table className="w-full text-sm text-center">
                        <thead>
                          <tr className="border-b border-slate-100">
                             <th className="text-left py-3 px-2 font-bold text-slate-500">Organism</th>
                             {analytics.antibioticsList.map(abx => (
                               <th key={abx} className="py-3 px-2 font-medium text-slate-500 text-xs uppercase">{abx.substring(0, 3)}</th>
                             ))}
                          </tr>
                        </thead>
                        <tbody>
                           {analytics.heatmapData.map((row, i) => (
                             <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                               <td className="text-left py-3 px-2 font-medium text-slate-700">{row.name}</td>
                               {analytics.antibioticsList.map(abx => {
                                 const val = row[abx];
                                 let bgColor = 'bg-slate-50';
                                 let textColor = 'text-slate-400';
                                 
                                 if (val !== undefined) {
                                    if (val >= 50) { bgColor = 'bg-rose-100'; textColor = 'text-rose-700'; }
                                    else if (val >= 20) { bgColor = 'bg-amber-100'; textColor = 'text-amber-700'; }
                                    else { bgColor = 'bg-emerald-50'; textColor = 'text-emerald-700'; }
                                 }

                                 return (
                                   <td key={abx} className="p-1">
                                      <div className={`w-full h-8 flex items-center justify-center rounded ${val !== undefined ? bgColor : ''}`}>
                                        <span className={`text-xs font-bold ${textColor}`}>
                                            {val !== undefined ? `${val}%` : '-'}
                                        </span>
                                      </div>
                                   </td>
                                 );
                               })}
                             </tr>
                           ))}
                        </tbody>
                      </table>
                   </div>

                   <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                     <h3 className="text-lg font-bold text-slate-800 mb-6">Ward Burden</h3>
                     <div className="h-72">
                        <ResponsiveContainer width="100%" height="100%">
                           <BarChart data={analytics.wardData} layout="vertical" margin={{left: 20}}>
                              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                              <XAxis type="number" hide />
                              <YAxis type="category" dataKey="name" width={80} tick={{fontSize: 12}} />
                              <RechartsTooltip cursor={{fill: '#f1f5f9'}} />
                              <Bar dataKey="cases" fill="#8b5cf6" radius={[0, 4, 4, 0]} barSize={20} />
                           </BarChart>
                        </ResponsiveContainer>
                     </div>
                   </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* GRAPH EXPLORER */}
        {activeTab === 'graph' && (
          <div className="space-y-6 h-[calc(100vh-6rem)] flex flex-col animate-fade-in">
            <header className="flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold text-slate-800">Knowledge Graph Explorer</h2>
                <p className="text-slate-500">Topological analysis of Patients, Organisms, and Genes.</p>
              </div>
            </header>

            <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden">
              <div className="lg:col-span-2 h-full bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden relative">
                <KnowledgeGraph data={graphData} onNodeClick={handleNodeClick} />
              </div>

              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 overflow-y-auto">
                {selectedNode ? (
                  <div className="animate-fade-in space-y-6">
                     <div>
                       <span className={`inline-block px-2 py-1 rounded text-xs font-bold mb-3 ${
                         selectedNode.type === NodeType.PATIENT ? 'bg-blue-100 text-blue-700' :
                         selectedNode.type === NodeType.ORGANISM ? 'bg-rose-100 text-rose-700' :
                         selectedNode.type === NodeType.GENE ? 'bg-violet-100 text-violet-700' :
                         selectedNode.type === NodeType.ANTIBIOTIC ? 'bg-emerald-100 text-emerald-700' :
                         'bg-amber-100 text-amber-700'
                       }`}>
                         {selectedNode.type}
                       </span>
                       <h3 className="text-xl font-bold text-slate-800">{selectedNode.label}</h3>
                       <p className="text-xs text-slate-500 font-mono mt-1">{selectedNode.id}</p>
                     </div>

                     <div>
                       <h4 className="text-xs font-bold text-slate-400 uppercase mb-3 flex items-center gap-2">Properties</h4>
                       <div className="bg-slate-50 rounded-lg border border-slate-100 overflow-hidden">
                           <table className="w-full text-sm text-left">
                             <tbody>
                               {getNodeProperties(selectedNode).map(([key, value]) => (
                                 <tr key={key} className="border-b border-slate-100 last:border-0">
                                   <td className="px-4 py-2 font-medium text-slate-600 bg-slate-100/50 w-1/3 break-words">{key}</td>
                                   <td className="px-4 py-2 text-slate-800 break-words">{String(value)}</td>
                                 </tr>
                               ))}
                             </tbody>
                           </table>
                       </div>
                     </div>
                     
                     <div>
                       <h4 className="text-xs font-bold text-slate-400 uppercase mb-3 flex items-center gap-2"><LinkIcon className="w-3 h-3" /> Neighbors</h4>
                       <div className="space-y-2">
                         {neighbors.map((n, idx) => (
                             <div key={idx} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-100 rounded-lg group">
                               <div className="flex items-center gap-3">
                                  <div className={`w-2 h-2 rounded-full ${n.direction === 'outgoing' ? 'bg-blue-400' : 'bg-violet-400'}`} />
                                  <div>
                                    <p className="text-sm font-semibold text-slate-700">{n.neighbor?.label}</p>
                                    <p className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">{n.relationship.replace(/_/g, ' ')}</p>
                                  </div>
                               </div>
                               {n.direction === 'outgoing' ? <ArrowRight className="w-4 h-4 text-slate-300" /> : <ArrowLeft className="w-4 h-4 text-slate-300" />}
                             </div>
                           ))
                         }
                       </div>
                     </div>
                  </div>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-slate-400 text-center">
                    <Network className="w-12 h-12 mb-4 opacity-50" />
                    <p>Select a node to inspect details.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* VISUAL DIAGNOSTICS */}
        {activeTab === 'visual_dx' && (
           <div className="space-y-6 animate-fade-in">
              <header>
                <h2 className="text-2xl font-bold text-slate-800">Visual Diagnostics</h2>
                <p className="text-slate-500">AI-powered analysis of Agar Plates and Antibiograms.</p>
              </header>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div className="bg-white p-8 rounded-xl shadow-sm border border-slate-200 text-center">
                      <ScanEye className="w-16 h-16 text-blue-500 mx-auto mb-4" />
                      <h3 className="text-lg font-bold text-slate-800 mb-2">Upload Petri Dish Image</h3>
                      <p className="text-slate-500 mb-6 text-sm">
                          The AI will identify colony morphology and estimate zones of inhibition.
                      </p>
                      {/* Reuse Agent Interface for the heavy lifting, but contextualized */}
                      <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 text-left">
                          <p className="text-xs font-bold text-slate-500 mb-2 uppercase">Instructions</p>
                          <ol className="list-decimal list-inside text-sm text-slate-600 space-y-1">
                              <li>Ensure good lighting and focus.</li>
                              <li>Upload image using the Agent panel on the right.</li>
                              <li>Ask: <i>"Analyze this agar plate."</i></li>
                          </ol>
                      </div>
                  </div>
                  <div className="h-[600px]">
                      <AgentInterface />
                  </div>
              </div>
           </div>
        )}

        {/* GENOTYPE PREDICTOR */}
        {activeTab === 'genomics' && (
           <div className="space-y-6 animate-fade-in">
               <GenomicPredictor data={genomicData} />
               
               {/* Context for Graph Linkage */}
               <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 mt-6">
                   <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
                       <Network className="w-5 h-5 text-violet-500" /> Linked Graph Context
                   </h3>
                   <div className="h-64 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-center text-slate-400">
                       <p className="text-sm">
                           Search for a sample above to see its visualized relationships in the Graph Explorer.
                           <br />
                           (Integration active: Gene nodes are automatically created from CSV uploads)
                       </p>
                   </div>
               </div>
           </div>
        )}

        {/* STEWARDSHIP AI */}
        {activeTab === 'stewardship' && (
          <div className="space-y-6 animate-fade-in">
             <header className="mb-6">
                <h2 className="text-2xl font-bold text-slate-800">Automated Stewardship</h2>
                <p className="text-slate-500">Draft clinical notes and review prescriptions against guidelines.</p>
             </header>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <div className="space-y-8">
                 <SmartSelect />
                 <div className="bg-emerald-50 p-6 rounded-xl border border-emerald-100">
                    <h3 className="text-emerald-900 font-bold flex items-center gap-2 mb-2">
                      <FileText className="w-5 h-5" /> Stewardship Protocol
                    </h3>
                    <ul className="text-sm text-emerald-800 list-disc list-inside space-y-1">
                        <li>Always check renal function (eGFR).</li>
                        <li>Verify allergy status (Penicillin/Cephalosporin).</li>
                        <li>Review for de-escalation in 48-72 hours.</li>
                    </ul>
                 </div>
              </div>
              
              <div className="space-y-6 h-[600px]">
                <AgentInterface />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
