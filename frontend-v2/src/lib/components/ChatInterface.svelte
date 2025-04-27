<script lang="ts">
  import { onMount, afterUpdate, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import { 
    addUserMessage, 
    addSystemMessage,
    messageInput,
    isLoading,
    fileAttachment,
    clearFileAttachment,
    conversations,
    activeAgentId,
    statusMessage
  } from '$lib/stores/chatStore';
  import { 
    activeAgent, 
    currentAgent, 
    currentConversation,
    addMessageToConversation
  } from '$lib/stores/agentsStore';
  import { darkMode } from '$lib/stores/themeStore';
  import { sendChatMessage, showConnectionStatus } from '$lib/stores/websocketStore';
  import ConnectionStatus from './ConnectionStatus.svelte';
  import StatusMessage from './StatusMessage.svelte';
  import FirstResponderAgent from './FirstResponderAgent.svelte';
  import NumberNinjaAgent from './NumberNinjaAgent.svelte';
  import PersephoneAgent from './PersephoneAgent.svelte';
  import LibrarianAgent from './LibrarianAgent.svelte';
  import ButterflyAgent from './ButterflyAgent.svelte';
  import SubmissionsAgent from './SubmissionsAgent.svelte';
  import FilesAgent from './FilesAgent.svelte';
  import { v4 as uuidv4 } from 'uuid';
  
  let messageInputElement: HTMLTextAreaElement;
  let messagesContainer: HTMLDivElement;
  let fileInput: HTMLInputElement;
  
  // Format agent names for display only, without changing the original agentId
  function getAgentDisplayName(agentId: string): string {
    switch(agentId) {
      case 'first_responder':
        return 'First Responder';
      case 'number_ninja':
        return 'Number Ninja';
      case 'persephone':
        return 'Persephone';
      case 'librarian':
        return 'Librarian';
      case 'butterfly':
        return 'Butterfly';
      case 'submissions':
        return 'Submissions';
      case 'files':
        return 'Files';
      default:
        return agentId.charAt(0).toUpperCase() + agentId.slice(1);
    }
  }
  
  // For autoresizing the textarea
  function resizeTextarea() {
    if (messageInputElement) {
      messageInputElement.style.height = 'auto';
      messageInputElement.style.height = `${messageInputElement.scrollHeight}px`;
    }
  }
  
  // For scrolling to bottom of messages
  function scrollToBottom() {
    if (messagesContainer) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  }
  
  // Auto-scroll on new messages
  $: if ($currentConversation) {
    scrollToBottom();
  }
  
  // Auto-resize input on value change
  $: if ($messageInput) {
    resizeTextarea();
  }
  
  // Lifecycle hooks
  onMount(() => {
    console.log('Chat interface mounted');
    resizeTextarea();
    scrollToBottom();
    
    // Focus input on mount
    if (messageInputElement) {
      messageInputElement.focus();
    }
  });
  
  afterUpdate(() => {
    scrollToBottom();
  });
  
  // Clean up event listeners on component unmount
  onDestroy(() => {
    // No event listeners to clean up
  });
  
  // Handle keyboard input
  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }
  
  // Handle sending messages
  async function sendMessage() {
    if (!$messageInput.trim() && !$fileAttachment) {
      return;
    }
    
    const message = $messageInput.trim();
    console.log('Sending message:', message);
    console.log('File attachment state:', $fileAttachment ? {
      id: $fileAttachment.id,
      name: $fileAttachment.name,
      type: $fileAttachment.type,
      size: $fileAttachment.size,
      hasFile: !!$fileAttachment.file
    } : 'No file attached');
    
    // Reset input
    $messageInput = '';
    resizeTextarea();
      
    // Get any file attachments
    const attachments = $fileAttachment ? [{
      id: $fileAttachment.id,
      name: $fileAttachment.name,
      type: $fileAttachment.type,
      size: $fileAttachment.size,
      file: $fileAttachment.file
    }] : [];
    
    // Generate a query ID for this message
    const queryId = uuidv4();
    
    // Create a user message directly - default to 'recall' operation
    // Individual agent components will override this when appropriate
    const userMessage = {
      id: uuidv4(),
      type: 'user',
      content: message,
      sender: 'User',
      agentId: $activeAgent,
      operationType: 'recall' as 'recall' | 'record', // Default to recall, agents can override
      timestamp: new Date(),
      attachments,
      queryId
    };
    
    // Add directly to the conversation history
    addMessageToConversation($activeAgent, userMessage);
      
    // Set loading state
    $isLoading = true;
    
    // Special handling for Butterfly agent with file attachments
    if ($activeAgent === 'butterfly' && $fileAttachment && $fileAttachment.file) {
      console.log('Butterfly agent with file attachment detected, handling file upload');
      
      // Removed status message for file upload
      const fileType = $fileAttachment.type.startsWith('image/') ? 'image' : 'video';
      
      try {
        // Upload the file using fetch
        // Must use the backend API server URL, not the frontend server origin
        const apiBaseUrl = 'http://localhost:8000';
        const userId = localStorage.getItem('userId') || 'user123';
        
        console.log(`Uploading file to ${apiBaseUrl}/social_media/upload`);
        
        const formData = new FormData();
        formData.append('file', $fileAttachment.file);
        formData.append('user_id', userId);
        
        const response = await fetch(`${apiBaseUrl}/social_media/upload`, {
          method: 'POST',
          body: formData
        });
        
        console.log('Response status:', response.status);
        const result = await response.json();
        console.log('Social media upload response:', result);
        
        if (!result.success) {
          console.error('File upload failed:', result.message);
          // Removed status message for file upload failure
          $isLoading = false;
          clearFileAttachment();
          return;
        }
        
        if (!result.file_ids || result.file_ids.length === 0) {
          console.error('File upload returned no file path');
          // Removed status message for no file path
          $isLoading = false;
          clearFileAttachment();
          return;
        }
        
        const filePath = result.file_ids[0];
        console.log('File uploaded successfully, path:', filePath);
        
        // Removed success status message
        
        // Now send the message with the attachment path
        const success = sendChatMessage(message, queryId, [], filePath, userMessage.operationType);
        
        if (!success) {
          statusMessage.set('Failed to send message. Please check your connection.');
          console.log('Set error status message: Failed to send message');
          $isLoading = false;
        }
      } catch (error: any) {
        console.error('Error uploading file:', error);
        // Removed error status message for file upload
        $isLoading = false;
      }
    } else {
      // Standard message sending for other agents
      const success = sendChatMessage(message, queryId, [], undefined, userMessage.operationType);
      
      if (!success) {
        statusMessage.set('Failed to send message. Please check your connection.');
        console.log('Set error status message: Failed to send message');
        $isLoading = false;
      }
    }
    
    // Clear file attachment after sending
    if ($fileAttachment) {
      console.log('Clearing file attachment after sending');
      clearFileAttachment();
    }
  }
  
  // Handle file selection
  function handleFileSelection(event: Event) {
    console.log('File selection event triggered');
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      console.log('File selected:', file.name, file.type, file.size);
      
      // Set file attachment
      clearFileAttachment();
      fileAttachment.set({
        id: uuidv4(),
        name: file.name,
        type: file.type,
        size: file.size,
        file: file
      });
      console.log('File attachment set successfully');
    } else {
      console.log('No file selected or file selection canceled');
    }
  }
  
  // Trigger file selection dialog
  function handleFileButtonClick() {
    console.log('File attachment button clicked');
    if (fileInput) {
      fileInput.click();
    }
  }
  
  // Toggle dark mode
  function toggleDarkMode() {
    darkMode.toggleTheme();
  }
  
  // Clear chat history
  function clearChat() {
    const confirmed = confirm('Are you sure you want to clear the chat history?');
    if (confirmed) {
      const agentId = $activeAgentId || $activeAgent;
      conversations.update(convs => {
        convs[agentId] = [];
        return convs;
      });
    }
  }
  
  // Remove selected file
  function removeSelectedFile() {
    console.log('Manually removing file attachment');
    clearFileAttachment();
  }
