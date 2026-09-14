from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.availability import router as availability_router
from app.api.v1.consultation import router as consultation_router
from app.api.v1.doctor import router as doctor_router


__all__ = [
    "admin_router",
    "auth_router",
    "availability_router",
    "consultation_router",
    "doctor_router",
]
