from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.connection_requests import router as connection_requests_router
from app.api.routes.equity_splitter import router as equity_router
from app.api.routes.property_listings import router as property_listings_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(equity_router, tags=["equity-splitter"])
api_router.include_router(connection_requests_router, tags=["marketplace"])
api_router.include_router(property_listings_router, tags=["listings"])
