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
   * Uploads a messy PDF/Image lab report OR a CSV data file and gets structured analysis.
   */
  public async analyzeLabReport(fileBase64: string, mimeType: string): Promise<string> {
    if (!this.ai) return "Error: API Key missing.";

    try {
      const isCsv = mimeType === 'text/csv' || mimeType.includes('csv') || mimeType === 'application/vnd.ms-excel';

      let parts: any[] = [];

      if (isCsv) {
          // Decode Base64 to string for CSV text analysis
          const binaryString = atob(fileBase64);
          parts = [
              { text: "Here is the content of a CSV data file:" },
              { text: binaryString },
              { text: "Analyze this clinical data. Identify any trends, resistance clusters, or anomalies. Output a summary in JSON or Markdown format highlighting key findings." }
          ];
      } else {
         const prompt = `
          Analyze this clinical document (Lab Report or Agar Plate Image). 
          
          IF LAB REPORT:
          Extract the following fields into a valid JSON format:
          - PatientID
          - SampleDate
          - OrganismIdentified
          - AntibioticsTested (Array of objects with 'Antibiotic', 'MIC', 'Interpretation' fields)

          IF AGAR PLATE IMAGE:
          Identify the colony morphology (e.g., 'Mucoid' = Klebsiella, 'Golden' = S. aureus).
          Estimate zone of inhibition sizes if discs are visible.
          Flag 'Satellite colonies' inside a zone of inhibition.
          
          If the image is not a valid clinical artifact, say "This does not appear to be a valid microbiology report or image."
        `;
         parts = [
            { inlineData: { mimeType: mimeType, data: fileBase64 } },
            { text: prompt }
         ];
      }

      const response = await this.ai.models.generateContent({
        model: this.modelId,
        contents: { parts }
      });

      return response.text || "Could not analyze document.";
    } catch (error) {
      console.error("Lab Report Analysis Error:", error);
      return "Error processing the document. Please check the file format.";
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
      Role: You are BioNexus 2026, the world's most advanced Antimicrobial Resistance (AMR) Intelligence System.

      Data Sources (Context):
      1. You have access to phenotypic lab results (Context provided).
      2. You have access to genomic data (Context provided).

      --- CORE CAPABILITIES (2026 FEATURES) ---

      1. 🧬 GENOMIC PREDICTION (Genotype-to-Phenotype):
         * When asked about a specific patient or sample, ALWAYS cross-reference the genomic context.
         * Explain the MECHANISM.
           * Bad Response: "Patient has mecA gene."
           * Good Response: "Patient P-1024 carries the **mecA** gene. This encodes the **PBP2a protein** with low affinity for beta-lactams, rendering **Oxacillin** and **Cefoxitin** ineffective (MRSA). Vancomycin is required."
         * If the gene is 'blaNDM-1' or 'mcr-1', flag this as a **"GLOBAL BIO-THREAT"**.

      2. 👁️ VISUAL DIAGNOSTICS (Multimodal):
         * If the user uploads an image of a Petri dish/Agar plate:
           * Identify the colony morphology (e.g., "Mucoid" = Klebsiella, "Golden/Yellow" = S. aureus, "Swarming" = Proteus).
           * Estimate zone of inhibition sizes visually if discs are visible.
           * Flag "Satellite colonies" inside a zone of inhibition as potential heteroresistance.

      3. 💊 AUTOMATED STEWARDSHIP (Prescription Engine):
         * When asked for treatment advice, draft a formal "Antimicrobial Stewardship Note".
         * Structure:
           * **Assessment:** (e.g., "ESBL E. coli bacteraemia").
           * **Recommendation:** (e.g., "Meropenem 1g IV q8h").
           * **De-escalation Plan:** (e.g., "Review in 48h for step-down to oral Ciprofloxacin if susceptible").
         * **Safety Check:** Always ask about **Renal Function (eGFR)** and **Allergies** before finalizing.

      4. GRAPH QUERY: Convert questions into Neo4j Cypher queries. 
         Schema: 
         - (:Patient)-[:PROVIDED]->(:Sample)-[:HAS_ORGANISM]->(:Organism)
         - (:Organism)-[:RESISTANT_TO {mic: "val"}]->(:Antibiotic)
         - (:Sample)-[:COLLECTED_AT]->(:Location)
         - (:Sample)-[:DETECTED_GENE]->(:Gene {mechanism: "val"})
         
      Context from Dashboard: ${context}

      Constraints:
      - NEVER invent medical advice.
      - If data is missing, state it.
      - Use **bold** for key findings.
      - Use emojis (🚨, 🧬, 💊, ✅) for readability.
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