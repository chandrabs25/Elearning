"use client";

/**
 * Persistence utilities for frontend state resilience.
 * Uses localStorage to cache chat messages, section status, pending operations,
 * and app-wide data like progress and context.
 */

const STORAGE_KEYS = {
    CHAT_MESSAGES: "tutor_chat_messages",
    SECTION_STATUS: "tutor_section_status",
    PENDING_OPS: "tutor_pending_ops",
    PROGRESS: "tutor_progress",
    CONTEXT: "tutor_context",
    UI_STATE: "tutor_ui_state",
} as const;

// Types for section status and pending operations
export interface SectionStatus {
    total_count: number;
    explained_count: number;
    verified_count: number;
    all_explained: boolean;
    all_verified: boolean;
}

export interface PendingOperation {
    id: string;
    type: "verify" | "teach-subconcept" | "chat-message";
    payload: Record<string, unknown>;
    createdAt: number;
    retryCount: number;
}

// ============================================================================
// Chat Messages - Uses generics to work with any message type
// ============================================================================

function getMessagesKey(userId: string, sectionId: string): string {
    return `${userId}:${sectionId}`;
}

export function saveMessages<T>(userId: string, sectionId: string, messages: T[]): void {
    if (typeof window === "undefined") return;

    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.CHAT_MESSAGES) || "{}");
        stored[getMessagesKey(userId, sectionId)] = {
            messages,
            updatedAt: Date.now(),
        };
        localStorage.setItem(STORAGE_KEYS.CHAT_MESSAGES, JSON.stringify(stored));
    } catch (err) {
        console.warn("[Persistence] Failed to save messages:", err);
    }
}

export function loadMessages<T>(userId: string, sectionId: string): T[] {
    if (typeof window === "undefined") return [];

    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.CHAT_MESSAGES) || "{}");
        const entry = stored[getMessagesKey(userId, sectionId)];
        return entry?.messages || [];
    } catch (err) {
        console.warn("[Persistence] Failed to load messages:", err);
        return [];
    }
}

export function clearMessages(userId: string, sectionId: string): void {
    if (typeof window === "undefined") return;

    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.CHAT_MESSAGES) || "{}");
        delete stored[getMessagesKey(userId, sectionId)];
        localStorage.setItem(STORAGE_KEYS.CHAT_MESSAGES, JSON.stringify(stored));
    } catch (err) {
        console.warn("[Persistence] Failed to clear messages:", err);
    }
}

// ============================================================================
// Section Status
// ============================================================================

function getStatusKey(userId: string, sectionId: string): string {
    return `${userId}:${sectionId}`;
}

export function saveSectionStatus(userId: string, sectionId: string, status: SectionStatus): void {
    if (typeof window === "undefined") return;

    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.SECTION_STATUS) || "{}");
        stored[getStatusKey(userId, sectionId)] = {
            status,
            updatedAt: Date.now(),
        };
        localStorage.setItem(STORAGE_KEYS.SECTION_STATUS, JSON.stringify(stored));
    } catch (err) {
        console.warn("[Persistence] Failed to save section status:", err);
    }
}

export function loadSectionStatus(userId: string, sectionId: string): SectionStatus | null {
    if (typeof window === "undefined") return null;

    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.SECTION_STATUS) || "{}");
        const entry = stored[getStatusKey(userId, sectionId)];
        return entry?.status || null;
    } catch (err) {
        console.warn("[Persistence] Failed to load section status:", err);
        return null;
    }
}

// ============================================================================
// App-Wide Progress Data
// ============================================================================

export function saveProgress<T>(userId: string, progress: T): void {
    if (typeof window === "undefined") return;

    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.PROGRESS) || "{}");
        stored[userId] = {
            progress,
            updatedAt: Date.now(),
        };
        localStorage.setItem(STORAGE_KEYS.PROGRESS, JSON.stringify(stored));
    } catch (err) {
        console.warn("[Persistence] Failed to save progress:", err);
    }
}

export function loadProgress<T>(userId: string): T | null {
    if (typeof window === "undefined") return null;

    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.PROGRESS) || "{}");
        const entry = stored[userId];
        return entry?.progress || null;
    } catch (err) {
        console.warn("[Persistence] Failed to load progress:", err);
        return null;
    }
}

// ============================================================================
// Conversation Context
// ============================================================================

export function saveContext<T>(userId: string, context: T): void {
    if (typeof window === "undefined") return;

    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.CONTEXT) || "{}");
        stored[userId] = {
            context,
            updatedAt: Date.now(),
        };
        localStorage.setItem(STORAGE_KEYS.CONTEXT, JSON.stringify(stored));
    } catch (err) {
        console.warn("[Persistence] Failed to save context:", err);
    }
}

