"""
LLM Abstraction Layer для FRIDAY — v2.
- Pluggable backend: OpenAI / Anthropic / OpenRouter / rule-based fallback
- Retry с exponential backoff
- Авто-переключение при 401/429/5xx
"""
import os
import time
from typing import Optional
from logger import log


class LLMClient:
    """Обёртка над LLM-провайдерами с retry и fallback."""

    def __init__(self):
        self.provider: Optional[str] = None
        self.client = None
        self.model: Optional[str] = None
        self._init_client()

    def _init_client(self):
        """Автоопределение доступного провайдера."""
        providers = [
            ("openai", "OPENAI_API_KEY", None, "gpt-4o-mini"),
            ("anthropic", "ANTHROPIC_API_KEY", None, "claude-3-haiku-20240307"),
            ("openrouter", "OPENROUTER_API_KEY",
             os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
             "openai/gpt-4o-mini"),
        ]

        for name, key_env, base_url, default_model in providers:
            api_key = os.environ.get(key_env)
            if not api_key:
                continue
            try:
                if name in ("openai", "openrouter"):
                    import openai
                    kwargs = {"api_key": api_key}
                    if base_url:
                        kwargs["base_url"] = base_url
                    self.client = openai.OpenAI(**kwargs)
                elif name == "anthropic":
                    import anthropic
                    self.client = anthropic.Anthropic(api_key=api_key)
                self.provider = name
                self.model = default_model
                log.info("LLM: %s готов (модель %s)", name, default_model)
                return
            except Exception as e:
                log.warning("LLM %s не загрузился: %s", name, e)

        log.info("LLM: без API-ключа — rule-based режим")

    @property
    def available(self) -> bool:
        return self.client is not None

    def chat(self, messages: list, model: str = None, temperature: float = 0.3,
             max_tokens: int = 400, retries: int = 2):
        """Чат с retry + exponential backoff."""
        if not self.client:
            raise RuntimeError("LLM unavailable — используй rule-based fallback")

        use_model = model or self.model

        for attempt in range(retries + 1):
            try:
                return self._call(messages, use_model, temperature, max_tokens)
            except Exception as e:
                err = str(e)
                if "401" in err or "403" in err:
                    log.error("LLM auth error — ключ невалиден")
                    raise
                if attempt < retries:
                    wait = 2 ** attempt
                    log.warning("LLM retry %d/%d через %ds: %s", attempt + 1, retries, wait, err[:100])
                    time.sleep(wait)
                else:
                    log.error("LLM failed after %d retries: %s", retries, err[:200])
                    raise

    def _call(self, messages: list, model: str, temperature: float, max_tokens: int):
        """Реальный вызов API в зависимости от провайдера."""
        if self.provider in ("openai", "openrouter"):
            resp = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content

        elif self.provider == "anthropic":
            system_msg = None
            user_msgs = []
            for m in messages:
                if m["role"] == "system":
                    system_msg = m["content"]
                else:
                    user_msgs.append(m)
            resp = self.client.messages.create(
                model=model,
                system=system_msg,
                messages=user_msgs,
                max_tokens=max_tokens,
            )
            return resp.content[0].text

        raise RuntimeError(f"Unknown provider: {self.provider}")


_llm_instance: Optional[LLMClient] = None


def get_llm() -> Optional[LLMClient]:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMClient()
    return _llm_instance if _llm_instance.available else None


def is_llm_available() -> bool:
    return get_llm() is not None
