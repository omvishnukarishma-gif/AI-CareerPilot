"""LLM provider abstraction.

This module provides a clean interface for optional LLM-powered features.
When ``LLM_API_KEY`` is empty (the default), the app falls back to the
deterministic heuristic algorithms in ``matcher.py`` and ``interviewer.py``.
No feature is broken by the absence of an API key.

Design:
    - ``LLMProvider`` — abstract base with methods for each AI-assisted feature.
    - ``OpenAIProvider`` — implementation using the OpenAI-compatible chat
      completions API (works with OpenAI, OpenRouter, LM Studio, etc.).
    - ``get_llm_provider()`` — factory that returns a provider instance or None.

Security:
    - API keys are read from environment / .env and never sent to the frontend.
    - All prompts are constructed server-side.
    - User-supplied text (resumes, JDs, answers) is treated as untrusted input
      and is never injected into system prompts — only sent as user messages.
    - Responses are validated with Pydantic models before use.
    - Timeouts are enforced to prevent hanging.
    - Malformed or unavailable responses fall back to deterministic output.

Usage in routers::

    from app.core.llm import get_llm_provider

    provider = get_llm_provider()
    if provider:
        enhanced_recs = provider.enhance_recommendations(
            matched_skills, missing_skills, resume_text, jd_text
        )
    else:
        enhanced_recs = deterministic_recommendations  # from matcher.py
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

# Timeout for LLM API calls (seconds)
_LLM_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Response validation models
# ---------------------------------------------------------------------------


class EnhanceRecommendationsResult(BaseModel):
    """Validated LLM response for skill-gap recommendations."""

    recommendations: list[str]


class EnhanceFeedbackResult(BaseModel):
    """Validated LLM response for interview answer feedback."""

    score: float
    strengths: list[str]
    improvements: list[str]
    note: str


class ResumeAnalysisResult(BaseModel):
    """Validated LLM response for resume analysis."""

    strengths: list[str]
    improvements: list[str]
    missing_info: list[str]
    summary: str


# ---------------------------------------------------------------------------
# Abstract base provider
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """Abstract interface for LLM-powered features.

    Every method returns a validated Pydantic model or None (on failure).
    Callers must handle None by falling back to deterministic output.
    """

    @abstractmethod
    def enhance_recommendations(
        self,
        matched_skills: list[str],
        missing_skills: list[str],
        resume_text: str,
        jd_text: str,
    ) -> EnhanceRecommendationsResult | None:
        """Generate enhanced skill-gap recommendations using the LLM."""

    @abstractmethod
    def enhance_feedback(
        self,
        question_text: str,
        question_category: str,
        answer_text: str,
        deterministic_score: float,
    ) -> EnhanceFeedbackResult | None:
        """Generate enhanced interview answer feedback using the LLM."""

    @abstractmethod
    def analyze_resume(
        self,
        resume_text: str,
    ) -> ResumeAnalysisResult | None:
        """Generate a structured resume analysis using the LLM."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """True if the provider has valid credentials and is ready to use."""


# ---------------------------------------------------------------------------
# OpenAI-compatible provider
# ---------------------------------------------------------------------------


class OpenAIProvider(LLMProvider):
    """LLM provider using the OpenAI-compatible chat completions API.

    Works with OpenAI, OpenRouter, LM Studio, Ollama, and any service
    that implements the ``/v1/chat/completions`` endpoint.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def _chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel | None:
        """Send a chat completion request and validate the response.

        Returns the validated Pydantic model, or None on any failure.
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1000,
        }

        try:
            with httpx.Client(timeout=_LLM_TIMEOUT) as client:
                resp = client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            content = data["choices"][0]["message"]["content"]
            # The model may wrap JSON in markdown code blocks — strip them.
            content = content.strip()
            if content.startswith("```"):
                # Remove ```json ... ``` wrapping
                lines = content.split("\n")
                content = "\n".join(
                    l for l in lines if not l.startswith("```")
                )
            parsed = json.loads(content)
            return response_model.model_validate(parsed)

        except httpx.TimeoutException:
            logger.warning("LLM request timed out")
        except httpx.HTTPStatusError as exc:
            logger.warning("LLM API returned %d: %s", exc.response.status_code, exc)
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.warning("LLM response parsing failed: %s", exc)
        except ValidationError as exc:
            logger.warning("LLM response validation failed: %s", exc)
        except Exception:  # noqa: BLE001
            logger.warning("Unexpected LLM error", exc_info=True)

        return None

    # --- System prompts ---
    #
    # IMPORTANT: System prompts never include user-supplied text.
    # User content (resumes, JDs, answers) is sent only as the user message,
    # reducing prompt-injection risk.

    _RECS_SYSTEM = (
        "You are a career advisor helping a job seeker understand their skill gaps. "
        "Based on the matched and missing skills, provide 3-6 actionable, specific recommendations. "
        "Be honest and encouraging. Do not claim the candidate lacks a skill — only that it was not found in their resume. "
        "Respond as a JSON object: {\"recommendations\": [\"...\", \"...\"]}"
    )

    _FEEDBACK_SYSTEM = (
        "You are an interview coach evaluating a candidate's practice answer. "
        "Provide constructive, specific feedback. Score 0-100 based on relevance, clarity, and depth. "
        "Do not claim to assess technical accuracy you cannot verify. "
        "Respond as a JSON object: "
        "{\"score\": 75.0, \"strengths\": [\"...\"], \"improvements\": [\"...\"], \"note\": \"...\"}"
    )

    _RESUME_SYSTEM = (
        "You are a professional resume reviewer. Analyze the resume text and provide "
        "structured, actionable feedback. Identify strengths, areas for improvement, "
        "and missing information. Be specific and constructive. "
        "Respond as a JSON object: "
        "{\"strengths\": [\"...\"], \"improvements\": [\"...\"], \"missing_info\": [\"...\"], \"summary\": \"...\"}"
    )

    def enhance_recommendations(
        self,
        matched_skills: list[str],
        missing_skills: list[str],
        resume_text: str,
        jd_text: str,
    ) -> EnhanceRecommendationsResult | None:
        # Truncate user text to avoid excessive token usage
        resume_excerpt = resume_text[:2000]
        jd_excerpt = jd_text[:2000]

        user_prompt = (
            f"Matched skills: {', '.join(matched_skills) or 'none'}\n"
            f"Missing skills: {', '.join(missing_skills) or 'none'}\n\n"
            f"Resume excerpt:\n{resume_excerpt}\n\n"
            f"Job description excerpt:\n{jd_excerpt}\n\n"
            "Provide recommendations for the missing skills."
        )
        result = self._chat_completion(
            self._RECS_SYSTEM, user_prompt, EnhanceRecommendationsResult
        )
        return result if isinstance(result, EnhanceRecommendationsResult) else None

    def enhance_feedback(
        self,
        question_text: str,
        question_category: str,
        answer_text: str,
        deterministic_score: float,
    ) -> EnhanceFeedbackResult | None:
        # Truncate to avoid token explosion
        answer_excerpt = answer_text[:1500]

        user_prompt = (
            f"Question ({question_category}): {question_text}\n\n"
            f"Candidate's answer:\n{answer_excerpt}\n\n"
            f"The heuristic keyword-match score was {deterministic_score:.0f}/100. "
            "Provide your own assessment."
        )
        result = self._chat_completion(
            self._FEEDBACK_SYSTEM, user_prompt, EnhanceFeedbackResult
        )
        return result if isinstance(result, EnhanceFeedbackResult) else None

    def analyze_resume(
        self,
        resume_text: str,
    ) -> ResumeAnalysisResult | None:
        resume_excerpt = resume_text[:3000]

        user_prompt = f"Resume text:\n{resume_excerpt}"
        result = self._chat_completion(
            self._RESUME_SYSTEM, user_prompt, ResumeAnalysisResult
        )
        return result if isinstance(result, ResumeAnalysisResult) else None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_provider_instance: LLMProvider | None = None
_initialized = False


def get_llm_provider() -> LLMProvider | None:
    """Return the configured LLM provider, or None if no API key is set.

    The provider is instantiated once and cached.  If the API key is empty,
    returns None — callers must handle this by falling back to deterministic
    algorithms.
    """
    global _provider_instance, _initialized

    if _initialized:
        return _provider_instance

    _initialized = True

    if not settings.llm_api_key:
        logger.info("No LLM_API_KEY configured — using deterministic fallback")
        return None

    _provider_instance = OpenAIProvider(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
    )
    logger.info("LLM provider initialized: model=%s, base_url=%s", settings.llm_model, settings.llm_base_url)
    return _provider_instance
