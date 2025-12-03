import React, { useState } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell 
} from 'recharts';
import { Activity, ShieldAlert, Users, LayoutDashboard, Network, UploadCloud, Link as LinkIcon, ArrowRight, ArrowLeft } from 'lucide-react';
import KnowledgeGraph from './KnowledgeGraph';
import SmartSelect from './SmartSelect';
import AgentInterface from './AgentInterface';
import { INITIAL_GRAPH_DATA } from '../constants';
import { GraphNode } from '../types';

const Dashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'surveillance' | 'investigation'>('surveillance');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // Mock stats data
  const resistanceData = [
    { name: 'MRSA', cases: 12, risk: 'High' },
    { name: 'VRE', cases: 5, risk: 'Medium' },
    { name: 'ESBL E.coli', cases: 8, risk: 'High' },
    { name: 'C. auris', cases: 2, risk: 'Critical' },
  ];

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
  };

  const getNeighbors = (node: GraphNode) => {
    return INITIAL_GRAPH_DATA.links
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
        const neighborNode = INITIAL_GRAPH_DATA.nodes.find(n => n.id === neighborId);
        
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
      <aside className="w-full md:w-64 bg-slate-900 text-slate-300 flex-shrink-0 flex flex-col h-auto md:h-screen sticky top-0">
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
            <Network className="w-5 h-5" />
            Surveillance Graph
          </button>
          <button 
            onClick={() => setActiveTab('investigation')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${activeTab === 'investigation' ? 'bg-blue-600 text-white' : 'hover:bg-slate-800'}`}
          >
            <LayoutDashboard className="w-5 h-5" />
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
      <main className="flex-1 p-4 md:p-8 overflow-y-auto">
        {activeTab === 'surveillance' && (
          <div className="space-y-6">
            <header className="flex justify-between items-center mb-6">
              <div>
                <h2 className="text-2xl font-bold text-slate-800">Live Surveillance Map</h2>
                <p className="text-slate-500">Real-time visualization of patient-pathogen relationships.</p>
              </div>
              <button className="flex items-center gap-2 bg-white border border-slate-300 text-slate-700 px-4 py-2 rounded-lg hover:bg-slate-50 shadow-sm transition">
                <UploadCloud className="w-4 h-4" /> Import CSV Data
              </button>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Stats Cards */}
              <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                 <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-medium text-slate-500">Total Active Cases</h3>
                    <Users className="w-5 h-5 text-blue-500" />
                 </div>
                 <p className="text-3xl font-bold text-slate-800">1,248</p>
                 <span className="text-xs text-emerald-600 bg-emerald-50 px-2 py-1 rounded mt-2 inline-block">↓ 2.4% from last week</span>
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

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[600px]">
              {/* Graph Vis */}
              <div className="lg:col-span-2 h-full">
                <KnowledgeGraph data={INITIAL_GRAPH_DATA} onNodeClick={handleNodeClick} />
              </div>

              {/* Node Details Panel */}
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 overflow-y-auto flex flex-col">
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
                             <div key={idx} className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-lg hover:border-blue-300 transition-colors group">
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

        {activeTab === 'investigation' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="space-y-8">
               <SmartSelect />
               
               <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                 <h3 className="text-lg font-bold text-slate-800 mb-6">Regional Resistance Patterns</h3>
                 <div className="h-64">
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
            
            <div className="space-y-6">
              <AgentInterface />
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default Dashboard;