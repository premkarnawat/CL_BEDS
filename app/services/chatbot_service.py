"""
CL-BEDS LLM Coaching Chatbot Service
Builds context-aware prompts and queries the configured LLM provider.
Supports OpenAI, Anthropic, and Groq.
"""

import logging
from typing import AsyncGenerator, List, Optional

import httpx

from app.config import settings
from app.schemas.metrics import SHAPReport
from app.schemas.session import ChatMessageOut

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt engineering
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are Dr. BEDS, a professional CBT-based productivity and wellbeing coach embedded in a cognitive load monitoring system.

IMPORTANT RULES:
1. Do NOT provide any medical diagnosis or clinical assessments.
2. Speak in a warm, empathetic, non-judgmental tone.
3. Focus on evidence-based CBT productivity strategies.
4. Structure your responses as:
   - 1 immediate action (can be done right now)
   - 3-step short-term recovery plan (next 24–48 hours)
   - 1 weekly improvement habit
5. Keep responses concise (under 300 words unless asked to elaborate).
6. If the user seems in crisis, encourage them to speak to a qualified mental health professional.
"""


def _build_context_prompt(shap_report: Optional[SHAPReport] = None) -> str:
    """Inject SHAP/risk context into the system message."""
    if not shap_report:
        return ""

    drivers = ", ".join(
        f"{d['feature']} (impact: {d['impact']:+.1f})"
        for d in shap_report.top_drivers[:3]
    )
    return (
        f"\n\nCURRENT USER CONTEXT:\n"
        f"Risk Level: {shap_report.risk_level} "
        f"(confidence: {shap_report.confidence * 100:.0f}%)\n"
        f"Top cognitive load drivers: {drivers}\n"
        f"Tailor your advice to address these specific factors."
    )


# ---------------------------------------------------------------------------
# Provider wrappers
# ---------------------------------------------------------------------------

async def _call_openai(
    messages: List[dict],
    stream: bool = False,
) -> str:
    """Call the OpenAI Chat Completions API."""
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "max_tokens": settings.LLM_MAX_TOKENS,
        "temperature": settings.LLM_TEMPERATURE,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def _call_anthropic(messages: List[dict]) -> str:
    """Call the Anthropic Messages API."""
    # Extract system from messages list
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_messages = [m for m in messages if m["role"] != "system"]

    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": settings.LLM_MAX_TOKENS,
        "system": system,
        "messages": user_messages,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]


async def _call_groq(messages: List[dict]) -> str:
    """Call the Groq API (OpenAI-compatible endpoint)."""
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "llama3-8b-8192",
        "messages": messages,
        "max_tokens": settings.LLM_MAX_TOKENS,
        "temperature": settings.LLM_TEMPERATURE,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def get_coaching_response(
    user_message: str,
    history: List[ChatMessageOut],
    shap_report: Optional[SHAPReport] = None,
) -> tuple[str, int]:
    """
    Generate an AI coaching response.

    Returns (reply_text, approximate_token_count).
    """
    context = _build_context_prompt(shap_report)
    system_content = _SYSTEM_PROMPT + context

    messages: List[dict] = [{"role": "system", "content": system_content}]

    # Add conversation history (last 10 turns to stay within context)
    for msg in history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    provider = settings.LLM_PROVIDER.lower()
    try:
        if provider == "openai":
            reply = await _call_openai(messages)
        elif provider == "anthropic":
            reply = await _call_anthropic(messages)
        elif provider == "groq":
            reply = await _call_groq(messages)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
    except httpx.HTTPStatusError as exc:
        logger.error("LLM API error %s: %s", exc.response.status_code, exc.response.text)
        reply = (
            "I'm having trouble connecting to my knowledge base right now. "
            "Please try again in a moment. In the meantime, consider taking a "
            "5-minute break and some slow, deep breaths."
        )

    token_estimate = len(reply.split()) * 4 // 3  # rough token estimate
    return reply, token_estimate
