# BioNexus AMR

BioNexus AMR is a graph-based intelligence platform for antimicrobial
resistance (AMR) surveillance, built with South African hospital networks
in mind. A Neo4j knowledge graph links patients, admissions, wards,
isolates, pathogens, antibiograms, resistance genes and mobile genetic
elements, and graph analytics find outbreaks, gene transfer and
transmission hubs.

| Part | Where | What it does |
|---|---|---|
| Surveillance dashboard | repository root (Vite + React + D3) | Overview, outbreak timeline (by lab phenotype or genome), ward and genomic networks, gene-transfer signals, clinical and discordance alerts, WHO AWaRe stewardship, isolate explorer |
| Backend | [`backend/`](backend/README.md) (FastAPI + Neo4j + GDS) | Ontology-grounded ingest (MIC or disk zones, CLSI 2025; POPIA pseudonymisation), analytics and alert rules; REST API and CLI |
| Demo dataset | [`backend/data/demo/`](backend/data/demo/README.md) | 600 synthetic patients across four fictional South African hospitals, with eight planted scenarios |
| Knowledge graph | [`graph/`](graph/README.md) | The demo graph itself as a Neo4j database dump and a portable Cypher script (3,373 nodes, 13,092 relationships), ready to open in Neo4j Browser |

## Try it: the static demo site

`docs/` holds a static build of the dashboard with a snapshot of the
backend's output on the demo dataset. GitHub Pages can serve it directly:

1. **Settings → Pages → Build and deployment → Source: Deploy from a branch.**
2. Choose the branch that contains `docs/` and the **`/docs`** folder, then save.
3. The site appears at `https://<user>.github.io/BioNexus-AMR/`.

GitHub Pages needs a public repository, or a paid plan for private ones.
To preview locally instead:

```bash
npm install
npm run build:pages
python3 -m http.server --directory docs 8080   # open http://localhost:8080
```

The static site only filters and totals in the browser. Every cluster,
gene-transfer signal, ward ranking and alert was computed by the backend
on Neo4j with Graph Data Science and exported to `public/data/snapshot.json`.
The data is **synthetic** and not for clinical use.

## Development

```bash
npm install
npm run dev          # dashboard on http://localhost:3000 (reads public/data/snapshot.json)
npm run typecheck
```

To regenerate the snapshot after changing the backend or dataset, start a
disposable Neo4j with GDS and export:

```bash
cd backend
tools/embedded-neo4j/run.sh &        # or: docker compose up neo4j
NEO4J_USER= BIONEXUS_PSEUDONYMISATION_KEY=bionexus-public-demo-key-not-secret \
  python tools/export_site_snapshot.py --load   # wipes that database first
cd .. && npm run build:pages
```

Earlier prototype components (`components/Dashboard.tsx`,
`AgentInterface.tsx`, `services/geminiService.ts`) are no longer part of
the build. The Gemini agent needs a server-side API key, so it belongs
behind the backend rather than in a static page.

## License

MIT
