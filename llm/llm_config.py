"""
llm/llm_config.py — Provider-agnostic LLM wrapper.

To swap LLM providers, only this file (and .env) needs to change.
The rest of the codebase imports `get_llm()` — never imports a provider directly.
"""

from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel

from core.config import get_settings


@dataclass
class LLMConfig:
    """Current LLM configuration snapshot (for logging / debugging)."""

    provider: str       # "groq" | "openai" | "anthropic" | "ollama"
    model: str          # e.g. "llama-3.3-70b-versatile"
    temperature: float
    max_tokens: int


def get_llm() -> BaseChatModel:
    """
    Return a LangChain-compatible chat model based on the current settings.

    Supported providers:
        - groq   → ChatGroq (default)
        - openai → ChatOpenAI
        - anthropic → ChatAnthropic
        - ollama → ChatOllama
    """
    settings = get_settings()
    provider = settings.llm_provider.lower()

    common_kwargs = {
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
    }

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            api_key=settings.groq_api_key,
            **common_kwargs,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            api_key=settings.openai_api_key,
            **common_kwargs,
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            model_name=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    elif provider == "ollama":
        from langchain_community.chat_models import ChatOllama

        return ChatOllama(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
        )

    else:
        raise ValueError(
            f"Unsupported LLM provider: '{provider}'. "
            f"Supported: groq, openai, anthropic, ollama"
        )


def get_llm_config() -> LLMConfig:
    """Return the current LLM configuration (for logging / debugging)."""
    settings = get_settings()
    return LLMConfig(
        provider=settings.llm_provider,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )
