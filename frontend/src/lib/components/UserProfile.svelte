<script lang="ts">
  import { onMount } from 'svelte';
  import { 
    userFacts, 
    filteredFacts, 
    currentCategory, 
    isLoading, 
    error,
    loadUserFacts, 
    deleteFact,
    filterByCategory,
    factCategories 
  } from '$lib/stores/userFactsStore';
  import { formatDateTimeForDisplay } from '$lib/utils/dateUtils';
  
  // Props
  export let isOpen = false;
  
  // User ID - in a real app, this would come from an auth store
  let userId = 'default';
  let isEditing = false;
  let tempUserId = userId;
  
  // Load user facts on mount
  onMount(() => {
    // Load facts on mount if the panel is open
    if (isOpen) {
      loadUserFacts(userId);
    }
    
    // Listen for refresh events
    const handleRefreshEvent = (event: CustomEvent) => {
      const detail = event.detail || {};
      const refreshUserId = detail.userId || userId;
      loadUserFacts(refreshUserId);
    };
    
    document.addEventListener('refresh-user-facts', handleRefreshEvent as EventListener);
    
    return () => {
      document.removeEventListener('refresh-user-facts', handleRefreshEvent as EventListener);
    };
  });
  
  // Watch for panel open state to load facts when opened
  $: if (isOpen) {
    loadUserFacts(userId);
  }
  
  // Make user ID editable
  function startEditing() {
    isEditing = true;
    tempUserId = userId;
    setTimeout(() => {
      const inputElement = document.getElementById('userIdInput');
      if (inputElement) {
        inputElement.focus();
      }
    }, 10);
  }
  
  function saveUserId() {
    if (tempUserId.trim() !== '') {
      userId = tempUserId.trim();
    } else {
      tempUserId = userId;
    }
    isEditing = false;
    
    // Reload facts with new user ID
    loadUserFacts(userId);
  }
  
  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      saveUserId();
    } else if (event.key === 'Escape') {
      isEditing = false;
      tempUserId = userId;
    }
  }
  
  // Confirm and delete a fact
  async function handleDeleteFact(factId: string) {
    if (confirm('Are you sure you want to delete this fact?')) {
      const success = await deleteFact(userId, factId);
      if (!success) {
        alert('Failed to delete the fact. Please try again.');
      }
      // The WebSocket handler will update the store if successful
    }
  }
  
  // Format category name for display
  function formatCategory(category: string): string {
    return category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }
</script>

