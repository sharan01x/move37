<script lang="ts">
  import { connectionStatus, isConnected, isReconnecting, reconnectCount, ConnectionStatus, recallWsService, recordWsService } from '$lib/services/websocketService';
  
  export let showReconnectButton = true;
  export let showAlways = false; // If true, always show status. If false, only show on non-connected states
  
  function reconnect() {
    recallWsService.connect();
    recordWsService.connect();
  }
  
  // Map status to display details
  $: statusDetails = {
    [ConnectionStatus.CONNECTED]: {
      text: 'Connected',
      icon: 'fa-check-circle',
      color: 'text-green-500',
      background: 'bg-green-100 dark:bg-green-900/20'
    },
    [ConnectionStatus.CONNECTING]: {
      text: 'Connecting',
      icon: 'fa-sync fa-spin',
      color: 'text-blue-500',
      background: 'bg-blue-100 dark:bg-blue-900/20'
    },
    [ConnectionStatus.DISCONNECTED]: {
      text: 'Disconnected',
      icon: 'fa-times-circle',
      color: 'text-orange-500',
      background: 'bg-orange-100 dark:bg-orange-900/20'
    },
    [ConnectionStatus.ERROR]: {
      text: 'Connection Error',
      icon: 'fa-exclamation-triangle',
      color: 'text-red-500',
      background: 'bg-red-100 dark:bg-red-900/20'
    }
  };
  
  $: currentStatus = statusDetails[$connectionStatus];
  $: showStatus = showAlways || !$isConnected;
</script>

{#if showStatus}
  <div class="connection-status {currentStatus.background}">
    <div class="status-content">
      <i class="fas {currentStatus.icon} {currentStatus.color}"></i>
      <span class="status-text">
        {currentStatus.text}
        {#if $isReconnecting}
          (Attempt {$reconnectCount})
        {/if}
      </span>
    </div>
    
    {#if showReconnectButton && ($connectionStatus === ConnectionStatus.DISCONNECTED || $connectionStatus === ConnectionStatus.ERROR)}
      <button class="reconnect-button" on:click={reconnect}>
        <i class="fas fa-sync-alt"></i>
        Reconnect
      </button>
    {/if}
  </div>
{/if}

<style>
  .connection-status {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 1rem;
    border-radius: 0.25rem;
    margin-bottom: 0.5rem;
    transition: all 0.2s ease;
  }
  
  .status-content {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  
  .status-text {
    font-size: 0.875rem;
    font-weight: 500;
  }
  
  .reconnect-button {
    background: none;
    border: 1px solid var(--border-color, #e0e0e0);
    border-radius: 0.25rem;
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.25rem;
    transition: all 0.2s ease;
  }
  
  .reconnect-button:hover {
    background-color: var(--hover-color, #f0f0f0);
  }
  
  /* Animation for the spinning icon */
  :global(.fa-spin) {
    animation: spin 1s infinite linear;
  }
  
  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }
</style> 