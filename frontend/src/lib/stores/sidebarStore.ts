import { writable, derived } from 'svelte/store';
import { activeAgent, agents } from './agentsStore';

// Track the currently active sidebar item
export const activeSidebarItem = writable<string>('all'); // Default to 'all' (Group Chat)

// Initialize from existing stores
activeAgent.subscribe(id => {
  activeSidebarItem.set(id);
});

// Helper function to set the active sidebar item
export function setActiveSidebarItem(id: string): void {
  activeSidebarItem.set(id);
  activeAgent.set(id);
}

// Create a derived store to check if an item is active
export function createIsActiveStore(id: string) {
  return derived(
    activeSidebarItem,
    $activeSidebarItem => $activeSidebarItem === id
  );
} 