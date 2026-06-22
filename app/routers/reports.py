from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import CurrentUser, get_current_user
from app.repositories.report_repository import ReportRepository
from app.services.report_service import ReportService
from app.services.report_ai_service import ReportAIService
from app.schemas.report_schemas import (
    ReportRunRequest,
    ReportResult,
    ReportTemplateCreate,
    ReportTemplateUpdate,
    ReportTemplateResponse,
    ReportTypeDefinition,
    PromptReportRequest,
    AIReportResponse,
)

router = APIRouter(prefix="/api/reports", tags=["Reports"])


def get_report_service(db: Session = Depends(get_db)) -> ReportService:
    repo = ReportRepository(db)
    return ReportService(repo)


@router.get("/catalog", response_model=List[ReportTypeDefinition])
def get_catalog(
    user: CurrentUser = Depends(get_current_user),
    service: ReportService = Depends(get_report_service)
):
    return service.get_catalog(user)


@router.post("/run", response_model=ReportResult)
def run_report(
    req: ReportRunRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ReportService = Depends(get_report_service)
):
    return service.run_report(req, user)


@router.post("/export")
def export_report(
    req: ReportRunRequest,
    format: str = Query("pdf"),
    user: CurrentUser = Depends(get_current_user),
    service: ReportService = Depends(get_report_service)
):
    file_bytes, media_type, filename = service.export_report(req, format, user)

    if format.lower() == "html":
        return HTMLResponse(content=file_bytes.decode('utf-8'))

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


# --- Plantillas QBE CRUD ---

@router.get("/templates", response_model=List[ReportTemplateResponse])
def list_templates(
    user: CurrentUser = Depends(get_current_user),
    service: ReportService = Depends(get_report_service)
):
    return service.list_templates(user)


@router.post("/templates", response_model=ReportTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    req: ReportTemplateCreate,
    user: CurrentUser = Depends(get_current_user),
    service: ReportService = Depends(get_report_service)
):
    return service.create_template(req, user)


@router.put("/templates/{id}", response_model=ReportTemplateResponse)
def update_template(
    id: int,
    req: ReportTemplateUpdate,
    user: CurrentUser = Depends(get_current_user),
    service: ReportService = Depends(get_report_service)
):
    return service.update_template(id, req, user)


@router.delete("/templates/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    id: int,
    user: CurrentUser = Depends(get_current_user),
    service: ReportService = Depends(get_report_service)
):
    service.delete_template(id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── IA: Asistente de reportes ─────────────────────────────────

@router.post("/prompt", response_model=AIReportResponse)
def run_report_by_prompt(
    req: PromptReportRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ReportService = Depends(get_report_service)
):
    parsed = ReportAIService.parse_prompt(req.prompt)
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo interpretar la solicitud. Reformula tu consulta."
        )

    run_req = _build_run_request_from_ai(parsed)
    result = service.run_report(run_req, user)
    return AIReportResponse(query=run_req, result=result)


@router.post("/audio", response_model=AIReportResponse)
def run_report_by_audio(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    service: ReportService = Depends(get_report_service)
):
    audio_bytes = file.file.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo de audio está vacío."
        )

    transcript = ReportAIService.transcribe_audio(audio_bytes, file.filename or "audio.webm")
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo transcribir el audio. Intenta de nuevo."
        )

    parsed = ReportAIService.parse_prompt(transcript)
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo interpretar la transcripción. Reformula tu consulta."
        )

    run_req = _build_run_request_from_ai(parsed)
    result = service.run_report(run_req, user)
    return AIReportResponse(transcript=transcript, query=run_req, result=result)


def _build_run_request_from_ai(parsed: dict) -> ReportRunRequest:
    filters = []
    for f in parsed.get("filters", []):
        filters.append({
            "field": f.get("field", ""),
            "operator": f.get("operator", "EQ").upper(),
            "value": f.get("value")
        })

    return ReportRunRequest(
        reportType=parsed.get("reportType", ""),
        selectedFields=parsed.get("selectedFields", []),
        filters=filters,
        sortField=parsed.get("sortField"),
        sortOrder=parsed.get("sortOrder", "asc"),
        dateFrom=parsed.get("dateFrom"),
        dateTo=parsed.get("dateTo"),
        limit=parsed.get("limit", 100),
        offset=parsed.get("offset", 0),
    )
