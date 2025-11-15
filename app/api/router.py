from fastapi import APIRouter

from app.api.endpoints import analysis, company

api_router = APIRouter()
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(company.router, prefix="/company", tags=["company"])
