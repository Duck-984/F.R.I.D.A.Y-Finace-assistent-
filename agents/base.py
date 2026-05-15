"""
Base Agent — фундамент для всех AI-агентов FRIDAY.
Каждый агент наследуется от этого класса.
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime


@dataclass
class AgentResult:
    """Стандартизированный результат работы агента"""
    agent: str
    action: str
    data: dict = field(default_factory=dict)
    insights: list = field(default_factory=list)
    confidence: float = 1.0  # 0..1, насколько агент уверен
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class UserContext:
    """Контекст пользователя — передаётся по цепочке агентов"""
    user_id: int
    username: str
    first_name: str
    balance: float = 0.0
    monthly_income: float = 0.0
    monthly_expense: float = 0.0
    active_goals: list = field(default_factory=list)
    budget_alerts: list = field(default_factory=list)


class BaseAgent:
    """Базовый агент FRIDAY"""

    name: str = "BaseAgent"
    role: str = "base"
    emoji: str = "🤖"
    system_prompt: str = ""

    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm
        self._llm = None

    def analyze(self, message: str, context: UserContext, db_data: dict) -> AgentResult:
        """
        Анализирует сообщение в своём домене.
        
        Args:
            message: исходное сообщение пользователя
            context: контекст пользователя
            db_data: данные из БД (транзакции, категории и т.д.)
        
        Returns:
            AgentResult с анализом
        """
        if self.use_llm and self._llm:
            return self._llm_analyze(message, context, db_data)
        return self._rule_analyze(message, context, db_data)

    def _llm_analyze(self, message: str, context: UserContext, db_data: dict) -> AgentResult:
        """LLM-режим анализа (требует API-ключ)"""
        raise NotImplementedError(f"{self.name}: LLM mode not implemented")

    def _rule_analyze(self, message: str, context: UserContext, db_data: dict) -> AgentResult:
        """Rule-based режим анализа (fallback без API)"""
        raise NotImplementedError(f"{self.name}: rule-based mode not implemented")

    def get_llm_client(self):
        """Ленивое создание LLM-клиента"""
        if self._llm is None:
            from ..llm import get_llm
            self._llm = get_llm()
        return self._llm

    def __repr__(self):
        return f"{self.emoji} {self.name} ({self.role})"