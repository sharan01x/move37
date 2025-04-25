import { writable, derived, get } from 'svelte/store';
import type { Writable } from 'svelte/store';
import { activeAgent, addMessageToConversation } from './agentsStore';
import { v4 as uuidv4 } from 'uuid';
import type { UserFact } from './userFactsStore';

// Function to get current date time string (moved here to avoid external dependency)
function getCurrentDateTimeString(): string {
    return new Date().toISOString();
}

// Define message types
export const MESSAGE_TYPE = {
    USER: 'user',
    AGENT: 'agent',
    SYSTEM: 'system',
    STATUS: 'status_update'
} as const;

export type MessageType = typeof MESSAGE_TYPE[keyof typeof MESSAGE_TYPE];

// Define interface for a message
export interface FileAttachment {
    id: string;
    name: string;
    type: string;
    size: number;
    content?: string;
    file?: File;
}

export interface Message {
    id: string;
    type: MessageType;
    content: string;
    sender?: string;
    agentId?: string;
    score?: number;
    timestamp: string;
    attachments?: FileAttachment[];
    queryId?: string;
    pending?: boolean;
}

// Store for the message input
export const messageInput = writable('');

// Store for the current file attachment
export const fileAttachment = writable<FileAttachment | null>(null);

// Store for loading state
export const isLoading = writable(false);

// Store for status messages
export const statusMessage = writable('');

// Store for user ID
export const userId = writable<string | null>(null);

// Store for active agent ID
export const activeAgentId = writable<string | null>(null);

// Store for conversations
export const conversations = writable<{ [agentId: string]: Message[] }>({});

// Store for user facts
export const userFacts = writable<UserFact[]>([]);

// Function to generate a unique query ID
export function generateQueryId(): string {
    return uuidv4();
}

// Function to create a message
export function createMessage(
    type: MessageType,
    content: string,
    agentId?: string,
    score: number = 0,
    attachments: FileAttachment[] = [],
    queryId?: string
): Message {
    return {
        id: uuidv4(),
        type,
        content,
        agentId,
        score,
        timestamp: getCurrentDateTimeString(),
        attachments,
        queryId
    };
}

// Function to add a message to the active agent's conversation
export function addMessage(message: Message): void {
    conversations.update(convs => {
        const agentId = message.agentId || get(activeAgentId) || 'default';
        
        if (!convs[agentId]) {
            convs[agentId] = [];
        }
        
        convs[agentId] = [...convs[agentId], message];
        return convs;
    });
}

// Function to add a user message
export function addUserMessage(content: string, attachments: FileAttachment[] = [], queryId?: string): void {
    const agentId = get(activeAgentId);
    const message = createMessage(
        MESSAGE_TYPE.USER,
        content,
        agentId || undefined,
        0,
        attachments,
        queryId
    );
    addMessage(message);
    messageInput.set('');
}

// Function to add an agent message
export function addAgentMessage(content: string, queryId?: string): void {
    const agentId = get(activeAgentId);
    const message = createMessage(
        MESSAGE_TYPE.AGENT,
        content,
        agentId || undefined,
        0,  // Default score
        [], // No attachments for agent messages
        queryId
    );
    addMessage(message);
}

// Function to add a system message
export function addSystemMessage(content: string): void {
    const agentId = get(activeAgentId);
    const message = createMessage(
        MESSAGE_TYPE.SYSTEM, 
        content, 
        agentId || undefined
    );
    addMessage(message);
}

// Function to add an error message
export function addErrorMessage(content: string): void {
    const agentId = get(activeAgentId);
    const message = createMessage(
        MESSAGE_TYPE.SYSTEM, 
        content, 
        'system' // Use 'system' as the agentId for errors
    );
    addMessage(message);
}

// Function to add a status update message
export function addStatusMessage(content: string): void {
    const agentId = get(activeAgentId);
    const message = createMessage(
        MESSAGE_TYPE.STATUS, 
        content, 
        agentId || undefined
    );
    addMessage(message);
    
    // Update the statusMessage store
    statusMessage.set(content);
}

// Function to update the score of a message
export function updateMessageScore(messageId: string, score: number): void {
    conversations.update(convs => {
        const agentId = get(activeAgentId) || 'default';
        
        if (!convs[agentId]) {
            return convs;
        }
        
        convs[agentId] = convs[agentId].map(msg => {
            if (msg.id === messageId) {
                return { ...msg, score };
            }
            return msg;
        });
        
        return convs;
    });
}

// Function to clear the conversation for the active agent
export function clearConversation(): void {
    conversations.update(convs => {
        const agentId = get(activeAgentId) || 'default';
        convs[agentId] = [];
        return convs;
    });
}

// Get the user ID
export function getUserId(): string | null {
    return get(userId);
}

// Set the user ID
export function setUserId(id: string | null): void {
    userId.set(id);
}

// Function to set the active agent ID
export function setActiveAgentId(id: string): void {
    activeAgentId.set(id);
}

// Handle file attachment
export function setFileAttachment(file: File | FileAttachment | null): void {
    console.log('setFileAttachment called with:', file ? `${file.name} (${file.type})` : 'null');
    if (file === null) {
        fileAttachment.set(null);
    } else if ('type' in file && 'name' in file && 'size' in file) {
        // If it's a File object from input
        if (file instanceof File) {
            console.log('Setting file attachment from File object');
            fileAttachment.set({
                id: uuidv4(),
                name: file.name,
                type: file.type,
                size: file.size,
                file: file
            });
        } else {
            // It's already a FileAttachment
            console.log('Setting file attachment from FileAttachment object');
            fileAttachment.set(file);
        }
    }
}

// Clear file attachment
export function clearFileAttachment(): void {
    console.log('Clearing file attachment');
    fileAttachment.set(null);
}

// Function to set loading state
export function setLoading(loading: boolean): void {
    isLoading.set(loading);
} 