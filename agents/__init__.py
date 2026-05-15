"""
FRIDAY Multi-Agent System
5 специализированных AI-агентов:
- FRIDAY CORE — главный оркестратор
- FINANCE ANALYST — анализ расходов
- SAVINGS STRATEGIST — стратегия накоплений
- BEHAVIOR AI — анализ привычек
- COMMUNICATION AI — стиль общения (FRIDAY Voice)
"""

from .base import BaseAgent, AgentResult
from .core import FridayCore
from .analyst import FinanceAnalyst
from .strategist import SavingsStrategist
from .behavior import BehaviorAI
from .communicator import CommunicationAI