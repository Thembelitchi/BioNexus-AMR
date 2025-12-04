import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, Sparkles, Paperclip, FileText, X, ExternalLink, Dna } from 'lucide-react';
import { ChatMessage } from '../types';
import { geminiService } from '../services/geminiService';

interface AgentInterfaceProps {
  context?: string;
}

const AgentInterface: React.FC<AgentInterfaceProps> = ({ context }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init',
      role: 'model',
      content: 'Hello, I am **BioNexus 2026**. I can analyze **Genomic Data**, interpret **Agar Plates**, and draft **Stewardship Notes**.',
      timestamp: new Date()
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const convertFileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result as string;
        // Remove data URL prefix (e.g., "data:image/png;base64,")
        const base64 = result.split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  const handleSend = async () => {
    if ((!input.trim() && !selectedFile) || isLoading) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input || (selectedFile ? `Analyzed uploaded file: ${selectedFile.name}` : ''),
      timestamp: new Date(),
      attachment: selectedFile ? {
        name: selectedFile.name,
        type: selectedFile.type,
        data: '' // Not storing full data in history to save memory
      } : undefined
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);
    
    try {
      let responseText = '';
      let groundingData = undefined;

      if (selectedFile) {
        // Module B: Ingestion Engine (Enhanced for 2026)
        const base64 = await convertFileToBase64(selectedFile);
        responseText = await geminiService.analyzeLabReport(base64, selectedFile.type);
        clearFile();
      } else {
        // Module A & C: Agent Chat
        // In a real app, this context would be dynamically constructed from the current Dashboard state (Graph + Genomics)
        const activeContext = context || "Active Cluster: 3 MRSA cases in ICU. Genomic Data: blaNDM-1 detected in Sample S-20045 (K. pneumoniae).";
        const result = await geminiService.chatWithAgent(userMsg.content, activeContext);
        responseText = result.text;
        groundingData = result.groundingMetadata;
      }

      const botMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'model',
        content: responseText,
        timestamp: new Date(),
        groundingMetadata: groundingData
      };

      setMessages(prev => [...prev, botMsg]);
    } catch (e) {
      console.error(e);
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'model',
        content: 'I encountered an error processing your request.',
        timestamp: new Date()
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Helper to render grounding citations
  const renderGrounding = (metadata: any) => {
    if (!metadata?.groundingChunks) return null;

    const sources = metadata.groundingChunks
      .map((chunk: any) => chunk.web?.uri ? { title: chunk.web.title, uri: chunk.web.uri } : null)
      .filter(Boolean);

    if (sources.length === 0) return null;

    return (
      <div className="mt-3 pt-3 border-t border-slate-200">
        <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1">
          <Sparkles className="w-3 h-3" /> Sources
        </p>
        <div className="flex flex-wrap gap-2">
          {sources.map((source: any, idx: number) => (
            <a 
              key={idx} 
              href={source.uri} 
              target="_blank" 
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-[10px] bg-slate-100 text-blue-600 px-2 py-1 rounded hover:bg-slate-200 transition-colors"
            >
              {source.title || 'Source'} <ExternalLink className="w-3 h-3" />
            </a>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="bg-slate-900 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-lg shadow-lg">
              <Dna className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-white font-semibold">BioNexus Intelligence</h3>
              <p className="text-slate-400 text-[10px] uppercase tracking-wider">Genomics • Vision • Stewardship</p>
            </div>
        </div>
        <div className="text-[10px] text-emerald-400 bg-emerald-950/30 border border-emerald-900/50 px-2 py-1 rounded flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"/> Online
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50" ref={scrollRef}>
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 border ${
              msg.role === 'user' ? 'bg-blue-100 text-blue-600 border-blue-200' : 'bg-violet-100 text-violet-600 border-violet-200'
            }`}>
              {msg.role === 'user' ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
            </div>
            <div className={`max-w-[85%] p-3 rounded-2xl text-sm leading-relaxed shadow-sm ${
              msg.role === 'user' 
                ? 'bg-blue-600 text-white rounded-tr-none' 
                : 'bg-white text-slate-700 border border-slate-200 rounded-tl-none'
            }`}>
              {/* Attachment Badge */}
              {msg.attachment && (
                 <div className="mb-2 p-2 bg-white/20 rounded-lg flex items-center gap-2 text-xs border border-white/10">
                    <FileText className="w-4 h-4" />
                    <span className="truncate max-w-[150px]">{msg.attachment.name}</span>
                 </div>
              )}
              
              {/* Content Parser */}
              <div className="markdown-content">
                  {msg.content.split('```').map((part, i) => {
                    if (i % 2 === 1) {
                      // Code Block (likely Cypher)
                      return (
                        <pre key={i} className="bg-slate-900 text-emerald-400 p-3 rounded-lg my-2 overflow-x-auto text-xs font-mono border border-slate-800">
                          {part}
                        </pre>
                      );
                    }
                    // Text with Bold
                    return (
                        <span key={i}>
                            {part.split('**').map((subPart, j) => 
                                j % 2 === 1 ? <strong key={j} className={msg.role === 'model' ? "text-slate-900 font-bold" : "font-bold"}>{subPart}</strong> : subPart
                            )}
                        </span>
                    );
                  })}
              </div>

              {/* Grounding / Search Sources */}
              {msg.role === 'model' && renderGrounding(msg.groundingMetadata)}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex gap-3 animate-pulse">
             <div className="w-8 h-8 rounded-full bg-violet-100 text-violet-600 flex items-center justify-center shrink-0 border border-violet-200">
               <Bot className="w-5 h-5" />
             </div>
             <div className="bg-white p-3 rounded-2xl rounded-tl-none border border-slate-200 shadow-sm flex items-center gap-2">
               <Loader2 className="w-4 h-4 animate-spin text-violet-500" />
               <span className="text-xs text-slate-500 font-medium">
                  {selectedFile ? 'Processing Visual/Data Artifact...' : 'Consulting BioNexus Brain...'}
               </span>
             </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white border-t border-slate-200">
        
        {/* File Preview */}
        {selectedFile && (
            <div className="mb-2 flex items-center gap-2 bg-violet-50 text-violet-700 px-3 py-2 rounded-lg text-sm w-fit border border-violet-100 shadow-sm animate-fade-in">
                <FileText className="w-4 h-4" />
                <span className="max-w-[200px] truncate font-medium">{selectedFile.name}</span>
                <button onClick={clearFile} className="ml-2 hover:bg-violet-100 rounded-full p-1 transition-colors"><X className="w-3 h-3" /></button>
            </div>
        )}

        <div className="relative flex items-center gap-2">
            <input 
                type="file" 
                ref={fileInputRef} 
                className="hidden" 
                accept="image/*,.pdf,.csv"
                onChange={handleFileSelect}
            />
            <button 
                onClick={() => fileInputRef.current?.click()}
                className="p-3 text-slate-400 hover:text-violet-600 hover:bg-violet-50 rounded-xl transition-all border border-transparent hover:border-violet-100"
                title="Upload Image (Agar Plate), PDF (Report), or CSV"
            >
                <Paperclip className="w-5 h-5" />
            </button>

            <div className="relative flex-1">
                <input
                    type="text"
                    className="w-full pl-4 pr-12 py-3 bg-slate-100 border border-transparent rounded-xl focus:bg-white focus:border-violet-500 focus:ring-2 focus:ring-violet-100 outline-none transition-all placeholder:text-slate-400"
                    placeholder="Ask about genomics, stewardship, or upload data..."
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={!!selectedFile} 
                />
                <button 
                    onClick={handleSend}
                    disabled={isLoading || (!input.trim() && !selectedFile)}
                    className="absolute right-2 top-2 p-1.5 bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                >
                    <Send className="w-4 h-4" />
                </button>
            </div>
        </div>
      </div>
    </div>
  );
};

export default AgentInterface;