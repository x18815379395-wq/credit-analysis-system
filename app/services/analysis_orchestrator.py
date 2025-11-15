from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.schemas import AnalysisRequest, AnalysisResponse, SummaryBlock
from app.storage.memory import MemoryStore

from .financial_metrics import FinancialMetricsService
from .llm_service import LLMService
from .report_generator import ReportGenerator
from .scorecard_engine import ScorecardEngine
from .web_search import WebSearchService


class AnalysisOrchestrator:
    """Coordinates the end-to-end analysis workflow."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        metrics_service: Optional[FinancialMetricsService] = None,
        scorecard_engine: Optional[ScorecardEngine] = None,
        llm_service: Optional[LLMService] = None,
        web_search_service: Optional[WebSearchService] = None,
        report_generator: Optional[ReportGenerator] = None,
    ) -> None:
        self.store = store
        self.metrics_service = metrics_service or FinancialMetricsService()
        self.scorecard_engine = scorecard_engine or ScorecardEngine()
        self.llm_service = llm_service or LLMService()
        self.web_search_service = web_search_service or WebSearchService(self.llm_service)
        self.report_generator = report_generator or ReportGenerator()

    async def run_full_analysis(self, payload: AnalysisRequest) -> AnalysisResponse:
        record = self.store.create_analysis(payload)
        try:
            web_profile = await self.web_search_service.enrich_company_profile(
                name=payload.customer.name,
                uscc=payload.customer.uscc,
                region=payload.customer.region,
                industry_code=payload.customer.industry_code,
            )

            metrics = self.metrics_service.compute(self._statement_dicts(payload))
            score_result = self.scorecard_engine.compute(metrics, web_profile, payload.collateral_info.model_dump())

            industry_text = await self.llm_service.generate_industry_analysis(web_profile, metrics)
            financial_text = await self.llm_service.explain_financials(metrics)
            risk_summary = await self.llm_service.summarize_risks(score_result, metrics, web_profile)

            summary_block = SummaryBlock(
                headline=risk_summary["headline"],
                key_risks=risk_summary["key_risks"],
                suggestions=risk_summary["suggestions"],
            )

            report_payload = self.report_generator.render(
                customer=record["customer"],
                web_profile=web_profile,
                metrics=metrics,
                scores=score_result,
                industry_text=industry_text,
                financial_text=financial_text,
                risk_summary=risk_summary["narrative"],
            )
            report_id = self.store.save_report(
                record["id"],
                markdown=report_payload["markdown"],
                html=report_payload["html"],
            )

            completed = self.store.complete_analysis(
                record["id"],
                metrics=metrics,
                scores=score_result,
                web_profile=web_profile,
                llm_sections={
                    "industry_analysis": industry_text,
                    "financial_analysis": financial_text,
                    "risk_summary": risk_summary["narrative"],
                },
                summary=summary_block,
                report_id=report_id,
            )

            return AnalysisResponse(
                analysis_id=completed["id"],
                status=completed["status"],
                total_score=score_result["total_score"],
                risk_level=score_result["risk_level"],
                summary=summary_block,
            )
        except Exception as exc:  # pragma: no cover - orchestration level safety net
            self.store.fail_analysis(record["id"], str(exc))
            raise

    @staticmethod
    def _statement_dicts(payload: AnalysisRequest) -> List[Dict[str, Any]]:
        return [
            {
                "year": item.year,
                "income_statement": item.income_statement,
                "balance_sheet": item.balance_sheet,
                "cashflow_statement": item.cashflow_statement,
            }
            for item in payload.financial_statements
        ]
