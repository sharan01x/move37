<script>
  import { onMount } from 'svelte';
  import { darkMode } from '$lib/stores/themeStore';

  // Ensure the theme is correctly applied on first load
  onMount(() => {
    // Force dark mode to initialize to light mode (false) on first load
    if (localStorage.getItem('darkMode') === null) {
      darkMode.setDarkMode(false);
    }
    
    // Subscribe to darkMode changes
    const unsubscribe = darkMode.subscribe(value => {
      if (value) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    });
    
    return unsubscribe;
  });
</script>

<!-- This component has no visual elements, it just initializes the theme --> 