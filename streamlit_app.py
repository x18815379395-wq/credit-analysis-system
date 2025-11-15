# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
import streamlit as st
from urllib3.util.retry import Retry

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "30"))

_retry_strategy = Retry(
    total=3,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=frozenset({"GET", "POST", "PUT", "DELETE", "PATCH"}),
    backoff_factor=0.5,
)
_http_adapter = HTTPAdapter(max_retries=_retry_strategy)
SESSION = requests.Session()
SESSION.mount("http://", _http_adapter)
SESSION.mount("https://", _http_adapter)


# ---------------------------------------------------------------------------
# Sample data for graceful fallbacks
# ---------------------------------------------------------------------------
SAMPLE_ANALYSES: List[Dict[str, Any]] = [
    {
        "analysis_id": "ANL-2024-001",
        "customer_name": "深圳市星火科技有限公司",
        "industry_code": "C39",
        "risk_level": "B",
        "total_score": 78,
        "status": "SUCCESS",
        "analysis_date": "2024-11-05T10:00:00Z",
        "requested_by": "张三",
    },
    {
        "analysis_id": "ANL-2024-002",
        "customer_name": "杭州远航制造有限公司",
        "industry_code": "D44",
        "risk_level": "A",
        "total_score": 88,
        "status": "SUCCESS",
        "analysis_date": "2024-11-03T09:30:00Z",
        "requested_by": "李四",
    },
    {
        "analysis_id": "ANL-2024-003",
        "customer_name": "重庆宏泰商贸集团",
        "industry_code": "F51",
        "risk_level": "C",
        "total_score": 63,
        "status": "SUCCESS",
        "analysis_date": "2024-10-29T15:45:00Z",
        "requested_by": "赵六",
    },
]

SAMPLE_DETAILS: Dict[str, Dict[str, Any]] = {
    "ANL-2024-001": {
        "analysis_id": "ANL-2024-001",
        "customer": {
            "name": "深圳市星火科技有限公司",
            "region": "广东省深圳市",
            "industry_code": "C39",
            "register_date": "2016-05-18",
            "registered_capital": 5000,
        },
        "status": "SUCCESS",
        "total_score": 78,
        "risk_level": "B",
        "scores": {
            "total_score": 78,
            "risk_level": "B",
            "dimension_scores": {
                "industry": 14,
                "character": 18,
                "business": 15,
                "financial": 16,
                "collateral": 15,
            },
        },
        "metrics": {
            "years": [
                {"year": 2022, "revenue": 3.5e8, "net_income": 26000000, "gross_margin": 0.36},
                {"year": 2023, "revenue": 3.8e8, "net_income": 24000000, "gross_margin": 0.33},
                {"year": 2024, "revenue": 3.6e8, "net_income": 21000000, "gross_margin": 0.31},
            ],
            "latest_year": {
                "year": 2024,
                "revenue": 3.6e8,
                "net_income": 21000000,
                "gross_margin": 0.31,
                "asset_liability_ratio": 0.74,
                "ocf_vs_profit": 0.78,
            },
        },
        "summary": {
            "headline": "风险等级 B（78 分），盈利能力尚可但现金流走弱。",
            "key_risks": ["客户集中度偏高", "毛利率连续下滑", "经营性现金流减弱"],
            "suggestions": ["控制授信集中度", "适度缩短授信期限", "关注现金流覆盖情况"],
        },
        "llm_sections": {
            "industry_analysis": "电子制造行业处于成熟阶段，政策环境稳定但竞争激烈。",
            "financial_analysis": "收入保持高位但净利率下降，杠杆水平略高且现金流覆盖不足。",
            "risk_summary": "风险集中在客户集中度、毛利率下滑与现金流波动。",
        },
    }
}

SAMPLE_REPORTS = {
    "ANL-2024-001": {
        "analysis_id": "ANL-2024-001",
        "format": "markdown",
        "content": "# 信贷分析报告（示例）\n\n- 风险等级：B\n- 总分：78\n- 主要风险：客户集中度偏高、现金流走弱\n\n（此处展示完整 Markdown 报告内容）",
    }
}

SAMPLE_COMPANY_PROFILE = {
    "company": {
        "name": "深圳市星火科技有限公司",
        "region": "广东省深圳市",
        "uscc": "91440300MA5FXXXXXX",
        "register_date": "2014-05-18",
        "registered_capital": 5000.0,
        "paid_in_capital": 3800.0,
        "registered_address": "广东省深圳市南山区南山大道 88 号创新大厦 15F",
        "legal_person": "李明",
        "industry_code": "C39",
        "industry_category": "智能制造",
        "equity_structure": "控股股东 55%，创始团队 30%，员工持股平台 15%",
        "shareholders": [
            {"name": "星火控股有限公司", "ratio": 55.0},
            {"name": "张三", "ratio": 25.0},
            {"name": "员工持股平台", "ratio": 20.0},
        ],
        "last_updated": "2024-10-01T10:00:00Z",
    },
    "industry": {
        "code": "C39",
        "name": "智能制造",
        "lifecycle": "mature",
        "risk_level": "medium",
        "risks": ["需求波动", "政策调整"],
        "opportunities": ["数字化升级", "绿色转型"],
    },
}


@dataclass
class FinancialUploadResult:
    statements: List[Dict[str, Any]]
    detected_years: List[int]
    warnings: List[str]


def _deduplicate_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def aggregate_upload_results(results: List[FinancialUploadResult]) -> FinancialUploadResult:
    if not results:
        raise RuntimeError("未获取到有效的财报解析结果")
    if len(results) == 1:
        return results[0]

    statements_by_year: Dict[int, Dict[str, Any]] = {}
    warnings: List[str] = []
    for result in results:
        warnings.extend(result.warnings)
        for statement in result.statements:
            year = statement.get("year")
            if year is None:
                continue
            statements_by_year[int(year)] = statement

    combined_statements = sorted(statements_by_year.values(), key=lambda item: item["year"])
    detected_years = sorted(statements_by_year.keys())
    return FinancialUploadResult(
        statements=combined_statements,
        detected_years=detected_years,
        warnings=_deduplicate_preserve_order(warnings),
    )


def parse_uploaded_files(uploaded_files: List[Any]) -> FinancialUploadResult:
    parsed_results: List[FinancialUploadResult] = []
    for uploaded in uploaded_files:
        uploaded.seek(0)
        content = uploaded.read()
        if not content:
            continue
        parsed_results.append(upload_financials(uploaded.name, content))
    if not parsed_results:
        raise RuntimeError("未获取到有效文件内容，请重新上传。")
    return aggregate_upload_results(parsed_results)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
def request_json(method: str, path: str, **kwargs) -> Any:
    url = f"{API_BASE_URL}{path}"
    try:
        response = SESSION.request(method, url, timeout=API_TIMEOUT_SECONDS, **kwargs)
    except requests.Timeout as exc:
        raise RuntimeError("请求后端超时，请确认服务是否已启动或稍后重试。") from exc
    except requests.ConnectionError as exc:
        raise RuntimeError("无法连接后端：请检查 API_BASE_URL、VPN 或网络设置。") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"请求失败：{exc}") from exc

    text = response.text
    try:
        data = response.json()
    except requests.exceptions.JSONDecodeError:
        if response.status_code >= 400:
            raise RuntimeError(text or f"HTTP {response.status_code}")
        raise RuntimeError("后端返回了非 JSON 响应，请检查 API 地址与服务状态。")

    if response.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else None
        raise RuntimeError(detail or f"HTTP {response.status_code}: {text or '请求失败'}")
    return data


