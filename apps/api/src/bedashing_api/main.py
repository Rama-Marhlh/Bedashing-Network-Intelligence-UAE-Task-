# ruff: noqa: E501
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.usage import UsageLimits

from bedashing_api.agent import build_agent
from bedashing_api.models.analyst import AnalystQuery, AnalystResponse
from bedashing_api.repositories.app_data_repository import AppDataRepository
from bedashing_api.services.analyst import AnalystService
from bedashing_api.services.intelligence import IntelligenceService

ROOT = Path(__file__).resolve().parents[4]
LOGGER = logging.getLogger(__name__)
# The repository-level .env is the source of truth for this local application.
# Override stale values inherited from a terminal (for example ANALYST_MODE=static).
load_dotenv(ROOT / ".env", override=True)
repository = AppDataRepository(ROOT / "app_data")
# Fail startup clearly when a present external export is invalid; fall back only
# when that file is absent.
repository.review_collection()
repository.validate_startup_snapshot()
service = AnalystService(repository)
intelligence = IntelligenceService(repository)


mode = os.getenv("ANALYST_MODE", "static").lower()
if mode not in {"static", "auto", "llm"}:
    raise RuntimeError("ANALYST_MODE must be static, auto, or llm")
agent = None
if mode in {"auto", "llm"}:
    try:
        agent = build_agent(service)
    except Exception as exc:
        if mode == "llm":
            raise RuntimeError(
                "ANALYST_MODE=llm requires a working Pydantic AI provider configuration"
            ) from exc
        agent = None

app = FastAPI(title="Bedashing Network Intelligence API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://127.0.0.1:3003",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


def analyst_failure(question: str, provider_issue: str | None = None) -> AnalystResponse:
    deterministic = service.deterministic_aggregate_answer(question)
    if deterministic is not None:
        return deterministic
    return AnalystResponse(
        answer=(
            "I couldn't complete that analyst request because the model-backed tool workflow "
            "is currently unavailable. No dashboard actions were applied. "
            + (provider_issue or "Please retry.")
        ),
        key_findings=[f"Original request preserved: {question}"],
        limitations=[
            "The requested repository tools were not completed, so no factual substitute was returned.",
            *([provider_issue] if provider_issue else []),
        ],
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": "llm" if agent else ("static-fallback" if mode == "auto" else "static"),
    }


@app.get("/api/data-health")
def data_health() -> dict[str, int | str | bool]:
    return repository.validate_startup_snapshot()


@app.get("/api/portfolio-health")
def portfolio_health() -> dict:
    return service.portfolio_health()


@app.get("/api/branches/{branch_id}/intelligence")
def branch_intelligence(branch_id: str) -> dict:
    try:
        payload = intelligence.branch_bundle(branch_id)
        payload["rating_distribution"] = intelligence.rating_distribution(branch_id)
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/branches/{branch_id}/reviews")
def branch_reviews(
    branch_id: str,
    query: str | None = None,
    sentiment: str | None = Query(default=None, pattern="^(POSITIVE|NEUTRAL|NEGATIVE)$"),
    stars: int | None = Query(default=None, ge=1, le=5),
    language: str | None = Query(default=None, pattern="^(ARABIC|ENGLISH|UNKNOWN)$"),
    topic: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    sort: str = Query(default="newest", pattern="^(newest|oldest)$"),
) -> dict:
    try:
        return intelligence.search_reviews(
            branch_id=branch_id,
            query=query,
            sentiment=sentiment,
            stars=stars,
            language=language,
            topic=topic,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
            sort=sort,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/services")
def services(category: str | None = None) -> dict:
    return {
        "items": intelligence.services(category),
        "category_summaries": intelligence.service_summaries(),
        "availability": "Official catalogue; branch-level availability is not available.",
    }


@app.get("/api/competitors/{competitor_id}")
def competitor_details(competitor_id: str) -> dict:
    try:
        return service.competitor_details(competitor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/competitors/{competitor_id}/relationships")
def competitor_relationships(competitor_id: str) -> dict:
    try:
        return service.competitor_branch_relationships(competitor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/whitespace/{h3_cell}")
def whitespace_opportunity(h3_cell: str) -> dict:
    try:
        return service.whitespace_opportunity(h3_cell)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/analyst/query", response_model=AnalystResponse)
async def analyst_query(query: AnalystQuery) -> AnalystResponse:
    if service.classify_question(query.question) == "greeting":
        return service.answer(query.question)
    if agent is None:
        LOGGER.warning("Analyst provider is disabled; request was not executed")
        return analyst_failure(query.question)
    try:
        timeout_seconds = min(max(float(os.getenv("ANALYST_TIMEOUT_SECONDS", "90")), 5), 120)
        grounded_prompt = query.question
        if query.dashboard_context:
            grounded_prompt += "\n\nCurrent dashboard context (validated UI state): " + json.dumps(
                query.dashboard_context, ensure_ascii=False, sort_keys=True
            )
        run_task = asyncio.create_task(
            agent.run(grounded_prompt, usage_limits=UsageLimits(request_limit=8))
        )
        done, _ = await asyncio.wait({run_task}, timeout=timeout_seconds)
        if not done:
            run_task.cancel()
            LOGGER.warning("Model-backed analyst timed out; no substitute answer returned")
            return analyst_failure(query.question)
        result = run_task.result()
        if "temporarily unavailable" in result.output.answer.casefold():
            LOGGER.warning("Model returned a non-substantive availability response")
            return analyst_failure(query.question)
        return result.output
    except UnexpectedModelBehavior as exc:
        cause = str(exc.__cause__ or exc)[:500]
        LOGGER.warning("Agent output validation exhausted retries: %s", cause)
        return analyst_failure(query.question)
    except ModelHTTPError as exc:
        if exc.status_code == 401:
            LOGGER.warning("Model provider rejected OPENAI_API_KEY")
            return analyst_failure(
                query.question,
                "The configured OPENAI_API_KEY was rejected; replace it with a valid key and restart FastAPI.",
            )
        LOGGER.warning("Model provider HTTP error: %s", exc.status_code)
        return analyst_failure(query.question)
    except Exception as exc:
        LOGGER.warning("Model-backed analyst failed: %s: %s", type(exc).__name__, str(exc)[:500])
        return analyst_failure(query.question)


@app.post("/api/agui")
async def agui(query: AnalystQuery) -> StreamingResponse:
    """Small AG-UI-compatible SSE adapter for static and model-backed responses."""
    response = await analyst_query(query)
    thread_id, run_id, message_id = str(uuid4()), str(uuid4()), str(uuid4())

    def events():
        yield f"data: {json.dumps({'type': 'RUN_STARTED', 'threadId': thread_id, 'runId': run_id})}\n\n"
        yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_START', 'messageId': message_id, 'role': 'assistant'})}\n\n"
        yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_CONTENT', 'messageId': message_id, 'delta': response.answer})}\n\n"
        yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_END', 'messageId': message_id})}\n\n"
        yield f"data: {json.dumps({'type': 'RUN_FINISHED', 'threadId': thread_id, 'runId': run_id})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
