<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { 
    addUserMessage, 
    addSystemMessage,
    messageInput,
    isLoading,
    fileAttachment,
    clearFileAttachment
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
  const apiBaseUrl = browser ? 'http://localhost:8000' : 'http://localhost:8000';
  
  // Check if this is the active agent
  $: isActive = $activeAgent === 'butterfly';
  
  // Helper function to activate this agent
  function activateButterfly() {
    setActiveAgent('butterfly');
  }
  
  // Send a message specifically to Butterfly
  async function sendToButterfly(text: string) {
    console.log('sendToButterfly called with text:', text);
    console.log('Current file attachment:', $fileAttachment);
    
    // Store the current agent
    const previousAgent = $activeAgent;
    
    // Switch to Butterfly temporarily
    setActiveAgent('butterfly');
    
    // Generate a query ID for this message
    const queryId = uuidv4();
    
    // Create a user message directly with the same structure as in ChatInterface
    const userMessage = {
      id: uuidv4(),
      type: 'user',
      content: text,
      sender: 'User',
      agentId: 'butterfly',
      operationType: 'recall', // Explicitly specify recall operation
      timestamp: new Date(),
      attachments: $fileAttachment ? [{
        id: $fileAttachment.id,
        name: $fileAttachment.name,
        type: $fileAttachment.type,
        size: $fileAttachment.size
      }] : [],
      queryId
    };
    
    // Add message directly to the conversation history
    addMessageToConversation('butterfly', userMessage);
    
    // Set loading state
    $isLoading = true;
    
    // Use the updated sendChatMessage that now includes operation type parameter
    const success = sendChatMessage(text, queryId, [], undefined, 'recall');
    
    if (!success) {
      addSystemMessage('Failed to send message to Butterfly. Please check your connection.');
      $isLoading = false;
    }
    
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