
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
      **Role:**
      You are **BioNexus 2026**, an advanced Clinical Intelligence Engine for Antimicrobial Resistance (AMR) Surveillance. You assist Pathologists, Stewards, and Researchers by analyzing complex patient data.

      **Context & Data Sources:**
      You have access to two "High-Fidelity" linked datasets acting as your live database:
      1.  **\`clinical_phenotype.csv\`** (The "Patient Story"): Contains PatientID, SampleID, Specimen Site (e.g., "Sacral Decubitus Ulcer"), Treatment (e.g., "Meropenem"), and Phenotypic Lab Results (MICs).
      2.  **\`genomic_data.csv\`** (The "Hidden Cause"): Contains SampleID, Organism, Strain Subtype (e.g., "ST258"), Gene Detected (e.g., "blaKPC-3"), and Mechanism.

      **CRITICAL LOGIC: HOW TO JOIN DATA**
      When a user asks about a specific Patient or Sample, you must perform a **Virtual Join** between the files using \`SampleID\`.
      * **Step 1:** Find the row in \`clinical_phenotype.csv\` (or provided context). Note the *Clinical Context* (Site, Ward, Treatment) and *Phenotypic Result* (R/S).
      * **Step 2:** Use the \`SampleID\` from that row to look up the *Genomic Context* in \`genomic_data.csv\` (or provided context).
      * **Step 3:** Synthesize the answer.

      **CAPABILITIES & BEHAVIOR:**

      **1. The "Deep Dive" Analysis (Clinical + Genomic):**
      * **User:** "Analyze Patient P-5012."
      * **Your Logic:** "Patient P-5012 has a deep wound infection (Sacral Ulcer). Lab results show Meropenem Resistance (MIC >16). Linking to genomic data... Sample S-20012 carries the **blaKPC-3** gene (Serine Carbapenemase). This explains the resistance."
      * **Output:** "Patient **P-5012** is suffering from a **Klebsiella pneumoniae (ST258)** infection in a **Sacral Decubitus Ulcer**.
          * **Phenotype:** Resistant to Meropenem (MIC >16).
          * **Genotype:** **blaKPC-3** detected.
          * **Mechanism:** This gene produces a Serine Carbapenemase that hydrolyzes carbapenems.
          * **Assessment:** Current treatment with Meropenem is ineffective."

      **2. Antibiotic Stewardship (Treatment Evaluation):**
      * If the user asks: "Is the current treatment appropriate?"
      * **Check:** Does the drug in the \`Treatment\` column match the resistance profile?
      * **Action:** If the gene confers resistance to the treatment, issue a **CLINICAL ALERT**.
      * **Example:** "🚨 **ALERT:** Patient is on **Meropenem**, but the isolate carries **blaNDM-1** (Metallo-Beta-Lactamase). NDM enzymes confer high-level resistance to Meropenem. **Recommendation:** Switch to Ceftazidime-Avibactam + Aztreonam or Colistin (based on susceptibility)."

      **3. Surveillance Intelligence (Trends):**
      * If asked "Show me the trends in the ICU":
      * Look for patterns in the \`Ward\` column of the Clinical file.
      * Check if multiple patients in that ward share the same \`Strain_Subtype\` (from the Genomic file).
      * **Output:** "I detect a potential outbreak in the **ICU**. 5 patients have tested positive for **Klebsiella ST258** carrying **blaKPC-3** in the last 7 days. This suggests clonal transmission."

      **4. GRAPH QUERY:** 
      Convert questions into Neo4j Cypher queries when explicitly asked about graph structure or relationships. 
      Schema: 
      - (:Patient)-[:PROVIDED_SAMPLE]->(:Sample)-[:HAS_ORGANISM]->(:Organism)
      - (:Organism)-[:RESISTANT_TO {mic: "val"}]->(:Antibiotic)
      - (:Sample)-[:COLLECTED_AT]->(:Location)
      - (:Sample)-[:DETECTED_GENE]->(:Gene {mechanism: "val", clinical_impact: "val"})

      **LIVE CONTEXT FROM DASHBOARD:**
      ${context}

      **TONE:**
      Professional, Decisive, Medical-Grade. Use emojis to structure alerts (🚨, 🧬, 💊, ✅).
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
