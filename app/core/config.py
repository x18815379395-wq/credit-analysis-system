from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import AnyHttpUrl, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from env vars/.env."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    PROJECT_NAME: str = "Credit Analysis Platform"
    API_V1_STR: str = "/api/v1"
    DEFAULT_ENVIRONMENT: str = "TEST"
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] | List[str] = []
    LLM_PROVIDER: str = "mock"
    LLM_API_BASE: Optional[HttpUrl] = None
    LLM_API_KEY: Optional[str] = None
    LLM_TIMEOUT_SECONDS: int = 20
    LLM_TASK_MODELS: Dict[str, str] = {
        "INDUSTRY_ANALYSIS": "general-32k",
        "FINANCIAL_EXPLAIN": "general-16k",
        "RISK_SUMMARY": "risk-analyst",
        "COMPANY_PROFILE_ENRICH": "general-16k",
        "OCR_STRUCTURED_PARSE": "general-32k",
    }
    SEARCH_API_BASE_URL: Optional[HttpUrl] = None
    SEARCH_API_KEY: Optional[str] = None
    SEARCH_TIMEOUT_SECONDS: int = 10
    API_BASE_URL: Optional[AnyHttpUrl] = None

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, value: str | List[str]) -> List[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("[") and value.endswith("]"):
                return [origin.strip().strip('"') for origin in json.loads(value)]
            return [origin.strip() for origin in value.split(",")]
        return []

    @field_validator("LLM_TASK_MODELS", mode="before")
    @classmethod
    def parse_llm_models(cls, value: str | Dict[str, str]) -> Dict[str, str]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return {}
            return json.loads(value)
        return {}

    @property
    def root_path(self) -> Path:
        return Path(__file__).resolve().parents[2]


settings = Settings()
