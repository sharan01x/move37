<script lang="ts">
  import { onMount } from 'svelte';
  import Sidebar from './Sidebar.svelte';
  import { darkMode } from '$lib/stores/themeStore';
  import { setActiveSidebarItem } from '$lib/stores/sidebarStore';
  
  // Props
  export let showSidebar = true;
  export let showUserPanel = false;
  
  // State
  let isMobile = false;
  let sidebarVisible = showSidebar && !isMobile;

  // Handle window resize for responsive layout
  function handleResize() {
    isMobile = window.innerWidth < 768;
    sidebarVisible = showSidebar && !isMobile;
  }
  
  // Toggle sidebar visibility (especially for mobile)
  function toggleSidebar() {
    sidebarVisible = !sidebarVisible;
  }
  
  // Function to handle item selection
  function handleItemSelect(id: string) {
    setActiveSidebarItem(id);
  }
  
  // This function isn't actually used to toggle the profile directly
  // It's used as a placeholder for the close button
  function toggleUserPanel() {
    // The actual toggle happens via the global event handler
    // This is just to have a function to bind to the close button
  }

  // Initialize on mount
  onMount(() => {
    handleResize();
    window.addEventListener('resize', handleResize);
    
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  });
</script>

<div class="app-layout {$darkMode ? 'dark-mode' : 'light-mode'}">
  <!-- Mobile Header (only visible on mobile) -->
  {#if isMobile}
    <div class="mobile-header">
      <button class="menu-button" on:click={toggleSidebar} aria-label="Toggle menu">
        <i class="fas fa-bars"></i>
      </button>
      <img 
        src={$darkMode ? "/images/Move37Logo-DarkBackground.png" : "/images/Move37Logo-TransparentBackground.png"} 
        alt="Move 37 Logo" 
        class="mobile-logo" 
      />
      <button class="user-button user-profile-button" aria-label="Toggle user panel">
        <i class="fas fa-user"></i>
      </button>
    </div>
  {/if}
  
  <!-- App Content -->
  <div class="app-content">
    <!-- Sidebar (collapsible on mobile) -->
    {#if sidebarVisible}
      <div class="sidebar-container" class:mobile={isMobile}>
        {#if isMobile}
          <button class="close-sidebar" on:click={toggleSidebar}>
            <i class="fas fa-times"></i>
          </button>
        {/if}
        <Sidebar isMobile={isMobile} />
      </div>
    {/if}
    
    <!-- Main Content Area -->
    <main class="main-content">
      <slot />
    </main>
    
    <!-- User Panel (optional) -->
    {#if showUserPanel}
      <div class="user-panel" class:mobile={isMobile}>
        {#if isMobile}
          <button class="close-panel user-profile-button" aria-label="Close panel">
            <i class="fas fa-times"></i>
          </button>
        {/if}
        <div class="user-panel-content">
          <slot name="user-panel" />
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .app-layout {
    display: flex;
    flex-direction: column;
    height: 100vh;
    width: 100%;
    overflow: hidden;
    background-color: var(--background-color, #ffffff);
    color: var(--text-color, #333333);
  }
  
  .app-content {
    display: flex;
    flex: 1;
    overflow: hidden;
    position: relative;
  }
  
  .sidebar-container {
    position: relative;
    height: 100%;
    z-index: 10;
    transition: transform 0.3s ease;
    overflow-y: auto;
  }
  
  .sidebar-container.mobile {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
  }
  
  .main-content {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  
  .user-panel {
    width: 300px;
    height: 100%;
    border-left: 1px solid var(--border-color, #e0e0e0);
    background-color: var(--background-color, #ffffff);
    overflow-y: auto;
    z-index: 20;
  }
  
  .user-panel.mobile {
    position: absolute;
    top: 0;
    right: 0;
    height: 100%;
    box-shadow: -2px 0 10px rgba(0, 0, 0, 0.1);
  }
  
  .user-panel-content {
    padding: 1rem;
  }
  
  .mobile-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem;
    background-color: var(--header-bg, #f9f9f9);
    border-bottom: 1px solid var(--border-color, #e0e0e0);
    z-index: 5;
  }
  
  .mobile-logo {
    max-width: 150px;
    height: auto;
  }
  
  .mobile-header h1 {
    font-size: 1.25rem;
    font-weight: 600;
    margin: 0;
  }
  
  .menu-button, .user-button, .close-sidebar, .close-panel {
    background: none;
    border: none;
    font-size: 1.25rem;
    color: var(--text-color, #333333);
    cursor: pointer;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    transition: background-color 0.2s;
  }
  
  .menu-button:hover, .user-button:hover, .close-sidebar:hover, .close-panel:hover {
    background-color: var(--hover-color, #f0f0f0);
  }
  
  .close-sidebar, .close-panel {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    font-size: 1rem;
    z-index: 11;
  }
  
  @media (max-width: 768px) {
    .app-layout {
      display: flex;
      flex-direction: column;
    }
  }
  
  /* Custom scrollbar styles - add to any scrollable container */
  :global(*::-webkit-scrollbar) {
    width: 6px;
    height: 6px;
  }
  
  :global(*::-webkit-scrollbar-track) {
    background: transparent;
  }
  
  :global(*::-webkit-scrollbar-thumb) {
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 10px;
  }
  
  :global(*::-webkit-scrollbar-thumb:hover) {
    background-color: rgba(0, 0, 0, 0.3);
  }
  
  :global(:is(.dark-mode) *::-webkit-scrollbar-thumb) {
    background-color: rgba(255, 255, 255, 0.2);
  }
  
  :global(:is(.dark-mode) *::-webkit-scrollbar-thumb:hover) {
    background-color: rgba(255, 255, 255, 0.3);
  }
</style> 