import React, { useState, useEffect } from 'react';
import { FlaskConical, TestTube2, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import { ORGANISM_KB } from '../constants';
import { OrganismData } from '../types';

const SmartSelect: React.FC = () => {
  const [selectedOrganismName, setSelectedOrganismName] = useState<string>("");
  const [organismData, setOrganismData] = useState<OrganismData | null>(null);

  useEffect(() => {
    if (selectedOrganismName && ORGANISM_KB[selectedOrganismName]) {
      setOrganismData(ORGANISM_KB[selectedOrganismName]);
    } else {
      setOrganismData(null);
    }
  }, [selectedOrganismName]);

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
        <div className="flex items-center gap-2 mb-4">
            <FlaskConical className="w-5 h-5 text-blue-600" />
            <h2 className="text-lg font-semibold text-slate-800">Smart Clinical Investigation</h2>
        </div>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Detected Organism</label>
            <select 
              className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none transition-all"
              value={selectedOrganismName}
              onChange={(e) => setSelectedOrganismName(e.target.value)}
            >
              <option value="">-- Select Organism --</option>
              {Object.keys(ORGANISM_KB).map(key => (
                <option key={key} value={key}>{key}</option>
              ))}
            </select>
          </div>

          {organismData && (
            <div className="animate-fade-in">
              <div className="p-3 bg-blue-50 border border-blue-100 rounded-lg mb-4 flex items-start gap-3">
                 <AlertTriangle className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
                 <div>
                    <h4 className="text-sm font-bold text-blue-800">{organismData.type} Profile</h4>
                    <p className="text-sm text-blue-700 mt-1">{organismData.alert}</p>
                 </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Investigations */}
                <div className="bg-slate-50 p-4 rounded-lg border border-slate-200">
                  <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-2">
                    <TestTube2 className="w-3 h-3" /> Recommended Tests
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {organismData.investigations.map((test, i) => (
                      <span key={i} className="px-2 py-1 bg-white border border-slate-200 rounded text-xs text-slate-600 font-medium shadow-sm">
                        {test}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Antibiotics */}
                <div className="bg-slate-50 p-4 rounded-lg border border-slate-200">
                  <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3">Antimicrobial Panel</h3>
                  <div className="space-y-2">
                    {organismData.antibiotics.map((abx, i) => (
                      <div key={i} className={`p-2 rounded border flex justify-between items-center ${
                          abx.resistanceLikelihood === 'Intrinsic' ? 'opacity-50 bg-slate-100 border-slate-200' : 
                          abx.resistanceLikelihood === 'High' ? 'bg-rose-50 border-rose-100' :
                          'bg-emerald-50 border-emerald-100'
                      }`}>
                        <div>
                          <p className={`text-sm font-semibold ${
                             abx.resistanceLikelihood === 'High' ? 'text-rose-700' : 
                             abx.resistanceLikelihood === 'Intrinsic' ? 'text-slate-500' : 'text-emerald-700'
                          }`}>{abx.name}</p>
                          <p className="text-[10px] text-slate-500">{abx.class} • {abx.note}</p>
                        </div>
                        {abx.resistanceLikelihood === 'High' ? <XCircle className="w-4 h-4 text-rose-500" /> : 
                         abx.resistanceLikelihood === 'Intrinsic' ? <span className="text-[10px] font-bold text-slate-400">N/A</span> :
                         <CheckCircle2 className="w-4 h-4 text-emerald-500" />}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SmartSelect;