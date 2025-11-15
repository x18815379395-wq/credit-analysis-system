from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ShareholderInfo(BaseModel):
    name: str
    ratio: Optional[float] = Field(
        None, description="Ownership percentage expressed as a number between 0 and 100"
    )
    capital: Optional[float] = Field(None, description="Capital contribution, in ten-thousand RMB units")


class CustomerInfo(BaseModel):
    name: str
    uscc: Optional[str] = Field(None, description="Unified social credit code")
    region: Optional[str] = None
    industry_code: Optional[str] = None
    register_date: Optional[datetime] = None
    registered_capital: Optional[float] = None
    paid_in_capital: Optional[float] = None
    registered_address: Optional[str] = None
    legal_person: Optional[str] = None
    industry_category: Optional[str] = None
    equity_structure: Optional[str] = None
    shareholders: List[ShareholderInfo] = Field(default_factory=list)


class CollateralInfo(BaseModel):
    has_collateral: bool = False
    collateral_type: Optional[str] = None
    appraised_value: Optional[float] = None
    coverage_ratio: Optional[float] = None
    notes: Optional[str] = None


class FinancialStatementPayload(BaseModel):
    year: int
    income_statement: Dict[str, float] = Field(default_factory=dict)
    balance_sheet: Dict[str, float] = Field(default_factory=dict)
    cashflow_statement: Dict[str, float] = Field(default_factory=dict)


class FinancialUploadResult(BaseModel):
    financial_statements: List[FinancialStatementPayload]
    detected_years: List[int]
    warnings: List[str] = Field(default_factory=list)


class AnalysisRequest(BaseModel):
    customer: CustomerInfo
    financial_statements: List[FinancialStatementPayload]
    collateral_info: CollateralInfo = Field(default_factory=CollateralInfo)
    requested_by: Optional[str] = None


class SummaryBlock(BaseModel):
    headline: str
    key_risks: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    analysis_id: str
    status: Literal["PENDING", "RUNNING", "SUCCESS", "FAILED"]
    total_score: Optional[int] = None
    risk_level: Optional[str] = None
    summary: SummaryBlock


class AnalysisListItem(BaseModel):
    analysis_id: str
    customer_name: str
    industry_code: Optional[str]
    total_score: Optional[int]
    risk_level: Optional[str]
    status: str
    created_at: datetime
    analysis_date: Optional[datetime] = None
    requested_by: Optional[str] = None


class ScoreBreakdown(BaseModel):
    total_score: int
    risk_level: str
    dimension_scores: Dict[str, float]


class LLMSections(BaseModel):
    industry_analysis: str
    financial_analysis: str
    risk_summary: str


class AnalysisDetail(BaseModel):
    analysis_id: str
    customer: CustomerInfo
    status: str
    total_score: Optional[int]
    risk_level: Optional[str]
    scores: Optional[ScoreBreakdown]
    metrics: Dict[str, Any]
    web_profile: Dict[str, Any]
    llm_sections: Optional[LLMSections]
    summary: SummaryBlock
    report_html: Optional[str]
    created_at: datetime
    updated_at: datetime
    analysis_date: Optional[datetime] = None


class ReportResponse(BaseModel):
    analysis_id: str
    format: Literal["html", "markdown"]
    content: str


class CompanyEnrichmentResponse(BaseModel):
    company: CustomerInfo
    industry: Dict[str, Any] = Field(default_factory=dict)
