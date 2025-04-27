#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Base message handling interface for the Move 37 application.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Callable, Optional
from datetime import datetime
import uuid

from app.models.messages import BaseMessage, MessageType

class MessageHandler(ABC):
    """Abstract base class for message handling."""
    
    def __init__(self):
        self._message_callbacks = {}
    
    def register_callback(self, message_type: MessageType, callback: Callable) -> None:
        """Register a callback for a specific message type."""
        self._message_callbacks[message_type] = callback
    
    @abstractmethod
    async def send_message(self, message: BaseMessage) -> None:
        """Send a message to the client."""
        pass
    
    @abstractmethod
    async def receive_message(self) -> BaseMessage:
        """Receive a message from the client."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the connection."""
        pass
    
    def _create_message(self, message_type: MessageType, data: Dict[str, Any]) -> BaseMessage:
        """Create a new message with the given type and data."""
        return BaseMessage(
            type=message_type,
            data=data,
            timestamp=datetime.now().timestamp(),
            message_id=str(uuid.uuid4())
        )
    
    async def send_status_update(self, message: str, operation_id: str) -> None:
        """Send a status update message."""
        status_message = self._create_message(
            MessageType.STATUS_UPDATE,
            {
                "message": message,
                "operation_id": operation_id,
                "final_response": False
            }
        )
        await self.send_message(status_message)
    
    async def send_agent_response(self, response: Dict[str, Any]) -> None:
        """Send an agent response message."""
        agent_message = self._create_message(
            MessageType.AGENT_RESPONSE,
            response
        )
        await self.send_message(agent_message)
    
    async def send_quality_update(self, updates: Dict[str, Any]) -> None:
        """Send a quality update message."""
        quality_message = self._create_message(
            MessageType.QUALITY_UPDATE,
            updates
        )
        await self.send_message(quality_message)
    
    async def process_messages(self) -> None:
        """Process incoming messages."""
        while True:
            try:
                message = await self.receive_message()
                if message.type in self._message_callbacks:
                    await self._message_callbacks[message.type](message)
            except Exception as e:
                print(f"Error processing message: {e}")
                break 