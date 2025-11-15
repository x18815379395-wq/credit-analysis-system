# Credit Analysis System

Full-stack toolkit for automating SME credit analysis following the 5C + cash-flow methodology.  
The implementation follows the blueprint documented in `PROJECT_TECH_PLAN_V1.md`: a FastAPI backend that orchestrates metrics, scoring, LLM-style narratives, and report generation, plus a Streamlit workspace for dashboards, onboarding, detail views, and exports.

---

## Architecture

```
credit-analysis-system/
├── app/                     # FastAPI backend (API, services, in-memory store)
│   ├── api/                 # REST endpoints (`/api/v1/analysis`)
│   ├── core/                # Settings
│   ├── schemas/             # Pydantic DTOs
│   ├── services/            # Metrics, scoring, LLM proxy, orchestrator, report builder
│   └── storage/             # Thread-safe in-memory store
├── streamlit_app.py         # Streamlit UI entrypoint
├── PROJECT_TECH_PLAN_V1.md  # Product/engineering blueprint
└── requirements.txt
```

- **Backend**: stateless FastAPI app, orchestrates analysis flow in-memory (no DB).  
  Modules mirror the document: `FinancialMetricsService`, `ScorecardEngine`, `LLMService`, `WebSearchService`, `ReportGenerator`, and the `AnalysisOrchestrator`.
- **Frontend**: Streamlit single-page workspace (`streamlit_app.py`) styled with an internal-risk blue theme (primary `#1677ff`). Provides dashboard, wizard-style onboarding (with upload parsing), list/detail tabs, report preview, and settings placeholders from the blueprint.
- **In-memory persistence**: `app/storage/memory.py` tracks analyses, metrics, profile data, and generated reports for the current process.

---

## Backend

### Setup

```bash
python -m venv .venv
. .venv/Scripts/activate  # or source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- Swagger UI: `http://localhost:8000/docs`
- Health: `GET /health`
- Router prefix: `/api/v1`

### Key Endpoints

| Method | Path                               | Purpose                                                |
| ------ | ---------------------------------- | ------------------------------------------------------ |
| POST   | `/api/v1/analysis`                 | Run the full pipeline (enrichment → metrics → scoring → narratives → report) |
| GET    | `/api/v1/analysis`                 | List analyses with optional filters (risk level, industry, status) |
| GET    | `/api/v1/analysis/{analysis_id}`   | Fetch detailed metrics, scores, profile, and report preview |
| GET    | `/api/v1/analysis/{analysis_id}/report?format=markdown` | Download rendered report in HTML or Markdown |
| POST   | `/api/v1/analysis/upload`          | Upload Excel/CSV templates → returns structured financial statements |

All scoring is explainable: the API returns `dimension_scores`, narratives, raw metrics, and the parsed upload payload so you can audit every step.

### Financial File Ingestion

1. Prepare the template: Excel sheets named `Income Statement`, `Balance Sheet`, `Cash Flow` (or include a `statement` column). Columns should include `Year` plus the metrics you have (Revenue, Net Income, Total Assets, etc.).  
2. **PDF 支持**：可直接上传包含表格的 PDF；若为扫描件，请先通过 OCR 生成可复制文本（依赖 `pdfplumber`，必要时结合第三方 OCR）。  
3. Upload via the wizard (or `POST /api/v1/analysis/upload`). The parser normalizes fields, validates years，并在 PDF 无表格时调用大模型（OCR_STRUCTURED_PARSE）将文本结构化。  
4. Pass the returned `financial_statements` array to `POST /api/v1/analysis`.

### 大模型任务与供应商

- **使用场景**：行业/企业分析、财务说明、风险总结、工商信息补全、PDF OCR 结构化均可由大模型生成或增强。  
- **支持供应商**：`mock`（本地调试）、`http`（自定义 JSON 接口）、以及 OpenAI/OpenRouter/DeepSeek（deepsee）/Grok/Gemini/Qwen/Kimi 等 OpenAI Chat Completions 兼容服务。  
- **配置方式**：在 `.env` 中设置 `LLM_PROVIDER`、`LLM_API_KEY`、`LLM_API_BASE`（可选）、`LLM_TASK_MODELS`。各任务默认模型可按需覆盖。  
- **任务模板**：`INDUSTRY_ANALYSIS`、`FINANCIAL_EXPLAIN`、`RISK_SUMMARY`、`COMPANY_PROFILE_ENRICH`、`OCR_STRUCTURED_PARSE` 等模板均内置在 `LLMService`。

### External LLM & Search Providers

- Configure environment variables in `.env`:

```
LLM_PROVIDER=http
LLM_API_BASE=https://your-llm-gateway/v1/completions
LLM_API_KEY=sk-...
SEARCH_API_BASE_URL=https://internal-search/api
SEARCH_API_KEY=...
```

- When unset, the system falls back to deterministic mock responses so the workflow remains testable offline.

---

## Frontend (Streamlit)

### Setup

```bash
pip install -r requirements.txt
API_BASE_URL=http://localhost:8000/api/v1 streamlit run streamlit_app.py
```

> `API_BASE_URL` defaults to `http://localhost:8000/api/v1`, override as needed when deploying.

The Streamlit UI mirrors the blueprint:

- **仪表盘**：展示 KPI 与最新分析；
- **新建分析**：录入基础信息、上传 Excel/CSV 财报 → 服务端解析 → 一键发起分析；
- **分析列表/详情**：查看历史列表、详细指标、风险和建议；
- **报告**：在线预览 Markdown，支持下载；
- **设置**：提醒如何配置 LLM/搜索等环境变量（只读占位）。

所有 API 交互通过 streamlit_app.py 内的请求函数直接调用 FastAPI 后端。

## Documentation

- Product/engineering blueprint: [`PROJECT_TECH_PLAN_V1.md`](PROJECT_TECH_PLAN_V1.md)
- This README: quick-start plus architecture summary.

For next steps (database schema, FastAPI module TODOs, etc.) extend the blueprint or request the companion "FastAPI module checklist" mentioned in the document.
