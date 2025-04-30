<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { 
    addSystemMessage,
    messageInput,
    isLoading,
    registerMessageHandler,
    type MessageHandler
  } from '$lib/stores/chatStore';
  import { 
    activeAgent, 
    setActiveAgent,
    addMessageToConversation,
    conversationHistory
  } from '$lib/stores/agentsStore';
  import { sendChatMessage } from '$lib/stores/websocketStore';
  import { get } from 'svelte/store';
  import { v4 as uuidv4 } from 'uuid';
  
  // Check if this is the active agent
  $: isActive = $activeAgent === 'submissions';
  
  // Helper function to activate this agent
  function activateSubmissions() {
    setActiveAgent('submissions');
  }
  
  // Create a message handler to intercept message sending
  const submissionsMessageHandler: MessageHandler = {
    handleMessage: async (message: string, attachments: any[] = []) => {
      try {
        console.log('Submissions agent handling message:', message);
        
        // Generate a query ID for this message
        const queryId = uuidv4();
        
        // Create a user message with record operation type
        const userMessage = {
          id: uuidv4(),
          type: 'user',
          content: message,
          sender: 'User',
          agentId: 'submissions',
          operationType: 'record', // Ensure record operation
          timestamp: new Date(),
          attachments,
          queryId
        };
        
        // Add directly to the conversation history
        addMessageToConversation('submissions', userMessage);
          
        // Set loading state
        $isLoading = true;
        
        // Use sendChatMessage with the record operation type parameter
        const success = sendChatMessage(message, queryId, [], undefined, 'record');
        
        if (!success) {
          addSystemMessage('Failed to send message to Submissions. Please check your connection.');
          $isLoading = false;
        }
        
        // Return true to indicate message was handled
        return true;
      } catch (error) {
        console.error('Error in submissions message handler:', error);
        addSystemMessage('An error occurred while processing your submission.');
        $isLoading = false;
        return true; // Consider the message handled even if there was an error
      }
    }
  };
  
  // Register the message handler when the agent is active
  $: if (isActive) {
    console.log('Registering submissions message handler');
    registerMessageHandler('submissions', submissionsMessageHandler);
  }
  
  // Send a message specifically to Submissions
  async function sendToSubmissions(text: string) {
    // Store the current agent
    const previousAgent = $activeAgent;
    
    // Switch to Submissions temporarily
    setActiveAgent('submissions');
    
    // Use the message handler directly
    try {
      await submissionsMessageHandler.handleMessage(text, []);
    } catch (error) {
      console.error('Error in sendToSubmissions:', error);
      addSystemMessage('Failed to process your submission.');
    }
    
    // Return to previous agent if needed
    if (previousAgent !== 'submissions') {
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
  
  // Submissions specific prompt templates
  const promptTemplates = [
    "Record that I went to the gym today",
    "Remember that I took my medication at 8am",
    "Log my weight as 85.4 Kgs today",
    "Note that I met with Sharan and discussed the following:",
  ];
  
  function addWelcomeMessage() {
    // Check if we should add the welcome message
    // Only add if: there are no messages in the submissions conversation
    const convHistory = get(conversationHistory);
    const submissionsConversation = convHistory['submissions'] || [];
    const currentAgentId = get(activeAgent);
    
    // Only add welcome message to submissions conversation if it's empty
    if (submissionsConversation.length === 0 && currentAgentId === 'submissions') {
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
        id: `submissions_welcome_${Date.now()}`,
        type: 'agent',
        content: `<div class="welcome-message">
          <p>I can help you record any information you'd like to remember. Try examples like:</p>
          <div class="template-buttons">
            ${templateButtonsHtml}
          </div>
        </div>`,
        sender: 'Submissions',
        agentId: 'submissions',
        timestamp: new Date(),
        isHtml: true
      };
      
      // Add to submissions conversation only
      addMessageToConversation('submissions', welcomeMessage);
      
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
    // Initialize any Submissions specific functionality
    console.log('Submissions agent component mounted');
    
    // Register the message handler for submissions
    registerMessageHandler('submissions', submissionsMessageHandler);
    
    // Only run welcome message in browser environment
    if (browser) {
      addWelcomeMessage();
      
      // Add event listener for agent changes
      const unsubscribe = activeAgent.subscribe(agentId => {
        if (agentId === 'submissions') {
          // Check if we need to add welcome message when switching to Submissions
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