import { writable, derived } from 'svelte/store';
import type { Writable, Readable } from 'svelte/store';
import { sendMessage } from '$lib/services/websocket';

export interface UserFact {
    id: string;
    fact: string;
    category: string;
    recorded_at: string;
    created_at?: string;
    user_id: string;
}

// Categories that we support for user facts
export const factCategories = [
    'all',
    'personal_info',
    'preference',
    'habit',
    'goal',
    'relationship'
];

// State for user facts
export const userFacts: Writable<UserFact[]> = writable([]);
export const isLoading: Writable<boolean> = writable(false);
export const error: Writable<string | null> = writable(null);
export const currentCategory: Writable<string> = writable('all');

// Derived store for filtered facts
export const filteredFacts: Readable<UserFact[]> = derived(
    [userFacts, currentCategory],
    ([$userFacts, $currentCategory]) => {
        if ($currentCategory === 'all') {
            return $userFacts;
        }
        return $userFacts.filter(fact => fact.category === $currentCategory);
    }
);

// Filter facts by category
export function filterByCategory(category: string): void {
    currentCategory.set(category);
}

// Load user facts from the server
export async function loadUserFacts(userId: string): Promise<void> {
    isLoading.set(true);
    error.set(null);
    
    try {
        // Generate a request ID
        const requestId = generateQueryId();
        
        // Send the request via WebSocket
        const success = sendMessage('recall', {
            type: "user_facts_get",
            request_id: requestId,
            data: {
                user_id: userId
            }
        });
        
        if (!success) {
            throw new Error('Failed to send user facts request');
        }
        
        console.log('Sent user facts request via WebSocket');
        
        // Note: The actual response will be handled by the WebSocket message handler
        // which will update the store. This function just initiates the request.
    } catch (err) {
        console.error('Error loading user facts:', err);
        error.set(err instanceof Error ? err.message : 'Failed to load user facts');
        isLoading.set(false);
    }
}

// Delete a user fact
export async function deleteFact(userId: string, factId: string): Promise<boolean> {
    try {
        // Generate a request ID
        const requestId = generateQueryId();
        
        // Send the delete request via WebSocket
        const success = sendMessage('record', {
            type: "user_facts_delete",
            request_id: requestId,
            data: {
                user_id: userId,
                fact_id: factId
            }
        });
        
        if (!success) {
            throw new Error('Failed to send fact deletion request');
        }
        
        console.log('Sent fact deletion request via WebSocket');
        return true;
        
        // Note: The actual response will be handled by the WebSocket message handler
    } catch (err) {
        console.error('Error deleting fact:', err);
        return false;
    }
}

// Update user facts in the store
export function updateUserFacts(facts: UserFact[]): void {
    // Sort facts by recording date (newest first)
    const sortedFacts = [...facts].sort((a, b) => 
        new Date(b.recorded_at || b.created_at || '').getTime() - 
        new Date(a.recorded_at || a.created_at || '').getTime()
    );
    
    userFacts.set(sortedFacts);
    isLoading.set(false);
}

// Generate a unique query ID (helper function)
function generateQueryId(): string {
    return 'q_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Declare the WebSocket connections for TypeScript
declare global {
    interface Window {
        recallWsConnection: WebSocket;
        recordWsConnection: WebSocket;
    }
} 