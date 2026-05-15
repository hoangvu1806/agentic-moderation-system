from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()

from app.api.routes import router
from app.repositories.moderation_repository import ModerationRepository
from app.settings import settings


app = FastAPI(title="Agentic Moderation Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.state.moderation_repository = ModerationRepository()
app.include_router(router)
