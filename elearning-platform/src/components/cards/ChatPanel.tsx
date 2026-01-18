"use client";

import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Sparkles, MessageCircle } from "lucide-react";
import "katex/dist/katex.min.css";

// Dynamic import to avoid SSR issues
import dynamic from "next/dynamic";
const BlockMath = dynamic(
    () => import("react-katex").then((mod) => mod.BlockMath),
    { ssr: false, loading: () => <div className="animate-pulse h-8 bg-white/10 rounded" /> }
);
const InlineMath = dynamic(
    () => import("react-katex").then((mod) => mod.InlineMath),
    { ssr: false, loading: () => <span className="animate-pulse bg-white/10 rounded px-2">...</span> }
);

// Helper to parse text with inline LaTeX ($...$)
const parseInlineLatex = (text: string): React.ReactNode => {
    if (!text) return null;
    const regex = /\$([^$]+)\$/g;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;
    let key = 0;

    while ((match = regex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            parts.push(text.slice(lastIndex, match.index));
        }
        parts.push(<InlineMath key={key++}>{match[1]}</InlineMath>);
        lastIndex = regex.lastIndex;
    }

    if (lastIndex < text.length) {
        parts.push(text.slice(lastIndex));
    }

    return parts.length > 0 ? parts : text;
};

interface ContentItem {
    type: string;
    text?: string;
    content?: string;
    latex?: string;
    label?: string;
    description?: string;
}

export interface ChatMessage {
    role: "user" | "assistant";
    content: ContentItem[] | string;
}

interface ChatPanelProps {
    context?: {
        current_section_id?: string;
        current_section_title?: string;
        user_id?: string;
    };
    messages: ChatMessage[];
    isTyping?: boolean;
    suggestions?: string[];
    isFocused?: boolean;
    onFocus?: () => void;
    onClose?: () => void;
    onSuggestionClick?: (suggestion: string) => void;
}

export default function ChatPanel({
    context,
    messages = [],
    isTyping = false,
    suggestions = [],
    isFocused = false,
    onFocus,
    onClose,
    onSuggestionClick,
}: ChatPanelProps) {
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when messages change - scroll the container, not the element
    useEffect(() => {
        const container = scrollContainerRef.current;
        if (container) {
            // Use requestAnimationFrame to ensure DOM has updated
            requestAnimationFrame(() => {
                container.scrollTop = container.scrollHeight;
            });
        }
    }, [messages, isTyping]);

    return (
        <motion.div
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            onClick={onFocus}
            className={`
                flex flex-col h-full min-h-0 max-h-full overflow-hidden
                bg-gradient-to-br from-white/5 to-transparent 
                rounded-3xl border backdrop-blur-sm
                transition-all duration-300
                ${isFocused
                    ? "border-blue-500/50 ring-2 ring-blue-500/20"
                    : "border-white/10 hover:border-white/20"
                }
            `}
        >
            {/* Header */}
            <div className="flex-shrink-0 flex items-center justify-between p-4 border-b border-white/10">
                <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-xl ${isFocused ? "bg-blue-500/20" : "bg-white/10"}`}>
                        <MessageCircle className={`w-5 h-5 ${isFocused ? "text-blue-400" : "text-white/60"}`} />
                    </div>
                    <div>
                        <h3 className="text-white font-medium">AI Chat</h3>
                        {context?.current_section_title && (
                            <p className="text-xs text-white/40">
                                Context: {context.current_section_title}
                            </p>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {isFocused && (
                        <span className="text-xs text-blue-400 bg-blue-500/10 px-2 py-1 rounded-full">
                            Active
                        </span>
                    )}
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            onClose?.();
                        }}
                        className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                    >
                        <X className="w-4 h-4 text-white/40 hover:text-white" />
                    </button>
                </div>
            </div>

            {/* Messages - this is the scroll container */}
            <div 
                ref={scrollContainerRef}
                className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-white/40 hover:scrollbar-thumb-white/60 min-h-0"
            >
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center py-8">
                        <div className="p-4 bg-blue-500/10 rounded-2xl mb-4">
                            <Sparkles className="w-8 h-8 text-blue-400" />
                        </div>
                        <p className="text-white/60 mb-2">Ask me anything!</p>
                        <p className="text-sm text-white/40">
                            I can explain concepts, derive formulas, or answer questions.
                        </p>
                        {isFocused && (
                            <p className="text-xs text-blue-400 mt-4">
                                Type in the input bar below ↓
                            </p>
                        )}
                    </div>
                ) : (
                    <>
                        {messages.map((message, index) => (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                            >
                                <div
                                    className={`max-w-[85%] p-4 rounded-2xl ${message.role === "user"
                                        ? "bg-blue-500/20 border border-blue-500/30"
                                        : "bg-white/5 border border-white/10"
                                        }`}
                                >
                                    {renderMessageContent(message.content)}
                                </div>
                            </motion.div>
                        ))}
                    </>
                )}

                {isTyping && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="flex justify-start"
                    >
                        <div className="bg-white/5 border border-white/10 p-4 rounded-2xl">
                            <div className="flex gap-1">
                                {[0, 1, 2].map((i) => (
                                    <motion.div
                                        key={i}
                                        animate={{ y: [0, -5, 0] }}
                                        transition={{ repeat: Infinity, delay: i * 0.1, duration: 0.6 }}
                                        className="w-2 h-2 bg-blue-400 rounded-full"
                                    />
                                ))}
                            </div>
                        </div>
                    </motion.div>
                )}
            </div>

            {/* Suggestions footer (no input - use global input bar) */}
            {suggestions.length > 0 && (
                <div className="flex-shrink-0 p-4 border-t border-white/10">
                    <p className="text-xs text-white/40 mb-2">Suggestions:</p>
                    <div className="flex flex-wrap gap-2">
                        {suggestions.map((suggestion, i) => (
                            <button
                                key={i}
                                onClick={() => onSuggestionClick?.(suggestion)}
                                className="text-xs px-3 py-1.5 bg-blue-500/10 border border-blue-500/30 rounded-full text-blue-400 hover:bg-blue-500/20 transition-colors"
                            >
                                {suggestion}
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </motion.div>
    );
}

function renderMessageContent(content: ContentItem[] | string) {
    if (typeof content === "string") {
        return <p className="text-white/80">{parseInlineLatex(content)}</p>;
    }

    return (
        <div className="space-y-3">
            {content.map((item, i) => {
                switch (item.type) {
                    case "text":
                        return (
                            <p key={i} className="text-white/80 leading-relaxed">
                                {parseInlineLatex(item.text || item.content || "")}
                            </p>
                        );
                    case "latex":
                        return (
                            <div key={i} className="p-3 bg-blue-500/10 rounded-xl overflow-x-auto">
                                <BlockMath>{item.latex || item.content || ""}</BlockMath>
                                {item.description && (
                                    <p className="mt-2 text-sm text-white/50 italic">{item.description}</p>
                                )}
                            </div>
                        );
                    case "listItem":
                        return (
                            <div key={i} className="flex gap-2 text-white/70">
                                <span className="text-blue-400">{item.label || "•"}</span>
                                <span>{parseInlineLatex(item.text || item.content || "")}</span>
                            </div>
                        );
                    default:
                        return (
                            <p key={i} className="text-white/60">
                                {item.text || item.content || JSON.stringify(item)}
                            </p>
                        );
                }
            })}
        </div>
    );
}
