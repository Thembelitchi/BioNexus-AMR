# BioNexus AMR 🧬

**Revolutionizing Microbial Surveillance through Knowledge Graph Technology and AI Agents.**

BioNexus AMR is an AI-driven, graph-based intelligence platform designed for clinical pathologists, R&D scientists, and medical students. Unlike static dashboards, BioNexus uses a dynamic Knowledge Graph to map relationships between patients, samples, microbes, resistance genes, and treatments, augmented by a "Micro-Brain" AI agent.

![BioNexus Dashboard](https://via.placeholder.com/800x400?text=BioNexus+AMR+Dashboard+Preview)

## 🚀 Key Features

### 1. 🕸️ Live Surveillance Knowledge Graph
- **Interactive Visualization**: Powered by **D3.js**, visualize complex relationships (e.g., `Patient` → `Sample` → `Organism` → `Antibiotic`).
- **Cluster Detection**: Identify potential outbreaks (e.g., MRSA clusters in ICU) through visual topology.
- **Deep Dive**: Click any node to see direct neighbors, specific properties, and resistance alerts in a detail panel.

### 2. 🤖 BioNexus Micro-Brain Agent
- **Powered by Google Gemini 1.5 Pro**: Context-aware medical AI orchestrator.
- **Multimodal Ingestion**: Upload images or PDFs of lab reports; the agent extracts structured JSON data (Patient ID, MIC values, Interpretation).
- **R&D Scout**: Uses **Google Search Grounding** to find real-time R&D updates, clinical trials, and guidelines (CLSI/EUCAST) when internal data is insufficient.
- **Text-to-Cypher**: Converts natural language clinical questions into Graph Database queries.

### 3. 🔬 Smart Clinical Investigation
- **Context-Aware Logic**: Select an organism (e.g., *Pseudomonas aeruginosa*) and the system automatically filters relevant antibiotics and investigations based on intrinsic resistance rules.
- **Guideline Guardrails**: Visualizes warnings (e.g., "Intrinsic Resistance") to prevent prescription errors.
- **Regional Statistics**: Interactive charts visualizing local resistance patterns and risk levels using **Recharts**.

## 🛠️ Technology Stack

- **Frontend**: React 19, TypeScript
- **Styling**: Tailwind CSS
- **Visualization**: D3.js (Force-directed graph), Recharts (Analytics)
- **AI & Reasoning**: Google GenAI SDK (`@google/genai`)
- **Icons**: Lucide React

## 📦 Setup & Configuration

### Prerequisites
- Node.js (v18+)
- A valid Google Cloud API Key with access to Gemini models.

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/bionexus-amr.git
   cd bionexus-amr
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Environment Setup**
   The application relies on the `API_KEY` environment variable for the Google Gemini API. Ensure this is set in your build environment or `.env` file.

   ```env
   API_KEY=your_google_gemini_api_key
   ```

4. **Run the Application**
   ```bash
   npm start
   ```

## 🖥️ User Guide

### 1. Surveillance Mode
- **Navigation**: Switch to the "Surveillance Graph" tab.
- **Interaction**: Drag nodes to rearrange the graph layout. Zoom capabilities are automatic via D3 force simulation.
- **Inspection**: Click on any node (Patient, Organism, etc.) to view its metadata and list of connected neighbors in the right-hand panel.

### 2. Investigation Mode
- **Navigation**: Switch to the "Clinical Investigation" tab.
- **Smart Select**: Use the dropdown to select a detected organism. Observe how the "Antimicrobial Panel" updates to reflect specific drug-bug combinations.
- **AI Agent**: 
    - Type questions like *"Show me the latest trials for C. auris"* to trigger a web search.
    - Click the 📎 **Paperclip icon** to upload a dummy lab report image for analysis.

## 📄 License
This project is licensed under the MIT License.
