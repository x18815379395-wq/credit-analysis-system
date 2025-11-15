# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx
import logging
from jinja2 import Template

from app.core.config import settings

logger = logging.getLogger(__name__)

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(self, *, prompt: str, model: str, task_type: str) -> Optional[str]:
        raise NotImplementedError


class MockLLMProvider(BaseLLMProvider):
    async def generate(self, *, prompt: str, model: str, task_type: str) -> Optional[str]:
        return f"[{task_type}] {prompt[:400]}"


class HttpLLMProvider(BaseLLMProvider):
    """Generic JSON endpoint provider (expects `model` + `prompt`)."""

    def __init__(self, base_url: str, api_key: Optional[str], timeout: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def generate(self, *, prompt: str, model: str, task_type: str) -> Optional[str]:
        payload = {"model": model, "prompt": prompt, "task_type": task_type}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()
            return self._extract_text(response)

    def _extract_text(self, response: httpx.Response) -> Optional[str]:
        data = response.json()
        if isinstance(data, dict):
            if "output" in data:
                return data["output"]
            if "choices" in data and data["choices"]:
                choice = data["choices"][0]
                if isinstance(choice, dict):
                    return choice.get("text") or choice.get("message", {}).get("content")
        if isinstance(data, list) and data:
            return str(data[0])
        return None


class OpenAIStyleProvider(HttpLLMProvider):
    """Provider for OpenAI-compatible chat completions (OpenAI, OpenRouter, Grok, Kimi, etc.)."""

    def __init__(self, base_url: str, api_key: Optional[str], timeout: int) -> None:
        super().__init__(base_url, api_key, timeout)

    async def generate(self, *, prompt: str, model: str, task_type: str) -> Optional[str]:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a risk analyst assistant who responds with JSON when instructed."},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()
            return self._extract_text(response)


class LLMService:
    """LLM-aware service that routes tasks to configured providers with template rendering."""

    PROVIDER_ENDPOINTS: Dict[str, str] = {
        "openai": "https://api.openai.com/v1/chat/completions",
        "openrouter": "https://openrouter.ai/api/v1/chat/completions",
        "deepseek": "https://api.deepseek.com/chat/completions",
        "deepsee": "https://api.deepseek.com/chat/completions",
        "grok": "https://api.x.ai/v1/chat/completions",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "kimi": "https://api.moonshot.cn/v1/chat/completions",
    }

    TEMPLATES = {
        "INDUSTRY_ANALYSIS": Template(
            "你是银行企业分析师。根据行业画像 {{ industry }} 和公司信息 {{ company }} ，总结行业环境、生命周期与主要风险/机会。"
        ),
        "FINANCIAL_EXPLAIN": Template(
            "你是财务分析师。根据以下指标 {{ metrics }} ，总结盈利能力、杠杆水平、现金流与营运效率，给出 3 条观察。"
        ),
        "RISK_SUMMARY": Template(
            "结合评分 {{ scores }}、指标 {{ metrics }}、企业画像 {{ profile }} ，输出 JSON："
            '{"headline":"...","key_risks":["..."],"suggestions":["..."],"narrative":"..."}'
        ),
        "COMPANY_PROFILE_ENRICH": Template(
            "根据工商信息 {{ company }} 与行业信息 {{ industry }} ，输出 JSON ："
            '{"company": {...}, "industry": {...}} ，补全治理、业务模式、抵押等字段。'
        ),
        "OCR_STRUCTURED_PARSE": Template(
            "以下是财报 OCR 文本：```{{ document }}``` 请解析近三年财务数据，输出 JSON 数组："
            '[{"year":2022,"income_statement":{...},"balance_sheet":{...},"cashflow_statement":{...}}, ...]'
        ),
    }

    def __init__(self) -> None:
        self.provider = self._resolve_provider()
        self.models = settings.LLM_TASK_MODELS or {}

    def _resolve_provider(self) -> BaseLLMProvider:
        provider_name = (settings.LLM_PROVIDER or "mock").lower()
        timeout = settings.LLM_TIMEOUT_SECONDS
        api_key = settings.LLM_API_KEY
        api_base = settings.LLM_API_BASE

        if provider_name in {"mock", ""}:
            return MockLLMProvider()

        if provider_name == "http" and api_base:
            return HttpLLMProvider(api_base, api_key, timeout)

        if provider_name in self.PROVIDER_ENDPOINTS:
            base_url = api_base or self.PROVIDER_ENDPOINTS[provider_name]
            return OpenAIStyleProvider(base_url, api_key, timeout)

        return MockLLMProvider()

    async def generate_industry_analysis(self, profile: Dict[str, Any], metrics: Dict[str, Any]) -> str:
        prompt = self._render_template(
            "INDUSTRY_ANALYSIS",
            {"industry": profile.get("industry", {}), "company": profile.get("company", {}), "metrics": metrics},
        )
        response = await self._call("INDUSTRY_ANALYSIS", prompt)
        return response or self._fallback_industry_text(profile)

    async def explain_financials(self, metrics: Dict[str, Any]) -> str:
        prompt = self._render_template("FINANCIAL_EXPLAIN", {"metrics": metrics})
        response = await self._call("FINANCIAL_EXPLAIN", prompt)
        return response or self._fallback_financial_text(metrics)

    async def summarize_risks(
        self,
        scores: Dict[str, Any],
        metrics: Dict[str, Any],
        profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        prompt = self._render_template("RISK_SUMMARY", {"scores": scores, "metrics": metrics, "profile": profile})
        response = await self._call("RISK_SUMMARY", prompt)
        if response:
            parsed = self._parse_summary(response)
            if parsed:
                return parsed
        return self._fallback_risk_summary(scores, metrics)

    async def enrich_company_profile(self, company: Dict[str, Any], industry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        prompt = self._render_template("COMPANY_PROFILE_ENRICH", {"company": company, "industry": industry})
        response = await self._call("COMPANY_PROFILE_ENRICH", prompt)
        if not response:
            return None
        try:
            data = json.loads(response)
            if isinstance(data, dict) and "company" in data and "industry" in data:
                return data
        except json.JSONDecodeError:
            return None
        return None

    async def parse_financials_from_text(self, document_text: str) -> Optional[List[Dict[str, Any]]]:
        prompt = self._render_template("OCR_STRUCTURED_PARSE", {"document": document_text})
        response = await self._call("OCR_STRUCTURED_PARSE", prompt)
        if not response:
            return None
        try:
            data = json.loads(response)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            return None
        return None

    def _render_template(self, task_type: str, variables: Dict[str, Any]) -> str:
        template = self.TEMPLATES.get(task_type)
        if template:
            return template.render(**variables)
        return json.dumps(variables, ensure_ascii=False)

    async def _call(self, task_type: str, prompt: str) -> Optional[str]:
        model = self.models.get(task_type, settings.LLM_TASK_MODELS.get(task_type, "general-16k"))
        try:
            return await self.provider.generate(prompt=prompt, model=model, task_type=task_type)
        except Exception as exc:
            logger.exception("LLM task %s failed: %s", task_type, exc)
            return None

    def _parse_summary(self, payload: str) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(payload)
            if isinstance(data, dict):
                return {
                    "headline": data.get("headline") or self._first_sentence(data.get("narrative", "")),
                    "key_risks": data.get("key_risks") or self._extract_bullets(payload, ["风险", "risk"]),
                    "suggestions": data.get("suggestions") or self._extract_bullets(payload, ["建议", "mitigation"]),
                    "narrative": data.get("narrative") or payload,
                }
        except json.JSONDecodeError:
            return None
        return None

    def _fallback_industry_text(self, profile: Dict[str, Any]) -> str:
        industry = profile.get("industry", {})
        name = industry.get("name", "目标行业")
        lifecycle = industry.get("lifecycle", "成熟期")
        risks = ", ".join(industry.get("risks", ["需求波动"]))
        opportunities = ", ".join(industry.get("opportunities", ["区域扩张"]))
        return f"{name}处于{lifecycle}阶段，机会集中在{opportunities}，需关注{risks}等变化。"

    def _fallback_financial_text(self, metrics: Dict[str, Any]) -> str:
        latest = metrics.get("latest_year", {})
        revenue = latest.get("revenue")
        margin = latest.get("gross_margin")
        leverage = latest.get("asset_liability_ratio")
        ocf_ratio = latest.get("ocf_vs_profit")
        parts = []
        if revenue is not None:
            parts.append(f"营收约 {revenue:,.0f}")
        if margin is not None:
            parts.append(f"毛利率 {margin:.1%}")
        if leverage is not None:
            parts.append(f"资产负债率 {leverage:.0%}")
        if ocf_ratio is not None:
            parts.append(f"经营现金流 / 净利润 {ocf_ratio:.2f}")
        return "；".join(parts) or "财务数据需进一步补齐。"

    def _fallback_risk_summary(self, scores: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        latest = metrics.get("latest_year", {})
        leverage = latest.get("asset_liability_ratio")
        ocf_ratio = latest.get("ocf_vs_profit")
        risks = ["客户集中度待核实"]
        if leverage and leverage > 0.75:
            risks.append("资产负债率偏高")
        if ocf_ratio and ocf_ratio < 0.8:
            risks.append("经营性现金流覆盖不足")
        suggestions = [
            "设置授信集中度上限与触发条款",
            "结合抵押或保证增强担保",
            "按季度跟踪经营现金流波动",
        ]
        headline = f"等级 {scores.get('risk_level', 'B')}：关注 {risks[0]}"
        narrative = (
            f"综合得分 {scores.get('total_score', 0)}。主要风险：{', '.join(risks)}。"
            f"建议：{', '.join(suggestions)}。"
        )
        return {"headline": headline, "key_risks": risks, "suggestions": suggestions, "narrative": narrative}

    def _first_sentence(self, text: str) -> str:
        if not text:
            return ""
        for separator in ["。", ".", "\n"]:
            if separator in text:
                return text.split(separator)[0]
        return text

    def _extract_bullets(self, text: str, keywords: List[str]) -> List[str]:
        bullets: List[str] = []
        for line in text.splitlines():
            normalized = line.strip(" -*0123456789.")
            if any(keyword.lower() in normalized.lower() for keyword in keywords):
                bullets.append(normalized)
        return bullets[:5]
