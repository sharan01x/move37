<script lang="ts">
  import { onMount } from 'svelte';
  import Sidebar from './Sidebar.svelte';
  import ChatInterface from './ChatInterface.svelte';
  import UserProfile from './UserProfile.svelte';
  import { connectRecallWebSocket, connectRecordWebSocket } from '$lib/services/websocket';
  import { initializeWebSocketHandlers } from '$lib/services/websocketHandlers';
  import { darkMode } from '$lib/stores/themeStore';
  
  // Current mode (recall or record)
  let currentMode: 'recall' | 'record' = 'recall';
  
  // User profile panel state
  let isUserProfileOpen = false;
  
  // Initialize WebSocket connections on mount
  onMount(() => {
    // Connect WebSockets
    connectRecallWebSocket();
    connectRecordWebSocket();
    
    // Initialize WebSocket handlers
    initializeWebSocketHandlers();
  });
  
  // Switch between recall and record modes
  function switchMode(mode: 'recall' | 'record') {
    currentMode = mode;
  }
  
  // Toggle user profile panel
  function toggleUserProfile() {
    isUserProfileOpen = !isUserProfileOpen;
  }
  
  // Toggle dark mode
  function toggleDarkMode() {
    darkMode.toggleTheme();
  }
</script>

<div class="app-container">
  <Sidebar onUserProfileClick={toggleUserProfile} />
  
  <!-- Always show ChatInterface regardless of mode or record type -->
  <ChatInterface />
  
  <!-- User Profile Panel -->
  <UserProfile isOpen={isUserProfileOpen} />
  
  <!-- CSS Variables -->
  <div class="css-variables"></div>
</div>

<style>
  .app-container {
    width: 100%;
    height: 100vh;
    display: flex;
    overflow: hidden;
    background-color: var(--background-color, #ffffff);
    position: relative;
  }
  
  /* CSS Variables */
  .css-variables {
    display: none;
    
    /* Colors */
    --primary-color: #3b82f6;
    --primary-hover: #2563eb;
    --text-color: #333333;
    --light-text: #666666;
    --border-color: #e0e0e0;
    --system-msg-bg: #f5f5f5;
    --user-msg-bg: #eeeeee;
    --assistant-msg-bg: #f8f8f8;
    --shadow-color: rgba(0, 0, 0, 0.05);
    --background-color: #ffffff;
    --header-bg: #f9f9f9;
    --hover-color: #f0f0f0;
    --active-color: #e8e8e8;
    --sidebar-bg: #f0f2f5;
    --sidebar-width: 280px;
    
    /* Agent-specific colors */
    --agent-all-color: #3b82f6;
    --agent-ninja-color: #8b5cf6;
    --agent-responder-color: #10b981;
    --agent-persephone-color: #ec4899;
    --agent-system-color: #64748b;
    --agent-librarian-color: #eab308;
    --agent-butterfly-color: #06b6d4;
    
    /* Record-specific colors */
    --record-submissions-color: #f59e0b;
    --record-files-color: #6366f1;
    --record-voice-color: #ec4899;
    --record-video-color: #ef4444;
    --record-photos-color: #14b8a6;
  }
  
  /* Dark mode would be defined here */
  @media (prefers-color-scheme: dark) {
    :global(html.dark) {
      /* Dark mode color overrides */
    }
  }
</style> 