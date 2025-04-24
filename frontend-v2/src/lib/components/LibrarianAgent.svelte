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
  $: isActive = $activeAgent === 'librarian';
  
  // Helper function to activate this agent
  function activateLibrarian() {
    setActiveAgent('librarian');
  }
  
  // Send a message specifically to Librarian
  async function sendToLibrarian(text: string) {
    // Store the current agent
    const previousAgent = $activeAgent;
    
    // Switch to Librarian temporarily
    setActiveAgent('librarian');
    
    // Generate a query ID for this message
    const queryId = uuidv4();
    
    // Create a user message directly with the same structure as in ChatInterface
    const userMessage = {
      id: uuidv4(),
      type: 'user',
      content: text,
      sender: 'User',
      agentId: 'librarian',
      timestamp: new Date(),
      attachments: [],
      queryId
    };
    
    // Add message directly to the conversation history
    addMessageToConversation('librarian', userMessage);
    
    // Set loading state
    $isLoading = true;
    
    // Use the updated sendChatMessage that now uses the proper message format
    const success = sendChatMessage(text, queryId);
    
    if (!success) {
      addSystemMessage('Failed to send message to Librarian. Please check your connection.');
      $isLoading = false;
    }
    
    // Return to previous agent if needed
    if (previousAgent !== 'librarian') {
      // Wait a bit to ensure the message is processed
      setTimeout(() => setActiveAgent(previousAgent), 100);
    }
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
        .map(template => `<button class="template-button" data-prompt="${template}">${template}</button>`)
        .join('');
      
      // Create welcome message
      const welcomeMessage = {
        id: `librarian_welcome_${Date.now()}`,
        type: 'agent',
        content: `<div class="welcome-message">
          <p>I can help you find information in your documents. Try asking:</p>
          <div class="template-buttons">
            ${templateButtonsHtml}
          </div>
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
                sendToLibrarian(prompt);
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