<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { 
    addUserMessage, 
    addSystemMessage,
    messageInput,
    isLoading
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
  
  // Send a message specifically to Persephone
  async function sendToPersephone(text: string) {
    // Store the current agent
    const previousAgent = $activeAgent;
    
    // Switch to Persephone temporarily
    setActiveAgent('persephone');
    
    // Generate a query ID for this message
    const queryId = uuidv4();
    
    // Create a user message directly with the same structure as in ChatInterface
    const userMessage = {
      id: uuidv4(),
      type: 'user',
      content: text,
      sender: 'User',
      agentId: 'persephone',
      timestamp: new Date(),
      attachments: [],
      queryId
    };
    
    // Add message directly to the conversation history
    addMessageToConversation('persephone', userMessage);
    
    // Set loading state
    $isLoading = true;
    
    // Use the updated sendChatMessage that now uses the proper message format
    const success = sendChatMessage(text, queryId);
    
    if (!success) {
      addSystemMessage('Failed to send message to Persephone. Please check your connection.');
      $isLoading = false;
    }
    
    // Return to previous agent if needed
    if (previousAgent !== 'persephone') {
      // Wait a bit to ensure the message is processed
      setTimeout(() => setActiveAgent(previousAgent), 100);
    }
  }
  
  // Persephone specific prompt templates
  const promptTemplates = [
    "What are my recent health activities?",
    "Remind me what I did last weekend",
    "What information do you have about my family?",
    "Summarize the last three things I recorded"
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
        .map(template => `<button class="template-button" data-prompt="${template}">${template}</button>`)
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
                sendToPersephone(prompt);
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