export function loadContext<T>(userId: string): T | null {
    if (typeof window === "undefined") return null;

    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.CONTEXT) || "{}");
        const entry = stored[userId];
        return entry?.context || null;
    } catch (err) {
        console.warn("[Persistence] Failed to load context:", err);
        return null;
    }
}

// ============================================================================
// UI State (panels, layout, etc.)
// ============================================================================

export function saveUIState<T>(userId: string, ui: T): void {
    if (typeof window === "undefined") return;

    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.UI_STATE) || "{}");
        stored[userId] = {
            ui,
            updatedAt: Date.now(),
        };
        localStorage.setItem(STORAGE_KEYS.UI_STATE, JSON.stringify(stored));
    } catch (err) {
        console.warn("[Persistence] Failed to save UI state:", err);
    }
}

export function loadUIState<T>(userId: string): T | null {
    if (typeof window === "undefined") return null;

    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.UI_STATE) || "{}");
        const entry = stored[userId];
        return entry?.ui || null;
    } catch (err) {
        console.warn("[Persistence] Failed to load UI state:", err);
        return null;
    }
}

// ============================================================================
// Pending Operations Queue (for retry on reconnect)
// ============================================================================

export function addPendingOperation(op: Omit<PendingOperation, "id" | "createdAt" | "retryCount">): void {
    if (typeof window === "undefined") return;

    try {
        const stored: PendingOperation[] = JSON.parse(
            localStorage.getItem(STORAGE_KEYS.PENDING_OPS) || "[]"
        );
        stored.push({
            ...op,
            id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            createdAt: Date.now(),
            retryCount: 0,
        });
        localStorage.setItem(STORAGE_KEYS.PENDING_OPS, JSON.stringify(stored));
    } catch (err) {
        console.warn("[Persistence] Failed to add pending operation:", err);
    }
}

export function getPendingOperations(): PendingOperation[] {
    if (typeof window === "undefined") return [];

    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEYS.PENDING_OPS) || "[]");
    } catch (err) {
        console.warn("[Persistence] Failed to get pending operations:", err);
        return [];
    }
}

export function removePendingOperation(id: string): void {
    if (typeof window === "undefined") return;

    try {
        const stored: PendingOperation[] = JSON.parse(
            localStorage.getItem(STORAGE_KEYS.PENDING_OPS) || "[]"
        );
        const filtered = stored.filter((op) => op.id !== id);
        localStorage.setItem(STORAGE_KEYS.PENDING_OPS, JSON.stringify(filtered));
    } catch (err) {
        console.warn("[Persistence] Failed to remove pending operation:", err);
    }
}

export function incrementRetryCount(id: string): void {
    if (typeof window === "undefined") return;

    try {
        const stored: PendingOperation[] = JSON.parse(
            localStorage.getItem(STORAGE_KEYS.PENDING_OPS) || "[]"
        );
        const updated = stored.map((op) =>
            op.id === id ? { ...op, retryCount: op.retryCount + 1 } : op
        );
        localStorage.setItem(STORAGE_KEYS.PENDING_OPS, JSON.stringify(updated));
    } catch (err) {
        console.warn("[Persistence] Failed to increment retry count:", err);
    }
}

export function clearAllPendingOperations(): void {
    if (typeof window === "undefined") return;

    try {
        localStorage.setItem(STORAGE_KEYS.PENDING_OPS, "[]");
    } catch (err) {
        console.warn("[Persistence] Failed to clear pending operations:", err);
    }
}

// ============================================================================
// Retry Queue Processor
// ============================================================================

const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 2000;

export async function processRetryQueue(
    handlers: {
        verify?: (payload: Record<string, unknown>) => Promise<boolean>;
        "teach-subconcept"?: (payload: Record<string, unknown>) => Promise<boolean>;
        "chat-message"?: (payload: Record<string, unknown>) => Promise<boolean>;
    }
): Promise<void> {
    const pending = getPendingOperations();

    for (const op of pending) {
        if (op.retryCount >= MAX_RETRIES) {
            console.warn(`[Retry] Giving up on operation ${op.id} after ${MAX_RETRIES} retries`);
            removePendingOperation(op.id);
            continue;
        }

        const handler = handlers[op.type];
        if (!handler) {
            console.warn(`[Retry] No handler for operation type: ${op.type}`);
            removePendingOperation(op.id);
            continue;
        }

        try {
            const success = await handler(op.payload);
            if (success) {
                removePendingOperation(op.id);
                console.log(`[Retry] Successfully processed operation ${op.id}`);
            } else {
                incrementRetryCount(op.id);
            }
        } catch (err) {
            console.warn(`[Retry] Failed to process operation ${op.id}:`, err);
            incrementRetryCount(op.id);
        }

        // Delay between retries to avoid hammering the server
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
    }
}
