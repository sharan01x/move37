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
  $: isActive = $activeAgent === 'butterfly';
  
  // Helper function to activate this agent
  function activateButterfly() {
    setActiveAgent('butterfly');
  }
  
  // Create a message handler to intercept message sending for Butterfly agent
  const butterflyMessageHandler: MessageHandler = {
    handleMessage: async (message: string, attachments: any[] = []) => {
      console.log('Butterfly agent handling message:', message);
      console.log('Current file attachment:', get(fileAttachment));
      
      // Generate a query ID for this message
      const queryId = uuidv4();
      
      // Create a user message directly with recall operation type
      const userMessage = {
        id: uuidv4(),
        type: 'user',
        content: message,
        sender: 'User',
        agentId: 'butterfly',
        operationType: 'recall', // Explicitly use recall operation for Butterfly
        timestamp: new Date(),
        attachments: attachments,
        queryId
      };
      
      // Add directly to the conversation history
      addMessageToConversation('butterfly', userMessage);
        
      // Set loading state
      $isLoading = true;
      
      // Special handling for file attachments
      const currentFileAttachment = get(fileAttachment);
      if (currentFileAttachment && currentFileAttachment.file) {
        console.log('Butterfly agent with file attachment detected, handling file upload');
        
        const fileType = currentFileAttachment.type.startsWith('image/') ? 'image' : 'video';
        
        try {
          // Upload the file using fetch
          const userId = browser ? localStorage.getItem('userId') || 'default' : 'default';
          
          console.log(`Uploading file to ${apiBaseUrl}/social_media/upload`);
          
          const formData = new FormData();
          formData.append('file', currentFileAttachment.file);
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
            $isLoading = false;
            clearFileAttachment();
            return true;
          }
          
          if (!result.file_ids || result.file_ids.length === 0) {
            console.error('File upload returned no file path');
            $isLoading = false;
            clearFileAttachment();
            return true;
          }
          
          const filePath = result.file_ids[0];
          console.log('File uploaded successfully, path:', filePath);
          
          // Now send the message with the attachment path
          const success = sendChatMessage(message, queryId, [], filePath, 'recall');
          
          if (!success) {
            addSystemMessage('Failed to send message to Butterfly. Please check your connection.');
            $isLoading = false;
          }
          
          // Clear file attachment after sending
          clearFileAttachment();
        } catch (error: any) {
          console.error('Error uploading file:', error);
          $isLoading = false;
          clearFileAttachment();
        }
      } else {
        // Standard message sending without file attachment
        const success = sendChatMessage(message, queryId, [], undefined, 'recall');
        
        if (!success) {
          addSystemMessage('Failed to send message to Butterfly. Please check your connection.');
          $isLoading = false;
        }
      }
      
      return true;
    }
  };
  
  // Register the message handler when the agent is active
  $: if (isActive) {
    console.log('Registering butterfly message handler');
    registerMessageHandler('butterfly', butterflyMessageHandler);
  }
  
  // Send a message specifically to Butterfly
  async function sendToButterfly(text: string) {
    console.log('sendToButterfly called with text:', text);
    
    // Store the current agent
    const previousAgent = $activeAgent;
    
    // Switch to Butterfly temporarily
    setActiveAgent('butterfly');
    
    // Use the message handler directly
    butterflyMessageHandler.handleMessage(text, get(fileAttachment) ? [get(fileAttachment)] : []);
    
    // Return to previous agent if needed
    if (previousAgent !== 'butterfly') {
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
  
  // Butterfly specific prompt templates with placeholders for user input
  const promptTemplates = [
    "Post \"Hello World\" on my personal account on Twitter",
    "Post \"This is new today...\" on all my company accounts",
    "Post \"Check out this new product...\" on my BlueSky accounts",
    "Post \"Happy to be here...\" to all my accounts"
  ];
  
  function addWelcomeMessage() {
    // Check if we should add the welcome message
    // Only add if: there are no messages in the butterfly conversation
    const convHistory = get(conversationHistory);
    const butterflyConversation = convHistory['butterfly'] || [];
    const currentAgentId = get(activeAgent);
    
    // Only add welcome message to butterfly conversation if it's empty
    if (butterflyConversation.length === 0 && currentAgentId === 'butterfly') {
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
        id: `butterfly_welcome_${Date.now()}`,
        type: 'agent',
        content: `<div class="welcome-message">
          <p>Post across Twitter, LinkedIn (Company and Personal), Lens, BlueSky, Mastodon and Farcaster easily. You can post to specific accounts, types of accounts, a specific platform, or to all of them. Click a template below and modify the details before hitting send:</p>
          <div class="template-buttons">
            ${templateButtonsHtml}
          </div>
          <p>You can also attach images or videos to your posts using the paperclip icon in the chat interface.</p>
        </div>`,
        sender: 'Butterfly',
        agentId: 'butterfly',
        timestamp: new Date(),
        isHtml: true
      };
      
      // Add to butterfly conversation only
      addMessageToConversation('butterfly', welcomeMessage);
      
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
    // Initialize any Butterfly specific functionality
    console.log('Butterfly agent component mounted');
    
    // Register the message handler for butterfly
    registerMessageHandler('butterfly', butterflyMessageHandler);
    
    // Only run welcome message in browser environment
    if (browser) {
      addWelcomeMessage();
      
      // Add event listener for agent changes
      const unsubscribe = activeAgent.subscribe(agentId => {
        if (agentId === 'butterfly') {
          // Check if we need to add welcome message when switching to Butterfly
          addWelcomeMessage();
        }
      });
      
      return () => {
        unsubscribe();
      };
    }
  });
</script>

<!-- We don't actually need a hidden file input in this component, as we're using the one from ChatInterface -->
<!-- <input 
  type="file"
  bind:this={fileInput}
  accept="image/*,video/*"
  on:change={handleFileSelection}
  style="display: none;"
/> -->

<!-- No visible UI elements - only logic for adding welcome message --> 