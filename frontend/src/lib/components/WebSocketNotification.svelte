<script lang="ts">
  import { wsNotifications, dismissNotification } from '$lib/stores/websocketStore';
  
  function handleDismiss() {
    dismissNotification();
  }
  
  // Map notification types to styling
  $: typeStyles = {
    'info': {
      bg: 'bg-blue-100 dark:bg-blue-900/20',
      icon: 'fa-info-circle',
      color: 'text-blue-500'
    },
    'success': {
      bg: 'bg-green-100 dark:bg-green-900/20',
      icon: 'fa-check-circle',
      color: 'text-green-500'
    },
    'warning': {
      bg: 'bg-orange-100 dark:bg-orange-900/20',
      icon: 'fa-exclamation-circle',
      color: 'text-orange-500'
    },
    'error': {
      bg: 'bg-red-100 dark:bg-red-900/20',
      icon: 'fa-exclamation-triangle',
      color: 'text-red-500'
    }
  };
  
  $: currentStyle = typeStyles[$wsNotifications.type];
</script>

{#if $wsNotifications.show}
  <div class="notification {currentStyle.bg}" role="alert">
    <div class="notification-content">
      <i class="fas {currentStyle.icon} {currentStyle.color}"></i>
      <span class="notification-message">{$wsNotifications.message}</span>
    </div>
    <button class="dismiss-button" on:click={handleDismiss} aria-label="Dismiss">
      <i class="fas fa-times"></i>
    </button>
  </div>
{/if}

<style>
  .notification {
    position: fixed;
    top: 1rem;
    right: 1rem;
    min-width: 300px;
    max-width: 400px;
    padding: 0.75rem 1rem;
    border-radius: 0.375rem;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    z-index: 50;
    display: flex;
    align-items: center;
    justify-content: space-between;
    animation: slideIn 0.3s ease-out;
  }
  
  .notification-content {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  
  .notification-message {
    font-size: 0.875rem;
    font-weight: 500;
  }
  
  .dismiss-button {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0.25rem;
    color: var(--light-text, #666666);
    transition: color 0.2s;
  }
  
  .dismiss-button:hover {
    color: var(--text-color, #333333);
  }
  
  @keyframes slideIn {
    from {
      transform: translateX(100%);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
</style> 