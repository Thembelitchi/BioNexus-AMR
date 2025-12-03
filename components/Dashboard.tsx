import React, { useState, useRef, useCallback } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell 
} from 'recharts';
import { Activity, ShieldAlert, Users, LayoutDashboard, Network, UploadCloud, Link as LinkIcon, ArrowRight, ArrowLeft, Microscope, Search } from 'lucide-react';
import KnowledgeGraph from './KnowledgeGraph';
import SmartSelect from './SmartSelect';
import AgentInterface from './AgentInterface';
import { INITIAL_GRAPH_DATA } from '../constants';
import { GraphNode, GraphData, NodeType, GraphLink } from '../types';

const Dashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'surveillance' | 'graph' | 'investigation'>('surveillance');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [graphData, setGraphData] = useState<GraphData>(INITIAL_GRAPH_DATA);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Mock stats data
  const resistanceData = [
    { name: 'MRSA', cases: 12, risk: 'High' },
    { name: 'VRE', cases: 5, risk: 'Medium' },
    { name: 'ESBL E.coli', cases: 8, risk: 'High' },
    { name: 'C. auris', cases: 2, risk: 'Critical' },
  ];

  // Memoize handleNodeClick to prevent KnowledgeGraph re-rendering loop
  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
  }, []);

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      processCSV(text);
    };
    reader.readAsText(file);
    // Reset input
    event.target.value = '';
  };

  const processCSV = (csvText: string) => {
    try {
      const lines = csvText.split('\n');
      const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
      
      // Basic validation
      if (!headers.includes('patientid') || !headers.includes('organism')) {
        alert("Invalid CSV format. Expected columns: PatientID, Ward, SampleID, Organism, Antibiotic, Result, MIC");
        return;
      }

      // Clone existing data to avoid mutation during iteration
      const newNodes = new Map(graphData.nodes.map(n => [n.id, { ...n }]));
      const newLinks = [...graphData.links];

      // Helper to add node if missing
      const addNode = (id: string, label: string, type: NodeType, group: number) => {
        if (!newNodes.has(id)) {
          newNodes.set(id, { id, label, type, group });
        }
        return id;
      };

      // Helper to add link
      const addLink = (source: string, target: string, relationship: string, details?: any) => {
        // Check if link exists
        const exists = newLinks.some(l => 
          (typeof l.source === 'string' ? l.source === source : (l.source as GraphNode).id === source) &&
          (typeof l.target === 'string' ? l.target === target : (l.target as GraphNode).id === target) &&
          l.relationship === relationship
        );
        
        if (!exists) {
          newLinks.push({ source, target, relationship, details });
        }
      };

      // Process rows
      for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        
        const cols = line.split(',').map(c => c.trim());
        const row: Record<string, string> = {};
        headers.forEach((h, idx) => { row[h] = cols[idx] || ''; });

        if (!row['patientid'] || !row['sampleid']) continue;

        // 1. Nodes
        const locId = `LOC-${row['ward'] || 'Unknown'}`;
        const patientId = row['patientid']; // Assuming ID is already unique/prefixed in CSV or raw
        const sampleId = row['sampleid'];
        const orgId = `ORG-${row['organism'].replace(/\s+/g, '-')}`;
        const abxId = `ABX-${row['antibiotic']}`;

        addNode(locId, row['ward'] || 'Unknown Ward', NodeType.LOCATION, 1);
        addNode(patientId, row['patientid'], NodeType.PATIENT, 2);
        addNode(sampleId, row['sampleid'], NodeType.SAMPLE, 3);
        addNode(orgId, row['organism'], NodeType.ORGANISM, 4);
        
        if (row['antibiotic']) {
          addNode(abxId, row['antibiotic'], NodeType.ANTIBIOTIC, 5);
        }

        // 2. Links
        addLink(patientId, sampleId, 'PROVIDED_SAMPLE');
        addLink(sampleId, locId, 'COLLECTED_AT');
        addLink(sampleId, orgId, 'IDENTIFIED');

        if (row['antibiotic'] && row['result']) {
          const relationship = row['result'].toUpperCase().startsWith('R') ? 'RESISTANT_TO' : 'SUSCEPTIBLE_TO';
          const details = { mic: row['mic'] || 'N/A' };
          addLink(orgId, abxId, relationship, details);
        }
      }

      setGraphData({
        nodes: Array.from(newNodes.values()),
        links: newLinks
      });
      
      alert(`Successfully imported ${lines.length - 1} records.`);

    } catch (e) {
      console.error("CSV Import Error", e);
      alert("Failed to parse CSV. Please check the console for details.");
    }
  };

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
    // Filter out internal D3 properties and UI specific props
    const ignoredKeys = ['index', 'x', 'y', 'vx', 'vy', 'fx', 'fy', 'group', 'label', 'type'];
    return Object.entries(node).filter(([key]) => !ignoredKeys.includes(key));
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row">
      {/* Sidebar Navigation */}
      <aside className="w-full md:w-64 bg-slate-900 text-slate-300 flex-shrink-0 flex flex-col h-auto md:h-screen sticky top-0 z-50">
        <div className="p-6 border-b border-slate-800">
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Activity className="text-blue-500" />
            BioNexus AMR
          </h1>
          <p className="text-xs text-slate-500 mt-1">Graph Intelligence Platform</p>
        </div>
        
        <nav className="flex-1 p-4 space-y-2">
          <button 
            onClick={() => setActiveTab('surveillance')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${activeTab === 'surveillance' ? 'bg-blue-600 text-white' : 'hover:bg-slate-800'}`}
          >
            <LayoutDashboard className="w-5 h-5" />
            Surveillance
          </button>
          <button 
            onClick={() => setActiveTab('graph')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${activeTab === 'graph' ? 'bg-blue-600 text-white' : 'hover:bg-slate-800'}`}
          >
            <Network className="w-5 h-5" />
            Graph Explorer
          </button>
          <button 
            onClick={() => setActiveTab('investigation')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${activeTab === 'investigation' ? 'bg-blue-600 text-white' : 'hover:bg-slate-800'}`}
          >
            <Microscope className="w-5 h-5" />
            Clinical Investigation
          </button>
        </nav>

        <div className="p-4 border-t border-slate-800">
           <div className="bg-slate-800 rounded-xl p-4">
             <h4 className="text-xs font-bold text-slate-400 uppercase mb-2">System Status</h4>
             <div className="flex items-center gap-2 text-sm text-emerald-400">
               <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span>
               Neo4j Connected
             </div>
             <div className="flex items-center gap-2 text-sm text-violet-400 mt-1">
               <span className="w-2 h-2 bg-violet-400 rounded-full animate-pulse"></span>
               AI Agent Active
             </div>
           </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-4 md:p-8 overflow-y-auto overflow-x-hidden">
        
        {/* TAB 1: SURVEILLANCE DASHBOARD */}
        {activeTab === 'surveillance' && (
          <div className="space-y-6">
            <header className="flex justify-between items-center mb-6">
              <div>
                <h2 className="text-2xl font-bold text-slate-800">Live Surveillance Overview</h2>
                <p className="text-slate-500">Real-time statistics and alert monitoring.</p>
              </div>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Stats Cards */}
              <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                 <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-medium text-slate-500">Total Active Cases</h3>
                    <Users className="w-5 h-5 text-blue-500" />
                 </div>
                 <p className="text-3xl font-bold text-slate-800">{1248 + (graphData.nodes.length - INITIAL_GRAPH_DATA.nodes.length)}</p>
                 <span className="text-xs text-emerald-600 bg-emerald-50 px-2 py-1 rounded mt-2 inline-block">Live Data</span>
              </div>
              <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                 <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-medium text-slate-500">Critical Alerts</h3>
                    <ShieldAlert className="w-5 h-5 text-rose-500" />
                 </div>
                 <p className="text-3xl font-bold text-slate-800">3</p>
                 <span className="text-xs text-rose-600 bg-rose-50 px-2 py-1 rounded mt-2 inline-block">New Cluster in ICU</span>
              </div>
               <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                 <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-medium text-slate-500">AI Predictions</h3>
                    <Activity className="w-5 h-5 text-violet-500" />
                 </div>
                 <p className="text-sm text-slate-600 leading-relaxed">
                   High probability (85%) of MRSA outbreak in Ward 4 based on recent admission patterns.
                 </p>
              </div>
            </div>

            {/* Regional Resistance Chart */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
              <h3 className="text-lg font-bold text-slate-800 mb-6">Regional Resistance Patterns</h3>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={resistanceData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 12}} />
                    <YAxis axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 12}} />
                    <Tooltip cursor={{fill: '#f1f5f9'}} contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}} />
                    <Bar dataKey="cases" radius={[4, 4, 0, 0]}>
                      {resistanceData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.risk === 'Critical' || entry.risk === 'High' ? '#e11d48' : '#3b82f6'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: GRAPH EXPLORER */}
        {activeTab === 'graph' && (
          <div className="space-y-6 h-[calc(100vh-6rem)] flex flex-col">
            <header className="flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold text-slate-800">Knowledge Graph Explorer</h2>
                <p className="text-slate-500">Interactive visualization of patient-pathogen relationships.</p>
              </div>
              <div>
                <input 
                  type="file" 
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept=".csv"
                  className="hidden" 
                />
                <button 
                  onClick={handleImportClick}
                  className="flex items-center gap-2 bg-white border border-slate-300 text-slate-700 px-4 py-2 rounded-lg hover:bg-slate-50 shadow-sm transition"
                >
                  <UploadCloud className="w-4 h-4" /> Import CSV Data
                </button>
              </div>
            </header>

            <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden">
              {/* Graph Vis */}
              <div className="lg:col-span-2 h-full bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <KnowledgeGraph data={graphData} onNodeClick={handleNodeClick} />
              </div>

              {/* Node Details Panel */}
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 overflow-y-auto">
                {selectedNode ? (
                  <div className="animate-fade-in space-y-6">
                     {/* Header */}
                     <div>
                       <span className={`inline-block px-2 py-1 rounded text-xs font-bold mb-3 ${
                         selectedNode.type === 'PATIENT' ? 'bg-blue-100 text-blue-700' :
                         selectedNode.type === 'ORGANISM' ? 'bg-rose-100 text-rose-700' :
                         selectedNode.type === 'ANTIBIOTIC' ? 'bg-emerald-100 text-emerald-700' :
                         'bg-amber-100 text-amber-700'
                       }`}>
                         {selectedNode.type}
                       </span>
                       <h3 className="text-xl font-bold text-slate-800">{selectedNode.label}</h3>
                       <p className="text-xs text-slate-500 font-mono mt-1">{selectedNode.id}</p>
                     </div>

                     {/* Properties */}
                     <div>
                       <h4 className="text-xs font-bold text-slate-400 uppercase mb-3 flex items-center gap-2">
                         Properties
                       </h4>
                       <div className="bg-slate-50 rounded-lg border border-slate-100 overflow-hidden">
                         {getNodeProperties(selectedNode).length > 0 ? (
                           <table className="w-full text-sm text-left">
                             <tbody>
                               {getNodeProperties(selectedNode).map(([key, value]) => (
                                 <tr key={key} className="border-b border-slate-100 last:border-0">
                                   <td className="px-4 py-2 font-medium text-slate-600 bg-slate-100/50 w-1/3">{key}</td>
                                   <td className="px-4 py-2 text-slate-800">{String(value)}</td>
                                 </tr>
                               ))}
                             </tbody>
                           </table>
                         ) : (
                           <p className="p-4 text-xs text-slate-500 italic">No additional properties.</p>
                         )}
                       </div>
                     </div>
                     
                     {/* Neighbors */}
                     <div>
                       <h4 className="text-xs font-bold text-slate-400 uppercase mb-3 flex items-center gap-2">
                         <LinkIcon className="w-3 h-3" /> Direct Neighbors
                       </h4>
                       <div className="space-y-2">
                         {neighbors.length > 0 ? (
                           neighbors.map((n, idx) => (
                             <div key={idx} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-100 rounded-lg hover:bg-white hover:border-blue-300 transition-all group">
                               <div className="flex items-center gap-3">
                                  <div className={`w-2 h-2 rounded-full ${
                                      n.direction === 'outgoing' ? 'bg-blue-400' : 'bg-violet-400'
                                  }`} />
                                  <div>
                                    <p className="text-sm font-semibold text-slate-700 group-hover:text-blue-600 transition-colors">
                                      {n.neighbor?.label || 'Unknown Node'}
                                    </p>
                                    <p className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">
                                      {n.relationship.replace(/_/g, ' ')}
                                    </p>
                                  </div>
                               </div>
                               {n.direction === 'outgoing' ? (
                                 <ArrowRight className="w-4 h-4 text-slate-300" />
                               ) : (
                                 <ArrowLeft className="w-4 h-4 text-slate-300" />
                               )}
                             </div>
                           ))
                         ) : (
                            <p className="text-sm text-slate-500 italic">No connected nodes found.</p>
                         )}
                       </div>
                     </div>

                     {/* Alerts */}
                     {selectedNode.type === 'ORGANISM' && (
                       <div className="p-4 bg-rose-50 border border-rose-100 rounded-lg">
                         <h4 className="text-sm font-bold text-rose-800 mb-2 flex items-center gap-2">
                           <ShieldAlert className="w-4 h-4" /> Resistance Alert
                         </h4>
                         <p className="text-xs text-rose-700">
                           This pathogen is being tracked for potential outbreak clusters.
                         </p>
                       </div>
                     )}
                  </div>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-slate-400 text-center">
                    <Network className="w-12 h-12 mb-4 opacity-50" />
                    <p>Select a node in the graph to view detailed relationships.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: CLINICAL INVESTIGATION */}
        {activeTab === 'investigation' && (
          <div className="space-y-6">
             <header className="mb-6">
                <h2 className="text-2xl font-bold text-slate-800">Clinical Investigation Tools</h2>
                <p className="text-slate-500">AI-powered analysis and antibiotic stewardship.</p>
             </header>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <div className="space-y-8">
                 <SmartSelect />
                 <div className="bg-blue-50 p-6 rounded-xl border border-blue-100">
                    <h3 className="text-blue-900 font-bold flex items-center gap-2 mb-2">
                      <Search className="w-5 h-5" /> Need specific data?
                    </h3>
                    <p className="text-sm text-blue-800">
                      Use the Agent on the right to query the database or search for external guidelines.
                    </p>
                 </div>
              </div>
              
              <div className="space-y-6">
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