"""Тесты базы данных."""
import pytest


class TestUsers:
    def test_ensure_user_creates(self, test_db):
        test_db.ensure_user(1, "alice", "Alice")
        assert test_db.get_balance(1) == 0

    def test_ensure_user_updates(self, test_db):
        test_db.ensure_user(1, "old", "Old")
        test_db.ensure_user(1, "new", "New")
        assert test_db.get_balance(1) == 0


class TestTransactions:
    def test_add_and_balance(self, test_db):
        test_db.ensure_user(1, "alice", "Alice")
        cats = test_db.get_categories("income")
        test_db.add_transaction(1, "income", 1000, cats[0]["id"], "зарплата")
        test_db.add_transaction(1, "expense", 300, None, "обед")
        balance = test_db.get_balance(1)
        assert balance == 700

    def test_delete(self, test_db):
        test_db.ensure_user(1, "alice", "Alice")
        cats = test_db.get_categories("income")
        tid = test_db.add_transaction(1, "income", 500, cats[0]["id"])
        assert test_db.delete_transaction(1, tid)
        assert test_db.get_balance(1) == 0

    def test_history_limit(self, test_db):
        test_db.ensure_user(1, "alice", "Alice")
        cats = test_db.get_categories("income")
        for i in range(15):
            test_db.add_transaction(1, "income", 100, cats[0]["id"], f"txn {i}")
        history = test_db.get_recent(1, limit=5)
        assert len(history) == 5


class TestGoals:
    def test_goal_lifecycle(self, test_db):
        test_db.ensure_user(1, "alice", "Alice")
        test_db.add_goal(1, "Отпуск", 100000, "2026-12-31")
        goals = test_db.get_goals(1)
        assert len(goals) == 1
        assert goals[0]["name"] == "Отпуск"
        assert goals[0]["target_amount"] == 100000


class TestBudgets:
    def test_budget_alerts(self, test_db):
        test_db.ensure_user(1, "alice", "Alice")
        cats = test_db.get_categories("expense")
        test_db.set_budget(1, cats[0]["id"], 1000)
        test_db.add_transaction(1, "expense", 950, cats[0]["id"], "почти лимит")
        alerts = test_db.check_budget_alerts(1)
        assert len(alerts) >= 1

    def test_budget_overrun(self, test_db):
        test_db.ensure_user(1, "alice", "Alice")
        cats = test_db.get_categories("expense")
        test_db.set_budget(1, cats[0]["id"], 500)
        test_db.add_transaction(1, "expense", 600, cats[0]["id"], "превышение")
        alerts = test_db.check_budget_alerts(1)
        assert any("превышен" in a for a in alerts)
