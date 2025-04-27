#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WebSocket message handler implementation for the Move 37 application.
"""

from typing import Dict, Any, Optional, Callable
import json
import logging
from fastapi import WebSocket
from pydantic import BaseModel

from app.messaging.base import MessageHandler
from app.models.messages import BaseMessage, MessageType, RecallQueryMessage
from app.utils.file_handler import FileUploadManager

logger = logging.getLogger(__name__)

class WebSocketHandler(MessageHandler):
    """WebSocket implementation of the message handler."""
    
    def __init__(self, websocket: WebSocket):
        super().__init__()
        self.websocket = websocket
    
    async def send_message(self, message: BaseMessage) -> None:
        """Send a message through the WebSocket connection."""
        await self.websocket.send_json(message.dict())
    
    async def receive_message(self) -> BaseMessage:
        """Receive a message from the WebSocket connection."""
        data = await self.websocket.receive_json()
        return BaseMessage(**data)
    
    async def close(self) -> None:
        """Close the WebSocket connection."""
        await self.websocket.close()


class MessageService:
    """Service for handling WebSocket messages."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.message_handlers: Dict[MessageType, Callable] = {}
        self.file_manager = FileUploadManager()  # Initialize file upload manager
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Connect a new WebSocket client."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
    
    def disconnect(self, client_id: str):
        """Disconnect a WebSocket client."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
    
    def register_handler(self, message_type: MessageType, handler: Callable):
        """Register a handler for a specific message type."""
        self.message_handlers[message_type] = handler
    
    async def send_message(self, client_id: str, message_type: MessageType, data: Dict[str, Any]):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            message = {
                "type": message_type,
                "data": data
            }
            await websocket.send_text(json.dumps(message))
    
    async def broadcast(self, message_type: MessageType, data: Dict[str, Any]):
        """Broadcast a message to all connected clients."""
        for client_id in self.active_connections:
            await self.send_message(client_id, message_type, data)
    
    async def handle_message(self, client_id: str, data: dict):
        """Handle an incoming message from a client."""
        try:
            logger.info(f"Handling message in MessageService: {data['type'] if 'type' in data else 'unknown'}")  # Debug log
            message_type = data.get("type")
            if not message_type:
                logger.warning("No message type found in data")
                return
                
            try:
                message_type_enum = MessageType(message_type)
                logger.debug(f"Converted message type to enum: {message_type_enum}")
            except ValueError as e:
                logger.warning(f"Invalid message type: {message_type}")
                return
            
            # Check if this is a file-related message
            if message_type_enum in [MessageType.FILES_LIST, MessageType.FILES_UPLOAD, MessageType.FILES_DELETE]:
                logger.info(f"Handling file-related message: {message_type_enum}")
                websocket = self.active_connections.get(client_id)
                if websocket:
                    try:
                        response = await self.file_manager.handle_file_message(data, websocket)
                        if response:
                            response_type = response.get('type')
                            if response_type == 'error':
                                await self.send_message(
                                    client_id,
                                    MessageType.STATUS_UPDATE,
                                    {"message": response.get('data', {}).get('error', 'Unknown error')}
                                )
                            else:
                                await self.send_message(
                                    client_id,
                                    MessageType.FILES_RESPONSE,
                                    response.get('data', {})
                                )
                    except Exception as e:
                        logger.error(f"Error handling file message: {e}")
                        await self.send_message(
                            client_id,
                            MessageType.STATUS_UPDATE,
                            {"message": f"Error handling file operation: {str(e)}"}
                        )
            # Handle other message types
            elif message_type_enum in self.message_handlers:
                handler = self.message_handlers[message_type_enum]
                logger.debug(f"Calling handler for {message_type_enum}")
                await handler(client_id, data)
            else:
                logger.warning(f"No handler registered for message type: {message_type_enum}")
                await self.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": f"No handler registered for message type: {message_type}"}
                )
                
        except Exception as e:
            logger.error(f"Error handling message from client {client_id}: {e}")
            # Send error message to client
            await self.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error handling message: {str(e)}"}
            )


class WebSocketConnectionHandler:
    """Handler for WebSocket connections."""
    
    def __init__(self):
        self.message_service = MessageService()
    
    async def handle_connection(self, websocket: WebSocket, client_id: str):
        """Handle a new WebSocket connection."""
        print(f"New WebSocket connection from client {client_id}")  # Debug log
        await self.message_service.connect(websocket, client_id)
        try:
            while True:
                message = await websocket.receive_text()
                print(f"Received WebSocket message from client {client_id}: {message}")  # Debug log
                try:
                    # Parse the message once
                    data = json.loads(message)
                    print(f"Parsed message data: {data}")  # Debug log
                    
                    # Pass the parsed data directly to the message service
                    await self.message_service.handle_message(client_id, data)
                except json.JSONDecodeError as e:
                    print(f"Error parsing message: {e}")  # Debug log
                    # Send error message to client
                    await self.message_service.send_message(
                        client_id,
                        MessageType.STATUS_UPDATE,
                        {"message": f"Error parsing message: {str(e)}"}
                    )
                except Exception as e:
                    print(f"Error handling message: {e}")  # Debug log
                    # Send error message to client
                    await self.message_service.send_message(
                        client_id,
                        MessageType.STATUS_UPDATE,
                        {"message": f"Error handling message: {str(e)}"}
                    )
        except Exception as e:
            print(f"Error in WebSocket connection: {e}")
        finally:
            print(f"Closing WebSocket connection for client {client_id}")  # Debug log
            self.message_service.disconnect(client_id)