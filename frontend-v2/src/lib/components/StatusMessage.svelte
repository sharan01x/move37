<script lang="ts">
  import { statusMessage } from '$lib/stores/chatStore';
  import { onMount } from 'svelte';
  
  // Control the visibility
  let visible = false;
  let timeoutId: number | null = null;
  
  // When the status message changes, show it
  $: if ($statusMessage) {
    showMessage();
  }
  
  // Show the message for a few seconds
  function showMessage() {
    visible = true;
    
    // Clear any existing timeout
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    
    // Hide the message after 5 seconds
    timeoutId = window.setTimeout(() => {
      visible = false;
      // Give time for the animation to complete before clearing the message
      setTimeout(() => {
        if (!visible) statusMessage.set('');
      }, 500);
    }, 5000);
  }
  
  // Clean up on component unmount
  onMount(() => {
    return () => {
      if (timeoutId) clearTimeout(timeoutId);
    };
  });
</script>

<div class="status-message-container" class:visible={visible && $statusMessage}>
  <div class="status-message">
    <i class="fas fa-info-circle"></i>
    <span>{$statusMessage}</span>
  </div>
</div>

<style>
  .status-message-container {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 100%; /* Position above the input */
    pointer-events: none;
    transform: translateY(10px);
    opacity: 0;
    transition: transform 0.3s ease, opacity 0.3s ease;
    z-index: 20; /* Higher z-index to appear above other elements */
  }
  
  .status-message-container.visible {
    transform: translateY(0);
    opacity: 1;
  }
  
  .status-message {
    background-color: #e0f2fe;
    color: #0369a1;
    padding: 0.75rem 1rem;
    border-radius: 0.5rem 0.5rem 0 0;
    font-size: 0.875rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    box-shadow: 0 -2px 4px rgba(0, 0, 0, 0.05);
    margin: 0 0.5rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .status-message i {
    flex-shrink: 0;
  }
</style> 