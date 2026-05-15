"""Тесты LLM-слоя."""
import pytest
from llm import LLMClient, get_llm, is_llm_available


class TestLLMClient:
    def test_rule_based_when_no_key(self, monkeypatch):
        """Без ключей — client is None, available=False."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        client = LLMClient()
        assert not client.available
        with pytest.raises(RuntimeError):
            client.chat([{"role": "user", "content": "test"}])

    def test_get_llm_returns_none_without_keys(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        import llm
        llm._llm_instance = None
        assert get_llm() is None
        assert not is_llm_available()
