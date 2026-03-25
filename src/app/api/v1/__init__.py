from fastapi import APIRouter

from app.api.v1 import alerts, dashboard, pep, risk, transactions

router = APIRouter()
router.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])
router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
router.include_router(risk.router, prefix="/risk", tags=["Risk"])
router.include_router(pep.router, prefix="/pep", tags=["PEP"])
router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
