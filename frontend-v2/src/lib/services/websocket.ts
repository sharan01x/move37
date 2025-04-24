import { writable, get } from 'svelte/store';
import type { Writable } from 'svelte/store';
import { recallWsService, recordWsService } from './websocketService';

// Define types for the WebSocket states and messages
type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

interface WebSocketState {
    status: ConnectionStatus;
    error: Event | null;
}

interface WebSocketMessage {
    type: string;
    data?: any;
    request_id?: string;
    [key: string]: any;
}

type MessageHandler = (clientId: string, message: WebSocketMessage) => void;

// Connection status stores
export const recallWsState: Writable<WebSocketState> = writable({
    status: 'disconnected',
    error: null
});

export const recordWsState: Writable<WebSocketState> = writable({
    status: 'disconnected',
    error: null
});

// Store for message handlers
type MessageHandlersMap = Record<string, MessageHandler[]>;
export const messageHandlers: Writable<MessageHandlersMap> = writable({});

// Connect to the recall WebSocket (for READ operations)
export function connectRecallWebSocket(): void {
    recallWsState.update(state => ({ ...state, status: 'connecting' }));
    
    // Subscribe to recall WebSocket service
    recallWsService.on('open', () => {
        recallWsState.update(state => ({
            ...state,
            status: 'connected',
            error: null
        }));
        
        console.log('Recall WebSocket connected');
    });
    
    recallWsService.on('close', () => {
        recallWsState.update(state => ({
            ...state,
            status: 'disconnected'
        }));
        
        console.log('Recall WebSocket closed');
    });
    
    recallWsService.on('error', (error) => {
        recallWsState.update(state => ({
            ...state,
            status: 'error',
            error: error
        }));
        
        console.error('Recall WebSocket error:', error);
    });
    
    // Make sure it's connected
    recallWsService.connect();
}

// Connect to the record WebSocket (for WRITE operations)
export function connectRecordWebSocket(): void {
    recordWsState.update(state => ({ ...state, status: 'connecting' }));
    
    // Subscribe to record WebSocket service
    recordWsService.on('open', () => {
        recordWsState.update(state => ({
            ...state,
            status: 'connected',
            error: null
        }));
        
        console.log('Record WebSocket connected');
    });
    
    recordWsService.on('close', () => {
        recordWsState.update(state => ({
            ...state,
            status: 'disconnected'
        }));
        
        console.log('Record WebSocket closed');
    });
    
    recordWsService.on('error', (error) => {
        recordWsState.update(state => ({
            ...state,
            status: 'error',
            error: error
        }));
        
        console.error('Record WebSocket error:', error);
    });
    
    // Make sure it's connected
    recordWsService.connect();
}

// Send a message through the appropriate WebSocket
export function sendMessage(messageType: 'recall' | 'record', message: WebSocketMessage): boolean {
    const service = messageType === 'recall' ? recallWsService : recordWsService;
    return service.send(message);
}

// Disconnect both WebSockets
export function disconnectWebSockets(): void {
    recallWsService.disconnect();
    recordWsService.disconnect();
}

// Auto-connect on import
if (typeof window !== 'undefined') {
    // Only connect in browser environment
    connectRecallWebSocket();
    connectRecordWebSocket();
} 