import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

// Connection status enum
export enum ConnectionStatus {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  ERROR = 'error'
}

// WebSocket message types
export enum MessageType {
  AGENT_RESPONSE = 'agent_response',
  QUALITY_UPDATES = 'quality_updates',
  STATUS_UPDATE = 'status_update',
  RECORD_RESPONSE = 'record_response',
  FILES_RESPONSE = 'files_response',
  USER_FACTS_RESPONSE = 'user_facts_response',
  SYSTEM_MESSAGE = 'system_message',
  UPLOAD_PROGRESS = 'upload_progress',
  USER_FACTS_UPDATE = 'user_facts_update',
  ERROR = 'error'
}

// WebSocket message interface
export interface WebSocketMessage {
  type: MessageType | string;
  payload: any;
  data?: any;
  timestamp?: string;
  id?: string;
}

// Configuration
const DEFAULT_CONFIG = {
  reconnectInterval: 1000, // Starting interval for reconnect (1 second)
  maxReconnectInterval: 30000, // Maximum reconnect interval (30 seconds)
  reconnectDecay: 1.5, // Exponential factor for reconnect backoff
  maxReconnectAttempts: 10, // Maximum number of reconnect attempts (null for infinite)
  debug: false // Debug mode toggle
};

// Create stores for WebSocket state
export const connectionStatus = writable<ConnectionStatus>(ConnectionStatus.DISCONNECTED);
export const lastMessage = writable<WebSocketMessage | null>(null);
export const messageHistory = writable<WebSocketMessage[]>([]);
export const reconnectCount = writable(0);
export const isReconnecting = writable(false);

// Derived store for checking if connected
export const isConnected = derived(
  connectionStatus,
  $status => $status === ConnectionStatus.CONNECTED
);

// Event handlers storage - Map for all message types including dynamic ones from backend
const messageHandlers: Record<string, Array<(data?: any) => void>> = {};

// Initialize handlers for known message types
Object.values(MessageType).forEach(type => {
  messageHandlers[type] = [];
});

// WebSocket service class
export class WebSocketService {
  private socket: WebSocket | null = null;
  private reconnectTimeout: number | null = null;
  private reconnectAttempts = 0;
  private config = { ...DEFAULT_CONFIG };
  private url: string;
  private intentionallyClosed = false;
  
  constructor(url: string, config = {}) {
    this.url = url;
    this.config = { ...DEFAULT_CONFIG, ...config };
    
    // Reset reconnect attempts when we successfully connect
    connectionStatus.subscribe(status => {
      if (status === ConnectionStatus.CONNECTED) {
        this.reconnectAttempts = 0;
        reconnectCount.set(0);
        isReconnecting.set(false);
      }
    });
  }
  
  // Initialize the WebSocket connection
  public connect(): void {
    // Only attempt to connect in browser environments
    if (!browser) return;
    
    // Don't try to connect if already connecting/connected
    if (this.socket && (this.socket.readyState === WebSocket.CONNECTING || this.socket.readyState === WebSocket.OPEN)) {
      return;
    }
    
    this.intentionallyClosed = false;
    connectionStatus.set(ConnectionStatus.CONNECTING);
    
    try {
      this.socket = new WebSocket(this.url);
      
      // Configure socket event handlers
      this.socket.onopen = this.handleOpen.bind(this);
      this.socket.onmessage = this.handleMessage.bind(this);
      this.socket.onclose = this.handleClose.bind(this);
      this.socket.onerror = this.handleError.bind(this);
      
      this.log('WebSocket connecting to:', this.url);
    } catch (error) {
      this.log('WebSocket connection error:', error);
      connectionStatus.set(ConnectionStatus.ERROR);
      this.scheduleReconnect();
    }
  }
  
  // Gracefully close the connection
  public disconnect(): void {
    this.intentionallyClosed = true;
    
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    connectionStatus.set(ConnectionStatus.DISCONNECTED);
    this.log('WebSocket disconnected by client');
  }
  
  // Send a message through the WebSocket
  public send(message: any): boolean {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.log('Cannot send message, socket is not open');
      return false;
    }
    
