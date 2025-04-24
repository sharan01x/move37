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
  $: isActive = $activeAgent === 'number_ninja';
  
  // Helper function to activate this agent
  function activateNumberNinja() {
    setActiveAgent('number_ninja');
  }
  
  // Send a message specifically to Number Ninja
  async function sendToNumberNinja(text: string) {
    // Store the current agent
    const previousAgent = $activeAgent;
    
    // Switch to Number Ninja temporarily
    setActiveAgent('number_ninja');
    
    // Generate a query ID for this message
    const queryId = uuidv4();
    
    // Create a user message directly with the same structure as in ChatInterface
    const userMessage = {
      id: uuidv4(),
      type: 'user',
      content: text,
      sender: 'User',
      agentId: 'number_ninja',
      timestamp: new Date(),
      attachments: [],
      queryId
    };
    
    // Add message directly to the conversation history
    addMessageToConversation('number_ninja', userMessage);
    
    // Set loading state
    $isLoading = true;
    
    // Use the updated sendChatMessage that now uses the proper message format
    const success = sendChatMessage(text, queryId);
    
    if (!success) {
      addSystemMessage('Failed to send message to Number Ninja. Please check your connection.');
      $isLoading = false;
    }
    
    // Return to previous agent if needed
    if (previousAgent !== 'number_ninja') {
      // Wait a bit to ensure the message is processed
      setTimeout(() => setActiveAgent(previousAgent), 100);
    }
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
        .map(template => `<button class="template-button" data-prompt="${template}">${template}</button>`)
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
                sendToNumberNinja(prompt);
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