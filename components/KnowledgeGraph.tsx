import React, { useEffect, useRef, useState, memo } from 'react';
import * as d3 from 'd3';
import { Save, Download, RotateCcw, ZoomIn, ZoomOut, Maximize } from 'lucide-react';
import { GraphData, GraphNode, GraphLink, NodeType } from '../types';

interface KnowledgeGraphProps {
  data: GraphData;
  onNodeClick: (node: GraphNode) => void;
}

const KnowledgeGraph: React.FC<KnowledgeGraphProps> = ({ data, onNodeClick }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphLink> | null>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  // 1. PERFORMANCE: Use ResizeObserver instead of window 'resize' listener
  useEffect(() => {
    if (!wrapperRef.current) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        // Debounce slightly or just set
        setDimensions({ width, height });
      }
    });

    resizeObserver.observe(wrapperRef.current);
    return () => resizeObserver.disconnect();
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
          node.fx = saved.x;
          node.fy = saved.y;
          appliedCount++;
        }
      });

      if (simulationRef.current) {
        simulationRef.current.alpha(0.3).restart();
      }
      
      alert(`Layout loaded. Applied positions to ${appliedCount} nodes.`);
    } catch (e) {
      console.error("Failed to load layout", e);
      alert("Error loading layout.");
    }
  };

  const handleResetLayout = () => {
    data.nodes.forEach(node => {
      node.fx = null;
      node.fy = null;
    });
    
    if (simulationRef.current) {
      simulationRef.current.alpha(1).restart();
    }
  };

  const handleZoomIn = () => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current)
        .transition()
        .duration(300)
        .call(zoomRef.current.scaleBy, 1.2);
    }
  };

  const handleZoomOut = () => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current)
        .transition()
        .duration(300)
        .call(zoomRef.current.scaleBy, 0.8);
    }
  };

  const handleResetView = () => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current)
        .transition()
        .duration(750)
        .call(zoomRef.current.transform, d3.zoomIdentity);
    }
  };

  useEffect(() => {
    if (!svgRef.current || !data.nodes.length) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove(); 

    const width = dimensions.width;
    const height = dimensions.height;

    const container = svg.append("g").attr("class", "zoom-container");

    // 2. PERFORMANCE: Level of Detail (LOD) handling in Zoom
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 8])
      .on("zoom", (event) => {
        container.attr("transform", event.transform);
        
        // Semantic LOD: Hide labels when zoomed out to reduce rendering cost
        if (event.transform.k < 0.6) {
          container.selectAll("text").style("opacity", 0);
        } else {
          container.selectAll("text").style("opacity", 1);
        }
      });

    svg.call(zoom);
    zoomRef.current = zoom;

    // 3. PERFORMANCE: Optimized Simulation Parameters
    const simulation = d3.forceSimulation<GraphNode>(data.nodes)
      .force("link", d3.forceLink<GraphNode, GraphLink>(data.links).id(d => d.id).distance(100))
      .force("charge", d3.forceManyBody()
        .strength(-300)
        .theta(0.9) // Barnes-Hut approximation: 0.9 is faster/less accurate than default 0.8
        .distanceMax(500) // Don't calculate forces for far away nodes
      )
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide(25).iterations(1)); // Reduce collision iterations

    // Stop simulation sooner to save CPU
    simulation.alphaDecay(0.02); // Settle faster
    simulation.alphaMin(0.01); 

    simulationRef.current = simulation;

    const link = container.append("g")
      .attr("stroke", "#94a3b8")
      .attr("stroke-opacity", 0.6)
      .selectAll("line")
      .data(data.links)
      .join("line")
      .attr("stroke-width", 1.5); // Slightly thinner for performance

    const getColor = (type: NodeType) => {
      switch (type) {
        case NodeType.PATIENT: return "#3b82f6";
        case NodeType.ORGANISM: return "#dc2626";
        case NodeType.ANTIBIOTIC: return "#10b981";
        case NodeType.LOCATION: return "#f59e0b";
        case NodeType.GENE: return "#8b5cf6";
        default: return "#64748b";
      }
    };

    const node = container.append("g")
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5)
      .selectAll("circle")
      .data(data.nodes)
      .join("circle")
      .attr("r", 10) // Slightly smaller radius
      .attr("fill", (d: GraphNode) => getColor(d.type))
      .style("cursor", "pointer")
      .call(d3.drag<SVGCircleElement, GraphNode>()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended) as any
      )
      .on("click", (event, d) => {
        event.stopPropagation();
        onNodeClick(d as GraphNode);
      })
      .on("mouseover", (event, d) => {
        setHoveredNode(d as GraphNode);
        setTooltipPos({ x: event.clientX, y: event.clientY });
      })
      .on("mousemove", (event) => {
        setTooltipPos({ x: event.clientX, y: event.clientY });
      })
      .on("mouseout", () => {
        setHoveredNode(null);
      });

    const labels = container.append("g")
      .selectAll("text")
      .data(data.nodes)
      .join("text")
      .attr("dx", 14)
      .attr("dy", 4)
      .text((d: GraphNode) => d.label)
      .attr("font-size", "10px")
      .attr("fill", "#334155")
      .style("pointer-events", "none")
      // Initial opacity based on zoom (default 1)
      .style("opacity", 1); 

    simulation.on("tick", () => {
      // 4. PERFORMANCE: Batch attribute updates
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);

      node
        .attr("cx", (d: GraphNode) => d.x!)
        .attr("cy", (d: GraphNode) => d.y!);
      
      labels
        .attr("x", (d: GraphNode) => d.x!)
        .attr("y", (d: GraphNode) => d.y!);
    });

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
    <div ref={wrapperRef} className="w-full h-full bg-slate-50 rounded-xl border border-slate-200 shadow-inner overflow-hidden relative group">
      {/* Legend */}
      <div className="absolute top-4 left-4 z-10 bg-white/90 p-2 rounded shadow backdrop-blur-sm text-xs text-slate-600">
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 rounded-full bg-blue-500"></span> Patient</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 rounded-full bg-red-600"></span> Organism</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 rounded-full bg-emerald-500"></span> Antibiotic</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 rounded-full bg-violet-500"></span> Gene</div>
        <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-amber-500"></span> Location</div>
      </div>

      {/* Control Buttons */}
      <div className="absolute top-4 right-4 z-10 flex flex-col gap-2">
        <div className="flex flex-col gap-1 bg-white rounded shadow p-1">
          <button onClick={handleZoomIn} title="Zoom In" className="p-2 text-slate-600 hover:text-blue-600 hover:bg-slate-50 rounded transition-colors">
            <ZoomIn className="w-4 h-4" />
          </button>
          <button onClick={handleZoomOut} title="Zoom Out" className="p-2 text-slate-600 hover:text-blue-600 hover:bg-slate-50 rounded transition-colors">
            <ZoomOut className="w-4 h-4" />
          </button>
          <button onClick={handleResetView} title="Fit View" className="p-2 text-slate-600 hover:text-blue-600 hover:bg-slate-50 rounded transition-colors">
            <Maximize className="w-4 h-4" />
          </button>
        </div>
        
        <div className="flex flex-col gap-1 bg-white rounded shadow p-1 mt-2">
          <button onClick={handleSaveLayout} title="Save Layout" className="p-2 text-slate-600 hover:text-blue-600 hover:bg-slate-50 rounded transition-colors">
            <Save className="w-4 h-4" />
          </button>
          <button onClick={handleLoadLayout} title="Load Layout" className="p-2 text-slate-600 hover:text-blue-600 hover:bg-slate-50 rounded transition-colors">
            <Download className="w-4 h-4" />
          </button>
          <button onClick={handleResetLayout} title="Reset Node Positions" className="p-2 text-slate-600 hover:text-blue-600 hover:bg-slate-50 rounded transition-colors">
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Tooltip */}
      {hoveredNode && (
        <div 
          style={{ 
            position: 'fixed', 
            left: tooltipPos.x + 15, 
            top: tooltipPos.y - 10,
            zIndex: 50
          }}
          className="bg-slate-800/90 text-white text-xs p-2 rounded-lg shadow-xl backdrop-blur-sm pointer-events-none border border-slate-700"
        >
          <div className="font-bold mb-0.5">{hoveredNode.label}</div>
          <div className="opacity-80 text-[10px] uppercase tracking-wider">{hoveredNode.type}</div>
          {hoveredNode.group && <div className="opacity-60 text-[10px] mt-1">Cluster Group: {hoveredNode.group}</div>}
        </div>
      )}

      <svg ref={svgRef} className="w-full h-full cursor-grab active:cursor-grabbing"></svg>
    </div>
  );
};

// 5. PERFORMANCE: Prevent re-renders on parent state changes
export default memo(KnowledgeGraph);