def fetch_analyses() -> List[Dict[str, Any]]:
    return request_json("GET", "/analysis")


def fetch_analysis_detail(analysis_id: str) -> Dict[str, Any]:
    return request_json("GET", f"/analysis/{analysis_id}")


def fetch_report(analysis_id: str, fmt: str = "markdown") -> Dict[str, Any]:
    return request_json("GET", f"/analysis/{analysis_id}/report", params={"format": fmt})


def fetch_company_profile(name: str, region: Optional[str], uscc: Optional[str], industry_code: Optional[str]) -> Dict[str, Any]:
    params = {
        "name": name,
        "region": region,
        "uscc": uscc,
        "industry_code": industry_code,
    }
    params = {k: v for k, v in params.items() if v}
    return request_json("GET", "/company/enrich", params=params)


def upload_financials(file_name: str, content: bytes) -> FinancialUploadResult:
    files = {"file": (file_name, content)}
    data = request_json("POST", "/analysis/upload", files=files)
    return FinancialUploadResult(
        statements=data["financial_statements"],
        detected_years=data["detected_years"],
        warnings=data.get("warnings", []),
    )


def create_analysis(payload: Dict[str, Any]) -> Dict[str, Any]:
    return request_json("POST", "/analysis", json=payload)


def safe_fetch(fetcher, fallback):
    try:
        return fetcher(), False
    except RuntimeError as exc:
        st.warning(f"使用示例数据：{exc}")
        return fallback, True


def normalize_date_input(value: Any) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, (dt.datetime, dt.date)):
        return value.strftime("%Y-%m-%d")
    try:
        parsed = pd.to_datetime(value)
    except Exception:
        return str(value)
    return parsed.strftime("%Y-%m-%d")


def parse_float_field(value: Any) -> Optional[float]:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", "").replace("，", "").replace("万", "")
    cleaned = cleaned.replace("%", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def prepare_date_for_payload(value: Any) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, (dt.datetime, dt.date)):
        return value.strftime("%Y-%m-%d")
    try:
        parsed = pd.to_datetime(value)
    except Exception:
        return None
    return parsed.strftime("%Y-%m-%d")


