from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.api.dependencies import get_analysis_orchestrator, get_llm_service
from app.schemas import (
    AnalysisDetail,
    AnalysisListItem,
    AnalysisRequest,
    AnalysisResponse,
    FinancialUploadResult,
    ReportResponse,
    SummaryBlock,
)
from app.services.analysis_orchestrator import AnalysisOrchestrator
from app.services.llm_service import LLMService
from app.services.statement_parser import FinancialStatementParser
from app.storage.memory import MemoryStore, get_store

router = APIRouter()


@router.post("", response_model=AnalysisResponse)
async def create_analysis(
    payload: AnalysisRequest,
    orchestrator: AnalysisOrchestrator = Depends(get_analysis_orchestrator),
) -> AnalysisResponse:
    return await orchestrator.run_full_analysis(payload)


@router.get("", response_model=List[AnalysisListItem])
def list_analyses(
    store: MemoryStore = Depends(get_store),
    risk_level: Optional[str] = Query(None, description="Filter by risk level (A-D)"),
    industry_code: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
) -> List[AnalysisListItem]:
    records = store.list_analyses()
    filtered = []
    for record in records:
        if risk_level and (record.get("risk_level") or "").upper() != risk_level.upper():
            continue
        if industry_code and (record.get("customer", {}).get("industry_code") or "").upper() != industry_code.upper():
            continue
        if status and record.get("status") != status:
            continue
        filtered.append(record)

    items: List[AnalysisListItem] = []
    for record in filtered:
        customer = record.get("customer", {})
        items.append(
            AnalysisListItem(
                analysis_id=record["id"],
                customer_name=customer.get("name", "Unknown"),
                industry_code=customer.get("industry_code"),
                total_score=record.get("total_score"),
                risk_level=record.get("risk_level"),
                status=record.get("status", "PENDING"),
                created_at=record.get("created_at"),
                 analysis_date=record.get("analysis_date"),
                requested_by=record.get("requested_by"),
            )
        )
    return items


@router.get("/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(analysis_id: str, store: MemoryStore = Depends(get_store)) -> AnalysisDetail:
    record = store.get_analysis(analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")

    summary = record.get("summary", {})
    report = store.get_report(analysis_id, "html")
    scores = record.get("scores")

    return AnalysisDetail(
        analysis_id=record["id"],
        customer=record["customer"],
        status=record.get("status", "PENDING"),
        total_score=record.get("total_score"),
        risk_level=record.get("risk_level"),
        scores=scores,
        metrics=record.get("metrics") or {},
        web_profile=record.get("web_profile") or {},
        llm_sections=record.get("llm_sections"),
        summary=SummaryBlock(**summary) if summary else SummaryBlock(headline="", key_risks=[], suggestions=[]),
        report_html=report["content"] if report else None,
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
        analysis_date=record.get("analysis_date"),
    )


@router.get("/{analysis_id}/report", response_model=ReportResponse)
def get_report(
    analysis_id: str,
    format: str = Query("html", enum=["html", "markdown"]),
    store: MemoryStore = Depends(get_store),
) -> ReportResponse:
    report = store.get_report(analysis_id, format)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportResponse(**report)


@router.post("/upload", response_model=FinancialUploadResult)
async def upload_financials(
    file: UploadFile = File(...),
    llm_service: LLMService = Depends(get_llm_service),
) -> FinancialUploadResult:
    parser = FinancialStatementParser(llm_service=llm_service)
    data = await file.read()
    try:
        return await parser.parse(file.filename or "upload", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
