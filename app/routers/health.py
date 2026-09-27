from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Простий health-check для балансувальника навантаження."""
    return {"status": "ok"}


x = 1
