"""MessageBus interface for future multi-agent communication. V2: not implemented."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import time


@dataclass
class AgentMessage:
    sender: str
    recipient: str | None = None  # None = broadcast
    content: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class MessageBus:
    """Message bus for inter-agent communication.

    V2: stub only. Agents pass `bus=None` for single-agent mode.
    Future: implement pub/sub routing, message filtering, dead-letter queues.
    """

    def __init__(self):
        self._subscribers: dict[str, Callable] = {}
        self._message_log: list[AgentMessage] = []

    def subscribe(self, agent_name: str, callback: Callable) -> None:
        """Register an agent to receive messages addressed to it."""
        self._subscribers[agent_name] = callback

    def unsubscribe(self, agent_name: str) -> None:
        self._subscribers.pop(agent_name, None)

    async def publish(self, msg: AgentMessage) -> None:
        """Send a message. Routes to recipient if specified, else broadcasts."""
        self._message_log.append(msg)
        if msg.recipient and msg.recipient in self._subscribers:
            await self._subscribers[msg.recipient](msg)
        elif msg.recipient is None:
            for name, cb in self._subscribers.items():
                if name != msg.sender:
                    await cb(msg)

    def history(self, limit: int = 50) -> list[AgentMessage]:
        return self._message_log[-limit:]
