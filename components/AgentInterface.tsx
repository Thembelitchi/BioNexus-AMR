import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, Sparkles, Paperclip, FileText, X, ExternalLink } from 'lucide-react';
import { ChatMessage } from '../types';
import { geminiService } from '../services/geminiService';

const AgentInterface: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init',
      role: 'model',
      content: 'Hello, I am BioNexus Agent. I can analyze **Lab Reports** (upload PDF/Images), generate **Cypher queries**, or search the web for **R&D updates**.',
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
        // Module B: Ingestion Engine
        const base64 = await convertFileToBase64(selectedFile);
        responseText = await geminiService.analyzeLabReport(base64, selectedFile.type);
        clearFile();
      } else {
        // Module A & C: Agent Chat
        const mockContext = "Active Cluster: 3 MRSA cases in ICU (Resistant to Oxacillin). Patient 103: K. pneumoniae (Burn Unit).";
        const result = await geminiService.chatWithAgent(userMsg.content, mockContext);
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
    <div className="flex flex-col h-[600px] bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="bg-slate-900 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
            <div className="p-2 bg-violet-600 rounded-lg">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-white font-semibold">BioNexus Micro-Brain</h3>
              <p className="text-slate-400 text-xs">Orchestrator • R&D Scout</p>
            </div>
        </div>
        <div className="text-[10px] text-slate-500 bg-slate-800 px-2 py-1 rounded">
            v1.0.0
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50" ref={scrollRef}>
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
              msg.role === 'user' ? 'bg-blue-100 text-blue-600' : 'bg-violet-100 text-violet-600'
            }`}>
              {msg.role === 'user' ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
            </div>
            <div className={`max-w-[85%] p-3 rounded-2xl text-sm leading-relaxed ${
              msg.role === 'user' 
                ? 'bg-blue-600 text-white rounded-tr-none' 
                : 'bg-white text-slate-700 border border-slate-200 shadow-sm rounded-tl-none'
            }`}>
              {/* Attachment Badge */}
              {msg.attachment && (
                 <div className="mb-2 p-2 bg-white/20 rounded flex items-center gap-2 text-xs">
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
                        <pre key={i} className="bg-slate-900 text-green-400 p-3 rounded-lg my-2 overflow-x-auto text-xs font-mono">
                          {part}
                        </pre>
                      );
                    }
                    // Text with Bold
                    return (
                        <span key={i}>
                            {part.split('**').map((subPart, j) => 
                                j % 2 === 1 ? <strong key={j} className={msg.role === 'model' ? "text-slate-900" : "font-bold"}>{subPart}</strong> : subPart
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
             <div className="w-8 h-8 rounded-full bg-violet-100 text-violet-600 flex items-center justify-center shrink-0">
               <Bot className="w-5 h-5" />
             </div>
             <div className="bg-white p-3 rounded-2xl rounded-tl-none border border-slate-200 shadow-sm flex items-center gap-2">
               <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
               <span className="text-xs text-slate-500">
                  {selectedFile ? 'Parsing Lab Report...' : 'Searching & Reasoning...'}
               </span>
             </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white border-t border-slate-200">
        
        {/* File Preview */}
        {selectedFile && (
            <div className="mb-2 flex items-center gap-2 bg-blue-50 text-blue-700 px-3 py-2 rounded-lg text-sm w-fit border border-blue-100">
                <FileText className="w-4 h-4" />
                <span className="max-w-[200px] truncate">{selectedFile.name}</span>
                <button onClick={clearFile} className="ml-2 hover:bg-blue-100 rounded-full p-0.5"><X className="w-3 h-3" /></button>
            </div>
        )}

        <div className="relative flex items-center gap-2">
            <input 
                type="file" 
                ref={fileInputRef} 
                className="hidden" 
                accept="image/*,.pdf"
                onChange={handleFileSelect}
            />
            <button 
                onClick={() => fileInputRef.current?.click()}
                className="p-3 text-slate-400 hover:text-blue-600 hover:bg-slate-100 rounded-xl transition-colors"
                title="Upload Lab Report"
            >
                <Paperclip className="w-5 h-5" />
            </button>

            <div className="relative flex-1">
                <input
                    type="text"
                    className="w-full pl-4 pr-12 py-3 bg-slate-100 border border-transparent rounded-xl focus:bg-white focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all"
                    placeholder="Ask BioNexus or upload report..."
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={!!selectedFile} // Disable text if file is selected (for simplicity in this flow)
                />
                <button 
                    onClick={handleSend}
                    disabled={isLoading || (!input.trim() && !selectedFile)}
                    className="absolute right-2 top-2 p-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
