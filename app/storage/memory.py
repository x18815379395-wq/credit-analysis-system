from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.schemas.analysis import AnalysisRequest, SummaryBlock


class MemoryStore:
    """Thread-safe in-memory persistence used for local development."""

    def __init__(self) -> None:
        self._analyses: Dict[str, Dict[str, Any]] = {}
        self._reports: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    def create_analysis(self, payload: AnalysisRequest) -> Dict[str, Any]:
        analysis_id = str(uuid4())
        now = datetime.utcnow()
        customer_data = payload.customer.model_dump()
        if payload.requested_by:
            customer_data["requested_by"] = payload.requested_by
        record = {
            "id": analysis_id,
            "customer": customer_data,
            "financial_statements": [statement.model_dump() for statement in payload.financial_statements],
            "collateral_info": payload.collateral_info.model_dump(),
            "requested_by": payload.requested_by,
            "status": "RUNNING",
            "analysis_date": now,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self._analyses[analysis_id] = record
        return deepcopy(record)

    def list_analyses(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [deepcopy(record) for _, record in sorted(self._analyses.items(), key=lambda item: item[1]["created_at"], reverse=True)]

    def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._analyses.get(analysis_id)
            return deepcopy(record) if record else None

    def complete_analysis(
        self,
        analysis_id: str,
        *,
        metrics: Dict[str, Any],
        scores: Dict[str, Any],
        web_profile: Dict[str, Any],
        llm_sections: Dict[str, str],
        summary: SummaryBlock,
        report_id: str,
    ) -> Dict[str, Any]:
        with self._lock:
            record = self._analyses[analysis_id]
            record.update(
                {
                    "status": "SUCCESS",
                    "metrics": metrics,
                    "scores": scores,
                    "web_profile": web_profile,
                    "llm_sections": llm_sections,
                    "summary": summary.model_dump(),
                    "total_score": scores.get("total_score"),
                    "risk_level": scores.get("risk_level"),
                    "report_id": report_id,
                    "updated_at": datetime.utcnow(),
                }
            )
            return deepcopy(record)

    def fail_analysis(self, analysis_id: str, error: str) -> None:
        with self._lock:
            record = self._analyses.get(analysis_id)
            if not record:
                return
            record.update(
                {
                    "status": "FAILED",
                    "summary": {
                        "headline": "Analysis failed",
                        "key_risks": [error],
                        "suggestions": [],
                    },
                }
            )
            record["updated_at"] = datetime.utcnow()

    def save_report(self, analysis_id: str, *, markdown: str, html: str) -> str:
        report_id = str(uuid4())
        self._reports[report_id] = {
            "id": report_id,
            "analysis_id": analysis_id,
            "markdown": markdown,
            "html": html,
            "created_at": datetime.utcnow(),
        }
        return report_id

    def get_report(self, analysis_id: str, format_: str = "html") -> Optional[Dict[str, Any]]:
        with self._lock:
            for report in self._reports.values():
                if report["analysis_id"] == analysis_id:
                    payload = {"analysis_id": analysis_id, "format": format_.lower()}
                    if format_.lower() == "markdown":
                        payload["content"] = report["markdown"]
                    else:
                        payload["content"] = report["html"]
                    return payload
        return None


_STORE = MemoryStore()


def get_store() -> MemoryStore:
    return _STORE
