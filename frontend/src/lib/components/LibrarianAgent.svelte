<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { 
    addUserMessage, 
    addSystemMessage,
    messageInput,
    isLoading,
    fileAttachment,
    clearFileAttachment,
    registerMessageHandler,
    type MessageHandler
  } from '$lib/stores/chatStore';
  import { 
    activeAgent, 
    currentAgent, 
    setActiveAgent,
    addMessageToConversation,
    conversationHistory
  } from '$lib/stores/agentsStore';
  import { sendChatMessage } from '$lib/stores/websocketStore';
  import { get } from 'svelte/store';
  import { v4 as uuidv4 } from 'uuid';
  
  // API endpoint - needed for backend API calls
  const apiPort = browser ? (import.meta.env.VITE_API_PORT || window.location.port || '8000') : '8000';
  const apiBaseUrl = browser ? `${window.location.protocol}//${window.location.hostname}:${apiPort}` : 'http://localhost:8000';
  
  // Check if this is the active agent
  $: isActive = $activeAgent === 'librarian';
  
  // Helper function to activate this agent
  function activateLibrarian() {
    setActiveAgent('librarian');
  }
  
  // Create a message handler to intercept message sending
  const librarianMessageHandler: MessageHandler = {
    handleMessage: async (message: string, attachments: any[] = []) => {
      try {
        console.log('Librarian agent handling message:', message);
        
        // Generate a query ID for this message
        const queryId = uuidv4();
        
        // Create a user message with recall operation type
        const userMessage = {
          id: uuidv4(),
          type: 'user',
          content: message,
          sender: 'User',
          agentId: 'librarian',
          operationType: 'recall', // Explicitly use recall operation for Librarian
          timestamp: new Date(),
          attachments,
          queryId
        };
        
        // Add directly to the conversation history
        addMessageToConversation('librarian', userMessage);
          
        // Set loading state
        $isLoading = true;
        
        // Special handling for file attachments
        const currentFileAttachment = get(fileAttachment);
        if (currentFileAttachment && currentFileAttachment.file) {
          console.log('Librarian agent with file attachment detected, handling file upload');
          
          try {
            // Upload the file using fetch
            const userId = browser ? localStorage.getItem('userId') || 'user123' : 'user123';
            
            console.log(`Uploading file to ${apiBaseUrl}/files/upload`);
            
            // Create FormData and append file - backend expects 'files' parameter name
            const formData = new FormData();
            formData.append('files', currentFileAttachment.file);
            formData.append('user_id', userId);
            
            const response = await fetch(`${apiBaseUrl}/files/upload`, {
              method: 'POST',
              body: formData
            });
            
            console.log('Response status:', response.status);
            const result = await response.json();
            console.log('File upload response:', result);
            
            if (!result.success) {
              console.error('File upload failed:', result.message);
              addSystemMessage(`File upload failed: ${result.message}`);
              $isLoading = false;
              clearFileAttachment();
              return true;
            }
            
            if (!result.file_ids || result.file_ids.length === 0) {
              console.error('File upload returned no file IDs');
              addSystemMessage('File upload was unsuccessful. No file ID returned.');
              $isLoading = false;
              clearFileAttachment();
              return true;
            }
            
            console.log('File uploaded successfully, ID:', result.file_ids[0]);
            addSystemMessage(`File uploaded successfully. You can now ask questions about its contents.`);
            
            // Now send the message without waiting for the upload
            const success = sendChatMessage(message, queryId, [], undefined, 'recall');
            
            if (!success) {
              addSystemMessage('Failed to send message to Librarian. Please check your connection.');
              $isLoading = false;
            }
            
            // Clear file attachment after sending
            clearFileAttachment();
          } catch (error: any) {
            console.error('Error uploading file:', error);
            addSystemMessage(`Error uploading file: ${error.message || 'Unknown error'}`);
            $isLoading = false;
            clearFileAttachment();
          }
        } else {
          // Standard message sending without file attachment
          const success = sendChatMessage(message, queryId, [], undefined, 'recall');
          
          if (!success) {
            addSystemMessage('Failed to send message to Librarian. Please check your connection.');
            $isLoading = false;
          }
        }
        
        // Return true to indicate message was handled
        return true;
      } catch (error) {
        console.error('Error in Librarian message handler:', error);
        addSystemMessage('An error occurred while processing your message.');
        $isLoading = false;
        return true; // Consider the message handled even if there was an error
      }
    }
  };
  
  // Register the message handler when the agent is active
  $: if (isActive) {
    console.log('Registering Librarian message handler');
    registerMessageHandler('librarian', librarianMessageHandler);
  }
  
  // Send a message specifically to Librarian
  async function sendToLibrarian(text: string) {
    // Store the current agent
    const previousAgent = $activeAgent;
    
    // Switch to Librarian temporarily
    setActiveAgent('librarian');
    
    // Use the message handler directly
    try {
      await librarianMessageHandler.handleMessage(text, get(fileAttachment) ? [get(fileAttachment)] : []);
    } catch (error) {
      console.error('Error in sendToLibrarian:', error);
      addSystemMessage('Failed to process your message.');
    }
    
    // Return to previous agent if needed
    if (previousAgent !== 'librarian') {
      // Wait a bit to ensure the message is processed
      setTimeout(() => setActiveAgent(previousAgent), 100);
    }
  }
  
  // Remove selected file
  function removeSelectedFile() {
    clearFileAttachment();
  }
  
  // Fill the input box with template text
  function fillInputWithTemplate(template: string) {
    // Set the input value to the template text
    messageInput.set(template);
    
    // Focus the input field (if available)
    setTimeout(() => {
      const inputElement = document.querySelector('textarea');
      if (inputElement) {
        inputElement.focus();
      }
    }, 100);
  }
  
  // Librarian specific prompt templates
  const promptTemplates = [
    "What documents have I uploaded recently?",
    "Summarize my latest PDF file",
    "Find information about cooking in my documents",
    "When did I last upload a document?"
  ];
  
  function addWelcomeMessage() {
    // Check if we should add the welcome message
    // Only add if: there are no messages in the librarian conversation
    const convHistory = get(conversationHistory);
    const librarianConversation = convHistory['librarian'] || [];
    const currentAgentId = get(activeAgent);
    
    // Only add welcome message to librarian conversation if it's empty
    if (librarianConversation.length === 0 && currentAgentId === 'librarian') {
      // Create template buttons HTML
      const templateButtonsHtml = promptTemplates
        .map(template => {
          // Escape quotes for the data attribute
          const escapedTemplate = template.replace(/"/g, '&quot;');
          return `<button class="template-button" data-prompt="${escapedTemplate}">${template}</button>`;
        })
        .join('');
      
      // Create welcome message
      const welcomeMessage = {
        id: `librarian_welcome_${Date.now()}`,
        type: 'agent',
        content: `<div class="welcome-message">
          <p>I can help you find information in your documents. You can upload documents and then ask questions about them. Try asking:</p>
          <div class="template-buttons">
            ${templateButtonsHtml}
          </div>
          <p>You can also attach files using the paperclip icon in the chat interface.</p>
        </div>`,
        sender: 'Librarian',
        agentId: 'librarian',
        timestamp: new Date(),
        isHtml: true
      };
      
      // Add to librarian conversation only
      addMessageToConversation('librarian', welcomeMessage);
      
      // Only add DOM event listeners if in browser environment
      if (browser) {
        // Add message event listeners after a brief delay to ensure DOM is updated
        setTimeout(() => {
          document.querySelectorAll('.template-button').forEach(btn => {
            btn.addEventListener('click', (e) => {
              // Get the prompt from the data attribute
              const prompt = (e.currentTarget as HTMLElement).dataset.prompt;
              if (prompt) {
                // Instead of sending, fill the input box with the template
                fillInputWithTemplate(prompt);
              }
            });
          });
        }, 100);
      }
    }
  }
  
  onMount(() => {
    // Initialize any Librarian specific functionality
    console.log('Librarian agent component mounted');
    
    // Register the message handler for Librarian
    registerMessageHandler('librarian', librarianMessageHandler);
    
    // Only run welcome message in browser environment
    if (browser) {
      addWelcomeMessage();
      
      // Add event listener for agent changes
      const unsubscribe = activeAgent.subscribe(agentId => {
        if (agentId === 'librarian') {
          // Check if we need to add welcome message when switching to Librarian
          addWelcomeMessage();
        }
      });
      
      return () => {
        unsubscribe();
      };
    }
  });
</script>

<!-- No visible UI elements - only logic for adding welcome message --> 