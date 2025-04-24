<script lang="ts">
  import { onMount } from 'svelte';
  import { slide } from 'svelte/transition';
  import { agents, setActiveAgent } from '$lib/stores/agentsStore';
  import { darkMode } from '$lib/stores/themeStore';
  import { activeSidebarItem, setActiveSidebarItem } from '$lib/stores/sidebarStore';
  
  // Props
  export let onUserProfileClick: () => void;
  
  // Function to handle item selection
  function handleItemSelect(id: string) {
    setActiveSidebarItem(id);
  }
</script>

<div class="sidebar">
  <div class="sidebar-header">
    <h1>LifeScribe</h1>
  </div>
  
  <div class="conversation-list">
    <!-- Agents Section -->
    <div class="conversation-group">
      {#each $agents.filter(agent => !agent.hidden) as agent}
        <div 
          class="conversation-item {$activeSidebarItem === agent.id ? 'active' : ''}" 
          on:click={() => handleItemSelect(agent.id)}
        >
          <div class="conversation-icon {agent.id}">
            <i class="fas fa-{agent.icon}"></i>
          </div>
          <div class="conversation-info">
            <div class="conversation-name">{agent.name}</div>
            <div class="conversation-description">{agent.description}</div>
          </div>
        </div>
      {/each}
    </div>
  </div>
  
  <div class="sidebar-footer">
    <div id="userProfileButton" class="user-profile-button" on:click={onUserProfileClick}>
      <i class="fas fa-user-circle"></i>
      <span>User Profile</span>
    </div>
  </div>
</div>

<style>
  /* Sidebar Styles */
  .sidebar {
    width: var(--sidebar-width, 280px);
    height: 100%;
    background-color: var(--sidebar-bg, #f0f2f5);
    border-right: 1px solid var(--border-color, #e0e0e0);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .sidebar-header {
    padding: 1rem;
    border-bottom: 1px solid var(--border-color, #e0e0e0);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .sidebar-header h1 {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-color, #333333);
  }

  .conversation-list {
    flex: 1;
    overflow-y: auto;
    padding: 1rem 0;
  }
  
  /* Custom scrollbar styles */
  .conversation-list::-webkit-scrollbar {
    width: 5px;
  }
  
  .conversation-list::-webkit-scrollbar-track {
    background: transparent;
  }
  
  .conversation-list::-webkit-scrollbar-thumb {
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 10px;
  }
  
  .conversation-list:hover::-webkit-scrollbar-thumb {
    background-color: rgba(0, 0, 0, 0.3);
  }

  .conversation-group {
    margin-bottom: 1rem;
  }

  .conversation-item {
    display: flex;
    align-items: center;
    padding: 0.75rem 1rem;
    cursor: pointer;
    transition: background-color 0.2s;
    border-radius: 8px;
    margin: 0 0.5rem 0.5rem 0.5rem;
  }

  .conversation-item:hover {
    background-color: var(--hover-color, #f0f0f0);
  }

  .conversation-item.active {
    background-color: var(--active-color, #e8e8e8);
  }

  .conversation-icon {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 0.75rem;
    color: white;
  }

  /* Agent icons */
  .conversation-icon.all {
    background-color: var(--agent-all-color, #3b82f6);
  }

  .conversation-icon.number_ninja {
    background-color: var(--agent-ninja-color, #8b5cf6);
  }

  .conversation-icon.first_responder {
    background-color: var(--agent-responder-color, #10b981);
  }

  .conversation-icon.persephone {
    background-color: var(--agent-persephone-color, #ec4899);
  }

  .conversation-icon.librarian {
    background-color: var(--agent-librarian-color, #eab308);
  }

  .conversation-icon.butterfly {
    background-color: var(--agent-butterfly-color, #06b6d4);
  }

  /* Submissions and Files icons */
  .conversation-icon.submissions {
    background-color: var(--record-submissions-color, #f59e0b);
  }

  .conversation-icon.files {
    background-color: var(--record-files-color, #6366f1);
  }

  .conversation-info {
    flex: 1;
  }

  .conversation-name {
    font-weight: 500;
    font-size: 0.9rem;
  }

  .conversation-description {
    font-size: 0.75rem;
    color: var(--light-text, #666666);
  }

  .sidebar-footer {
    padding: 1rem;
    border-top: 1px solid var(--border-color, #e0e0e0);
  }

  .user-profile-button {
    display: flex;
    align-items: center;
    padding: 0.5rem;
    border-radius: 8px;
    cursor: pointer;
    transition: background-color 0.2s;
  }

  .user-profile-button:hover {
    background-color: var(--hover-color, #f0f0f0);
  }

  .user-profile-button i {
    margin-right: 0.5rem;
  }
  
  /* For mobile */
  @media (max-width: 768px) {
    .sidebar {
      width: 260px;
    }
  }
</style> 