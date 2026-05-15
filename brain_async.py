"""
Async Brain — асинхронный оркестратор с параллельным вызовом агентов.

В отличие от синхронного brain.py:
- Агенты вызываются конкурентно (asyncio.gather)
- Результаты собираются по мере готовности
- Есть таймауты на каждого агента
- Не блокирует event loop бота
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from agents.base import AgentResult, UserContext
from agents.core import FridayCore
from agents.analyst import FinanceAnalyst
from agents.strategist import SavingsStrategist
from agents.behavior import BehaviorAI
from agents.communicator import CommunicatorAI
from logger import log


@dataclass
class BrainResult:
    """Результат работы всего мозга."""
    intent: str = "general"
    core_result: Optional[AgentResult] = None
    analyst_result: Optional[AgentResult] = None
    strategist_result: Optional[AgentResult] = None
    behavior_result: Optional[AgentResult] = None
    communicator_result: Optional[AgentResult] = None
    final_answer: str = ""
    errors: list[str] = field(default_factory=list)
    latency_ms: float = 0

    @property
    def success(self) -> bool:
        return len(self.final_answer) > 0


class AsyncBrain:
    """Асинхронный оркестратор агентов."""

    AGENT_TIMEOUT = 15.0

    def __init__(self):
        self.core = FridayCore()
        self.analyst = FinanceAnalyst()
        self.strategist = SavingsStrategist()
        self.behavior = BehaviorAI()
        self.communicator = CommunicatorAI()

    async def _run_agent(self, name: str, coro) -> AgentResult:
        """Запустить агента с таймаутом."""
        try:
            return await asyncio.wait_for(coro, timeout=self.AGENT_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"Agent {name} timed out after {self.AGENT_TIMEOUT}s")
            return AgentResult(agent=name, action="timeout", success=False, error="timeout")
        except Exception as e:
            log.error(f"Agent {name} crashed: {e}")
            return AgentResult(agent=name, action="error", success=False, error=str(e))

    async def process(
        self,
        user_id: int,
        message: str,
        username: str = "",
        first_name: str = "",
        balance: float = 0,
        monthly_income: float = 0,
        monthly_expense: float = 0,
        active_goals: list = None,
        budget_alerts: list = None,
        monthly_stats: list = None,
        recent_transactions: list = None,
        category_limits: list = None,
        prev_month_stats: list = None,
    ) -> BrainResult:
        """Главный пайплайн с параллельными вызовами."""
        start = time.monotonic()
        result = BrainResult()

        ctx = UserContext(
            user_id=user_id,
            username=username,
            first_name=first_name,
            balance=balance,
            monthly_income=monthly_income,
            monthly_expense=monthly_expense,
            active_goals=active_goals or [],
            budget_alerts=budget_alerts or [],
        )

        db_data = {
            "monthly_stats": monthly_stats or [],
            "recent_transactions": recent_transactions or [],
            "category_limits": category_limits or [],
            "prev_month_stats": prev_month_stats or [],
        }

        # Шаг 1: CORE классифицирует интент (синхронно — быстро)
        core = await self._run_agent(
            "core",
            asyncio.to_thread(self.core.analyze, message, ctx, db_data)
        )
        result.core_result = core
        result.intent = core.action if core.success else "general"
        log.info(f"Intent: {result.intent}")

        # Шаг 2: параллельный запуск агентов
        tasks = []
        task_names = []

        if result.intent in ("report", "general"):
            tasks.append(self._run_agent(
                "analyst",
                asyncio.to_thread(self.analyst.analyze, message, ctx, db_data)
            ))
            task_names.append("analyst")

        if result.intent in ("goal", "general", "advice"):
            tasks.append(self._run_agent(
                "strategist",
                asyncio.to_thread(self.strategist.analyze, message, ctx, db_data)
            ))
            task_names.append("strategist")

        if result.intent != "greeting":
            tasks.append(self._run_agent(
                "behavior",
                asyncio.to_thread(self.behavior.analyze, message, ctx, db_data)
            ))
            task_names.append("behavior")

        if tasks:
            agent_results = await asyncio.gather(*tasks)
            for name, ar in zip(task_names, agent_results):
                setattr(result, f"{name}_result", ar)

        # Шаг 3: коммуникатор формирует финальный ответ
        comm = await self._run_agent(
            "communicator",
            asyncio.to_thread(self.communicator.analyze, message, ctx, {
                "analyst": result.analyst_result,
                "strategist": result.strategist_result,
                "behavior": result.behavior_result,
                "intent": result.intent,
            })
        )
        result.communicator_result = comm
        result.final_answer = (
            comm.data.get("response", "") if comm.success
            else "Извини, не могу сейчас ответить. Попробуй позже."
        )
        result.latency_ms = (time.monotonic() - start) * 1000

        log.info(f"Brain processed in {result.latency_ms:.0f}ms, "
                 f"intent={result.intent}, answer_len={len(result.final_answer)}")
        return result


# Глобальный экземпляр
brain = AsyncBrain()
