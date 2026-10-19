"""HTTP API for ingestion and epidemiological analytics.

Run with ``uvicorn --factory bionexus.api:create_app``.
"""

# No ``from __future__ import annotations`` here: FastAPI must resolve the
# Annotated aliases defined inside create_app at runtime.
import logging
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from . import alerts, analytics, notifiable
from .config import Settings, configure_logging, pseudonymiser_for
from .db import GraphClient, GraphUnavailableError
from .models import IngestReport
from .pipeline import ingest
from .schema import ensure_schema

log = logging.getLogger(__name__)


class Health(BaseModel):
    status: Literal["ok"]
    database: str
    gds_version: str | None


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    # Fail at startup, not on the first upload, if the key is unusable.
    pseudonymiser = pseudonymiser_for(settings)
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        client = GraphClient(settings)
        await run_in_threadpool(client.connect)
        await run_in_threadpool(ensure_schema, client)
        app.state.graph = client
        try:
            yield
        finally:
            client.close()

    app = FastAPI(title="BioNexus AMR Graph API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST"], allow_headers=["*"])

    @app.exception_handler(GraphUnavailableError)
    async def graph_unavailable(_: Request, exc: GraphUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": f"graph database unavailable: {exc}"})

    @app.exception_handler(analytics.GdsUnavailableError)
    async def gds_unavailable(_: Request, exc: analytics.GdsUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=501, content={"detail": str(exc)})

    def graph(request: Request) -> GraphClient:
        return request.app.state.graph

    Graph = Annotated[GraphClient, Depends(graph)]
    WindowDays = Annotated[int, Query(ge=1, le=365, description="Maximum days between linked isolates")]

    async def read_upload(upload: UploadFile | None) -> bytes | None:
        if upload is None:
            return None
        data = await upload.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(413, f"{upload.filename} exceeds {settings.max_upload_bytes} bytes")
        return data

    @app.get("/health", response_model=Health)
    def health(client: Graph) -> Health:
        client.query("RETURN 1 AS ok")
        return Health(status="ok", database=settings.neo4j_database, gds_version=analytics.gds_version(client))

    @app.post("/ingest", response_model=IngestReport)
    async def ingest_files(
        client: Graph,
        clinical: Annotated[UploadFile, File(description="clinical_phenotype.csv")],
        genomic: Annotated[UploadFile | None, File(description="genomic_data.csv")] = None,
        movements: Annotated[UploadFile | None, File(description="ADT movements CSV")] = None,
        dry_run: bool = False,
    ) -> IngestReport:
        files = [await read_upload(upload) for upload in (clinical, genomic, movements)]
        try:
            return await run_in_threadpool(
                ingest, client, files[0], files[1], files[2], batch_size=settings.batch_size, dry_run=dry_run,
                pseudonymiser=pseudonymiser,
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(422, f"unreadable CSV: {exc}") from exc

    @app.get("/analytics/clusters", response_model=list[analytics.SpatiotemporalCluster])
    def clusters(client: Graph, window_days: WindowDays = 14, min_size: Annotated[int, Query(ge=2)] = 2):
        return analytics.detect_spatiotemporal_clusters(client, window_days, min_size)

    @app.get("/analytics/clusters/phenotypic", response_model=list[analytics.PhenotypicCluster])
    def phenotypic_clusters(client: Graph, window_days: WindowDays = 14, min_size: Annotated[int, Query(ge=2)] = 2):
        return analytics.detect_phenotypic_clusters(client, window_days, min_size)

    @app.get("/analytics/hgt", response_model=list[analytics.HorizontalTransferSignal])
    def horizontal_gene_transfer(client: Graph, level: Literal["species", "genus"] = "species"):
        return analytics.detect_horizontal_gene_transfer(client, level)

    @app.get("/analytics/wards/centrality", response_model=analytics.WardNetworkReport)
    def ward_centrality(client: Graph, window_days: WindowDays = 14):
        return analytics.rank_wards(client, window_days)

    @app.get("/analytics/stewardship", response_model=list[analytics.PrescribingRow])
    def stewardship(client: Graph):
        return analytics.prescribing_by_aware(client)

    @app.get("/analytics/alerts", response_model=list[alerts.ClinicalAlert])
    def clinical_alerts(client: Graph):
        return alerts.clinical_alerts(client)

    @app.get("/analytics/resistance", response_model=list[analytics.ResistanceRate])
    def resistance_rates(client: Graph, facility: str | None = None):
        return analytics.resistance_rates(client, facility=facility)

    @app.get("/analytics/notifiable", response_model=list[notifiable.NotifiableCase])
    def notifiable_cases(client: Graph):
        return notifiable.notifiable_cases(client)

    return app

