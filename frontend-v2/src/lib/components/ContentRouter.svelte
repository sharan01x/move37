<script lang="ts">
  import { activeSidebarItem } from '$lib/stores/sidebarStore';
  import ChatInterface from './ChatInterface.svelte';
  
  // For all sidebar items, we'll use ChatInterface for now
  // This will be replaced with specialized interfaces later
</script>

<!-- Always render ChatInterface for all sidebar items -->
<ChatInterface /> 