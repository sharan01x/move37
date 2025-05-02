<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import { 
    addSystemMessage,
    isLoading,
    registerMessageHandler,
    type MessageHandler
  } from '$lib/stores/chatStore';
  import { 
    activeAgent, 
    setActiveAgent,
  } from '$lib/stores/agentsStore';
  import { sendChatMessage } from '$lib/stores/websocketStore';
  import { get } from 'svelte/store';
  import { v4 as uuidv4 } from 'uuid';
  
  // API endpoint - needed for backend API calls
  const apiPort = browser ? (import.meta.env.VITE_API_PORT || window.location.port || '8000') : '8000';
  const apiBaseUrl = browser ? `${window.location.protocol}//${window.location.hostname}:${apiPort}` : 'http://localhost:8000';
  
  // File management state
  let files: any[] = [];
  let isFileLoading = false;
  let selectedFiles = new Set<string>();
  
  // Modal state for text content editing
  let showModal = false;
  let modalFile: any = null;
  let textContent = '';
  let isTextContentChanged = false;
  
  // WebSocket connections
  let recallWsConnection: WebSocket | null = null;
  let recordWsConnection: WebSocket | null = null;
  
  // Check if this is the active agent
  $: isActive = $activeAgent === 'files';
  
  // Watch for when Files becomes active
  $: if (isActive && browser) {
    console.log('Files agent active, loading file list');
    loadFileList();
  }
  
  // Helper function to activate this agent
  function activateFiles() {
    setActiveAgent('files');
  }
  
  // Create a message handler to intercept message sending
  const filesMessageHandler: MessageHandler = {
    handleMessage: async (message: string, attachments: any[] = []) => {
      // Since we're completely replacing the chat interface, we only need
      // minimal implementation to avoid errors
      console.log('Files agent intercepted message, ignoring as chat is disabled');
      addSystemMessage('Chat is disabled in File Management mode.');
      return true; // Message handled (suppressed)
    }
  };
  
  // Register the message handler when the agent is active
  $: if (isActive) {
    console.log('Registering Files message handler');
    registerMessageHandler('files', filesMessageHandler);
  }
  
  // Connect to WebSockets
  function connectWebSockets() {
    connectRecallWebSocket();
    connectRecordWebSocket();
  }
  
  // Connect to recall WebSocket for READ operations (list files)
  function connectRecallWebSocket() {
    if (recallWsConnection) {
      return;
    }
    
    const wsUrl = `${apiBaseUrl.replace(/^http/, 'ws')}/ws/recall`;
    console.log('Connecting to Recall WebSocket:', wsUrl);
    
    recallWsConnection = new WebSocket(wsUrl);
    
    recallWsConnection.onopen = () => {
      console.log('Recall WebSocket connection established');
      // Load files if this agent is active
      if (isActive) {
        loadFileList();
      }
    };
    
    recallWsConnection.onclose = () => {
      console.log('Recall WebSocket connection closed');
      recallWsConnection = null;
      // Attempt to reconnect after delay
      setTimeout(connectRecallWebSocket, 3000);
    };
    
    recallWsConnection.onerror = (error) => {
      console.error('Recall WebSocket error:', error);
    };
    
    recallWsConnection.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log('Received Recall WebSocket message:', message);
        
        if (!message || !message.type) {
          console.warn('Invalid recall message format:', message);
          return;
        }
        
        switch (message.type) {
          case 'files_response':
            if (message.data) {
              console.log('Handling files response:', message.data);
              handleFilesResponse(message.data);
            }
            break;
          case 'status_update':
            if (message.data && message.data.message) {
              addSystemMessage(message.data.message);
            }
            break;
          default:
            console.log('Unhandled recall message type:', message.type);
        }
      } catch (error) {
        console.error('Error processing Recall WebSocket message:', error);
      }
    };
  }
  
  // Connect to record WebSocket for WRITE operations (delete files, update content)
  function connectRecordWebSocket() {
    if (recordWsConnection) {
      return;
    }
    
    const wsUrl = `${apiBaseUrl.replace(/^http/, 'ws')}/ws/record`;
    console.log('Connecting to Record WebSocket:', wsUrl);
    
    recordWsConnection = new WebSocket(wsUrl);
    
    recordWsConnection.onopen = () => {
      console.log('Record WebSocket connection established');
    };
    
    recordWsConnection.onclose = () => {
      console.log('Record WebSocket connection closed');
      recordWsConnection = null;
      // Attempt to reconnect after delay
      setTimeout(connectRecordWebSocket, 3000);
    };
    
    recordWsConnection.onerror = (error) => {
      console.error('Record WebSocket error:', error);
    };
    
    recordWsConnection.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log('Received Record WebSocket message:', message);
        
        if (!message || !message.type) {
          console.warn('Invalid record message format:', message);
          return;
        }
        
        switch (message.type) {
          case 'files_response':
            if (message.data) {
              console.log('Handling files response:', message.data);
              handleFilesResponse(message.data);
            }
            break;
          case 'record_response':
            if (message.data) {
              console.log('Handling record response:', message.data);
              handleRecordResponse(message.data);
            }
            break;
          case 'status_update':
            if (message.data && message.data.message) {
              addSystemMessage(message.data.message);
            }
            break;
          default:
            console.log('Unhandled record message type:', message.type);
        }
      } catch (error) {
        console.error('Error processing Record WebSocket message:', error);
      }
    };
  }
  
  // Handle files response from WebSocket
  function handleFilesResponse(response: any) {
    isFileLoading = false;
    
    if (response.success) {
      // Check if this is a list response with files array
      if (response.files && Array.isArray(response.files)) {
        console.log('File list received, displaying', response.files.length, 'files');
        files = response.files;
        selectedFiles = new Set();
      } 
      // Check if this is a delete response
      else if (response.message && response.message.includes('deleted')) {
        console.log('File deletion successful');
        addSystemMessage(response.message || 'File operation completed successfully');
        // Refresh the file list after deletion
        loadFileList();
      }
      // Other successful file operations
      else {
        addSystemMessage(response.message || 'File operation completed successfully');
      }
    } else {
      // Handle failed file operations
      const errorMsg = response.message || 'Error processing file operation';
      console.error('File operation error:', errorMsg);
      addSystemMessage(`Error: ${errorMsg}`);
    }
  }
  
  // Handle record operation responses
  function handleRecordResponse(response: any) {
    if (response.file_id) {
      // This is a file text content update response
      if (response.success) {
        addSystemMessage(response.message || 'File content updated successfully.');
        // Refresh the file list to show updated status
        loadFileList();
        // Close the edit modal
        closeModal();
      } else {
        addSystemMessage(`Error: ${response.message || 'Failed to update file content.'}`);
      }
    } else {
      // Other record responses
      addSystemMessage(response.message || (response.success ? 'Operation successful' : 'Operation failed'));
    }
  }
  
  // Load file list via WebSocket
  function loadFileList() {
    if (!browser) return;
    
    // Get userId from localStorage
    const userId = browser ? localStorage.getItem('userId') || 'user123' : 'user123';
    
    // Ensure recall WebSocket is connected
    if (!recallWsConnection || recallWsConnection.readyState !== WebSocket.OPEN) {
      connectRecallWebSocket();
      setTimeout(loadFileList, 1000); // Try again after connection is established
      return;
    }
    
    try {
      isFileLoading = true;
      addSystemMessage('Loading files...');
      
      // Create a unique ID for this request
      const requestId = uuidv4();
      
      // Send the request through WebSocket
      recallWsConnection.send(JSON.stringify({
        type: "files_list",
        request_id: requestId,
        data: {
          user_id: userId
        }
      }));
      
      console.log('Sent file list request via WebSocket');
    } catch (error) {
      console.error('Error loading files via WebSocket:', error);
      addSystemMessage('Error loading files. Please try again.');
      isFileLoading = false;
    }
  }
  
  // Handle file upload - uses REST API
  async function handleFilesUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    
    const filesArray = Array.from(input.files);
    const userId = browser ? localStorage.getItem('userId') || 'user123' : 'user123';
    
    try {
      addSystemMessage(`Uploading ${filesArray.length} file(s)...`);
      
      const formData = new FormData();
      filesArray.forEach(file => {
        console.log('Uploading file:', file.name, 'MIME type:', file.type);
        formData.append('files', file);
      });
      formData.append('user_id', userId);
      
      const response = await fetch(`${apiBaseUrl}/files/upload`, {
        method: 'POST',
        body: formData
      });
      
      const result = await response.json();
      if (result.success) {
        // Clear the file input
        input.value = '';
        // Refresh the file list
        loadFileList();
        // Show success message
        addSystemMessage(`Successfully uploaded ${result.file_ids.length} file(s).`);
      } else {
        // Handle file conflicts
        if (result.message && result.message.includes('file already exists')) {
          const shouldOverwrite = confirm('Some files already exist. Would you like to overwrite them?');
          if (shouldOverwrite) {
            // Retry upload with overwrite flag
            formData.append('overwrite', 'true');
            const retryResponse = await fetch(`${apiBaseUrl}/files/upload`, {
              method: 'POST',
              body: formData
            });
            const retryResult = await retryResponse.json();
            if (retryResult.success) {
              addSystemMessage(`Successfully uploaded ${retryResult.file_ids.length} file(s).`);
              loadFileList();
            }
          } else {
            addSystemMessage('File upload cancelled. Existing files were not overwritten.');
          }
        } else {
          addSystemMessage(`Error uploading files: ${result.message}`);
        }
      }
    } catch (error: any) {
      console.error('Error uploading files:', error);
      addSystemMessage(`Error uploading files: ${error.message || 'Unknown error'}`);
    }
  }
  
  // Delete a file via WebSocket
  function deleteFile(fileId: string) {
    // Remove the confirmation dialog
    const userId = browser ? localStorage.getItem('userId') || 'user123' : 'user123';
    
    // Ensure record WebSocket is connected
    if (!recordWsConnection || recordWsConnection.readyState !== WebSocket.OPEN) {
      connectRecordWebSocket();
      setTimeout(() => deleteFile(fileId), 1000); // Try again after connection is established
      return;
    }
    
    try {
      addSystemMessage('Deleting file...');
      
      // Create a unique ID for this request
      const requestId = uuidv4();
      
      // Send the delete request through WebSocket
      recordWsConnection.send(JSON.stringify({
        type: "files_delete",
        request_id: requestId,
        data: {
          user_id: userId,
          file_id: fileId
        }
      }));
      
      console.log('Sent file deletion request via WebSocket');
    } catch (error: any) {
      console.error('Error deleting file via WebSocket:', error);
      addSystemMessage(`Error deleting file: ${error.message || 'Unknown error'}`);
    }
  }
  
  // Delete selected files
  function deleteSelectedFiles() {
    if (selectedFiles.size === 0) return;
    
    // Delete each selected file
    selectedFiles.forEach(fileId => {
      deleteFile(fileId);
    });
  }
  
  // Toggle file selection
  function toggleFileSelection(fileId: string) {
    if (selectedFiles.has(fileId)) {
      selectedFiles.delete(fileId);
    } else {
      selectedFiles.add(fileId);
    }
    selectedFiles = selectedFiles; // Trigger reactivity
  }
  
  // Open text content modal
  function openModal(file: any) {
    if (!file.text_content) {
      addSystemMessage('No text content available for this file.');
      return;
    }
    
    modalFile = file;
    textContent = file.text_content || '';
    isTextContentChanged = false;
    showModal = true;
  }
  
  // Close text content modal
  function closeModal() {
    // Remove confirmation dialog for unsaved changes
    showModal = false;
    modalFile = null;
    textContent = '';
    isTextContentChanged = false;
  }
  
  // Handle text content change
  function handleTextContentChange(event: Event) {
    const textarea = event.target as HTMLTextAreaElement;
    textContent = textarea.value;
    isTextContentChanged = modalFile && textContent !== modalFile.text_content;
  }
  
  // Save text content
  async function saveTextContent() {
    if (!modalFile) return;
    
    const userId = browser ? localStorage.getItem('userId') || 'user123' : 'user123';
    
    // Ensure record WebSocket is connected
    if (!recordWsConnection || recordWsConnection.readyState !== WebSocket.OPEN) {
      connectRecordWebSocket();
      setTimeout(saveTextContent, 1000); // Try again after connection is established
      return;
    }
    
    try {
      addSystemMessage('Updating file content...');
      
      // Prepare the message to send
      const message = {
        type: "record_update_text",
        data: {
          file_id: modalFile.id,
          user_id: userId,
          text_content: textContent
        }
      };
      
      // Send the update message via WebSocket
      recordWsConnection.send(JSON.stringify(message));
      
      console.log('Sent file text content update request via Record WebSocket');
    } catch (error: any) {
      console.error('Error updating file content:', error);
      addSystemMessage(`Error updating file content: ${error.message || 'Unknown error'}`);
    }
  }
  
  // Helper functions
  function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
  
  function getFileIcon(fileType: string, fileName: string): string {
    // First check by file extension
    if (fileName) {
      const extension = fileName.split('.').pop()?.toLowerCase() || '';
      const extensionIconMap: {[key: string]: string} = {
        'pdf': 'fas fa-file-pdf',
        'doc': 'fas fa-file-word',
        'docx': 'fas fa-file-word',
        'csv': 'fas fa-file-csv',
        'json': 'fas fa-file-code',
        'md': 'fas fa-file-code',
        'txt': 'fas fa-file-alt',
        'text': 'fas fa-file-alt'
      };
      
      if (extension in extensionIconMap) {
        return extensionIconMap[extension];
      }
    }
    
    // Fallback to MIME type
    const mimeIconMap: {[key: string]: string} = {
      'text/plain': 'fas fa-file-alt',
      'application/pdf': 'fas fa-file-pdf',
      'application/msword': 'fas fa-file-word',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'fas fa-file-word',
      'text/csv': 'fas fa-file-csv',
      'application/json': 'fas fa-file-code',
      'text/markdown': 'fas fa-file-code',
      'text/x-markdown': 'fas fa-file-code'
    };
    
    return fileType in mimeIconMap ? mimeIconMap[fileType] : 'fas fa-file';
  }
  
  function formatDateTime(dateStr: string): string {
    // Format date to a more readable format
    const date = new Date(dateStr);
    const day = date.getDate().toString().padStart(2, '0');
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const month = monthNames[date.getMonth()];
    const year = date.getFullYear();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    
    return `${day} ${month} ${year} ${hours}:${minutes}`;
  }
  
  // Initialize WebSockets on mount
  onMount(() => {
    if (browser) {
      console.log('Files agent component mounted');
      connectWebSockets();
      
      // Load files if this agent is already active
      if (isActive) {
        loadFileList();
      }
    }
  });
  
  // Clean up on destroy
  onDestroy(() => {
    if (recallWsConnection) {
      recallWsConnection.close();
    }
    if (recordWsConnection) {
      recordWsConnection.close();
    }
  });
