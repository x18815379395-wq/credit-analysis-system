from fastapi import Depends

from app.services.analysis_orchestrator import AnalysisOrchestrator
from app.services.llm_service import LLMService
from app.services.web_search import WebSearchService
from app.storage.memory import MemoryStore, get_store

_LLM_SERVICE = LLMService()
_WEB_SEARCH_SERVICE = WebSearchService(_LLM_SERVICE)


def get_analysis_orchestrator(
    store: MemoryStore = Depends(get_store),
    llm_service: LLMService = Depends(get_llm_service),
    web_search_service: WebSearchService = Depends(get_web_search_service),
) -> AnalysisOrchestrator:
    return AnalysisOrchestrator(store, llm_service=llm_service, web_search_service=web_search_service)


def get_llm_service() -> LLMService:
    return _LLM_SERVICE


def get_web_search_service() -> WebSearchService:
    return _WEB_SEARCH_SERVICE
