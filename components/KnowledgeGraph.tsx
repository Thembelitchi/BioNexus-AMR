import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { Save, Download, RotateCcw } from 'lucide-react';
import { GraphData, GraphNode, GraphLink, NodeType } from '../types';

interface KnowledgeGraphProps {
  data: GraphData;
  onNodeClick: (node: GraphNode) => void;
}

const KnowledgeGraph: React.FC<KnowledgeGraphProps> = ({ data, onNodeClick }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphLink> | null>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // Update dimensions on resize
  useEffect(() => {
    const handleResize = () => {
      if (wrapperRef.current) {
        setDimensions({
          width: wrapperRef.current.offsetWidth,
          height: wrapperRef.current.offsetHeight
        });
      }
    };
    window.addEventListener('resize', handleResize);
    handleResize(); // Init
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Save Layout to LocalStorage
  const handleSaveLayout = () => {
    if (!data.nodes.length) return;
    
    const layout = data.nodes.map(node => ({
      id: node.id,
      x: node.x,
      y: node.y,
      fx: node.fx,
      fy: node.fy
    }));

    try {
      localStorage.setItem('bionexus_graph_layout', JSON.stringify(layout));
      alert("Layout saved successfully!");
    } catch (e) {
      console.error("Failed to save layout", e);
      alert("Error saving layout.");
    }
  };

  // Load Layout from LocalStorage
  const handleLoadLayout = () => {
    try {
      const savedLayout = localStorage.getItem('bionexus_graph_layout');
      if (!savedLayout) {
        alert("No saved layout found.");
        return;
      }

      const layoutMap = new Map<string, any>(JSON.parse(savedLayout).map((n: any) => [n.id, n]));
      let appliedCount = 0;

      data.nodes.forEach(node => {
        const saved = layoutMap.get(node.id);
        if (saved) {
          node.x = saved.x;
          node.y = saved.y;
          // Fix the position to match saved state exactly
          node.fx = saved.x;
          node.fy = saved.y;
          appliedCount++;
        }
      });

      if (simulationRef.current) {
        // Restart simulation with low alpha to settle links without disturbing nodes too much
        simulationRef.current.alpha(0.3).restart();
      }
      
      alert(`Layout loaded. Applied positions to ${appliedCount} nodes.`);
    } catch (e) {
      console.error("Failed to load layout", e);
      alert("Error loading layout.");
    }
  };

  // Reset Layout (Clear fixed positions)
  const handleResetLayout = () => {
    data.nodes.forEach(node => {
      node.fx = null;
      node.fy = null;
    });
    
    if (simulationRef.current) {
      simulationRef.current.alpha(1).restart();
    }
  };

  useEffect(() => {
    if (!svgRef.current || !data.nodes.length) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove(); // Clear previous render

    const width = dimensions.width;
    const height = dimensions.height;

    // Simulation Setup
    const simulation = d3.forceSimulation<GraphNode>(data.nodes)
      .force("link", d3.forceLink<GraphNode, GraphLink>(data.links).id(d => d.id).distance(100))
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide(30));

    simulationRef.current = simulation;

    // Elements
    const link = svg.append("g")
      .attr("stroke", "#94a3b8")
      .attr("stroke-opacity", 0.6)
      .selectAll("line")
      .data(data.links)
      .join("line")
      .attr("stroke-width", 2);

    // Color mapper based on Node Type
    const getColor = (type: NodeType) => {
      switch (type) {
        case NodeType.PATIENT: return "#3b82f6"; // Blue
        case NodeType.ORGANISM: return "#dc2626"; // Red
        case NodeType.ANTIBIOTIC: return "#10b981"; // Emerald
        case NodeType.LOCATION: return "#f59e0b"; // Amber
        default: return "#64748b";
      }
    };

    const node = svg.append("g")
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5)
      .selectAll("circle")
      .data(data.nodes)
      .join("circle")
      .attr("r", 12)
      .attr("fill", (d: GraphNode) => getColor(d.type))
      .call(d3.drag<SVGCircleElement, GraphNode>()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended) as any
      )
      .on("click", (event, d) => onNodeClick(d as GraphNode));

    const labels = svg.append("g")
      .selectAll("text")
      .data(data.nodes)
      .join("text")
      .attr("dx", 15)
      .attr("dy", 4)
      .text((d: GraphNode) => d.label)
      .attr("font-size", "10px")
      .attr("fill", "#334155")
      .style("pointer-events", "none");

    // Simulation Tick
    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => (d.source as GraphNode).x!)
        .attr("y1", (d: any) => (d.source as GraphNode).y!)
        .attr("x2", (d: any) => (d.target as GraphNode).x!)
        .attr("y2", (d: any) => (d.target as GraphNode).y!);

      node
        .attr("cx", (d: GraphNode) => d.x!)
        .attr("cy", (d: GraphNode) => d.y!);
      
      labels
        .attr("x", (d: GraphNode) => d.x!)
        .attr("y", (d: GraphNode) => d.y!);
    });

    // Drag Interaction Functions
    function dragstarted(event: any, d: GraphNode) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event: any, d: GraphNode) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event: any, d: GraphNode) {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }

    return () => {
      simulation.stop();
    };
  }, [data, dimensions, onNodeClick]);

  return (
    <div ref={wrapperRef} className="w-full h-full bg-slate-50 rounded-xl border border-slate-200 shadow-inner overflow-hidden relative">
      <div className="absolute top-4 left-4 z-10 bg-white/90 p-2 rounded shadow backdrop-blur-sm text-xs text-slate-600">
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 rounded-full bg-blue-500"></span> Patient</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 rounded-full bg-red-600"></span> Organism</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 rounded-full bg-emerald-500"></span> Antibiotic</div>
        <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-amber-500"></span> Location</div>
      </div>

      <div className="absolute top-4 right-4 z-10 flex flex-col gap-2">
        <button onClick={handleSaveLayout} title="Save Layout" className="p-2 bg-white rounded shadow text-slate-600 hover:text-blue-600 hover:bg-slate-50 transition-colors">
          <Save className="w-4 h-4" />
        </button>
        <button onClick={handleLoadLayout} title="Load Layout" className="p-2 bg-white rounded shadow text-slate-600 hover:text-blue-600 hover:bg-slate-50 transition-colors">
          <Download className="w-4 h-4" />
        </button>
        <button onClick={handleResetLayout} title="Reset Layout" className="p-2 bg-white rounded shadow text-slate-600 hover:text-blue-600 hover:bg-slate-50 transition-colors">
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      <svg ref={svgRef} className="w-full h-full cursor-grab active:cursor-grabbing"></svg>
    </div>
  );
};

export default KnowledgeGraph;