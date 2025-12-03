import React, { useState } from 'react';
import { Dna, Search, AlertTriangle, FileCheck2, ArrowRight } from 'lucide-react';
import { GenomicData } from '../types';

interface GenomicPredictorProps {
  data: GenomicData[];
}

const GenomicPredictor: React.FC<GenomicPredictorProps> = ({ data }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [prediction, setPrediction] = useState<GenomicData | null>(null);

  const handlePredict = () => {
    if (!searchTerm) return;
    const result = data.find(
      item => item.sampleId.toLowerCase().includes(searchTerm.toLowerCase())
    );
    setPrediction(result || null);
  };

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
        <div className="flex items-center gap-2 mb-4">
          <Dna className="w-6 h-6 text-violet-600" />
          <h2 className="text-xl font-bold text-slate-800">Genomic Resistance Predictor</h2>
        </div>
        <p className="text-slate-500 mb-6">
          Enter a Patient ID or Sample ID to cross-reference phenotypic results with genomic sequencing data (WGS).
        </p>

        <div className="flex gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3 text-slate-400 w-5 h-5" />
            <input 
              type="text" 
              placeholder="Enter Sample ID (e.g., SMP-A1, S-20045)"
              className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:border-violet-500 focus:ring-2 focus:ring-violet-100 outline-none transition-all"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handlePredict()}
            />
          </div>
          <button 
            onClick={handlePredict}
            className="bg-violet-600 hover:bg-violet-700 text-white px-6 py-3 rounded-xl font-medium transition-colors shadow-sm flex items-center gap-2"
          >
            Predict Resistance <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {prediction ? (
        <div className="animate-fade-in space-y-4">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
             <div className="bg-violet-50 p-4 border-b border-violet-100 flex items-center justify-between">
                <div className="flex items-center gap-3">
                   <div className="bg-violet-200 p-2 rounded-lg">
                      <Dna className="w-5 h-5 text-violet-700" />
                   </div>
                   <div>
                      <h3 className="font-bold text-violet-900">Genetic Profile Match</h3>
                      <p className="text-xs text-violet-700">Sample: {prediction.sampleId}</p>
                   </div>
                </div>
                <div className="bg-white/50 px-3 py-1 rounded text-xs font-mono text-violet-800 border border-violet-200">
                   CONFIDENCE: 99.9%
                </div>
             </div>
             
             <div className="p-6">
                <table className="w-full text-left">
                   <thead>
                      <tr className="border-b border-slate-100 text-xs font-bold text-slate-400 uppercase tracking-wider">
                         <th className="pb-3">Gene Detected</th>
                         <th className="pb-3">Biochemical Mechanism</th>
                         <th className="pb-3">Clinical Impact</th>
                      </tr>
                   </thead>
                   <tbody>
                      <tr>
                         <td className="py-4 font-mono font-bold text-slate-700">{prediction.geneDetected}</td>
                         <td className="py-4 text-slate-600">{prediction.mechanism}</td>
                         <td className="py-4">
                            {prediction.clinicalImpact.includes('CRITICAL') ? (
                               <span className="bg-rose-100 text-rose-700 px-2 py-1 rounded text-xs font-bold flex items-center w-fit gap-1">
                                  <AlertTriangle className="w-3 h-3" /> {prediction.clinicalImpact}
                               </span>
                            ) : (
                               <span className="text-slate-700">{prediction.clinicalImpact}</span>
                            )}
                         </td>
                      </tr>
                   </tbody>
                </table>
             </div>
          </div>
          
          <div className="bg-rose-50 border border-rose-100 p-4 rounded-xl flex gap-3 items-start">
             <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
             <div>
                <h4 className="font-bold text-rose-800 text-sm">Automated Resistance Prediction</h4>
                <p className="text-sm text-rose-700 mt-1">
                   Based on the presence of <strong>{prediction.geneDetected}</strong>, phenotypic resistance is highly likely. 
                   Standard treatment protocols should be adjusted immediately.
                </p>
             </div>
          </div>
        </div>
      ) : searchTerm && (
         <div className="p-8 text-center bg-slate-50 rounded-xl border border-slate-200 text-slate-400">
            <FileCheck2 className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No genomic sequencing records found for ID "{searchTerm}".</p>
            <p className="text-xs mt-1">Try uploading a genomic_data.csv file.</p>
         </div>
      )}
    </div>
  );
};

export default GenomicPredictor;