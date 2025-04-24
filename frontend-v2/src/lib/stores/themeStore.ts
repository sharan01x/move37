import { writable } from 'svelte/store';
import { browser } from '$app/environment';

// Initialize theme from localStorage or default to light mode
function createThemeStore() {
  // Default to light mode (false means light mode)
  const initialValue = browser 
    ? localStorage.getItem('darkMode') === 'true' 
    : false;
  
  // Set initial document class if in browser
  if (browser) {
    if (initialValue) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }
  
  const { subscribe, set, update } = writable(initialValue);

  return {
    subscribe,
    toggleTheme: () => {
      update(darkMode => {
        const newValue = !darkMode;
        if (browser) {
          // Update document class
          if (newValue) {
            document.documentElement.classList.add('dark');
          } else {
            document.documentElement.classList.remove('dark');
          }
          // Save to localStorage
          localStorage.setItem('darkMode', String(newValue));
        }
        return newValue;
      });
    },
    setDarkMode: (value: boolean) => {
      set(value);
      if (browser) {
        // Update document class
        if (value) {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
        // Save to localStorage
        localStorage.setItem('darkMode', String(value));
      }
    }
  };
}

export const darkMode = createThemeStore(); 