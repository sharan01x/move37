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
  $: isActive = $activeAgent === 'number_ninja';
  
  // Helper function to activate this agent
  function activateNumberNinja() {
    setActiveAgent('number_ninja');
  }
  
  // Create a message handler to intercept message sending
  const numberNinjaMessageHandler: MessageHandler = {
    handleMessage: async (message: string, attachments: any[] = []) => {
      try {
        console.log('Number Ninja agent handling message:', message);
        
        // Generate a query ID for this message
        const queryId = uuidv4();
        
        // Create a user message with recall operation type
        const userMessage = {
          id: uuidv4(),
          type: 'user',
          content: message,
          sender: 'User',
          agentId: 'number_ninja',
          operationType: 'recall', // Explicitly use recall operation for Number Ninja
          timestamp: new Date(),
          attachments,
          queryId
        };
        
        // Add directly to the conversation history
        addMessageToConversation('number_ninja', userMessage);
          
        // Set loading state
        $isLoading = true;
        
        // Use sendChatMessage with the recall operation type parameter
        const success = sendChatMessage(message, queryId, [], undefined, 'recall');
        
        if (!success) {
          addSystemMessage('Failed to send message to Number Ninja. Please check your connection.');
          $isLoading = false;
        }
        
        // Return true to indicate message was handled
        return true;
      } catch (error) {
        console.error('Error in Number Ninja message handler:', error);
        addSystemMessage('An error occurred while processing your message.');
        $isLoading = false;
        return true; // Consider the message handled even if there was an error
      }
    }
  };
  
  // Register the message handler when the agent is active
  $: if (isActive) {
    console.log('Registering Number Ninja message handler');
    registerMessageHandler('number_ninja', numberNinjaMessageHandler);
  }
  
  // Send a message specifically to Number Ninja
  async function sendToNumberNinja(text: string) {
    // Store the current agent
    const previousAgent = $activeAgent;
    
    // Switch to Number Ninja temporarily
    setActiveAgent('number_ninja');
    
    // Use the message handler directly
    try {
      await numberNinjaMessageHandler.handleMessage(text, []);
    } catch (error) {
      console.error('Error in sendToNumberNinja:', error);
      addSystemMessage('Failed to process your message.');
    }
    
    // Return to previous agent if needed
    if (previousAgent !== 'number_ninja') {
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
  
  // Number Ninja specific prompt templates
  const promptTemplates = [
    "What is the square root of 16?",
    "What is 18+24-32*45?",
    "What is 1000 divided by 25?",
    "25*325?"
  ];
  
  function addWelcomeMessage() {
    // Check if we should add the welcome message
    // Only add if: there are no messages in the number_ninja conversation
    const convHistory = get(conversationHistory);
    const nnConversation = convHistory['number_ninja'] || [];
    const currentAgentId = get(activeAgent);
    
    // Only add welcome message to number_ninja conversation if it's empty
    if (nnConversation.length === 0 && currentAgentId === 'number_ninja') {
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
        id: `nn_welcome_${Date.now()}`,
        type: 'agent',
        content: `<div class="welcome-message">
          <p>I'm your math assistant! I can help with calculations and numeric questions like:</p>
          <div class="template-buttons">
            ${templateButtonsHtml}
          </div>
        </div>`,
        sender: 'Number Ninja',
        agentId: 'number_ninja',
        timestamp: new Date(),
        isHtml: true
      };
      
      // Add to number ninja conversation only
      addMessageToConversation('number_ninja', welcomeMessage);
      
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
    // Initialize any Number Ninja specific functionality
    console.log('Number Ninja agent component mounted');
    
    // Register the message handler for Number Ninja
    registerMessageHandler('number_ninja', numberNinjaMessageHandler);
    
    // Only run welcome message in browser environment
    if (browser) {
      addWelcomeMessage();
      
      // Add event listener for agent changes
      const unsubscribe = activeAgent.subscribe(agentId => {
        if (agentId === 'number_ninja') {
          // Check if we need to add welcome message when switching to Number Ninja
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