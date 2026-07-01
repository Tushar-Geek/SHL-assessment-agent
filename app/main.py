from __future__ import annotations

from fastapi import Depends, FastAPI

from app.agent import SHLRecommendationAgent
from app.dependencies import get_agent
from app.logging_config import configure_logging
from app.schemas import ChatRequest, ChatResponse, HealthResponse

configure_logging()

app = FastAPI(title="SHL Assessment Recommendation Agent", version="1.0.0")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, agent: SHLRecommendationAgent = Depends(get_agent)) -> ChatResponse:
    return await agent.chat(request.messages)
