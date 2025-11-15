from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_web_search_service
from app.schemas import CompanyEnrichmentResponse, CustomerInfo, ShareholderInfo
from app.services.web_search import WebSearchService

router = APIRouter()


@router.get("/enrich", response_model=CompanyEnrichmentResponse)
async def enrich_company_profile(
    name: str = Query(..., description="Company name"),
    region: Optional[str] = Query(None, description="Registered region"),
    uscc: Optional[str] = Query(None, description="Unified social credit code"),
    industry_code: Optional[str] = Query(None, description="Industry code"),
    search_service: WebSearchService = Depends(get_web_search_service),
) -> CompanyEnrichmentResponse:
    if not name.strip():
        raise HTTPException(status_code=400, detail="Company name is required")

    profile = await search_service.enrich_company_profile(
        name=name, uscc=uscc, region=region, industry_code=industry_code
    )
    company = profile.get("company") or {}
    industry = profile.get("industry") or {}

    raw_shareholders = company.get("shareholders") or []
    shareholders: list[ShareholderInfo] = []
    for item in raw_shareholders:
        if not item:
            continue
        shareholder_name = item.get("name")
        if not shareholder_name:
            continue
        shareholders.append(
            ShareholderInfo(
                name=shareholder_name,
                ratio=item.get("ratio"),
                capital=item.get("capital"),
            )
        )

    customer_payload = CustomerInfo(
        name=company.get("name") or name,
        region=company.get("region") or region,
        uscc=company.get("uscc") or uscc,
        industry_code=company.get("industry_code") or industry_code,
        register_date=company.get("register_date"),
        registered_capital=company.get("registered_capital"),
        paid_in_capital=company.get("paid_in_capital"),
        registered_address=company.get("registered_address"),
        legal_person=company.get("legal_person"),
        industry_category=company.get("industry_category") or industry.get("name"),
        equity_structure=company.get("equity_structure"),
        shareholders=shareholders,
    )

    return CompanyEnrichmentResponse(company=customer_payload, industry=industry)
