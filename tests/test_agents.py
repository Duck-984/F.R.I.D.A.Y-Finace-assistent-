"""Тесты AI-агентов."""
import pytest
from unittest.mock import patch


class TestBaseAgent:
    def test_agent_result(self):
        from agents.base import AgentResult
        r = AgentResult(agent="test", action="analyze", data={"x": 1})
        assert r.agent == "test"
        assert r.success
        assert r.data["x"] == 1

    def test_agent_result_error(self):
        from agents.base import AgentResult
        r = AgentResult(agent="x", action="report", error="bad")
        assert not r.success
        assert r.error == "bad"

    def test_user_context(self):
        from agents.base import UserContext
        ctx = UserContext(
            user_id=1, username="alice", first_name="Alice",
            balance=5000, monthly_income=100000, monthly_expense=70000
        )
        assert ctx.user_id == 1
        assert ctx.balance == 5000


class TestCoreAgent:
    def test_intent_detection(self, monkeypatch):
        """CORE определяет интенты через _rule_analyze."""
        monkeypatch.setattr("agents.core.FridayCore._llm_analyze",
                          lambda s, m, c, d: None)
        from agents.core import FridayCore
        from agents.base import UserContext
        agent = FridayCore()
        ctx = UserContext(user_id=1, username="t", first_name="T")

        test_cases = [
            ("Баланс пожалуйста", "balance"),
            ("Как накопить 100к?", "goal"),
            ("Привет!", "unknown"),
            ("Зарплата пришла 50к", "add_income"),
            ("Дай совет по экономии", "advice"),
            ("удали запись", "delete"),
            ("отчёт за месяц", "report"),
        ]
        for msg, expected in test_cases:
            result = agent._rule_analyze(msg, ctx, {})
            assert result.action == expected, \
                f"'{msg}' → {result.action}, ожидалось {expected}"


class TestAnalystAgent:
    def test_basic_analysis(self, monkeypatch):
        monkeypatch.setattr("agents.analyst.FinanceAnalyst._llm_analyze",
                          lambda s, m, c, d: None)
        from agents.analyst import FinanceAnalyst
        from agents.base import UserContext
        agent = FinanceAnalyst()
        ctx = UserContext(user_id=1, username="t", first_name="T")
        result = agent._rule_analyze("отчёт", ctx, {"monthly_stats": []})
        assert result.success

    def test_category_breakdown(self, monkeypatch):
        monkeypatch.setattr("agents.analyst.FinanceAnalyst._llm_analyze",
                          lambda s, m, c, d: None)
        from agents.analyst import FinanceAnalyst
        from agents.base import UserContext
        agent = FinanceAnalyst()
        ctx = UserContext(user_id=1, username="t", first_name="T")
        db_data = {
            "monthly_stats": [
                {"icon": "🍕", "name": "Еда", "total": 15000},
                {"icon": "🚕", "name": "Такси", "total": 8000},
                {"icon": "🎮", "name": "Игры", "total": 3000},
            ]
        }
        result = agent._rule_analyze("отчёт", ctx, db_data)
        assert result.success
        assert result.data.get("total_expense") == 26000


class TestStrategistAgent:
    def test_savings_plan(self, monkeypatch):
        monkeypatch.setattr("agents.strategist.SavingsStrategist._llm_analyze",
                          lambda s, m, c, d: None)
        from agents.strategist import SavingsStrategist
        from agents.base import UserContext
        agent = SavingsStrategist()
        ctx = UserContext(
            user_id=1, username="t", first_name="T",
            monthly_income=50000, monthly_expense=35000,
            active_goals=[{
                "id": 1, "name": "Квартира", "target_amount": 3000000,
                "current_amount": 100000, "monthly_contribution": 15000,
                "deadline": "2028-01-01"
            }]
        )
        result = agent._rule_analyze("хочу квартиру", ctx, {})
        assert result.success
