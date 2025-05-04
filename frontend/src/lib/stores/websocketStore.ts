import { derived, writable } from 'svelte/store';
import { browser } from '$app/environment';
import { recallWsService, recordWsService } from '$lib/services/websocketService';
import { recallWsState, recordWsState } from '$lib/services/websocket';
import { get } from 'svelte/store';
import { activeAgent } from '$lib/stores/agentsStore';

// Create stores for WebSocket-related UI state
export const showConnectionStatus = writable<boolean>(false);
export const shouldAutoReconnect = writable<boolean>(true);
export const maxReconnectAttempts = writable<number>(10);

// Derived store to check if either websocket is connected
export const isConnected = derived(
  [recallWsState, recordWsState],
  ([$recallWsState, $recordWsState]) => 
    $recallWsState.status === 'connected' || $recordWsState.status === 'connected'
);

// A store for any important notices to show the user
export const wsNotifications = writable<{
  show: boolean;
  message: string;
  type: 'info' | 'warning' | 'error' | 'success';
  timeout?: number;
}>({
  show: false,
  message: '',
  type: 'info',
  timeout: 5000 // Default timeout in ms (5 seconds)
});

// Initialize WebSocket notification logic
if (browser) {
  // Wait until after component initialization
  setTimeout(() => {
    // Subscribe to connection status changes to show notifications
    recallWsState.subscribe(state => {
      if (state.status === 'connected') {
        showNotification('Connected to recall server', 'success');
      } else if (state.status === 'error') {
        showNotification('Recall connection error', 'error');
      } else if (state.status === 'disconnected') {
        showNotification('Disconnected from recall server', 'warning');
      }
    });
    
    recordWsState.subscribe(state => {
      if (state.status === 'connected') {
        showNotification('Connected to record server', 'success');
      } else if (state.status === 'error') {
        showNotification('Record connection error', 'error');
      } else if (state.status === 'disconnected') {
        showNotification('Disconnected from record server', 'warning');
      }
    });
    
    // Auto-show connection status when not connected
    isConnected.subscribe(connected => {
      showConnectionStatus.set(!connected);
    });
  }, 0);
}

/**
 * Helper function to show a notification
 */
export function showNotification(
  message: string,
  type: 'info' | 'warning' | 'error' | 'success' = 'info',
  timeout: number = 5000
): void {
  wsNotifications.set({
    show: true,
    message,
    type,
    timeout
  });
  
  if (timeout > 0) {
    setTimeout(() => {
      wsNotifications.update(n => {
        if (n.message === message) {
          return { ...n, show: false };
        }
        return n;
      });
    }, timeout);
  }
}

/**
 * Helper function to dismiss a notification
 */
export function dismissNotification(): void {
  wsNotifications.update(n => ({ ...n, show: false }));
}

/**
 * Helper function to manually connect WebSockets
 */
export function connect(): void {
  recallWsService.connect();
  recordWsService.connect();
}

/**
 * Helper function to manually disconnect WebSockets
 */
export function disconnect(): void {
  recallWsService.disconnect();
  recordWsService.disconnect();
}

/**
 * Send a message to the chat using the appropriate WebSocket
 * @param message The message text to send
 * @param queryId Optional query ID to identify this message
 * @param attachments Optional file attachments
 * @param attachmentPath Optional file path for attachments already uploaded
 * @param operationType Optional operation type ('record' or 'recall'), defaults to 'recall'
 * @returns Boolean indicating if the message was successfully sent
 */
export function sendChatMessage(
  message: string, 
  queryId?: string, 
  attachments: any[] = [],
  attachmentPath?: string,
  operationType: 'record' | 'recall' = 'recall'
): boolean {
  if (!message.trim()) return false;
  
  // Get the current active agent
  const currentAgentId = get(activeAgent);
  
  // Get user ID from localStorage or use a default
  const userId = browser ? localStorage.getItem('userId') || 'default' : 'default';
  
  // Use provided queryId or generate a new one
  const messageQueryId = queryId || `q_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  
  // Use different payload and service based on operation type
  if (operationType === 'record') {
    // Create a record submission payload
    const recordPayload = {
      type: "record_submission",
      data: {
        content: message,
        user_id: userId,
        record_type: currentAgentId, // Use agent ID as record type
        metadata: {
          timestamp: new Date().toISOString()
        },
        query_id: messageQueryId
      }
    };
    
    console.log("Sending record submission:", recordPayload);
    
    // Use record WebSocket service
    return recordWsService.send(recordPayload);
  } else {
    // Default to recall query
    const recallPayload: {
      type: string;
      data: {
        query: string;
        user_id: string;
        target_agent: string;
        query_id: string;
        attachment_file_path?: string; // Make this optional
      }
    } = {
      type: "recall_query",
      data: {
        query: message,
        user_id: userId,
        target_agent: currentAgentId,
        query_id: messageQueryId
      }
    };
    
    // For butterfly agent with attachment, add the attachment file path
    if (currentAgentId === 'butterfly' && attachmentPath) {
      recallPayload.data.attachment_file_path = attachmentPath;
    }
    
    console.log("Sending recall query:", recallPayload);
    
    // Use recall service for chat messages
    return recallWsService.send(recallPayload);
  }
} 