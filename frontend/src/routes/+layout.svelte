<script lang="ts">
	import '../app.postcss';
	import { darkMode } from '$lib/stores/themeStore';
	import { onMount } from 'svelte';
	import AppLayout from '$lib/components/AppLayout.svelte';
	import UserProfile from '$lib/components/UserProfile.svelte';
	import ThemeInitializer from '$lib/components/ThemeInitializer.svelte';
	import WebSocketNotification from '$lib/components/WebSocketNotification.svelte';
	import WebSocketInitializer from '$lib/components/WebSocketInitializer.svelte';
	import { writable, type Writable } from 'svelte/store';
	import { initializeUserId } from '$lib/stores/chatStore';
	
	// Create a global store for user profile panel visibility
	// Using a context instead of window property for better TypeScript integration
	const isUserProfileOpen = writable(false);
	
	// Initialize on mount
	onMount(() => {
		// Initialize user ID
		initializeUserId();
		
		// Listen for user profile button clicks (delegated event)
		const handleProfileButtonClick = (event: MouseEvent) => {
			const target = event.target as HTMLElement;
			const profileButton = target.closest('.user-profile-button');
			if (profileButton) {
				isUserProfileOpen.update(value => !value);
			}
		};
		
		document.addEventListener('click', handleProfileButtonClick as EventListener);
		
		return () => {
			document.removeEventListener('click', handleProfileButtonClick as EventListener);
		};
	});
</script>

<svelte:head>
	<link rel="icon" type="image/x-icon" href="/images/favicon.ico" />
	<link rel="icon" type="image/svg+xml" href="/images/favicon.svg" />
	<link rel="icon" type="image/png" sizes="96x96" href="/images/favicon-96x96.png" />
</svelte:head>

<!-- Initialize theme -->
<ThemeInitializer />

<!-- WebSocket notifications -->
<WebSocketNotification />

<!-- Initialize WebSocket handlers -->
<WebSocketInitializer />

<!-- User Profile Panel -->
<UserProfile isOpen={$isUserProfileOpen} />

<AppLayout>
	<slot />
</AppLayout>

<style>
	:global(:root) {
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
	:global(html.dark) {
		/* Dark mode color overrides */
		--text-color: #e0e0e0;
		--light-text: #a0a0a0;
		--border-color: #333333;
		--system-msg-bg: #222222;
		--user-msg-bg: #333333;
		--assistant-msg-bg: #222222;
		--background-color: #1a1a1a;
		--header-bg: #232323;
		--hover-color: #2c2c2c;
		--active-color: #333333;
		--sidebar-bg: #212121;
	}
</style> 