<div class="user-profile-panel" class:active={isOpen}>
  <div class="panel-header">
    <div class="panel-title">
      <h2>User Profile</h2>
      {#if isEditing}
        <input 
          id="userIdInput" 
          bind:value={tempUserId} 
          on:blur={saveUserId}
          on:keydown={handleKeydown}
          class="user-id-input"
        />
      {:else}
        <span 
          id="userIdDisplay" 
          class="user-id" 
          title="Click to edit"
          on:click={startEditing}
        >
          {userId}
        </span>
      {/if}
    </div>
    <button class="close-btn" on:click={() => isOpen = false} aria-label="Close profile panel">
      <i class="fas fa-times"></i>
    </button>
  </div>
  
  <div class="panel-content">
    <div class="user-facts-section">
      <h3>What I Know About You</h3>
      
      <div class="facts-filters">
        {#each factCategories as category}
          <button 
            class="filter-btn" 
            class:active={$currentCategory === category}
            data-category={category}
            on:click={() => filterByCategory(category)}
          >
            {category === 'all' ? 'All' : formatCategory(category)}
          </button>
        {/each}
      </div>
      
      <div class="user-facts-list">
        {#if $isLoading}
          <div class="loading-facts">Loading your information...</div>
        {:else if $error}
          <div class="loading-facts error">{$error}</div>
        {:else if $filteredFacts.length === 0}
          {#if $userFacts.length === 0}
            <div class="loading-facts">No information available yet.</div>
          {:else}
            <div class="loading-facts">No information in the "{formatCategory($currentCategory)}" category.</div>
          {/if}
        {:else}
          {#each $filteredFacts as fact (fact.id)}
            <div class="fact-item" data-id={fact.id}>
              <div class="fact-content">{fact.fact}</div>
              <div class="fact-metadata">
                <span class="fact-category">{formatCategory(fact.category)}</span>
                <span class="fact-date">Recorded: {formatDateTimeForDisplay(new Date(fact.recorded_at || fact.created_at || ''))}</span>
              </div>
              <div class="fact-actions">
                <button class="fact-action-btn delete-btn" on:click={() => handleDeleteFact(fact.id)}>
                  <i class="fas fa-trash"></i>
                </button>
              </div>
            </div>
          {/each}
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .user-profile-panel {
    position: fixed;
    top: 0;
    right: -350px;
    width: 350px;
    height: 100vh;
    background-color: var(--background-color, white);
    box-shadow: -2px 0 10px rgba(0, 0, 0, 0.1);
    transition: right 0.3s ease;
    z-index: 1000;
    display: flex;
    flex-direction: column;
    border-left: 1px solid var(--border-color, #e0e0e0);
  }

  .user-profile-panel.active {
    right: 0;
  }

  .panel-header {
    padding: 1rem;
    border-bottom: 1px solid var(--border-color, #e0e0e0);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .panel-title {
    display: flex;
    flex-direction: column;
  }

  .panel-header h2 {
    margin: 0;
    font-size: 1.2rem;
    font-weight: 600;
  }

  .panel-header .user-id {
    font-size: 0.85rem;
    color: var(--light-text, #666666);
    margin-top: 0.25rem;
    cursor: pointer;
  }

  .panel-header .user-id:hover {
    text-decoration: underline;
  }

  .user-id-input {
    font-size: 0.85rem;
    padding: 0.25rem;
    border: 1px solid var(--primary-color, #3b82f6);
    border-radius: 4px;
    outline: none;
    margin-top: 0.25rem;
  }

  .close-btn {
    background: none;
    border: none;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: var(--light-text, #666666);
    transition: background-color 0.2s;
  }

  .close-btn:hover {
    background-color: var(--hover-color, #f0f0f0);
    color: var(--text-color, #333333);
  }

  .panel-content {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
  }

  .user-facts-section h3 {
    font-size: 1.1rem;
    margin-bottom: 1rem;
    font-weight: 500;
  }

  .facts-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }

  .filter-btn {
    background-color: var(--background-color, white);
    border: 1px solid var(--border-color, #e0e0e0);
    border-radius: 20px;
    padding: 0.25rem 0.75rem;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s;
  }

  .filter-btn:hover {
    background-color: var(--hover-color, #f0f0f0);
  }

  .filter-btn.active {
    background-color: var(--primary-color, #3b82f6);
    color: white;
    border-color: var(--primary-color, #3b82f6);
  }

  .user-facts-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .fact-item {
    background-color: var(--background-color, white);
    border: 1px solid var(--border-color, #e0e0e0);
    border-radius: 8px;
    padding: 0.75rem;
    position: relative;
  }

  .fact-content {
    font-size: 0.9rem;
    margin-bottom: 0.25rem;
  }

  .fact-metadata {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .fact-category {
    font-size: 0.75rem;
    color: var(--light-text, #666666);
    background-color: var(--system-msg-bg, #f5f5f5);
    border-radius: 4px;
    padding: 0.1rem 0.35rem;
    display: inline-block;
    text-transform: capitalize;
  }

  .fact-date {
    font-size: 0.75rem;
    color: var(--light-text, #666666);
    display: inline-block;
  }

  .fact-actions {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
  }

  .fact-action-btn {
    background: none;
    border: none;
    font-size: 0.85rem;
    color: var(--light-text, #666666);
    cursor: pointer;
    padding: 0.25rem;
  }

  .fact-action-btn:hover {
    color: var(--text-color, #333333);
  }

  .delete-btn:hover {
    color: #d32f2f;
  }

  .loading-facts {
    text-align: center;
    padding: 2rem 0;
    color: var(--light-text, #666666);
    font-size: 0.9rem;
  }

  .loading-facts.error {
    color: #d32f2f;
  }

  @media (max-width: 768px) {
    .user-profile-panel {
      width: 100%;
      right: -100%;
    }
  }
</style> 