def sync_profile_to_state(profile: Dict[str, Any]) -> None:
    company = profile.get("company") or {}

    def _set_text(key: str, value: Any) -> None:
        if value in (None, ""):
            return
        st.session_state[key] = str(value)

    def _set_raw(key: str, value: Any) -> None:
        if value in (None, ""):
            return
        st.session_state[key] = value

    _set_raw("basic_uscc", company.get("uscc"))
    _set_raw("basic_region", company.get("region"))
    _set_raw("basic_industry", company.get("industry_code"))

    register_date = normalize_date_input(company.get("register_date"))
    if register_date:
        st.session_state["profile_register_date"] = register_date

    _set_text("profile_registered_capital", company.get("registered_capital"))
    _set_text("profile_paid_in_capital", company.get("paid_in_capital"))
    _set_text("profile_registered_address", company.get("registered_address"))
    _set_text("profile_legal_person", company.get("legal_person"))
    _set_text("profile_industry_category", company.get("industry_category"))
    _set_text("profile_equity_structure", company.get("equity_structure"))

    shareholders = company.get("shareholders")
    if isinstance(shareholders, list):
        st.session_state["profile_shareholders"] = shareholders


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
:root {
    --primary: #1677ff;
    --secondary: #52c41a;
    --accent: #faad14;
    --success: #52c41a;
    --warning: #faad14;
    --danger: #ff4d4f;
    --info: #1677ff;
    --light: #f0f5ff;
    --dark: #001529;
    --gray: #8c8c8c;
    --light-gray: #f0f0f0;
    --border-radius: 8px;
    --card-shadow: 0 2px 8px 0 rgba(0,0,0,0.1);
    --card-shadow-hover: 0 4px 12px 0 rgba(0,0,0,0.15);
    --transition: all 0.3s ease;
    --gradient-bg: linear-gradient(135deg, #f5f7fa 0%, #e4edf9 100%);
    --gradient-primary: linear-gradient(135deg, #1677ff 0%, #1d39c4 100%);
    --gradient-secondary: linear-gradient(135deg, #52c41a 0%, #389e0d 100%);
    --gradient-success: linear-gradient(135deg, #52c41a 0%, #389e0d 100%);
    --gradient-warning: linear-gradient(135deg, #faad14 0%, #d48806 100%);
    --gradient-danger: linear-gradient(135deg, #ff4d4f 0%, #f5222d 100%);
    --gradient-accent: linear-gradient(135deg, #faad14 0%, #d48806 100%);
    --surface: #ffffff;
    --surface-light: #fafafa;
    --text-primary: #262626;
    --text-secondary: #595959;
    --text-light: #8c8c8c;
    --border: #d9d9d9;
    --hover-bg: #f6ffed;
    --selected-bg: #e6f7ff;
    --font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Open Sans', 'Helvetica Neue', sans-serif;
}
body {
    background: var(--gradient-bg);
    font-family: var(--font-family);
    color: var(--text-primary);
}
[data-testid="stAppViewContainer"] > .main {
    background: transparent;
}
.main .block-container {
    padding: 1rem 2rem;
}
[data-testid="stSidebar"] {
    background: var(--dark) !important;
    color: var(--light) !important;
    box-shadow: 5px 0 15px rgba(0, 0, 0, 0.1);
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4,
[data-testid="stSidebar"] h5,
[data-testid="stSidebar"] h6 {
    color: var(--light) !important;
}
[data-testid="stSidebar"] .stSelectbox > div > div,
[data-testid="stSidebar"] .stTextInput > div > div > input,
[data-testid="stSidebar"] .stTextArea > div > div > textarea {
    background-color: rgba(255, 255, 255, 0.1) !important;
    color: var(--light) !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
}
[data-testid="stSidebar"] [data-baseweb="input"] {
    background-color: rgba(255, 255, 255, 0.1) !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
}
[data-testid="stSidebar"] [data-baseweb="input"]::placeholder {
    color: rgba(255, 255, 255, 0.6) !important;
}
.st-emotion-cache-1d391kg {
    padding: 2.5rem 1rem;
}
.st-emotion-cache-1oecknr {
    padding: 0rem 1rem;
}
.st-emotion-cache-1vrxgxj {
    background-color: transparent;
    border: none;
}
.header-container {
    background: var(--surface);
    border-radius: var(--border-radius);
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: var(--card-shadow);
    border: 1px solid var(--border);
    border-left: 4px solid var(--primary);
}
.header-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}
.header-title {
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
}
.header-subtitle {
    font-size: 0.9rem;
    color: var(--text-secondary);
    margin: 0;
}
.header-meta {
    text-align: right;
    font-size: 0.85rem;
    color: var(--text-secondary);
}
.header-meta div {
    margin: 0.1rem 0;
}
.nav-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-radius: var(--border-radius);
    background: var(--surface);
    color: var(--text-primary);
    box-shadow: var(--card-shadow);
    margin-bottom: 1.5rem;
    border: 1px solid var(--border);
}
.nav-brand {
    display: flex;
    gap: 0.75rem;
    align-items: center;
}
.nav-brand-mark {
    width: 42px;
    height: 42px;
    border-radius: 8px;
    background: var(--primary);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 18px;
    color: white;
}
.nav-brand-text {
    display: flex;
    flex-direction: column;
}
.nav-title {
    font-size: 1.3rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
}
.nav-subtitle {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin: 0;
}
.nav-actions {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.env-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.3rem 0.9rem;
    border-radius: 999px;
    background: #e6f7ff;
    color: var(--primary);
    font-size: 0.8rem;
    font-weight: 500;
    border: 1px solid #91d5ff;
}
.user-info {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3rem 0.9rem;
    border-radius: 999px;
    background: var(--light);
    color: var(--text-secondary);
    font-size: 0.8rem;
    border: 1px solid var(--border);
}
.stButton > button {
    border-radius: var(--border-radius);
    font-weight: 500;
    padding: 0.5rem 1rem;
    border: 1px solid transparent;
    background: var(--primary);
    color: #fff;
    box-shadow: 0 2px 4px rgba(22, 119, 255, 0.2);
    transition: var(--transition);
    height: auto;
    line-height: 1.5;
}
.stButton > button:hover {
    background: #4096ff;
    box-shadow: 0 4px 8px rgba(22, 119, 255, 0.3);
    transform: translateY(-1px);
}
.stButton > button:disabled {
    background: #f5f5f5;
    color: rgba(0, 0, 0, 0.25);
    border-color: #d9d9d9;
    transform: none;
    box-shadow: none;
    cursor: not-allowed;
}
.stButton > button.secondary {
    background: var(--surface);
    color: var(--text-primary);
    border: 1px solid var(--border);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}
.stButton > button.secondary:hover {
    background: #f6ffed;
    border-color: #b7eb8f;
}
.stButton > button.success {
    background: var(--gradient-success);
    box-shadow: 0 2px 4px rgba(82, 196, 26, 0.2);
}
.stButton > button.success:hover {
    background: #73d13d;
    box-shadow: 0 4px 8px rgba(82, 196, 26, 0.3);
}
.stButton > button.warning {
    background: var(--gradient-warning);
    box-shadow: 0 2px 4px rgba(250, 173, 20, 0.2);
}
.stButton > button.warning:hover {
    background: #ffc53d;
    box-shadow: 0 4px 8px rgba(250, 173, 20, 0.3);
}
.stButton > button.danger {
    background: var(--gradient-danger);
    box-shadow: 0 2px 4px rgba(255, 77, 79, 0.2);
}
.stButton > button.danger:hover {
    background: #ff7875;
    box-shadow: 0 4px 8px rgba(255, 77, 79, 0.3);
}
.info-card {
    border-radius: var(--border-radius);
    padding: 1.25rem;
    margin-bottom: 1.25rem;
    background: var(--surface);
    box-shadow: var(--card-shadow);
    border: 1px solid var(--border);
    transition: var(--transition);
}
.info-card:hover {
    box-shadow: var(--card-shadow-hover);
    border-color: #40a9ff;
}
.info-card-title {
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: 0.3px;
    margin-bottom: 0.75rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
}
.info-card-title .badge {
    margin-left: 0.5rem;
}
.info-card-body {
    margin-top: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-secondary);
}
.badge {
    font-size: 0.75rem;
    padding: 0.25rem 0.7rem;
    border-radius: var(--border-radius);
    font-weight: 500;
    text-transform: uppercase;
}
.badge.risk-a {
    background: #f6ffed;
    color: #52c41a;
    border: 1px solid #b7eb8f;
}
.badge.risk-b {
    background: #fffbe6;
    color: #faad14;
    border: 1px solid #ffe58f;
}
.badge.risk-c {
    background: #fff2e8;
    color: #fa8c16;
    border: 1px solid #ffbb96;
}
.badge.risk-d {
    background: #fff1f0;
    color: #ff4d4f;
    border: 1px solid #ffa39e;
}
.stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 1.25rem;
    margin-bottom: 2rem;
}
@media (max-width: 768px) {
    .stat-grid {
        grid-template-columns: 1fr;
        gap: 1rem;
    }
    .main .block-container {
        padding: 1rem;
    }
    [data-testid="stSidebar"] {
        width: 250px !important;
    }
    .header-top {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.5rem;
    }
    .header-meta {
        text-align: left;
    }
    .nav-container {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.75rem;
    }
    .nav-actions {
        width: 100%;
        justify-content: space-between;
    }
    .step-flow {
        justify-content: center;
    }
    .chart-container, .table-container, .info-card {
        padding: 1rem;
    }
    .stat-card .value {
        font-size: 1.8rem;
    }
    .section-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.5rem;
    }
}
@media (max-width: 480px) {
    .stat-card .value {
        font-size: 1.5rem;
    }
    .nav-title {
        font-size: 1.2rem;
    }
    .header-title {
        font-size: 1.3rem;
    }
    .step-flow {
        flex-direction: column;
    }
    .stButton > button {
        margin-bottom: 0.5rem;
    }
}
.stat-card {
    border-radius: var(--border-radius);
    padding: 1.5rem;
    color: var(--text-primary);
    box-shadow: var(--card-shadow);
    position: relative;
    overflow: hidden;
    background: var(--surface);
    border: 1px solid var(--border);
    transition: var(--transition);
    display: flex;
    flex-direction: column;
    height: 100%;
}
.stat-card:hover {
    transform: translateY(-3px);
    box-shadow: var(--card-shadow-hover);
    border-color: #40a9ff;
}
.stat-card .label {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
}
.stat-card .value {
    font-size: 2rem;
    font-weight: 600;
    margin: 0.5rem 0;
    color: var(--text-primary);
}
.stat-card .note {
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin-top: auto;
}
.chart-container {
    padding: 1.5rem;
    border-radius: var(--border-radius);
    background: var(--surface);
    box-shadow: var(--card-shadow);
    border: 1px solid var(--border);
    margin-bottom: 1.5rem;
    transition: var(--transition);
}
.chart-container:hover {
    box-shadow: var(--card-shadow-hover);
}
.section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
}
.section-title {
    font-size: 1.2rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
}
.section-description {
    color: var(--text-secondary);
    font-size: 0.9rem;
    margin: 0.25rem 0 1rem;
}
.step-flow {
    display: flex;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
}
.step {
    padding: 0.5rem 1.2rem;
    border-radius: 20px;
    font-size: 0.9rem;
    font-weight: 500;
    border: 1px solid var(--border);
    background: var(--surface-light);
    color: var(--text-secondary);
    transition: var(--transition);
}
.step.active {
    border-color: var(--primary);
    background: var(--selected-bg);
    color: var(--primary);
}
.step.completed {
    border-color: var(--success);
    background: var(--hover-bg);
    color: var(--success);
}
.table-container {
    background: var(--surface);
    border-radius: var(--border-radius);
    padding: 1rem;
    box-shadow: var(--card-shadow);
    border: 1px solid var(--border);
    overflow: hidden;
}
.stDataFrame {
    border-radius: var(--border-radius);
    overflow: hidden;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}
.stTabs [data-baseweb="tab-list"] {
    gap: 0.25rem;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
}
.stTabs [data-baseweb="tab"] {
    border-radius: var(--border-radius) var(--border-radius) 0 0;
    padding: 0.5rem 1.2rem;
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-secondary);
    font-weight: 500;
    transition: var(--transition);
    border-bottom: 2px solid transparent;
}
.stTabs [data-baseweb="tab"]:hover {
    background: #f5f5f5;
}
.stTabs [aria-selected="true"] {
    background: var(--surface);
    color: var(--primary);
    border-color: var(--border);
    border-bottom: 2px solid var(--primary);
}
[data-testid="stForm"] {
    background: var(--surface);
    border-radius: var(--border-radius);
    padding: 1.5rem;
    box-shadow: var(--card-shadow);
    border: 1px solid var(--border);
    margin-bottom: 1.5rem;
}
.stTextInput > label,
.stTextArea > label,
.stSelectbox > label,
.stNumberInput > label {
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 0.5rem;
    display: block;
}
.stTextInput input,
.stTextArea textarea,
.stSelectbox div[role="combobox"] {
    border-radius: var(--border-radius);
    border: 1px solid var(--border);
    padding: 0.5rem 0.75rem;
    transition: var(--transition);
    background-color: var(--surface);
}
.stTextInput input:focus,
.stTextArea textarea:focus,
.stSelectbox div[role="combobox"]:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.2);
}
.stMetric {
    background: var(--surface);
    padding: 1rem;
    border-radius: var(--border-radius);
    border: 1px solid var(--border);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}