    try {
      const messageString = typeof message === 'string' ? message : JSON.stringify(message);
      this.socket.send(messageString);
      return true;
    } catch (error) {
      this.log('Error sending message:', error);
      return false;
    }
  }
  
  // Register event handler for specific message types
  public on(type: string, callback: (data?: any) => void): void {
    if (!messageHandlers[type]) {
      messageHandlers[type] = [];
    }
    messageHandlers[type].push(callback);
  }
  
  // Remove event handler
  public off(type: string, callback: (data: any) => void): void {
    if (messageHandlers[type]) {
      messageHandlers[type] = messageHandlers[type].filter(handler => handler !== callback);
    }
  }
  
  // Handle WebSocket open event
  private handleOpen(event: Event): void {
    connectionStatus.set(ConnectionStatus.CONNECTED);
    this.log('WebSocket connected');
  }
  
  // Handle WebSocket message event
  private handleMessage(event: MessageEvent): void {
    try {
      const message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
      
      // Update stores
      lastMessage.set(message);
      messageHistory.update(history => [...history, message]);
      
      // Call appropriate message handlers
      if (message.type && messageHandlers[message.type]) {
        messageHandlers[message.type].forEach(handler => {
          try {
            // Use data property which is what backend uses or fall back to payload
            handler(message.data || message.payload);
          } catch (handlerError) {
            this.log('Error in message handler:', handlerError);
          }
        });
      } else {
        this.log('No handler registered for message type:', message.type);
      }
      
      this.log('WebSocket message received:', message);
    } catch (error) {
      this.log('Error processing message:', error, event.data);
    }
  }
  
  // Handle WebSocket close event
  private handleClose(event: CloseEvent): void {
    this.socket = null;
    
    if (!this.intentionallyClosed) {
      connectionStatus.set(ConnectionStatus.DISCONNECTED);
      this.log('WebSocket connection closed. Code:', event.code, 'Reason:', event.reason);
      this.scheduleReconnect();
    }
  }
  
  // Handle WebSocket error event
  private handleError(event: Event): void {
    connectionStatus.set(ConnectionStatus.ERROR);
    this.log('WebSocket error:', event);
  }
  
  // Schedule a reconnection attempt with exponential backoff
  private scheduleReconnect(): void {
    if (this.intentionallyClosed) return;
    
    // Check if we've reached max attempts
    if (this.config.maxReconnectAttempts !== null && this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      this.log('Maximum reconnect attempts reached, giving up');
      return;
    }
    
    // Clear any existing reconnect timeout
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
    }
    
    // Calculate the backoff delay
    const reconnectDelay = Math.min(
      this.config.reconnectInterval * Math.pow(this.config.reconnectDecay, this.reconnectAttempts),
      this.config.maxReconnectInterval
    );
    
    this.reconnectAttempts++;
    reconnectCount.set(this.reconnectAttempts);
    isReconnecting.set(true);
    
    this.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${reconnectDelay}ms`);
    
    // Schedule the reconnect
    this.reconnectTimeout = window.setTimeout(() => {
      this.log(`Attempting to reconnect (${this.reconnectAttempts})`);
      this.connect();
    }, reconnectDelay);
  }
  
  // Utility logging function respecting debug config
  private log(...args: any[]): void {
    if (this.config.debug) {
      console.log('[WebSocketService]', ...args);
    }
  }
}

// Create WebSocket services for READ and WRITE operations
let wsBaseUrl = browser ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname}:8000` : 'ws://localhost:8000';

// For production, use relative URL
if (!import.meta.env.DEV && browser) {
  wsBaseUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;
}

export const recallWsService = new WebSocketService(`${wsBaseUrl}/ws/recall`, { debug: import.meta.env.DEV });
export const recordWsService = new WebSocketService(`${wsBaseUrl}/ws/record`, { debug: import.meta.env.DEV });

// Automatically connect in browser environment
if (browser) {
  setTimeout(() => {
    recallWsService.connect();
    recordWsService.connect();
  }, 0);
} 