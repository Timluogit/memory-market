"""Agent抽象层 - 接口定义、管理器、上下文传递

基于Supermemory ASMR架构的多Agent并行推理系统基础组件
"""
from __future__ import annotations

import abc
import uuid
import time
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="BaseAgent")


class AgentRole(str, Enum):
    """Agent角色枚举"""
    OBSERVER_USER_INFO = "observer_user_info"
    OBSERVER_TEMPORAL = "observer_temporal"
    OBSERVER_GENERAL = "observer_general"
    SEARCHER_DIRECT = "searcher_direct"
    SEARCHER_CONTEXT = "searcher_context"
    SEARCHER_TIMELINE = "searcher_timeline"
    AGGREGATOR = "aggregator"


class AgentStatus(str, Enum):
    """Agent执行状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class AgentContext:
    """Agent上下文 - 在Agent之间传递的共享状态

    包含原始数据、中间结果、元数据等
    """
    query: str
    user_id: Optional[str] = None
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    raw_data: Dict[str, Any] = field(default_factory=dict)
    observations: Dict[str, Any] = field(default_factory=dict)
    search_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 6大维度提取结果
    dimension_user_info: Dict[str, Any] = field(default_factory=dict)
    dimension_preferences: Dict[str, Any] = field(default_factory=dict)
    dimension_events: Dict[str, Any] = field(default_factory=dict)
    dimension_temporal: Dict[str, Any] = field(default_factory=dict)
    dimension_updates: Dict[str, Any] = field(default_factory=dict)
    dimension_assistant: Dict[str, Any] = field(default_factory=dict)

    def get_dimension(self, name: str) -> Dict[str, Any]:
        """获取指定维度的数据"""
        dim_map = {
            "user_info": self.dimension_user_info,
            "preferences": self.dimension_preferences,
            "events": self.dimension_events,
            "temporal": self.dimension_temporal,
            "updates": self.dimension_updates,
            "assistant": self.dimension_assistant,
        }
        return dim_map.get(name, {})

    def set_dimension(self, name: str, data: Dict[str, Any]) -> None:
        """设置指定维度的数据"""
        dim_map = {
            "user_info": self.dimension_user_info,
            "preferences": self.dimension_preferences,
            "events": self.dimension_events,
            "temporal": self.dimension_temporal,
            "updates": self.dimension_updates,
            "assistant": self.dimension_assistant,
        }
        if name in dim_map:
            dim_map[name].update(data)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "query": self.query,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "raw_data": self.raw_data,
            "observations": self.observations,
            "search_results": self.search_results,
            "metadata": self.metadata,
            "dimensions": {
                "user_info": self.dimension_user_info,
                "preferences": self.dimension_preferences,
                "events": self.dimension_events,
                "temporal": self.dimension_temporal,
                "updates": self.dimension_updates,
                "assistant": self.dimension_assistant,
            },
        }


@dataclass
class AgentResult:
    """Agent执行结果"""
    agent_id: str
    role: AgentRole
    status: AgentStatus
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    execution_time_ms: float = 0.0
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.status == AgentStatus.COMPLETED


class BaseAgent(abc.ABC):
    """Agent基类 - 所有Agent的抽象接口"""

    def __init__(
        self,
        agent_id: Optional[str] = None,
        role: AgentRole = AgentRole.OBSERVER_GENERAL,
        timeout_seconds: float = 30.0,
    ):
        self.agent_id = agent_id or f"{role.value}_{uuid.uuid4().hex[:8]}"
        self.role = role
        self.timeout_seconds = timeout_seconds
        self._status = AgentStatus.IDLE

    @property
    def status(self) -> AgentStatus:
        return self._status

    @abc.abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """执行Agent任务

        Args:
            context: 共享上下文

        Returns:
            AgentResult: 执行结果
        """
        ...

    async def run(self, context: AgentContext) -> AgentResult:
        """运行Agent（带超时和异常处理）"""
        self._status = AgentStatus.RUNNING
        start_time = time.monotonic()

        try:
            import asyncio
            result = await asyncio.wait_for(
                self.execute(context),
                timeout=self.timeout_seconds,
            )
            result.execution_time_ms = (time.monotonic() - start_time) * 1000
            self._status = result.status
            return result

        except asyncio.TimeoutError:
            elapsed = (time.monotonic() - start_time) * 1000
            self._status = AgentStatus.TIMEOUT
            logger.warning(f"Agent {self.agent_id} timed out after {elapsed:.0f}ms")
            return AgentResult(
                agent_id=self.agent_id,
                role=self.role,
                status=AgentStatus.TIMEOUT,
                execution_time_ms=elapsed,
                error=f"Agent timed out after {self.timeout_seconds}s",
            )
        except Exception as e:
            elapsed = (time.monotonic() - start_time) * 1000
            self._status = AgentStatus.FAILED
            logger.error(f"Agent {self.agent_id} failed: {e}", exc_info=True)
            return AgentResult(
                agent_id=self.agent_id,
                role=self.role,
                status=AgentStatus.FAILED,
                execution_time_ms=elapsed,
                error=str(e),
            )


class AgentManager:
    """Agent管理器 - 注册、创建、管理Agent实例"""

    def __init__(self):
        self._registry: Dict[AgentRole, Type[BaseAgent]] = {}
        self._instances: Dict[str, BaseAgent] = {}

    def register(self, role: AgentRole, agent_cls: Type[BaseAgent]) -> None:
        """注册Agent类型"""
        self._registry[role] = agent_cls
        logger.info(f"Registered agent role: {role.value} -> {agent_cls.__name__}")

    def create(self, role: AgentRole, **kwargs) -> BaseAgent:
        """创建Agent实例"""
        if role not in self._registry:
            raise ValueError(f"Unknown agent role: {role}")
        agent = self._registry[role](role=role, **kwargs)
        self._instances[agent.agent_id] = agent
        return agent

    def get(self, agent_id: str) -> Optional[BaseAgent]:
        """获取Agent实例"""
        return self._instances.get(agent_id)

    def list_roles(self) -> List[AgentRole]:
        """列出已注册的角色"""
        return list(self._registry.keys())

    def list_instances(self) -> List[BaseAgent]:
        """列出所有实例"""
        return list(self._instances.values())

    def clear(self) -> None:
        """清除所有实例"""
        self._instances.clear()


# 全局Agent管理器
_manager: Optional[AgentManager] = None


def get_agent_manager() -> AgentManager:
    """获取全局Agent管理器单例"""
    global _manager
    if _manager is None:
        _manager = AgentManager()
        _register_default_agents(_manager)
    return _manager


def _register_default_agents(manager: AgentManager) -> None:
    """注册默认Agent"""
    from app.agents.observers.user_info_agent import UserInfoAgent
    from app.agents.observers.temporal_agent import TemporalAgent
    from app.agents.observers.general_observer import GeneralObserver
    from app.agents.searchers.direct_fact_agent import DirectFactAgent
    from app.agents.searchers.context_agent import ContextAgent
    from app.agents.searchers.timeline_agent import TimelineAgent
    from app.agents.aggregator import AggregatorAgent

    manager.register(AgentRole.OBSERVER_USER_INFO, UserInfoAgent)
    manager.register(AgentRole.OBSERVER_TEMPORAL, TemporalAgent)
    manager.register(AgentRole.OBSERVER_GENERAL, GeneralObserver)
    manager.register(AgentRole.SEARCHER_DIRECT, DirectFactAgent)
    manager.register(AgentRole.SEARCHER_CONTEXT, ContextAgent)
    manager.register(AgentRole.SEARCHER_TIMELINE, TimelineAgent)
    manager.register(AgentRole.AGGREGATOR, AggregatorAgent)
