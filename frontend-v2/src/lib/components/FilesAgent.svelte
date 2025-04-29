<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { 
    addUserMessage, 
    addSystemMessage,
    messageInput,
    isLoading,
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
  
  // Check if this is the active agent
  $: isActive = $activeAgent === 'files';
  
  // Helper function to activate this agent
  function activateFiles() {
    setActiveAgent('files');
  }
  
  // Create a message handler to intercept message sending
  const filesMessageHandler: MessageHandler = {
    handleMessage: async (message: string, attachments: any[] = []) => {
      try {
        console.log('Files agent handling message:', message);
        
        // Generate a query ID for this message
        const queryId = uuidv4();
        
        // Create a user message with recall operation type
        const userMessage = {
          id: uuidv4(),
          type: 'user',
          content: message,
          sender: 'User',
          agentId: 'files',
          operationType: 'recall', // Explicitly use recall operation for Files
          timestamp: new Date(),
          attachments,
          queryId
        };
        
        // Add directly to the conversation history
        addMessageToConversation('files', userMessage);
          
        // Set loading state
        $isLoading = true;
        
        // Use sendChatMessage with the recall operation type parameter
        const success = sendChatMessage(message, queryId, [], undefined, 'recall');
        
        if (!success) {
          addSystemMessage('Failed to send message to Files. Please check your connection.');
          $isLoading = false;
        }
        
        // Return true to indicate message was handled
        return true;
      } catch (error) {
        console.error('Error in Files message handler:', error);
        addSystemMessage('An error occurred while processing your message.');
        $isLoading = false;
        return true; // Consider the message handled even if there was an error
      }
    }
  };
  
  // Register the message handler when the agent is active
  $: if (isActive) {
    console.log('Registering Files message handler');
    registerMessageHandler('files', filesMessageHandler);
  }
  
  // Send a message specifically to Files
  async function sendToFiles(text: string) {
    // Store the current agent
    const previousAgent = $activeAgent;
    
    // Switch to Files temporarily
    setActiveAgent('files');
    
    // Use the message handler directly
    try {
      await filesMessageHandler.handleMessage(text, []);
    } catch (error) {
      console.error('Error in sendToFiles:', error);
      addSystemMessage('Failed to process your message.');
    }
    
    // Return to previous agent if needed
    if (previousAgent !== 'files') {
      // Wait a bit to ensure the message is processed
      setTimeout(() => setActiveAgent(previousAgent), 100);
    }
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
  
  // Files specific prompt templates
  const promptTemplates = [
    "Upload a new document",
    "Show my recently uploaded files",
    "Search for PDF files",
    "Help me organize my files"
  ];
  
  function addWelcomeMessage() {
    // Check if we should add the welcome message
    // Only add if: there are no messages in the files conversation
    const convHistory = get(conversationHistory);
    const filesConversation = convHistory['files'] || [];
    const currentAgentId = get(activeAgent);
    
    // Only add welcome message to files conversation if it's empty
    if (filesConversation.length === 0 && currentAgentId === 'files') {
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
        id: `files_welcome_${Date.now()}`,
        type: 'agent',
        content: `<div class="welcome-message">
          <p>This is the Files section. Here you can manage your uploaded documents:</p>
          <div class="template-buttons">
            ${templateButtonsHtml}
          </div>
        </div>`,
        sender: 'Files',
        agentId: 'files',
        timestamp: new Date(),
        isHtml: true
      };
      
      // Add to files conversation only
      addMessageToConversation('files', welcomeMessage);
      
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
    // Initialize any Files specific functionality
    console.log('Files agent component mounted');
    
    // Register the message handler for Files
    registerMessageHandler('files', filesMessageHandler);
    
    // Only run welcome message in browser environment
    if (browser) {
      addWelcomeMessage();
      
      // Add event listener for agent changes
      const unsubscribe = activeAgent.subscribe(agentId => {
        if (agentId === 'files') {
          // Check if we need to add welcome message when switching to Files
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