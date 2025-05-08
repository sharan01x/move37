import { writable, derived } from 'svelte/store';
import type { Writable, Readable } from 'svelte/store';
import { get } from 'svelte/store';

// Define types for agents
interface Agent {
    id: string;
    name: string;
    description: string;
    icon: string;
    color: string;
    hidden?: boolean;
}

interface Message {
    id: string;
    content: string;
    timestamp: Date;
    sender: string;
    agentId: string;
    status?: 'sending' | 'sent' | 'error';
    [key: string]: any;
}

type ConversationHistoryMap = Record<string, Message[]>;

// Agent definitions
const agentDefinitions: Agent[] = [
    {
        id: 'thinker',
        name: 'Thinker',
        description: 'Get thoughtful answers',
        icon: 'brain',
        color: 'blue'
    },
    {
        id: 'first_responder',
        name: 'First Responder',
        description: 'General knowledge specialist',
        icon: 'comment-medical',
        color: 'green'
    },
    {
        id: 'number_ninja',
        name: 'Number Ninja',
        description: 'Math specialist',
        icon: 'calculator',
        color: 'purple'
    },
    {
        id: 'persephone',
        name: 'Persephone',
        description: 'Personal information specialist',
        icon: 'user-circle',
        color: 'pink'
    },
    {
        id: 'librarian',
        name: 'Librarian',
        description: 'File information specialist',
        icon: 'file-alt',
        color: 'orange'
    },
    {
        id: 'butterfly',
        name: 'Butterfly',
        description: 'Social media poster',
        icon: 'broadcast-tower',
        color: 'teal'
    },
    // Add Submissions and Files as regular agents
    {
        id: 'submissions',
        name: 'Submissions',
        description: 'Record text notes',
        icon: 'edit',
        color: 'amber'
    },
    {
        id: 'files',
        name: 'Files',
        description: 'Upload documents',
        icon: 'file-alt',
        color: 'blue'
    },
    {
        id: 'system',
        name: 'System',
        description: 'System messages',
        icon: 'cog',
        color: 'gray',
        hidden: true // Not shown in sidebar
    }
];

// Initialize agents store with definitions
export const agents: Writable<Agent[]> = writable(agentDefinitions);

// Store for the active agent
export const activeAgent: Writable<string> = writable('thinker');

// Conversation history for all agents
export const conversationHistory: Writable<ConversationHistoryMap> = writable({
    'thinker': [],
    'first_responder': [],
    'number_ninja': [],
    'persephone': [],
    'librarian': [],
    'butterfly': [],
    'submissions': [],
    'files': []
});

// Derived store to get the current agent's details
export const currentAgent: Readable<Agent> = derived(
    [activeAgent, agents], 
    ([$activeAgent, $agents]) => {
        return $agents.find(agent => agent.id === $activeAgent) || $agents[0];
    }
);

// Derived store to get the current conversation
export const currentConversation: Readable<Message[]> = derived(
    [activeAgent, conversationHistory], 
    ([$activeAgent, $conversationHistory]) => {
        return $conversationHistory[$activeAgent] || [];
    }
);

// Helper functions for managing conversations
export function addMessageToConversation(agentId: string, message: Message, replace: boolean = false): void {
    conversationHistory.update(histories => {
        if (!histories[agentId]) {
            histories[agentId] = [];
        }
        
        if (replace) {
            // Replace existing message with the same id if found
            const messageIndex = histories[agentId].findIndex(msg => msg.id === message.id);
            if (messageIndex >= 0) {
                histories[agentId] = [
                    ...histories[agentId].slice(0, messageIndex),
                    message,
                    ...histories[agentId].slice(messageIndex + 1)
                ];
            } else {
                // If not found, just add it
                histories[agentId] = [...histories[agentId], message];
            }
        } else {
            // Simply add the message to history
        histories[agentId] = [...histories[agentId], message];
        }
        
        return histories;
    });
}

export function clearConversation(agentId: string): void {
    conversationHistory.update(histories => {
        histories[agentId] = [];
        return histories;
    });
}

export function clearAllConversations(): void {
    conversationHistory.update(histories => {
        Object.keys(histories).forEach(key => {
            histories[key] = [];
        });
        return histories;
    });
}

export function setActiveAgent(agentId: string): void {
    activeAgent.set(agentId);
} 