</script>

<style>
  .file-management {
    display: flex;
    flex-direction: column;
    height: 100%;
    width: 100%;
    overflow: hidden;
    background-color: var(--background-color, #f5f7f9);
    color: var(--text-color, #333);
  }
  
  .file-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    background-color: var(--card-background, #fff);
    border-bottom: 1px solid var(--border-color, #e0e4e8);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  }
  
  .header-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--primary-text, #333);
  }
  
  .file-actions {
    display: flex;
    gap: 0.75rem;
  }
  
  .file-action-button {
    padding: 0.5rem 1rem;
    border-radius: 4px;
    background-color: var(--primary-color, #4a69bd);
    color: white;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    font-weight: 500;
    transition: background-color 0.2s ease;
  }
  
  .file-action-button:hover {
    background-color: var(--primary-hover, #3a5aad);
  }
  
  .file-action-button:disabled {
    background-color: var(--disabled-color, #cbd5e0);
    cursor: not-allowed;
  }
  
  .file-action-button.secondary {
    background-color: var(--secondary-color, #718096);
  }
  
  .file-action-button.secondary:hover {
    background-color: var(--secondary-hover, #5a6780);
  }
  
  .file-action-button.danger {
    background-color: var(--danger-color, #e53e3e);
  }
  
  .file-action-button.danger:hover {
    background-color: var(--danger-hover, #c53030);
  }
  
  .file-list-container {
    flex: 1;
    overflow-y: auto;
    padding: 1rem 1.5rem;
  }
  
  .file-upload-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    border: 2px dashed var(--border-color, #e0e4e8);
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1.5rem;
    cursor: pointer;
    background-color: var(--drop-area-background, rgba(74, 105, 189, 0.05));
    transition: all 0.2s ease;
  }
  
  .file-upload-container:hover,
  .file-upload-container.drag-over {
    border-color: var(--primary-color, #4a69bd);
    background-color: var(--drop-area-hover, rgba(74, 105, 189, 0.1));
  }
  
  .file-upload-icon {
    font-size: 1.75rem;
    color: var(--icon-color, #718096);
    margin-bottom: 0.75rem;
  }
  
  .file-upload-text {
    text-align: center;
    font-weight: 500;
    margin-bottom: 0.5rem;
    color: var(--primary-text, #333);
  }
  
  .file-upload-hint {
    font-size: 0.875rem;
    color: var(--hint-text, #718096);
    text-align: center;
  }
  
  .file-item {
    display: flex;
    align-items: center;
    padding: 0.75rem 1rem;
    border-radius: 6px;
    margin-bottom: 0.75rem;
    background-color: var(--card-background, #fff);
    border: 1px solid var(--border-color, #e0e4e8);
    transition: all 0.2s ease;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  }
  
  .file-item:hover {
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.08);
    background-color: var(--card-hover, #f8fafc);
  }
  
  .file-item.selected {
    background-color: var(--selected-item, rgba(74, 105, 189, 0.1));
    border-color: var(--selected-border, rgba(74, 105, 189, 0.3));
  }
  
  .file-checkbox {
    margin-right: 0.75rem;
  }
  
  .file-icon {
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 4px;
    background-color: var(--icon-background, #f1f5f9);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 1rem;
  }
  
  .file-icon i {
    font-size: 1.25rem;
    color: var(--icon-color, #718096);
  }
  
  .file-info {
    flex: 1;
    min-width: 0;
  }
  
  .file-name {
    font-weight: 500;
    margin-bottom: 0.25rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--primary-text, #333);
  }
  
  .file-details {
    font-size: 0.75rem;
    color: var(--secondary-text, #718096);
  }
  
  .file-status {
    margin: 0 1rem;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.75rem;
    text-transform: capitalize;
    font-weight: 500;
  }
  
  .file-status.pending {
    background-color: var(--pending-background, rgba(237, 137, 54, 0.1));
    color: var(--pending-text, #ed8936);
  }
  
  .file-status.processing {
    background-color: var(--processing-background, rgba(66, 153, 225, 0.1));
    color: var(--processing-text, #4299e1);
  }
  
  .file-status.complete {
    background-color: var(--complete-background, rgba(72, 187, 120, 0.1));
    color: var(--complete-text, #48bb78);
  }
  
  .file-status.error {
    background-color: var(--error-background, rgba(229, 62, 62, 0.1));
    color: var(--error-text, #e53e3e);
  }
  
  .file-status.transcribed {
    background-color: var(--transcribed-background, rgba(102, 126, 234, 0.1));
    color: var(--transcribed-text, #667eea);
  }
  
  .file-item-actions {
    display: flex;
    gap: 0.5rem;
  }
  
  .file-item-button {
    width: 2rem;
    height: 2rem;
    border-radius: 4px;
    background-color: transparent;
    border: 1px solid var(--border-color, #e0e4e8);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: var(--icon-color, #718096);
    transition: all 0.2s ease;
  }
  
  .file-item-button:hover {
    background-color: var(--button-hover, #f1f5f9);
  }
  
  .file-item-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .file-item-button.delete:hover {
    background-color: var(--danger-color, #e53e3e);
    color: white;
    border-color: var(--danger-color, #e53e3e);
  }
  
  /* Modal styles */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    backdrop-filter: blur(2px);
  }
  
  .modal {
    background-color: var(--modal-background, white);
    border-radius: 8px;
    width: 80%;
    max-width: 800px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
    border: 1px solid var(--border-color, #e0e4e8);
  }
  
  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid var(--border-color, #e0e4e8);
  }
  
  .modal-title {
    font-weight: 600;
    font-size: 1.25rem;
    color: var(--primary-text, #333);
  }
  
  .modal-close {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 1.5rem;
    color: var(--icon-color, #718096);
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: 4px;
    transition: background-color 0.2s ease;
  }
  
  .modal-close:hover {
    background-color: var(--button-hover, #f1f5f9);
  }
  
  .modal-body {
    padding: 1.5rem;
    overflow-y: auto;
    flex: 1;
  }
  
  .modal-textarea {
    width: 100%;
    min-height: 300px;
    padding: 0.75rem;
    border: 1px solid var(--border-color, #e0e4e8);
    border-radius: 4px;
    resize: vertical;
    font-family: inherit;
    font-size: 0.875rem;
    line-height: 1.6;
  }
  
  .modal-footer {
    display: flex;
    justify-content: flex-end;
    padding: 1rem 1.5rem;
    border-top: 1px solid var(--border-color, #e0e4e8);
    gap: 0.75rem;
  }
  
  /* Empty state */
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    text-align: center;
  }
  
  .empty-icon {
    font-size: 3rem;
    color: var(--icon-color, #718096);
    margin-bottom: 1.5rem;
    opacity: 0.7;
  }
  
  .empty-title {
    font-size: 1.5rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
    color: var(--primary-text, #333);
  }
  
  .empty-description {
    color: var(--secondary-text, #718096);
    margin-bottom: 2rem;
    max-width: 35rem;
  }
  
  /* Loading state */
  .loading-spinner {
    display: inline-block;
    width: 2rem;
    height: 2rem;
    border: 3px solid rgba(74, 105, 189, 0.2);
    border-top-color: var(--primary-color, #4a69bd);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1.5rem;
  }
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  /* Responsive styles */
  @media (max-width: 768px) {
    .file-item {
      flex-wrap: wrap;
    }
    
    .file-info {
      width: 100%;
      margin: 0.5rem 0;
    }
    
    .file-status {
      margin: 0.5rem 0;
    }
    
    .file-item-actions {
      margin-left: auto;
    }
    
    .file-header {
      flex-direction: column;
      gap: 1rem;
      align-items: flex-start;
    }
    
    .file-actions {
      width: 100%;
      justify-content: space-between;
    }
  }
</style>

{#if isActive}
  <div class="file-management">
    <!-- Header with actions -->
    <div class="file-header">
      <div class="header-title">
        File Management
      </div>
      <div class="file-actions">
        <button class="file-action-button secondary" on:click={loadFileList}>
          <i class="fas fa-sync-alt"></i>
          Refresh
        </button>
        <button 
          class="file-action-button danger" 
          disabled={selectedFiles.size === 0}
          on:click={deleteSelectedFiles}
        >
          <i class="fas fa-trash"></i>
          Delete Selected ({selectedFiles.size})
        </button>
      </div>
    </div>
    
    <!-- Main content area -->
    <div class="file-list-container">
      <!-- Always show the file upload drop zone -->
      <div class="file-upload-container" 
        on:click={() => {
          const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
          if (fileInput) fileInput.click();
        }}
        on:dragenter={(e) => {
          e.preventDefault();
          e.stopPropagation();
          e.currentTarget.classList.add('drag-over');
        }}
        on:dragover={(e) => {
          e.preventDefault();
          e.stopPropagation();
          e.currentTarget.classList.add('drag-over');
        }}
        on:dragleave={(e) => {
          e.preventDefault();
          e.stopPropagation();
          e.currentTarget.classList.remove('drag-over');
        }}
        on:drop={(e) => {
          e.preventDefault();
          e.stopPropagation();
          e.currentTarget.classList.remove('drag-over');
          
          const dt = e.dataTransfer;
          if (dt && dt.files && dt.files.length > 0) {
            const input = document.querySelector('input[type="file"]') as HTMLInputElement;
            if (input) {
              // Create a dummy event with the dropped files
              const event = { target: { files: dt.files } } as unknown as Event;
              handleFilesUpload(event);
            }
          }
        }}
      >
        <i class="fas fa-cloud-upload-alt file-upload-icon"></i>
        <div class="file-upload-text">Drag and drop files here or click to upload</div>
        <div class="file-upload-hint">Supported file types: PDF, Word, Text, CSV, etc.</div>
        <input 
          type="file" 
          multiple 
          style="display: none;" 
          on:change={handleFilesUpload}
        />
      </div>
      
      {#if isFileLoading && files.length === 0}
        <div class="empty-state">
          <div class="loading-spinner"></div>
          <div class="empty-title">Loading Files</div>
          <div class="empty-description">Please wait while we fetch your files...</div>
        </div>
      {:else if files.length === 0}
        <!-- No files message shown below drop zone -->
        <div class="empty-state">
          <i class="fas fa-file-upload empty-icon"></i>
          <div class="empty-title">No Files Found</div>
          <div class="empty-description">Upload files to manage them here.</div>
        </div>
      {:else}
        {#each files as file (file.id)}
          <div class="file-item" class:selected={selectedFiles.has(file.id)}>
            <input 
              type="checkbox" 
              class="file-checkbox" 
              checked={selectedFiles.has(file.id)}
              on:change={() => toggleFileSelection(file.id)}
            />
            <div class="file-icon">
              <i class={getFileIcon(file.file_type, file.file_name)}></i>
            </div>
            <div class="file-info">
              <div class="file-name">{file.file_name}</div>
              <div class="file-details">
                {formatFileSize(file.file_size)} • Uploaded {formatDateTime(file.upload_date)}
              </div>
            </div>
            <div class="file-status {file.processing_status}">
              {file.processing_status ? file.processing_status.charAt(0).toUpperCase() + file.processing_status.slice(1) : 'Unknown'}
            </div>
            <div class="file-item-actions">
              <button 
                class="file-item-button" 
                disabled={!file.text_content || (file.processing_status !== 'transcribed' && file.processing_status !== 'complete')}
                on:click={() => openModal(file)}
              >
                <i class="fas fa-eye"></i>
              </button>
              <button class="file-item-button delete" on:click={() => deleteFile(file.id)}>
                <i class="fas fa-trash"></i>
              </button>
            </div>
          </div>
        {/each}
      {/if}
    </div>
    
    <!-- Text content modal -->
    {#if showModal && modalFile}
      <div class="modal-overlay" on:click|self={closeModal}>
        <div class="modal">
          <div class="modal-header">
            <div class="modal-title">{modalFile.file_name}</div>
            <button class="modal-close" on:click={closeModal}>&times;</button>
          </div>
          <div class="modal-body">
            <textarea 
              class="modal-textarea" 
              bind:value={textContent}
              on:input={handleTextContentChange}
            ></textarea>
          </div>
          <div class="modal-footer">
            <button 
              class="file-action-button" 
              disabled={!isTextContentChanged}
              on:click={saveTextContent}
            >
              <i class="fas fa-save"></i>
              Save Changes
            </button>
            <button class="file-action-button secondary" on:click={closeModal}>
              <i class="fas fa-times"></i>
              Cancel
            </button>
          </div>
        </div>
      </div>
    {/if}
  </div>
{/if} 