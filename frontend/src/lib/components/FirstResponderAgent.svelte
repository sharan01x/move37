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
  $: isActive = $activeAgent === 'first_responder';
  
  // Helper function to activate this agent
  function activateFirstResponder() {
    setActiveAgent('first_responder');
  }
  
  // Create a message handler to intercept message sending
  const firstResponderMessageHandler: MessageHandler = {
    handleMessage: async (message: string, attachments: any[] = []) => {
      try {
        console.log('First Responder agent handling message:', message);
        
        // Generate a query ID for this message
        const queryId = uuidv4();
        
        // Create a user message with recall operation type
        const userMessage = {
          id: uuidv4(),
          type: 'user',
          content: message,
          sender: 'User',
          agentId: 'first_responder',
          operationType: 'recall', // Explicitly use recall operation for First Responder
          timestamp: new Date(),
          attachments,
          queryId
        };
        
        // Add directly to the conversation history
        addMessageToConversation('first_responder', userMessage);
          
        // Set loading state
        $isLoading = true;
        
        // Use sendChatMessage with the recall operation type parameter
        const success = sendChatMessage(message, queryId, [], undefined, 'recall');
        
        if (!success) {
          addSystemMessage('Failed to send message to First Responder. Please check your connection.');
          $isLoading = false;
        }
        
        // Return true to indicate message was handled
        return true;
      } catch (error) {
        console.error('Error in First Responder message handler:', error);
        addSystemMessage('An error occurred while processing your message.');
        $isLoading = false;
        return true; // Consider the message handled even if there was an error
      }
    }
  };
  
  // Register the message handler when the agent is active
  $: if (isActive) {
    console.log('Registering First Responder message handler');
    registerMessageHandler('first_responder', firstResponderMessageHandler);
  }
  
  // Send a message specifically to First Responder
  async function sendToFirstResponder(text: string) {
    // Store the current agent
    const previousAgent = $activeAgent;
    
    // Switch to First Responder temporarily
    setActiveAgent('first_responder');
    
    // Use the message handler directly
    try {
      await firstResponderMessageHandler.handleMessage(text, []);
    } catch (error) {
      console.error('Error in sendToFirstResponder:', error);
      addSystemMessage('Failed to process your message.');
    }
    
    // Return to previous agent if needed
    if (previousAgent !== 'first_responder') {
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
  
  // Example First Responder specific prompt templates
  const promptTemplates = [
    "Tell me a new joke",
    "What is the distance from here to the moon?",
    "Who is Claude Shannon?",
    "Tell me a new random fact about health."
  ];
  
  function addWelcomeMessage() {
    // Check if we should add the welcome message
    // Only add if: there are no messages in the first_responder conversation
    const convHistory = get(conversationHistory);
    const frConversation = convHistory['first_responder'] || [];
    const currentAgentId = get(activeAgent);
    
    // Only add welcome message to first_responder conversation if it's empty
    if (frConversation.length === 0 && currentAgentId === 'first_responder') {
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
        id: `fr_welcome_${Date.now()}`,
        type: 'agent',
        content: `<div class="welcome-message">
          <p>I can answer a lot of general knowledge questions, like the ones below:</p>
          <div class="template-buttons">
            ${templateButtonsHtml}
          </div>
        </div>`,
        sender: 'First Responder',
        agentId: 'first_responder',
        timestamp: new Date(),
        isHtml: true
      };
      
      // Add to first responder conversation only
      addMessageToConversation('first_responder', welcomeMessage);
      
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
    // Initialize any First Responder specific functionality
    console.log('First Responder agent component mounted');
    
    // Register the message handler for First Responder
    registerMessageHandler('first_responder', firstResponderMessageHandler);
    
    // Only run welcome message in browser environment
    if (browser) {
      addWelcomeMessage();
      
      // Add event listener for agent changes
      const unsubscribe = activeAgent.subscribe(agentId => {
        if (agentId === 'first_responder') {
          // Check if we need to add welcome message when switching to First Responder
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