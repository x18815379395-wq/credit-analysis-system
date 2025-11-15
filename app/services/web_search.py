from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

import httpx

from app.core.config import settings

if TYPE_CHECKING:  # pragma: no cover - avoid circular import
    from .llm_service import LLMService


class ExternalSearchClient:
    def __init__(self, base_url: str, api_key: Optional[str], timeout: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def fetch_company_profile(self, *, name: str, region: Optional[str], uscc: Optional[str]) -> Dict[str, Any]:
        params = {"name": name, "region": region, "uscc": uscc}
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/company-profile", params=params, headers=headers)
            response.raise_for_status()
            return response.json()


class WebSearchService:
    """Fetch industry/company signals from external APIs with mock fallback."""

    def __init__(self, llm_service: "LLMService | None" = None) -> None:  # noqa: F821
        self.client: Optional[ExternalSearchClient] = None
        self.llm_service = llm_service
        if settings.SEARCH_API_BASE_URL:
            self.client = ExternalSearchClient(
                base_url=str(settings.SEARCH_API_BASE_URL),
                api_key=settings.SEARCH_API_KEY,
                timeout=settings.SEARCH_TIMEOUT_SECONDS,
            )

    async def enrich_company_profile(
        self,
        *,
        name: str,
        uscc: Optional[str],
        region: Optional[str],
        industry_code: Optional[str],
    ) -> Dict[str, Any]:
        if self.client:
            try:
                data = await self.client.fetch_company_profile(name=name, region=region, uscc=uscc)
                industry = data.get("industry") or {}
                company = data.get("company") or {}
                return {
                    "company": self._normalize_company_payload(name, region, company),
                    "industry": industry or self._fallback_industry(industry_code),
                }
            except httpx.HTTPError:
                pass

        return {
            "company": self._normalize_company_payload(name, region, {}),
            "industry": self._fallback_industry(industry_code),
        }

    def _normalize_company_payload(self, name: str, region: Optional[str], company: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._fallback_company(name, region)
        for key, value in company.items():
            if key == "shareholders" and isinstance(value, list):
                payload["shareholders"] = value
                continue
            if value in (None, "", []):
                continue
            payload[key] = value
        payload["last_updated"] = company.get("last_updated") or datetime.utcnow().isoformat()
        return payload

    def _fallback_company(self, name: str, region: Optional[str]) -> Dict[str, Any]:
        return {
            "name": name,
            "region": region,
            "uscc": "91440300MA5FXXXXXX",
            "register_date": "2014-05-18",
            "registered_capital": 5000.0,
            "paid_in_capital": 3800.0,
            "registered_address": (region or "广东省深圳市") + "南山大道 88 号创新大厦 15F",
            "legal_person": "李明",
            "industry_category": "智能制造",
            "equity_structure": "控股股东 55%，创始团队 30%，员工持股平台 15%",
            "shareholders": [
                {"name": "星火控股有限公司", "ratio": 55.0},
                {"name": "张三", "ratio": 25.0},
                {"name": "员工持股平台", "ratio": 20.0},
            ],
            "last_updated": datetime.utcnow().isoformat(),
            "governance": {
                "experience_years": 8,
                "negative_records": False,
                "transparency": "medium",
            },
            "business_scope": "研发、生产并销售智能制造设备，提供工业自动化整体解决方案。",
            "business_model": {
                "description": "B2B 客户 + 区域代理",
                "customer_concentration": "medium",
                "payment_terms": "standard",
                "supply_chain_risk": "medium",
            },
            "collateral": {"type": "factory_building", "liquidity": "medium"},
        }

    def _fallback_industry(self, industry_code: Optional[str]) -> Dict[str, Any]:
        lifecycle = "mature"
        if industry_code:
            lifecycle = (
                "growth"
                if industry_code[0].upper() in {"A", "B"}
                else "mature"
                if industry_code[0].upper() in {"C", "D"}
                else "decline"
            )
        return {
            "code": industry_code,
            "name": self._industry_name(industry_code),
            "lifecycle": lifecycle,
            "risk_level": "medium",
            "risks": ["需求波动", "政策调整"],
            "opportunities": ["数字化升级", "绿色转型"],
        }

    def _industry_name(self, code: Optional[str]) -> str:
        if not code:
            return "综合行业"
        mapping = {
            "A": "农林牧渔",
            "B": "采矿",
            "C": "制造业",
            "D": "电力热力",
            "E": "建筑业",
            "F": "批发零售",
        }
        return mapping.get(code[0].upper(), "服务业")
