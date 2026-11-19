"""Choose the model backend: Claude Haiku through the Claude API (online) or Gemma through LM Studio (offline)."""
from __future__ import annotations

PROVIDERS = ("claude", "local")


def make_llm(provider: str, faq_text: str):
    """Build the backend and check it works before any ticket is handled."""
    if provider == "claude":
        from .llm_claude import ClaudeLLM
        llm = ClaudeLLM(faq_text)
    elif provider == "local":
        from .llm import LLM
        llm = LLM(faq_text)
    else:
        raise SystemExit(f"unknown provider {provider!r}; use one of {PROVIDERS}")
    try:
        llm.check()
    except Exception as e:
        hint = ("set ANTHROPIC_API_KEY (see .env.example), or run with --provider local" if provider == "claude"
                else "start the LM Studio server and load the model")
        raise SystemExit(f"{provider} backend is not usable ({type(e).__name__}): {hint}")
    return llm
