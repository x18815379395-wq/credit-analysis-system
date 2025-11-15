from __future__ import annotations

from collections import defaultdict
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.schemas import FinancialStatementPayload, FinancialUploadResult
from app.services.llm_service import LLMService


class FinancialStatementParser:
    """Parse Excel/CSV/PDF templates into structured financial statements."""

    STATEMENT_ALIASES = {
        "income": "income_statement",
        "income_statement": "income_statement",
        "profit": "income_statement",
        "p&l": "income_statement",
        "balance": "balance_sheet",
        "balance_sheet": "balance_sheet",
        "assets": "balance_sheet",
        "cashflow": "cashflow_statement",
        "cash_flow": "cashflow_statement",
        "cash flow": "cashflow_statement",
        "cashflow_statement": "cashflow_statement",
    }

    COLUMN_ALIASES = {
        "year": "year",
        "fiscalyear": "year",
        "revenue": "revenue",
        "operatingincome": "revenue",
        "sales": "revenue",
        "grossprofit": "gross_profit",
        "netincome": "net_income",
        "profit": "net_income",
        "ebit": "ebit",
        "interestexpense": "interest_expense",
        "totalassets": "total_assets",
        "totalasset": "total_assets",
        "totalliabilities": "total_liabilities",
        "totalliability": "total_liabilities",
        "totalequity": "total_equity",
        "accountspayable": "accounts_payable",
        "accountsreceivable": "accounts_receivable",
        "inventory": "inventory",
        "interestbearingdebt": "interest_bearing_debt",
        "shorttermdebt": "short_term_debt",
        "longtermdebt": "long_term_debt",
        "operatingcashflow": "operating_cash_flow",
        "cashfromoperations": "operating_cash_flow",
        "cogs": "cost_of_goods_sold",
        "costofgoodssold": "cost_of_goods_sold",
    }

    PDF_KEYWORDS = {
        "income_statement": ["profit", "income", "损益", "利润", "收益"],
        "balance_sheet": ["balance", "资产负债", "资产負債", "资产 负债"],
        "cashflow_statement": ["cash", "现金流", "现金 流量", "cashflow"],
    }

    SUPPORTED_EXTENSIONS = (".xlsx", ".xlsm", ".xls", ".csv", ".pdf")

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service

    async def parse(self, file_name: str, raw_bytes: bytes) -> FinancialUploadResult:
        normalized_name = (file_name or "upload").lower()
        if not normalized_name.endswith(self.SUPPORTED_EXTENSIONS):
            raise ValueError("Unsupported file type. 请上传 Excel / CSV / PDF 财报模板。")

        frames, load_warnings, structured_override = await self._load_frames(normalized_name, raw_bytes)
        if structured_override is not None:
            detected_years = [payload.year for payload in structured_override]
            if len(detected_years) < 3:
                load_warnings.append("少于三年财务数据，建议补齐。")
            return FinancialUploadResult(
                financial_statements=structured_override,
                detected_years=detected_years,
                warnings=load_warnings,
            )

        if not frames:
            raise ValueError("未检测到可解析的财报表格，请检查文件格式或确保 PDF 为可复制文本。")

        parsed: Dict[int, Dict[str, Dict[str, float]]] = defaultdict(
            lambda: {
                "income_statement": {},
                "balance_sheet": {},
                "cashflow_statement": {},
            }
        )
        warnings: List[str] = list(load_warnings)

        for statement_type, df in frames:
            normalized_cols = {col: self._normalize_column(col) for col in df.columns}
            if "year" not in normalized_cols.values():
                warnings.append(f"Sheet '{statement_type}' 缺少 'Year' 列，已跳过。")
                continue

            df = df.dropna(how="all")
            for _, row in df.iterrows():
                year_value = row[self._original_column("year", normalized_cols)]
                if pd.isna(year_value):
                    continue
                try:
                    year = int(year_value)
                except (ValueError, TypeError):
                    warnings.append(f"{statement_type} 中存在无法解析的年份 '{year_value}'。")
                    continue

                payload = parsed[year][statement_type]
                for original_col, normalized in normalized_cols.items():
                    if normalized in {"year", None}:
                        continue
                    canonical = self.COLUMN_ALIASES.get(normalized)
                    if not canonical:
                        continue
                    value = row[original_col]
                    if pd.isna(value):
                        continue
                    try:
                        payload[canonical] = float(value)
                    except (ValueError, TypeError):
                        warnings.append(f"列 '{original_col}' 中的值 '{value}' 无法解析。")

        statements = [
            FinancialStatementPayload(
                year=year,
                income_statement=data["income_statement"],
                balance_sheet=data["balance_sheet"],
                cashflow_statement=data["cashflow_statement"],
            )
            for year, data in sorted(parsed.items())
            if any(data.values())
        ]
        if not statements:
            raise ValueError("无法根据上传内容生成结构化财报，请检查模板。")

        detected_years = [entry.year for entry in statements]
        if len(detected_years) < 3:
            warnings.append("少于三年财务数据，建议补齐。")

        return FinancialUploadResult(
            financial_statements=statements,
            detected_years=detected_years,
            warnings=warnings,
        )

    async def _load_frames(
        self, file_name: str, raw_bytes: bytes
    ) -> Tuple[List[Tuple[str, pd.DataFrame]], List[str], Optional[List[FinancialStatementPayload]]]:
        if file_name.endswith(".pdf"):
            return await self._load_pdf_frames(raw_bytes)

        if file_name.endswith(".csv"):
            df = pd.read_csv(BytesIO(raw_bytes))
            statement_col = self._find_statement_column(df.columns)
            if statement_col:
                frames: List[Tuple[str, pd.DataFrame]] = []
                for statement_type, group in df.groupby(statement_col):
                    normalized = self._normalize_statement_name(str(statement_type))
                    target_type = self.STATEMENT_ALIASES.get(normalized)
                    if target_type:
                        frames.append((target_type, group.drop(columns=[statement_col])))
                return frames, [], None
            return [("income_statement", df)], [], None

        workbook = pd.read_excel(BytesIO(raw_bytes), sheet_name=None)
        frames: List[Tuple[str, pd.DataFrame]] = []
        for sheet_name, df in workbook.items():
            normalized = self._normalize_statement_name(sheet_name)
            target_type = self.STATEMENT_ALIASES.get(normalized)
            if target_type:
                frames.append((target_type, df))
            else:
                statement_col = self._find_statement_column(df.columns)
                if statement_col:
                    for statement_type, group in df.groupby(statement_col):
                        normalized = self._normalize_statement_name(str(statement_type))
                        target_type = self.STATEMENT_ALIASES.get(normalized)
                        if target_type:
                            frames.append((target_type, group.drop(columns=[statement_col])))
        return frames, [], None

    async def _load_pdf_frames(
        self, raw_bytes: bytes
    ) -> Tuple[List[Tuple[str, pd.DataFrame]], List[str], Optional[List[FinancialStatementPayload]]]:
        warnings: List[str] = []
        try:
            import pdfplumber
        except ImportError as exc:
            raise ValueError("解析 PDF 需要安装 pdfplumber，请运行 `pip install pdfplumber`.") from exc

        frames: List[Tuple[str, pd.DataFrame]] = []
        text_chunks: List[str] = []
        with pdfplumber.open(BytesIO(raw_bytes)) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                if page_text:
                    text_chunks.append(page_text)
                tables = page.extract_tables()
                if not tables:
                    warnings.append(f"PDF 第 {page_index} 页未检测到可解析的表格，已跳过。")
                    continue
                for table_index, table in enumerate(tables, start=1):
                    df = pd.DataFrame(table)
                    if df.empty or len(df) <= 1:
                        continue
                    df = self._prepare_pdf_dataframe(df)
                    if df is None or df.empty:
                        continue
                    statement_type = self._infer_statement_type(df)
                    if not statement_type:
                        warnings.append(
                            f"无法判断 PDF 第 {page_index} 页表 {table_index} 属于哪类报表，请在表头包含“利润表/资产负债表/现金流量表”等关键词。"
                        )
                        continue
                    frames.append((statement_type, df))

        if frames:
            return frames, warnings, None

        if not self.llm_service:
            return frames, warnings, None
        full_text = "\n".join(text_chunks).strip()
        if not full_text:
            return frames, warnings, None

        try:
            llm_payloads = await self.llm_service.parse_financials_from_text(full_text)
        except Exception:
            llm_payloads = None

        if not llm_payloads:
            return frames, warnings, None

        payloads: List[FinancialStatementPayload] = []
        for item in llm_payloads:
            try:
                payloads.append(
                    FinancialStatementPayload(
                        year=int(item["year"]),
                        income_statement=item.get("income_statement", {}),
                        balance_sheet=item.get("balance_sheet", {}),
                        cashflow_statement=item.get("cashflow_statement", {}),
                    )
                )
            except Exception:
                warnings.append("LLM 返回的财报结构存在异常字段，部分记录已忽略。")

        if not payloads:
            return frames, warnings, None
        warnings.append("PDF 表格解析失败，已使用大模型根据 OCR 文本进行结构化。")
        return [], warnings, payloads

    def _prepare_pdf_dataframe(self, df: pd.DataFrame) -> pd.DataFrame | None:
        df = df.dropna(axis=1, how="all")
        if df.empty or len(df) <= 1:
            return None
        header = df.iloc[0].fillna("").astype(str).tolist()
        df = df.iloc[1:].copy()
        df.columns = [
            header[i].strip() if header[i].strip() else f"col_{i}"
            for i in range(len(header))
        ]
        df = df.dropna(how="all")
        return df

    def _infer_statement_type(self, df: pd.DataFrame) -> str | None:
        sample_text = " ".join(
            [
                " ".join(map(str, df.columns)),
                " ".join(df.astype(str).fillna("").head(2).values.flatten().tolist()),
            ]
        ).lower()
        for statement_type, keywords in self.PDF_KEYWORDS.items():
            if any(keyword in sample_text for keyword in keywords):
                return statement_type
        return None

    def _normalize_column(self, column_name: str) -> str:
        return column_name.strip().lower().replace(" ", "").replace("-", "").replace("_", "")

    def _normalize_statement_name(self, name: str) -> str:
        return name.strip().lower().replace(" ", "").replace("-", "").replace("_", "")

    def _find_statement_column(self, columns: List[str]) -> str | None:
        for column in columns:
            normalized = self._normalize_column(column)
            if normalized in {"statement", "statementtype", "sheet", "type"}:
                return column
        return None

    def _original_column(self, target: str, normalized_map: Dict[str, str]) -> str:
        for original, normalized in normalized_map.items():
            if normalized == target:
                return original
        return target