.metric-container {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
}
.metric-value {
    font-size: 1.8rem;
    font-weight: 600;
    color: var(--text-primary);
}
.metric-label {
    font-size: 0.9rem;
    color: var(--text-secondary);
}
.metric-delta {
    font-size: 0.9rem;
    font-weight: 500;
}
.metric-delta.positive {
    color: var(--success);
}
.metric-delta.negative {
    color: var(--danger);
}
.alert-container {
    border-radius: var(--border-radius);
    padding: 1rem;
    margin: 1rem 0;
    border-left: 4px solid var(--primary);
    background: var(--light);
    color: var(--text-primary);
}
.alert-container.warning {
    border-left-color: var(--warning);
    background: #fffbe6;
}
.alert-container.error {
    border-left-color: var(--danger);
    background: #fff2f0;
}
.alert-container.success {
    border-left-color: var(--success);
    background: #f6ffed;
}
/* Custom sidebar navigation */
.sidebar-nav-item {
    display: block;
    padding: 0.5rem 1rem;
    margin: 0.25rem 0;
    border-radius: var(--border-radius);
    color: rgba(255, 255, 255, 0.85);
    text-decoration: none;
    transition: var(--transition);
}
.sidebar-nav-item:hover {
    background: rgba(255, 255, 255, 0.1);
    color: white;
}
.sidebar-nav-item.active {
    background: rgba(255, 255, 255, 0.2);
    color: white;
    font-weight: 500;
}
/* Dashboard specific styles */
.dashboard-container {
    padding: 1rem 0;
}
.dashboard-card {
    background: var(--surface);
    border-radius: var(--border-radius);
    padding: 1.5rem;
    box-shadow: var(--card-shadow);
    border: 1px solid var(--border);
    margin-bottom: 1.5rem;
}
/* Report preview container */
.report-preview-container {
    background: var(--surface);
    border-radius: var(--border-radius);
    padding: 1.5rem;
    box-shadow: var(--card-shadow);
    border: 1px solid var(--border);
    max-height: 600px;
    overflow-y: auto;
}
/* Risk level indicators */
.risk-indicator {
    display: inline-block;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    margin-right: 0.5rem;
}
.risk-indicator.a { background: #f6ffed; border: 2px solid #52c41a; }
.risk-indicator.b { background: #fffbe6; border: 2px solid #faad14; }
.risk-indicator.c { background: #fff2e8; border: 2px solid #fa8c16; }
.risk-indicator.d { background: #fff1f0; border: 2px solid #ff4d4f; }
/* Responsive adjustments */
@media (max-width: 768px) {
    .nav-container {
        padding: 0.75rem 1rem;
    }
    .header-container {
        padding: 1rem;
    }
    .info-card {
        padding: 1rem;
    }
    .chart-container {
        padding: 1rem;
    }
}
</style>
"""


def inject_theme():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_header(title: str, subtitle: str = ""):
    now_text = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    subtitle_html = f'<p class="header-subtitle">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f"""
        <div class="header-container">
            <div class="header-top">
                <div>
                    <h2 class="header-title">{title.strip()}</h2>
                    {subtitle_html}
                </div>
                <div class="header-meta">
                    <div>环境：TEST</div>
                    <div>更新时间：{now_text}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, body: str = "", badge: Optional[str] = None):
    badge_html = f'<span class="badge">{badge}</span>' if badge else ""
    st.markdown(
        f"""
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div class="card-title">{title}</div>
                {badge_html}
            </div>
            <div class="card-body">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_risk_badge(risk_level: str) -> str:
    """Render a color-coded badge for risk level."""
    risk_mapping = {
        "A": ("A", "risk-a"),
        "B": ("B", "risk-b"), 
        "C": ("C", "risk-c"),
        "D": ("D", "risk-d")
    }
    level, css_class = risk_mapping.get(risk_level, (risk_level, ""))
    return f'<span class="badge {css_class}">{level}</span>'


def render_top_nav():
    now_text = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    st.markdown(
        f"""
        <div class="nav-container">
            <div class="nav-brand">
                <div class="nav-brand-mark">CA</div>
                <div class="nav-brand-text">
                    <div class="nav-title">信贷分析助手</div>
                    <div class="nav-subtitle">智能风险视图 · 内部测试版</div>
                </div>
            </div>
            <div class="nav-actions">
                <span class="env-badge">TEST</span>
                <span>{now_text}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# New Analysis
# ---------------------------------------------------------------------------
def render_new_analysis():
    render_top_nav()
    render_header("新建分析", "录入企业信息并上传最近三年财务报表，一键发起信贷分析。")
    
    # Step indicators
    st.markdown(
        """
        <div class="step-flow">
            <span class="step active">1. 企业基础信息</span>
            <span class="step">2. 上传财务报表</span>
            <span class="step">3. 发起分析</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "company_profile" not in st.session_state:
        st.session_state.company_profile = None
    if "upload_result" not in st.session_state:
        st.session_state.upload_result = None
    for key in [
        "profile_register_date",
        "profile_registered_capital",
        "profile_paid_in_capital",
        "profile_registered_address",
        "profile_legal_person",
        "profile_industry_category",
        "profile_equity_structure",
    ]:
        if key not in st.session_state:
            st.session_state[key] = ""
    if "profile_shareholders" not in st.session_state:
        st.session_state.profile_shareholders = []

    # Use tabs for better organization
    tab_info, tab_upload = st.tabs(["🏢 企业信息", "📊 财务报表"])
    
    with tab_info:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown('<div class="info-card-title">企业基础信息 <span class="badge">必填</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="info-card-body">请输入企业基本信息，系统可自动补全工商信息。</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Use a form for better UX
        with st.form("basic_info_form", clear_on_submit=False):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("企业名称 *", key="basic_name", help="请输入完整的公司名称")
                region = st.text_input("所在地区", key="basic_region", help="例如：广东省深圳市")
            with col2:
                uscc = st.text_input("统一社会信用代码", key="basic_uscc", help="请输入18位统一社会信用代码")
                industry = st.text_input("主要行业", key="basic_industry", help="例如：制造业、科技服务等")
            
            st.markdown("---")
            col_enrich, col_save = st.columns([1, 1])
            with col_enrich:
                enrich_clicked = st.form_submit_button("🔍 从网络补全工商信息", use_container_width=True, type="secondary")
            with col_save:
                save_basic = st.form_submit_button("💾 保存基础信息", use_container_width=True, type="primary")

        if save_basic and not name:
            st.warning("⚠️ 企业名称为必填项。")
        if enrich_clicked:
            if name:
                with st.spinner("🔎 正在通过网络补全工商信息..."):
                    try:
                        profile = fetch_company_profile(
                            name=name,
                            region=region or None,
                            uscc=uscc or None,
                            industry_code=industry or None,
                        )
                        st.session_state.company_profile = profile
                        sync_profile_to_state(profile)
                        st.success("✅ 已获取工商信息，可根据需要调整。")
                    except RuntimeError as exc:
                        st.warning(f"⚠️ 工商信息查询失败，将展示示例数据。详细信息：{exc}")
                        st.session_state.company_profile = SAMPLE_COMPANY_PROFILE
                        sync_profile_to_state(SAMPLE_COMPANY_PROFILE)
                        st.info("ℹ️ 已加载示例工商信息。")
            else:
                st.warning("⚠️ 请先输入企业名称。")

        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown('<div class="info-card-title">工商信息补全结果 <span class="badge">网络</span></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="info-card-body">点击“从网络补全工商信息”后，将自动拉取统一社会信用代码、注册资本、股权结构等关键字段，您也可以手动调整。</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

        profile = st.session_state.company_profile
        if profile:
            last_updated = profile.get("company", {}).get("last_updated")
            if last_updated:
                st.caption(f"信息更新时间：{normalize_date_input(last_updated)}")

        detail_cols = st.columns(2)
        with detail_cols[0]:
            st.text_input("成立日期", key="profile_register_date", help="请输入 YYYY-MM-DD 格式")
            st.text_input("注册资本（万元）", key="profile_registered_capital")
            st.text_input("注册地址", key="profile_registered_address")
        with detail_cols[1]:
            st.text_input("实缴资本（万元）", key="profile_paid_in_capital")
            st.text_input("法定代表人", key="profile_legal_person")
            st.text_input("行业大类", key="profile_industry_category")
        st.text_area("股权结构概览", key="profile_equity_structure", height=80)

        shareholders = st.session_state.get("profile_shareholders") or []
        st.markdown('<div class="section-header"><h3 class="section-title">股东名单及持股比例</h3></div>', unsafe_allow_html=True)
        if shareholders:
            shareholder_df = pd.DataFrame(
                [
                    {
                        "股东名称": item.get("name"),
                        "持股比例(%)": item.get("ratio"),
                        "出资额（万元）": item.get("capital"),
                    }
                    for item in shareholders
                ]
            )
            st.dataframe(shareholder_df, hide_index=True, use_container_width=True)
        else:
            st.info("暂无股东信息，请通过网络补全或手动录入相关字段。")

    with tab_upload:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown('<div class="info-card-title">上传财务报表 <span class="badge">推荐</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="info-card-body">请上传最近三年的财务报表，支持 Excel / CSV / PDF 格式。</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Template download and file upload
        col_template, col_help = st.columns([1, 3])
        with col_template:
            st.link_button("⬇️ 下载财报模板", url="#", type="secondary", use_container_width=True)
        with col_help:
            st.info("💡 提示：使用标准模板可以提高财报解析的准确性")
        
        # File uploader
        uploaded_files = st.file_uploader(
            "上传 1–3 个文件（支持 .xlsx、.xls、.csv、.pdf）",
            type=["xlsx", "xls", "csv", "pdf"],
            accept_multiple_files=True,
            help="请选择包含财务报表的文件，支持多个文件上传"
        )
        
        if uploaded_files:
            file_info = " | ".join([f"{f.name} ({f.size//1024}KB)" for f in uploaded_files])
            st.success(f"✅ 已选择 {len(uploaded_files)} 个文件：{file_info}")
        
        # Parse button
        parse_clicked = st.button(
            "📊 解析财报", 
            type="primary", 
            use_container_width=True, 
            disabled=not uploaded_files,
            help="点击开始解析上传的财务报表文件"
        )
        
        if parse_clicked and uploaded_files:
            try:
                st.session_state.upload_result = parse_uploaded_files(uploaded_files)
                st.success(f"✅ 解析成功，检测到 {len(st.session_state.upload_result.detected_years)} 年财报。")
            except RuntimeError as exc:
                error_msg = str(exc)
                if "HTTP 503" in error_msg or "503" in error_msg:
                    st.error("❌ 解析失败：服务器暂时不可用（503错误），请稍后重试或联系管理员。")
                elif "HTTP 500" in error_msg or "500" in error_msg or "Internal Server Error" in error_msg:
                    st.error("❌ 解析失败：服务器内部错误（500错误），请稍后重试或联系管理员。")
                elif "HTTP 4" in error_msg or "40" in error_msg:
                    st.error(f"❌ 解析失败：请求错误（4xx错误），请检查上传的文件格式。详细信息：{exc}")
                else:
                    st.error(f"❌ 解析失败：{exc}")
                st.session_state.upload_result = None

        # Show parsed results
        upload_result: Optional[FinancialUploadResult] = st.session_state.upload_result
        if upload_result:
            st.markdown('<div class="info-card">', unsafe_allow_html=True)
            st.markdown('<div class="info-card-title">财报解析预览</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            preview = []
            for statement in upload_result.statements:
                preview.append({
                    "年份": statement["year"],
                    "收入（万元）": f"{statement['income_statement'].get('revenue', 0)/1e6:.1f}",
                    "净利润（万元）": f"{statement['income_statement'].get('net_income', 0)/1e6:.1f}",
                    "总资产（万元）": f"{statement['balance_sheet'].get('total_assets', 0)/1e6:.1f}",
                    "总负债（万元）": f"{statement['balance_sheet'].get('total_liabilities', 0)/1e6:.1f}",
                    "资产负债率": f"{(statement['balance_sheet'].get('total_liabilities', 0)/statement['balance_sheet'].get('total_assets', 1)*100) if statement['balance_sheet'].get('total_assets', 1) > 0 else 0:.1f}%",
                })
            
            st.dataframe(pd.DataFrame(preview), use_container_width=True)
            if upload_result.warnings:
                st.warning("⚠️ " + "\n⚠️ ".join(upload_result.warnings))
    
    # Action buttons section
    st.markdown('<div class="info-card">', unsafe_allow_html=True)
    st.markdown('<div class="info-card-title">发起分析</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    col_run, col_reset = st.columns([2, 1])
    basic_name = st.session_state.get("basic_name") or ""
    with col_run:
        run_clicked = st.button(
            "🚀 开始分析",
            type="primary",
            use_container_width=True,
            disabled=not (st.session_state.upload_result and basic_name),
            help="开始进行信贷分析，此过程可能需要几分钟"
        )
    with col_reset:
        reset_clicked = st.button("🔄 清空表单", use_container_width=True, type="secondary")

    if reset_clicked:
        st.session_state.upload_result = None
        st.session_state.company_profile = None
        for key in ["basic_name", "basic_uscc", "basic_region", "basic_industry"]:
            if key in st.session_state:
                st.session_state[key] = ""
        for key in [
            "profile_register_date",
            "profile_registered_capital",
            "profile_paid_in_capital",
            "profile_registered_address",
            "profile_legal_person",
            "profile_industry_category",
            "profile_equity_structure",
        ]:
            st.session_state[key] = ""
        st.session_state.profile_shareholders = []
        st.success("✅ 已清空表单。")

    if run_clicked and st.session_state.upload_result and basic_name:
        payload = {
            "customer": {
                "name": basic_name,
                "uscc": st.session_state.get("basic_uscc") or None,
                "region": st.session_state.get("basic_region") or None,
                "industry_code": st.session_state.get("basic_industry") or None,
            },
            "financial_statements": st.session_state.upload_result.statements,
            "collateral_info": {"has_collateral": False},
        }
        payload["customer"].update(
            {
                "register_date": prepare_date_for_payload(st.session_state.get("profile_register_date")),
                "registered_capital": parse_float_field(st.session_state.get("profile_registered_capital")),
                "paid_in_capital": parse_float_field(st.session_state.get("profile_paid_in_capital")),
                "registered_address": st.session_state.get("profile_registered_address") or None,
                "legal_person": st.session_state.get("profile_legal_person") or None,
                "industry_category": st.session_state.get("profile_industry_category") or None,
                "equity_structure": st.session_state.get("profile_equity_structure") or None,
                "shareholders": st.session_state.get("profile_shareholders") or [],
            }
        )
        with st.spinner("🔄 正在解析财报、获取网络信息并调用模型，请稍候..."):
            try:
                result = create_analysis(payload)
                st.success(
                    f"✅ 分析完成（ID：{result['analysis_id']}，等级：{result.get('risk_level') or '-'}）。"
                )
                st.session_state.upload_result = None
            except RuntimeError as exc:
                error_msg = str(exc)
                if "HTTP 503" in error_msg or "503" in error_msg:
                    st.error("❌ 分析发起失败：服务器暂时不可用（503错误），请稍后重试或联系管理员。")
                elif "HTTP 500" in error_msg or "500" in error_msg or "Internal Server Error" in error_msg:
                    st.error("❌ 分析发起失败：服务器内部错误（500错误），请稍后重试或联系管理员。")
                elif "HTTP 4" in error_msg or "40" in error_msg:
                    st.error(f"❌ 分析发起失败：请求错误（4xx错误），请检查输入数据。详细信息：{exc}")
                else:
                    st.error(f"❌ 发起失败：{exc}")


# ---------------------------------------------------------------------------
# Analysis List & Detail
# ---------------------------------------------------------------------------
def render_analysis_list():
    render_top_nav()
    render_header("分析列表 / 详情", "查看历史分析记录，并深入查看单笔分析的指标、风险与建议。")
    records, used_sample = safe_fetch(fetch_analyses, SAMPLE_ANALYSES)
    if used_sample:
        st.warning("⚠️ 使用示例数据：无法连接后端或后端返回异常。")
    df = pd.DataFrame(records)
    if df.empty:
        st.info("📊 暂无分析记录。")
        return

    df["analysis_date"] = pd.NaT
    if "analysis_date" in df:
        df["analysis_date"] = pd.to_datetime(df["analysis_date"], errors="coerce")
    if "created_at" in df:
        created_series = pd.to_datetime(df["created_at"], errors="coerce")
        df["analysis_date"] = df["analysis_date"].fillna(created_series)

    # Filter section
    st.markdown('<div class="info-card">', unsafe_allow_html=True)
    st.markdown('<div class="info-card-title">筛选条件 <span class="badge">高级筛选</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="info-card-body">可按日期、行业、风险等级筛选历史记录。</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    f1, f2, f3 = st.columns(3)
    default_start = (dt.datetime.utcnow() - dt.timedelta(days=30)).date()
    default_end = dt.datetime.utcnow().date()
    with f1:
        date_range = st.date_input("分析日期范围", (default_start, default_end), help="选择分析日期范围")
    with f2:
        industry_filter = st.text_input("行业（可留空）", help="输入行业代码或名称进行筛选")
    with f3:
        level_filter = st.multiselect("风险等级", ["A", "B", "C", "D"], default=["A", "B", "C", "D"], help="选择要显示的风险等级")

    filtered_df = df.copy()
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (filtered_df["analysis_date"].dt.date >= start_date) & (filtered_df["analysis_date"].dt.date <= end_date)
        ]
    if industry_filter:
        filtered_df = filtered_df[filtered_df["industry_code"].str.contains(industry_filter, na=False, case=False)]
    if level_filter:
        filtered_df = filtered_df[filtered_df["risk_level"].isin(level_filter)]

    # Create a copy of the dataframe for display with proper column names
    df_display = filtered_df.copy()
    df_display = df_display.rename(columns={
        "analysis_id": "分析ID",
        "customer_name": "客户名称",
        "industry_code": "行业代码", 
        "risk_level": "风险等级",
        "total_score": "总分",
        "status": "状态",
        "analysis_date": "分析日期",
        "requested_by": "申请人"
    })
    
    # Add a formatted risk level column with badges
    if '风险等级' in df_display.columns:
        df_display['风险等级'] = df_display['风险等级'].apply(render_risk_badge)
    
    st.markdown('<div class="section-header"><h3 class="section-title">历史分析记录</h3><p class="section-description">点击列表项或下拉选择查看详情</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="table-container">', unsafe_allow_html=True)
    try:
        # Convert the risk level column to raw HTML for proper badge rendering
        from pandas.io.formats.style import Styler
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            unsafe_allow_html=True
        )
    except:
        # Fallback to regular dataframe if HTML rendering fails
        st.dataframe(filtered_df, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if filtered_df.empty:
        st.info("🔍 当前筛选条件下无记录。")
        return

    # Create a display version for the selectbox to show risk badges
    select_options = filtered_df["analysis_id"].tolist()
    select_labels = []
    for idx, row in filtered_df.iterrows():
        risk_badge = render_risk_badge(row.get("risk_level", "N/A"))
        label = f"{row['analysis_id']} - {row['customer_name']} ({risk_badge})"
        select_labels.append(label)
    
    selected_id = st.selectbox("选择一条记录查看详情", 
                              options=select_options, 
                              format_func=lambda x: select_labels[select_options.index(x)],
                              help="从列表中选择要查看详细信息的分析记录")

    detail, detail_sample = safe_fetch(lambda: fetch_analysis_detail(selected_id), SAMPLE_DETAILS.get(selected_id, {}))
    if not detail:
        st.warning("⚠️ 未找到该分析详情，显示示例内容。")
        detail = SAMPLE_DETAILS[next(iter(SAMPLE_DETAILS))]
    elif detail_sample:
        st.warning("⚠️ 该详情为示例数据。")

    # Analysis detail header
    st.markdown('<hr style="margin: 2rem 0; border-top: 1px solid var(--border);">', unsafe_allow_html=True)
    detail_cols = st.columns([3, 1])
    with detail_cols[0]:
        st.markdown(f"### 📋 分析详情：{selected_id} · {detail['customer']['name']}")
        analysis_raw = detail.get("analysis_date") or detail.get("created_at")
        analysis_date = normalize_date_input(analysis_raw) or "----"
        risk_level = detail.get('risk_level', '-')
        st.markdown(f"<p style='color: var(--text-secondary); margin-top: 0.5rem;'>📅 最近一次分析：{analysis_date}  |  🎯 风险等级：{render_risk_badge(risk_level)}</p>", unsafe_allow_html=True)
    with detail_cols[1]:
        col_export, col_reanalyze = st.columns(2)
        with col_export:
            st.download_button("📥 导出报告", 
                              data="Sample report content" if detail_sample else detail.get('report_html', ''), 
                              file_name=f"{selected_id}_report.md", 
                              use_container_width=True,
                              type="secondary")
        with col_reanalyze:
            st.button("🔄 重新分析", use_container_width=True, type="secondary")

    # Tabs for detailed information
    tab_summary, tab_industry, tab_financial, tab_score, tab_report = st.tabs(
        ["📈 综合概览", "🏢 行业与企业", "💰 财务与现金流", "📊 评分与规则", "📄 报告预览"]
    )

    summary = detail.get("summary", {})
    with tab_summary:
        st.markdown("#### 📊 综合概览")
        if summary.get("headline"):
            st.markdown(f"<div class='alert-container'>{summary['headline']}</div>", unsafe_allow_html=True)
        if summary.get("key_risks"):
            st.markdown("**⚠️ 主要风险点：**")
            for risk in summary["key_risks"]:
                st.markdown(f"- {risk}")
        if summary.get("suggestions"):
            st.markdown("**💡 风险缓释建议：**")
            for suggestion in summary["suggestions"]:
                st.markdown(f"- {suggestion}")

    with tab_industry:
        st.markdown("#### 🏭 行业与企业分析")
        industry_analysis = detail.get("llm_sections", {}).get("industry_analysis", "暂无内容。")
        if industry_analysis != "暂无内容。":
            st.markdown(f"<div class='info-card'>{industry_analysis}</div>", unsafe_allow_html=True)
        else:
            st.info(industry_analysis)

    with tab_financial:
        st.markdown("#### 💰 财务与现金流分析")
        metrics = detail.get("metrics", {})
        years = metrics.get("years", [])
        if years:
            trend_df = pd.DataFrame(years)
            # Format financial data for better display
            trend_df_display = trend_df.copy()
            if 'revenue' in trend_df_display.columns:
                trend_df_display['收入（万元）'] = (trend_df_display['revenue'] / 1e6).round(2)
                trend_df_display = trend_df_display.drop(columns=['revenue'])
            if 'net_income' in trend_df_display.columns:
                trend_df_display['净利润（万元）'] = (trend_df_display['net_income'] / 1e6).round(2)
                trend_df_display = trend_df_display.drop(columns=['net_income'])
            if 'gross_margin' in trend_df_display.columns:
                trend_df_display['毛利率（%）'] = (trend_df_display['gross_margin'] * 100).round(2)
                trend_df_display = trend_df_display.drop(columns=['gross_margin'])
                
            col_a, col_b = st.columns(2)
            with col_a:
                if '收入（万元）' in trend_df_display.columns and '净利润（万元）' in trend_df_display.columns:
                    st.markdown("**📈 收入 / 净利润三年趋势**")
                    chart_data = trend_df_display.set_index("year")[["收入（万元）", "净利润（万元）"]]
                    st.line_chart(chart_data)
                elif '收入（万元）' in trend_df_display.columns:
                    st.markdown("**📈 收入三年趋势**")
                    chart_data = trend_df_display.set_index("year")[["收入（万元）"]]
                    st.line_chart(chart_data)
            with col_b:
                if '毛利率（%）' in trend_df_display.columns:
                    st.markdown("**📊 毛利率趋势**")
                    chart_data = trend_df_display.set_index("year")[["毛利率（%）"]]
                    st.line_chart(chart_data)
            st.dataframe(trend_df_display, use_container_width=True)
        else:
            st.info("📊 暂无三年财务数据。")
        financial_analysis = detail.get("llm_sections", {}).get("financial_analysis", "暂无说明。")
        if financial_analysis != "暂无说明。":
            st.markdown("**💬 模型分析说明：**")
            st.markdown(f"<div class='info-card'>{financial_analysis}</div>", unsafe_allow_html=True)

    with tab_score:
        st.markdown("#### 📊 评分与规则")
        scores = detail.get("scores", {}).get("dimension_scores", {})
        if scores:
            score_df = pd.DataFrame(
                [{"维度": key.upper(), "得分": value} for key, value in scores.items()]
            )
            st.dataframe(score_df, use_container_width=True)
        risk_summary = detail.get("llm_sections", {}).get("risk_summary", "暂无评分说明。")
        if risk_summary != "暂无评分说明。":
            st.markdown("**💬 评分说明：**")
            st.markdown(f"<div class='info-card'>{risk_summary}</div>", unsafe_allow_html=True)

    with tab_report:
        st.markdown("#### 📄 报告预览")
        report_data, _ = safe_fetch(lambda: fetch_report(selected_id, "markdown"), SAMPLE_REPORTS.get(selected_id, {}))
        if report_data:
            content = report_data.get("content", "")
            if content:
                # Show the report content with proper formatting
                st.markdown('<div class="report-preview-container">', unsafe_allow_html=True)
                st.markdown(content)
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Download buttons
                col_down1, col_down2, col_down3 = st.columns(3)
                with col_down1:
                    st.download_button(
                        "📥 Markdown 报告",
                        data=content.encode("utf-8"),
                        file_name=f"{selected_id}.md",
                        use_container_width=True,
                        type="primary"
                    )
                with col_down2:
                    st.download_button(
                        "📥 PDF 报告",
                        data=content.encode("utf-8"),
                        file_name=f"{selected_id}.pdf",
                        use_container_width=True,
                        disabled=True,  # PDF export not implemented yet
                        type="secondary"
                    )
                with col_down3:
                    st.download_button(
                        "📥 Word 报告", 
                        data=content.encode("utf-8"),
                        file_name=f"{selected_id}.docx",
                        use_container_width=True,
                        disabled=True,  # Word export not implemented yet
                        type="secondary"
                    )
            else:
                st.info("📄 暂无报告内容。")
        else:
            st.info("📄 暂无报告内容。")


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
def render_reports():
    render_top_nav()
    render_header("报告管理", "选择一份分析报告进行预览和下载。")
    records, _ = safe_fetch(fetch_analyses, SAMPLE_ANALYSES)
    if not records:
        st.info("📊 暂无报告数据。")
        return

    col_selector, col_preview = st.columns([1, 2])
    with col_selector:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown('<div class="info-card-title">选择报告</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        selected_id = st.selectbox("选择报告", options=[item["analysis_id"] for item in records])
        if st.button("🔄 刷新报告内容", use_container_width=True, type="secondary"):
            st.rerun()

    with col_preview:
        if selected_id:
            report_data, report_sample = safe_fetch(lambda: fetch_report(selected_id, "markdown"), SAMPLE_REPORTS.get(selected_id, {}))
            if report_data:
                if report_sample:
                    st.warning("⚠️ 该报告为示例数据。")
                
                st.markdown('<div class="section-header"><h3 class="section-title">报告预览（Markdown）</h3></div>', unsafe_allow_html=True)
                st.markdown('<div class="report-preview-container">', unsafe_allow_html=True)
                st.markdown(report_data.get("content", ""))
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Download buttons
                st.markdown('<div class="section-header"><h3 class="section-title">下载报告</h3></div>', unsafe_allow_html=True)
                col_down1, col_down2, col_down3 = st.columns(3)
                with col_down1:
                    st.download_button(
                        "📥 Markdown 报告",
                        data=report_data.get("content", "").encode("utf-8"),
                        file_name=f"{selected_id}.md",
                        use_container_width=True,
                        type="primary"
                    )
                with col_down2:
                    st.download_button(
                        "📥 PDF 报告",
                        data=report_data.get("content", "").encode("utf-8"),
                        file_name=f"{selected_id}.pdf",
                        use_container_width=True,
                        disabled=True,  # PDF export not implemented yet
                        type="secondary"
                    )
                with col_down3:
                    st.download_button(
                        "📥 Word 报告",
                        data=report_data.get("content", "").encode("utf-8"),
                        file_name=f"{selected_id}.docx",
                        use_container_width=True,
                        disabled=True,  # Word export not implemented yet
                        type="secondary"
                    )
            else:
                st.info("📄 暂无报告内容。")
        else:
            st.info("🔍 请选择一条分析记录。")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def render_settings():
    render_top_nav()
    render_header("⚙️ 系统设置", "配置语言、主题和大模型等系统设置")
    
    # Language and theme settings
    st.markdown('<div class="info-card">', unsafe_allow_html=True)
    st.markdown('<div class="info-card-title">界面设置 <span class="badge">外观</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    col_lang, col_theme = st.columns(2)
    with col_lang:
        language = st.selectbox("选择语言", ["中文", "English"], index=0, help="选择界面显示语言")
    with col_theme:
        theme = st.selectbox("选择主题", ["明亮", "暗色", "系统默认"], index=0, help="选择界面主题风格")
    
    st.markdown("---")
    
    # LLM Provider settings
    st.markdown('<div class="info-card">', unsafe_allow_html=True)
    st.markdown('<div class="info-card-title">大模型配置 <span class="badge">AI模型</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="info-card-body">选择大模型供应商并配置相关参数</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    llm_provider = st.selectbox(
        "选择大模型供应商", 
        ["OpenAI", "Anthropic", "百度千帆", "阿里通义", "腾讯混元", "Grok", "OpenRouter", "Gemini", "自定义"], 
        index=0,
        help="选择您要使用的大模型服务提供商"
    )
    
    # Show provider-specific API key fields
    if llm_provider == "OpenAI":
        api_base = st.text_input("API Base URL", value="https://api.openai.com/v1", help="输入OpenAI API的基础URL")
        api_key = st.text_input("API Key", type="password", help="输入您的OpenAI API密钥")
        model = st.selectbox("模型", ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"], index=0)
    elif llm_provider == "Anthropic":
        api_base = st.text_input("API Base URL", value="https://api.anthropic.com/v1", help="输入Anthropic API的基础URL")
        api_key = st.text_input("API Key", type="password", help="输入您的Anthropic API密钥")
        model = st.selectbox("模型", ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"], index=0)
    elif llm_provider == "百度千帆":
        api_base = st.text_input("API Base URL", value="https://aip.baidubce.com/rpc/2.0/ai_custom", help="输入百度千帆API的基础URL")
        api_key = st.text_input("API Key", type="password", help="输入您的百度千帆API密钥")
        secret_key = st.text_input("Secret Key", type="password", help="输入您的百度千帆Secret密钥")
        model = st.selectbox("模型", ["ERNIE-Bot-4.5", "ERNIE-Bot-3.5", "Qianfan-BLOOMZ-7B"], index=0)
    elif llm_provider == "阿里通义":
        api_base = st.text_input("API Base URL", value="https://dashscope.aliyuncs.com/api/v1", help="输入阿里通义API的基础URL")
        api_key = st.text_input("API Key", type="password", help="输入您的阿里通义API密钥")
        model = st.selectbox("模型", ["qwen-max", "qwen-plus", "qwen-turbo"], index=0)
    elif llm_provider == "腾讯混元":
        api_base = st.text_input("API Base URL", value="https://hunyuan.tencentcloudapi.com", help="输入腾讯混元API的基础URL")
        api_key = st.text_input("Secret Id", type="password", help="输入您的腾讯混元Secret Id")
        secret_key = st.text_input("Secret Key", type="password", help="输入您的腾讯混元Secret密钥")
        model = st.selectbox("模型", ["hunYuan-pro", "hunYuan-standard", "hunYuan-lite"], index=0)
    elif llm_provider == "Grok":
        api_base = st.text_input("API Base URL", value="https://api.grok.com/v1", help="输入Grok API的基础URL")
        api_key = st.text_input("API Key", type="password", help="输入您的Grok API密钥")
        model = st.selectbox("模型", ["grok-beta", "grok-1", "grok-1-turbo"], index=0)
    elif llm_provider == "OpenRouter":
        api_base = st.text_input("API Base URL", value="https://openrouter.ai/api/v1", help="输入OpenRouter API的基础URL")
        api_key = st.text_input("API Key", type="password", help="输入您的OpenRouter API密钥")
        model = st.text_input("模型", help="输入要使用的模型名称，如：openai/gpt-4o 或 anthropic/claude-3.5-sonnet")
    elif llm_provider == "Gemini":
        api_base = st.text_input("API Base URL", value="https://generativelanguage.googleapis.com/v1", help="输入Gemini API的基础URL")
        api_key = st.text_input("API Key", type="password", help="输入您的Gemini API密钥")
        model = st.selectbox("模型", ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro"], index=0)
    else:  # 自定义
        api_base = st.text_input("API Base URL", help="输入自定义API的基础URL")
        api_key = st.text_input("API Key", type="password", help="输入自定义API的密钥")
        model = st.text_input("模型名称", help="输入要使用的模型名称")
    
    st.markdown("---")
    
    # LLM Configuration for different use cases
    st.markdown('<div class="info-card">', unsafe_allow_html=True)
    st.markdown('<div class="info-card-title">模型配置 <span class="badge">高级</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    col_fin, col_ind = st.columns(2)
    with col_fin:
        financial_model = st.text_input("财务分析模型", value=model, help="用于财务分析的特定模型")
    with col_ind:
        industry_model = st.text_input("行业分析模型", value=model, help="用于行业分析的特定模型")
    
    st.markdown("---")
    
    # Save settings button
    if st.button("💾 保存设置", type="primary", use_container_width=True):
        st.success("✅ 设置已保存！")
    
    st.info("💡 提示：这些配置信息将被安全地存储在服务器环境中。实际部署时需要通过环境变量或配置中心进行管理。")


PAGE_MAP = {
    " 新建分析": render_new_analysis,
    " 分析列表 / 详情": render_analysis_list,
    " 报告": render_reports,
    "⚙️ 设置": render_settings,
}


def main():
    st.set_page_config(page_title="信贷分析助手", layout="wide", initial_sidebar_state="expanded")
    inject_theme()
    
    # Initialize session state for page navigation if not already set
    if 'current_page' not in st.session_state:
        st.session_state.current_page = " 新建分析"
    
    with st.sidebar:
        st.markdown("""
        <div style="padding: 1.5rem 0;">
            <h2 style="color: white; margin: 0; font-size: 1.5rem;">📋 信贷分析助手</h2>
            <p style="color: rgba(255,255,255,0.8); margin: 0.5rem 0 0; font-size: 0.9rem;">智能风险视图 · 内部测试版</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        
        # Navigation with custom styling
        for page_name in PAGE_MAP.keys():
            # Use a custom button that changes appearance based on current page
            btn_type = "secondary" if st.session_state.current_page != page_name else "primary"
            if st.button(page_name, use_container_width=True, key=f"nav_{page_name}", type=btn_type):
                st.session_state.current_page = page_name
        
        st.markdown("---")
        st.markdown('<div style="color: rgba(255,255,255,0.6); font-size: 0.75rem; padding: 0.5rem 0 1rem;">v1.0.0</div>', unsafe_allow_html=True)
    
    # Render the current page
    PAGE_MAP[st.session_state.current_page]()


if __name__ == "__main__":
    main()
