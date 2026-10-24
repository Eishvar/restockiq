from fastapi import APIRouter, Depends

from app.ai import llm
from app.core.auth import current_user
from app.modules.help import service
from app.modules.help.faq import FAQ
from app.modules.help.schemas import AskIn, AskOut, FaqItem
from app.modules.settings.models import User

router = APIRouter(prefix="/help", tags=["help"])


@router.get("/faq", response_model=list[FaqItem])
def faq(_: User = Depends(current_user)):
    """Ready-made questions and answers. Free: no AI is involved."""
    return FAQ


@router.get("/status")
def status(_: User = Depends(current_user)):
    """Can the person also type their own question? (Only when an AI provider is configured.)"""
    return {"ai_available": llm.ai_available()}


@router.post("/ask", response_model=AskOut)
def ask(body: AskIn, user: User = Depends(current_user)):
    """Answer a how-do-I question: FAQ first, remembered answers next, the AI last."""
    return service.ask(user, body)
