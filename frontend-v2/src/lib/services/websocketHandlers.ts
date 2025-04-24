import { get } from 'svelte/store';
import { 
  addAgentMessage, 
  addSystemMessage, 
  addUserMessage, 
  isLoading, 
  statusMessage, 
  updateMessageScore
} from '$lib/stores/chatStore';
import { activeAgent, addMessageToConversation, conversationHistory } from '$lib/stores/agentsStore';
import { updateUserFacts } from '$lib/stores/userFactsStore';
import { MessageType } from '$lib/services/websocketService';

/**
 * Initialize WebSocket handlers for various message types
 */
export function initializeWebSocketHandlers(): void {
  console.log('Initializing WebSocket handlers');
  setupMessageHandlers();
}

/**
 * Register message handlers for different WebSocket message types
 */
function setupMessageHandlers() {
  if (typeof window === 'undefined') return; // Skip on server
  
  // Register handlers for recall service
  if (window.recallWsService) {
    window.recallWsService.on('agent_response', handleAgentResponse);
    window.recallWsService.on('quality_updates', handleQualityUpdates);
    window.recallWsService.on('status_update', handleStatusUpdate);
    window.recallWsService.on('user_facts_response', handleUserFactsResponse);
    window.recallWsService.on('files_response', handleFilesResponse);
  }
  
  // Register handlers for record service
  if (window.recordWsService) {
    window.recordWsService.on('record_response', handleRecordResponse);
    window.recordWsService.on('upload_progress', handleUploadProgress);
    window.recordWsService.on('user_facts_update', handleUserFactsUpdate);
  }
}

/**
 * Handle agent response messages
 */
function handleAgentResponse(data: any): void {
  console.log('Handling agent response:', data);
  if (!data) return;
  
  // Update loading state
  isLoading.set(false);
  statusMessage.set('');
  
  // Check if this is a First Responder message specifically
  if (data.agent_name === 'first_responder') {
    console.log('Processing First Responder message');
    handleFirstResponderResponse(data);
    return;
  }
  
  // Handle other agent responses
  if (data.answer) {
    console.log('Processing standard agent response for:', data.agent_name);
    // Create a message with the agent's name and response
    const message = {
      id: data.id || `msg_${Date.now()}`,
      type: 'agent',
      content: data.answer,
      sender: data.display_name || data.agent_name,
      agentId: data.agent_name,
      timestamp: new Date(),
      queryId: data.query_id
    };
    
    // Add to the conversation history for the current agent
    const currentAgentId = get(activeAgent);
    console.log('Adding message to conversation for agent:', currentAgentId);
    addMessageToConversation(currentAgentId, message);
    
    // Also log the current conversation after adding message
    const convHistory = get(conversationHistory);
    const conversation = convHistory[currentAgentId] || [];
    console.log(`Current conversation for ${currentAgentId} has ${conversation.length} messages`);
    } 
}

/**
 * Handle First Responder agent responses
 */
function handleFirstResponderResponse(data: any): void {
  console.log('Processing First Responder message with data:', data);
  if (!data || !data.answer) return;
  
  // Create a message for the First Responder
  const message = {
    id: data.id || `fr_${Date.now()}`,
    type: 'agent',
    content: data.answer,
    sender: 'First Responder',
    agentId: 'first_responder',
    timestamp: new Date(),
    queryId: data.query_id
  };
      
  // Add to the conversation history for the current agent
  const currentAgentId = get(activeAgent);
  console.log('Adding First Responder message to conversation for agent:', currentAgentId);
  addMessageToConversation(currentAgentId, message);
  
  // If we're in Group Chat, also add to first_responder conversation
  if (currentAgentId === 'all') {
    console.log('Also adding message to first_responder conversation');
    addMessageToConversation('first_responder', message);
  }
  
  // Log the current conversation after adding the message
  const convHistory = get(conversationHistory);
  const conversation = convHistory[currentAgentId] || [];
  console.log(`Current conversation for ${currentAgentId} now has ${conversation.length} messages`);
      }

/**
 * Handle status update messages
 */
function handleStatusUpdate(data: any): void {
  if (!data || !data.message) return;
  
  console.log('Handling status update:', data.message);
  
  // Update status message
  statusMessage.set(data.message);
  
  // If this is a final status, clear it after a short delay
  if (data.is_final) {
    setTimeout(() => {
      statusMessage.set('');
      isLoading.set(false); // Also update loading state when completed
    }, 2000);
  } else {
    // If not final, ensure loading is set to true to show the loading indicator
    isLoading.set(true);
  }
}

/**
 * Handle quality updates
 */
function handleQualityUpdates(data: any): void {
  if (!data || !Array.isArray(data)) return;
  
  console.log('Processing quality updates:', data);
  
  data.forEach(update => {
    if (update.agent_name && update.response_score !== undefined) {
      const convHistory = get(conversationHistory);
      const currentAgentId = get(activeAgent);
      
      // Get the conversation for the current agent
      const conversation = convHistory[currentAgentId] || [];
      
      // Find the last message from this agent
      const agentMessages = conversation.filter(
        msg => msg.type === 'agent' && msg.agentId === update.agent_name
      );
      
      if (agentMessages.length > 0) {
        // Get the last message from this agent
        const lastMessage = agentMessages[agentMessages.length - 1];
        
        console.log(`Updating score for ${update.agent_name}: ${update.response_score}`, lastMessage);
        
        // Create a new message with the updated score
        const updatedMessage = {
          ...lastMessage,
          score: update.response_score
        };
        
        // Update the conversation with the new message
        addMessageToConversation(currentAgentId, updatedMessage, true); // true = replace existing message
      }
    }
  });
}

/**
 * Handle user facts responses from WebSocket
 */
function handleUserFactsResponse(data: any): void {
  if (!data) return;
  
  if (data.success && data.facts) {
    // Update the user facts store
    updateUserFacts(data.facts);
  } else if (!data.success) {
    console.error('User facts response error:', data.message);
  }
}

/**
 * Handle file responses from WebSocket
 */
function handleFilesResponse(data: any): void {
  if (!data) return;
  
  // This would handle file list responses, file deletion confirmations, etc.
  console.log('Files response:', data);
}

/**
 * Handle record response messages
 */
function handleRecordResponse(data: any): void {
  if (!data) return;
  
  // Update loading state
  isLoading.set(false);
  
  if (data.success) {
    // Add a system message confirming the record operation
    addSystemMessage(data.message || 'Record operation completed successfully');
  } else {
    // Add an error message
    addSystemMessage(`Error: ${data.message || 'Record operation failed'}`);
  }
}

/**
 * Handle upload progress
 */
function handleUploadProgress(data: any): void {
  if (!data || typeof data.progress !== 'number') return;
  
  // Update status message with progress information
  statusMessage.set(`Uploading: ${Math.round(data.progress)}%`);
}

/**
 * Handle user facts updates
 */
function handleUserFactsUpdate(data: any): void {
  if (!data) return;
  
  // Trigger a refresh of user facts
  document.dispatchEvent(new CustomEvent('refresh-user-facts'));
    }

// Declare global interfaces
declare global {
  interface Window {
    recallWsService: any;
    recordWsService: any;
  }
} 