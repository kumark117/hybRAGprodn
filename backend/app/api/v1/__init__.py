from fastapi import APIRouter

from app.api.v1 import auth, health, index, query

router = APIRouter()
router.include_router(auth.router)
router.include_router(health.router)
router.include_router(index.router)
router.include_router(query.router)
