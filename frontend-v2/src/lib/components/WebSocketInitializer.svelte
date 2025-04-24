<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { initializeWebSocketHandlers } from '$lib/services/websocketHandlers';
  import { recallWsService, recordWsService } from '$lib/services/websocketService';
  
  // Initialize WebSocket handlers on mount
  onMount(() => {
    if (browser) {
      // Attach WebSocket services to window for global access
      window.recallWsService = recallWsService;
      window.recordWsService = recordWsService;
      
      // Initialize handlers after attaching services to window
      console.log('Initializing WebSocket services and handlers');
    initializeWebSocketHandlers();
    }
  });
</script>

<!-- This is a utility component with no UI --> 