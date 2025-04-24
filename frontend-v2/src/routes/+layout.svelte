<script>
	import '../app.postcss';
	import { darkMode } from '$lib/stores/themeStore';
	import { onMount } from 'svelte';
	import AppLayout from '$lib/components/AppLayout.svelte';
	import UserProfile from '$lib/components/UserProfile.svelte';
	import ThemeInitializer from '$lib/components/ThemeInitializer.svelte';
	import WebSocketNotification from '$lib/components/WebSocketNotification.svelte';
	import WebSocketInitializer from '$lib/components/WebSocketInitializer.svelte';
	import { writable } from 'svelte/store';
	
	// Store to manage user profile panel visibility
	const isUserProfileOpen = writable(false);
	
	// Initialize on mount
	onMount(() => {
		// Listen for user profile button clicks (delegated event)
		const handleProfileButtonClick = (event) => {
			const target = event.target;
			const profileButton = target.closest('.user-profile-button');
			if (profileButton) {
				isUserProfileOpen.update(value => !value);
			}
		};
		
		document.addEventListener('click', handleProfileButtonClick);
		
		return () => {
			document.removeEventListener('click', handleProfileButtonClick);
		};
	});
</script>

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
		--text-color: #e2e8f0;
		--light-text: #94a3b8;
		--border-color: #2d3748;
		--system-msg-bg: #1e293b;
		--user-msg-bg: #334155;
		--assistant-msg-bg: #1e293b;
		--background-color: #111827;
		--header-bg: #1f2937;
		--hover-color: #1f2937;
		--active-color: #2d3748;
		--sidebar-bg: #1a202c;
	}
</style> 