</script>

<div class="chat-interface" class:dark={$darkMode}>
  <!-- Invisible components for logic only -->
  <FirstResponderAgent />
  <NumberNinjaAgent />
  <PersephoneAgent />
  <LibrarianAgent />
  <ButterflyAgent />
  <SubmissionsAgent />
  <FilesAgent />
  
  <div class="header">
    <div class="connection-status-container">
      <ConnectionStatus />
    </div>
    
    <!-- Show conversation -->
    <div class="messages-container" bind:this={messagesContainer}>
      {#each $currentConversation as message (message.id)}
        {#if message.type === 'system'}
          <div class="message system">
            <div class="content">{@html message.content}</div>
            </div>
        {:else if message.type === 'user'}
          <div class="message user">
            <div class="content">{@html message.content}</div>
          </div>
        {:else if message.type === 'agent'}
          <div class="message agent" style={message.score ? `opacity: ${Math.max(0.4, message.score / 100)}` : ''}>
            {#if message.agentId && message.agentId !== 'system'}
              <div class="agent-name {message.agentId}">
                {#if message.sender && message.sender === message.agentId}
                  {getAgentDisplayName(message.agentId)}
                {:else if message.sender && message.sender.toLowerCase() === message.agentId}
                  {getAgentDisplayName(message.agentId)}
                {:else}
                  {message.sender || getAgentDisplayName(message.agentId)}
                {/if}
                <span class="score-dot" class:blinking={!message.score} class:score-100={message.score >= 90} class:score-0={message.score === 0} class:score-other={message.score > 0 && message.score < 90}></span>
              </div>
            {/if}
            <div class="content">{@html message.content}</div>
          </div>
        {/if}
      {/each}
    
    {#if $isLoading}
      <div class="message loading">
          <div class="loading-indicator">
        <div class="loading-dots">
              <span></span><span></span><span></span>
            </div>
        </div>
      </div>
    {/if}
  </div>
  
    <!-- File preview area -->
    {#if $fileAttachment}
      <div class="file-preview">
        <div class="file-info">
          <span class="file-name">{$fileAttachment.name}</span>
          <button class="remove-file-button" on:click={removeSelectedFile}>
          <i class="fas fa-times"></i>
        </button>
        </div>
      </div>
    {/if}
    
    <!-- Input area with StatusMessage positioned above it -->
    <div class="input-container">
      <StatusMessage />
      
      <div class="chat-input-container">
        <button class="icon-button attach-button" on:click={handleFileButtonClick}>
          <i class="fas fa-paperclip"></i>
        </button>
        
        <textarea 
          bind:this={messageInputElement}
          bind:value={$messageInput} 
          placeholder="Type your message..." 
          on:keydown={handleKeyDown}
          rows="1"
        ></textarea>
        
        <button 
          class="icon-button send-button" 
          disabled={!$messageInput.trim() && !$fileAttachment} 
          on:click={sendMessage}
        >
          <i class="fas fa-paper-plane"></i>
        </button>
        
        <button class="icon-button clear-button" on:click={clearChat}>
          <i class="fas fa-trash"></i>
        </button>
      </div>
    </div>
    
    <!-- Add theme toggle button fixed to the bottom of the screen -->
    <button class="theme-toggle-button" on:click={toggleDarkMode}>
      <i class="fas {$darkMode ? 'fa-sun' : 'fa-moon'}"></i>
    </button>
    
    <!-- Hidden file input -->
    <input 
      type="file" 
      bind:this={fileInput}
      on:change={handleFileSelection}
      style="display: none;"
    />
  </div>
</div>

<style>
  .chat-interface {
    display: flex;
    flex-direction: column;
    height: 100%;
    background-color: var(--background-color);
    color: var(--text-color);
  }

  .chat-interface.dark {
    --background-color: #1a1a1a;
    --text-color: #f0f0f0;
    --border-color: #333;
    --user-msg-bg: #2a2a2a;
    --agent-msg-bg: #333;
    --input-bg: #2a2a2a;
    --hover-color: #444;
  }

  .header {
    display: flex;
    flex-direction: column;
    flex-grow: 1;
    overflow: hidden;
    padding: 0.5rem;
  }

  .connection-status-container {
    margin-bottom: 0.5rem;
  }
  
  .messages-container {
    flex-grow: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .message {
    padding: 0.8rem;
    border-radius: 0.5rem;
    max-width: 80%;
    word-break: break-word;
    font-size: 1rem;
    line-height: 1.5;
  }

  .message.user {
    align-self: flex-end;
    background-color: var(--user-msg-bg, #e6f2ff);
    border-bottom-right-radius: 0;
  }

  .message.agent {
    align-self: flex-start;
    background-color: var(--agent-msg-bg, #f5f5f5);
    border-bottom-left-radius: 0;
  }

  .agent-name {
    font-size: 0.9rem;
    font-weight: bold;
    margin-bottom: 0.3rem;
    display: flex;
    align-items: center;
  }

  .message .content {
    font-size: 1rem;
    line-height: 1.5;
  }

  .score-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #ccc;
    margin-left: 0.5rem;
  }
  
  .score-dot.blinking {
    background-color: #FFC107; /* Yellow */
    animation: blink 1s infinite;
  }
  
  .score-dot.score-100 {
    background-color: #4CAF50; /* Green */
    animation: none;
  }
  
  .score-dot.score-0 {
    background-color: #F44336; /* Red */
    animation: none;
  }
  
  .score-dot.score-other {
    background-color: #FFC107; /* Yellow */
    animation: none;
  }
  
  @keyframes blink {
    0% { opacity: 1; }
    50% { opacity: 0.3; }
    100% { opacity: 1; }
  }
  
  .loading-indicator {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0.5rem;
  }

  .loading-dots {
    display: flex;
    gap: 4px;
  }

  .loading-dots span {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: var(--text-color, #333);
    animation: bounce 1.4s infinite ease-in-out both;
  }

  .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
  .loading-dots span:nth-child(2) { animation-delay: -0.16s; }

  @keyframes bounce {
    0%, 80%, 100% { transform: scale(0); }
    40% { transform: scale(1); }
  }

  .file-preview {
    background-color: var(--agent-msg-bg, #f5f5f5);
    border-radius: 0.5rem;
    padding: 0.5rem;
    margin-bottom: 0.5rem;
    }
  
  .file-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .file-name {
    font-size: 0.9rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .remove-file-button {
    background: none;
    border: none;
    color: var(--text-color, #333);
    cursor: pointer;
    padding: 0.25rem;
  }

  .input-container {
    position: relative;
    width: 100%;
    margin-bottom: 0.75rem;
  }

  .chat-input-container {
    display: flex;
    align-items: flex-end;
    gap: 0.75rem;
    padding: 0.75rem;
    background-color: var(--input-bg, #fff);
    border-radius: 0.5rem;
    border: 1px solid var(--border-color, #e0e0e0);
    min-height: 60px;
  }

  textarea {
    flex-grow: 1;
    resize: none;
    border: none;
    background: none;
    outline: none;
    color: var(--text-color);
    font-family: inherit;
    font-size: 1rem;
    padding: 0.5rem;
    min-height: 36px;
    max-height: 150px;
    overflow-y: auto;
    border-radius: 0.25rem;
    line-height: 1.5;
  }
  
  textarea:focus {
    outline: 1px solid #444;
    background-color: var(--hover-color, #f9f9f9);
    --tw-ring-color: #444 !important;
    --tw-ring-offset-shadow: 0 0 #0000 !important;
    --tw-ring-shadow: 0 0 #0000 !important;
    box-shadow: 0 0 0 1px #444 !important;
  }

  .icon-button {
    background: none;
    border: none;
    color: var(--text-color, #555);
    cursor: pointer;
    padding: 0.5rem;
    border-radius: 0.25rem;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background-color 0.2s;
    margin-bottom: 0.25rem;
  }

  .icon-button:hover {
    background-color: var(--hover-color, #f0f0f0);
  }
  
  .icon-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .icon-button i {
    font-size: 1.2rem;
  }
  
  /* Agent specific colors */
  .first_responder {
    color: var(--agent-responder-color, #10b981);
  }

  .number_ninja {
    color: var(--agent-ninja-color, #8b5cf6);
  }
  
  .persephone {
    color: var(--agent-persephone-color, #ec4899);
  }
  
  .librarian {
    color: var(--agent-librarian-color, #f59e0b);
  }
  
  .butterfly {
    color: var(--agent-butterfly-color, #06b6d4);
  }
  
  .system {
    color: var(--agent-system-color, #6b7280);
  }

  /* Move theme toggle button to fixed position at bottom of screen */
  .theme-toggle-button {
    position: fixed;
    bottom: 1rem;
    left: 1rem;
    background: none;
    border: none;
    color: var(--text-color, #555);
    cursor: pointer;
    padding: 0.5rem;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background-color 0.2s;
    z-index: 10;
    background-color: var(--background-color, white);
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
  }
  
  .theme-toggle-button:hover {
    background-color: var(--hover-color, #f0f0f0);
  }
  
  .theme-toggle-button i {
    font-size: 1.2rem;
  }
  
  /* Remove theme button from chat input container */
  .chat-input-container .theme-toggle-button {
    display: none;
  }
  
  /* Standardize welcome message styling */
  :global(.welcome-message) {
    padding: 0.5rem;
    margin-bottom: 0.5rem;
    font-size: 1rem;
  }

  :global(.welcome-message h3) {
    font-size: 1rem;
    margin: 0 0 0.5rem 0;
    color: var(--text-color, #333333);
  }
  
  :global(.welcome-message p) {
    font-size: 1rem;
    margin: 0 0 0.5rem 0;
    line-height: 1.5;
  }
  
  :global(.template-buttons) {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 0.5rem 0;
  }
  
  :global(.template-button) {
    background-color: var(--background-color, white);
    border: 1px solid var(--border-color, #e0e0e0);
    border-radius: 0.25rem;
    padding: 0.5rem 0.75rem;
    font-size: 0.9rem;
    cursor: pointer;
    transition: all 0.2s;
    color: var(--text-color, #333333);
  }

  :global(.template-button:hover) {
    background-color: var(--hover-color, #f0f0f0);
    border-color: var(--agent-responder-color, #10b981);
  }
</style> 