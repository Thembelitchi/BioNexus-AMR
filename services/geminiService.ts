import { GoogleGenAI, GenerateContentResponse } from "@google/genai";

class GeminiService {
  private ai: GoogleGenAI | null = null;
  private modelId = "gemini-2.5-flash";

  constructor() {
    if (process.env.API_KEY) {
      this.ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
    } else {
      console.warn("API_KEY not found. Gemini features disabled.");
    }
  }

  /**
   * Module B: Ingestion Engine
   * Uploads a messy PDF/Image lab report and gets structured JSON.
   */
  public async analyzeLabReport(fileBase64: string, mimeType: string): Promise<string> {
    if (!this.ai) return "Error: API Key missing.";

    try {
      const prompt = `
        Analyze this clinical lab report. 
        Extract the following fields into a valid JSON format:
        - PatientID
        - SampleDate
        - OrganismIdentified
        - AntibioticsTested (Array of objects with 'Antibiotic', 'MIC', 'Interpretation' fields)
        
        If the image is not a lab report, simply say "This does not appear to be a valid microbiology report."
      `;

      const response = await this.ai.models.generateContent({
        model: this.modelId,
        contents: {
          parts: [
            { inlineData: { mimeType: mimeType, data: fileBase64 } },
            { text: prompt }
          ]
        }
      });

      return response.text || "Could not analyze document.";
    } catch (error) {
      console.error("Lab Report Analysis Error:", error);
      return "Error processing the lab report. Please check the file format.";
    }
  }

  /**
   * Module A & C: Agentic R&D Scout & Graph Interface
   * Handles Chat, Graph Queries (Cypher), and Web Search.
   */
  public async chatWithAgent(
    query: string, 
    context: string
  ): Promise<{ text: string; groundingMetadata?: any }> {
    if (!this.ai) return { text: "Error: API Key missing." };

    const systemInstruction = `
      Role: You are BioNexus, an expert Clinical Microbiologist and Data Scientist.
      Your goal is to assist pathologists in analyzing Antimicrobial Resistance (AMR).

      Capabilities:
      1. GRAPH QUERY: Convert questions into Neo4j Cypher queries. 
         Schema: (:Patient)-[:PROVIDED]->(:Sample)-[:HAS_ORGANISM]->(:Organism)-[:RESISTANT_TO {mic: "val"}]->(:Antibiotic) and (:Sample)-[:COLLECTED_AT]->(:Location).
         If the user asks to "Find", "Show", or "List" data from the database, output a Markdown code block with 'cypher'.
      2. R&D SCOUT: You can search the web for the latest guidelines (CLSI/EUCAST) and R&D drug trials if the internal context is insufficient.
      3. INTERPRETATION: Interpret AST results.

      Context from Dashboard: ${context}

      Constraints:
      - NEVER invent medical advice.
      - If data is missing, state it.
      - When generating Cypher, ONLY use the node labels: :Patient, :Sample, :Organism, :Antibiotic, :Location.
      - Use **bold** for key findings.
    `;

    try {
      // We use the 'googleSearch' tool for R&D/Grounding
      const response = await this.ai.models.generateContent({
        model: this.modelId,
        contents: query,
        config: {
          systemInstruction: systemInstruction,
          tools: [{ googleSearch: {} }], 
          temperature: 0.3, 
        }
      });

      return {
        text: response.text || "No response generated.",
        groundingMetadata: response.candidates?.[0]?.groundingMetadata
      };

    } catch (error) {
      console.error("Agent Chat Error:", error);
      return { text: "I encountered an error connecting to the BioNexus Brain." };
    }
  }
}

export const geminiService = new GeminiService();
