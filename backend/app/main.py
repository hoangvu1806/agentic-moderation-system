from fastapi import FastAPI
from dotenv import load_dotenv
load_dotenv()

from app.api.routes import router
from app.repositories.moderation_repository import ModerationRepository


app = FastAPI(title="Agentic Moderation Backend", version="0.1.0")
app.state.moderation_repository = ModerationRepository()
app.include_router(router)
