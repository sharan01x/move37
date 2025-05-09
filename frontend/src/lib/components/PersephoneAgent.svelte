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
  $: isActive = $activeAgent === 'persephone';
  
  // Helper function to activate this agent
  function activatePersephone() {
    setActiveAgent('persephone');
  }
  
  // Create a message handler to intercept message sending
  const persephoneMessageHandler: MessageHandler = {
    handleMessage: async (message: string, attachments: any[] = []) => {
      try {
        console.log('Persephone agent handling message:', message);
        
        // Generate a query ID for this message
        const queryId = uuidv4();
        
        // Create a user message with recall operation type
        const userMessage = {
          id: uuidv4(),
          type: 'user',
          content: message,
          sender: 'User',
          agentId: 'persephone',
          operationType: 'recall', // Explicitly use recall operation for Persephone
          timestamp: new Date(),
          attachments,
          queryId
        };
        
        // Add directly to the conversation history
        addMessageToConversation('persephone', userMessage);
          
        // Set loading state
        $isLoading = true;
        
        // Use sendChatMessage with the recall operation type parameter
        const success = sendChatMessage(message, queryId, [], undefined, 'recall');
        
        if (!success) {
          addSystemMessage('Failed to send message to Persephone. Please check your connection.');
          $isLoading = false;
        }
        
        // Return true to indicate message was handled
        return true;
      } catch (error) {
        console.error('Error in Persephone message handler:', error);
        addSystemMessage('An error occurred while processing your message.');
        $isLoading = false;
        return true; // Consider the message handled even if there was an error
      }
    }
  };
  
  // Register the message handler when the agent is active
  $: if (isActive) {
    console.log('Registering Persephone message handler');
    registerMessageHandler('persephone', persephoneMessageHandler);
  }
  
  // Send a message specifically to Persephone
  async function sendToPersephone(text: string) {
    // Store the current agent
    const previousAgent = $activeAgent;
    
    // Switch to Persephone temporarily
    setActiveAgent('persephone');
    
    // Use the message handler directly
    try {
      await persephoneMessageHandler.handleMessage(text, []);
    } catch (error) {
      console.error('Error in sendToPersephone:', error);
      addSystemMessage('Failed to process your message.');
    }
    
    // Return to previous agent if needed
    if (previousAgent !== 'persephone') {
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
  
  // Persephone specific prompt templates
  const promptTemplates = [
    "Suggest something I may like to do",
    "What's one of my goals that I need to work on?",
    "What's a good vacation spot for me?",
    "Summarize the last three things I recorded in my journal"
  ];
  
  function addWelcomeMessage() {
    // Check if we should add the welcome message
    // Only add if: there are no messages in the persephone conversation
    const convHistory = get(conversationHistory);
    const persephoneConversation = convHistory['persephone'] || [];
    const currentAgentId = get(activeAgent);
    
    // Only add welcome message to persephone conversation if it's empty
    if (persephoneConversation.length === 0 && currentAgentId === 'persephone') {
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
        id: `persephone_welcome_${Date.now()}`,
        type: 'agent',
        content: `<div class="welcome-message">
          <p>I'm your personal assistant. I can help you recall your personal information like:</p>
          <div class="template-buttons">
            ${templateButtonsHtml}
          </div>
        </div>`,
        sender: 'Persephone',
        agentId: 'persephone',
        timestamp: new Date(),
        isHtml: true
      };
      
      // Add to persephone conversation only
      addMessageToConversation('persephone', welcomeMessage);
      
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
    // Initialize any Persephone specific functionality
    console.log('Persephone agent component mounted');
    
    // Register the message handler for Persephone
    registerMessageHandler('persephone', persephoneMessageHandler);
    
    // Only run welcome message in browser environment
    if (browser) {
      addWelcomeMessage();
      
      // Add event listener for agent changes
      const unsubscribe = activeAgent.subscribe(agentId => {
        if (agentId === 'persephone') {
          // Check if we need to add welcome message when switching to Persephone
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