"use client";

import { useRef, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Sparkles, MessageCircle, CheckCircle, Brain, Loader2, ArrowRight } from "lucide-react";
import "katex/dist/katex.min.css";
import {
    saveSectionStatus,
    loadSectionStatus,
    addPendingOperation,
    SectionStatus as CachedSectionStatus,
} from "@/lib/persistence";

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

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

// Helper to parse text with inline LaTeX ($...$) and markdown formatting (**bold**, *italic*)
const parseInlineLatex = (text: string): React.ReactNode => {
    if (!text) return null;

    // Combined regex for LaTeX (block $$...$$ and inline $...$), bold, and italic
    // Order matters: check $$ before $ to avoid conflicts, bold (**) before italic (*)
    const regex = /\$\$([^$]+)\$\$|\$([^$]+)\$|\*\*([^*]+)\*\*|\*([^*]+)\*/g;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;
    let key = 0;

    while ((match = regex.exec(text)) !== null) {
        // Add text before the match
        if (match.index > lastIndex) {
            parts.push(text.slice(lastIndex, match.index));
        }

        if (match[1]) {
            // Block LaTeX: $$...$$
            parts.push(<BlockMath key={key++}>{match[1]}</BlockMath>);
        } else if (match[2]) {
            // Inline LaTeX: $...$
            parts.push(<InlineMath key={key++}>{match[2]}</InlineMath>);
        } else if (match[3]) {
            // Bold: **...**
            parts.push(<strong key={key++} className="font-semibold text-white">{match[3]}</strong>);
        } else if (match[4]) {
            // Italic: *...*
            parts.push(<em key={key++} className="italic text-white/90">{match[4]}</em>);
        }

        lastIndex = regex.lastIndex;
    }

    if (lastIndex < text.length) {
        parts.push(text.slice(lastIndex));
    }

    return parts.length > 0 ? parts : text;
};

// Helper to parse full markdown text with headings, paragraphs, and inline formatting
const parseMarkdownText = (text: string): React.ReactNode => {
    if (!text) return null;

    // Split by double newlines first (paragraphs), then handle each line
    const lines = text.split(/\n/);
    const elements: React.ReactNode[] = [];
    let key = 0;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();

        // Skip empty lines but add spacing
        if (!trimmed) {
            continue;
        }

        // Check for markdown headings
        if (trimmed.startsWith('### ')) {
            elements.push(
                <h3 key={key++} className="text-lg font-semibold text-white mt-4 mb-2">
                    {parseInlineLatex(trimmed.slice(4))}
                </h3>
            );
        } else if (trimmed.startsWith('## ')) {
            elements.push(
                <h2 key={key++} className="text-xl font-semibold text-white mt-4 mb-2">
                    {parseInlineLatex(trimmed.slice(3))}
                </h2>
            );
        } else if (trimmed.startsWith('# ')) {
            elements.push(
                <h1 key={key++} className="text-2xl font-bold text-white mt-4 mb-2">
                    {parseInlineLatex(trimmed.slice(2))}
                </h1>
            );
        } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
            // Bullet points
            elements.push(
                <li key={key++} className="text-white/80 ml-4 list-disc">
                    {parseInlineLatex(trimmed.slice(2))}
                </li>
            );
        } else {
            // Regular paragraph
            elements.push(
                <p key={key++} className="text-white/80 leading-relaxed mb-2">
                    {parseInlineLatex(trimmed)}
                </p>
            );
        }
    }

    return <div className="space-y-1">{elements}</div>;
};

interface ContentItem {
    type: string;
    text?: string;
    content?: string;
    latex?: string;
    equation?: string;  // For 'equation' type content
    label?: string;
    description?: string;
    items?: string[];  // For 'list' type content
}

export interface ChatMessage {
    role: "user" | "assistant";
    content: ContentItem[] | string;
}

interface SectionStatus {
    section_id: string;
    concepts: Array<{ id: string; title: string; explained: boolean; verified: boolean }>;
    all_explained: boolean;
    all_verified: boolean;
    explained_count: number;
    verified_count: number;
    total_count: number;
}

interface ChatPanelProps {
    context?: {
        current_section?: string;
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
    onNextSection?: () => void;  // Navigate to next section
    onAddMessages?: (messages: ChatMessage[]) => void;  // Add messages to chat
    onTeachSubconcept?: (subconceptId: string) => void;  // Teach a specific subconcept via parent's stream
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
    onNextSection,
    onAddMessages,
    onTeachSubconcept,
}: ChatPanelProps) {
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    // Understanding check state
    const [sectionStatus, setSectionStatus] = useState<SectionStatus | null>(null);
    const [isCheckingUnderstanding, setIsCheckingUnderstanding] = useState(false);
    const [verificationQuestion, setVerificationQuestion] = useState<string | null>(null);
    const [currentVerifyConceptId, setCurrentVerifyConceptId] = useState<string | null>(null);
    const [verificationAnswer, setVerificationAnswer] = useState("");
    const [verificationFeedback, setVerificationFeedback] = useState<{ isCorrect: boolean; feedback: string } | null>(null);
    const [isVerifying, setIsVerifying] = useState(false);

    // Track pending next subconcept for manual "Continue" button
    const [pendingNextSubconcept, setPendingNextSubconcept] = useState<{ id: string; title: string } | null>(null);

    // Fetch section status when section changes
    useEffect(() => {
        if (context?.current_section && context?.user_id) {
            fetchSectionStatus();
        }
    }, [context?.current_section, context?.user_id]);

    // Refresh section status when messages change (e.g., after tutor teaches a concept)
    useEffect(() => {
        if (context?.current_section && context?.user_id && messages.length > 0) {
            // Debounce: only fetch after message is fully received
            const timer = setTimeout(() => {
                fetchSectionStatus();
            }, 500);
            return () => clearTimeout(timer);
        }
    }, [messages.length, context?.current_section, context?.user_id]);



    const fetchSectionStatus = async () => {
        if (!context?.current_section || !context?.user_id) return;

        // Load from cache immediately for instant button visibility
        const cached = loadSectionStatus(context.user_id, context.current_section);
        if (cached && !sectionStatus) {
            // Only use cache if we don't have fresh data
            setSectionStatus({
                ...cached,
                section_id: context.current_section,
                concepts: [],  // Cache doesn't store full concepts array
            });
        }

        // Then fetch from backend to sync
        try {
            const res = await fetch(
                `${BACKEND_URL}/api/tutor/section-status/${context.current_section}?user_id=${context.user_id}`
            );
            if (res.ok) {
                const data = await res.json();
                setSectionStatus(data);
                // Save to cache for offline access
                saveSectionStatus(context.user_id, context.current_section, {
                    total_count: data.total_count,
                    explained_count: data.explained_count,
                    verified_count: data.verified_count,
                    all_explained: data.all_explained,
                    all_verified: data.all_verified,
                });
            }
        } catch (err) {
            console.error("Failed to fetch section status:", err);
            // Cache already loaded above, so button still works
        }
    };

    const startUnderstandingCheck = async () => {
        if (!context?.current_section || !context?.user_id) return;

        setIsCheckingUnderstanding(true);
        setVerificationFeedback(null);

        try {
            const res = await fetch(`${BACKEND_URL}/api/tutor/check-understanding`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: context.user_id,
                    section_id: context.current_section
                })
            });

            if (res.ok) {
                const data = await res.json();
                if (data.all_verified) {
                    setVerificationQuestion(null);
                    setCurrentVerifyConceptId(null);
                    alert("🎉 You've already verified all concepts in this section!");
                    setIsCheckingUnderstanding(false);
                } else if (data.first_question) {
                    setVerificationQuestion(data.first_question);
                    setCurrentVerifyConceptId(data.first_concept_id);
                } else {
                    alert("No concepts to verify yet. Ask some questions first!");
                    setIsCheckingUnderstanding(false);
                }
            }
        } catch (err) {
            console.error("Failed to start understanding check:", err);
            setIsCheckingUnderstanding(false);
        }
    };

    const submitVerificationAnswer = async () => {
        if (!verificationAnswer.trim() || !currentVerifyConceptId || !context?.user_id) return;

        setIsVerifying(true);

        try {
            const res = await fetch(`${BACKEND_URL}/api/tutor/verify-understanding`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: context.user_id,
                    concept_id: currentVerifyConceptId,
                    answer: verificationAnswer,
                    question: verificationQuestion  // Pass question for context-aware evaluation
                })
            });

            if (res.ok) {
                const data = await res.json();
                setVerificationFeedback({ isCorrect: data.is_correct, feedback: data.feedback });
                setVerificationAnswer("");

                // Refresh section status
                await fetchSectionStatus();

                // Store pending next subconcept for manual "Continue" button
                if (data.is_correct && data.next_subconcept_id) {
                    setPendingNextSubconcept({
                        id: data.next_subconcept_id,
                        title: data.next_subconcept_title || data.next_subconcept_id
                    });
                    // User must click "Continue" button to proceed
                } else if (data.all_verified) {
                    // All subconcepts verified - show section complete message
                    setPendingNextSubconcept(null);
                    const completeMessage = data.next_section_id
                        ? `🎉 **Section Complete!** You've mastered all concepts in this section.\n\nReady to continue to **${data.next_section_title || data.next_section_id}**?`
                        : `🎉 **Section Complete!** You've mastered all concepts in this section.`;

                    onAddMessages?.([{ role: "assistant" as const, content: completeMessage }]);

                    setTimeout(() => {
                        setIsCheckingUnderstanding(false);
                        setVerificationQuestion(null);
                        setVerificationFeedback(null);
                    }, 2000);
                } else if (data.next_question && data.is_correct) {
                    // Only auto-transition to next question if answer was correct
                    // For wrong answers, user must click "Try Again" button
                    setPendingNextSubconcept(null);
                    setTimeout(() => {
                        setVerificationQuestion(data.next_question);
                        setCurrentVerifyConceptId(data.next_concept?.id);
                        setVerificationFeedback(null);
                    }, 2000);
                }
                // For wrong answers: feedback stays visible until user clicks "Try Again"
            }

        } catch (err) {
            console.error("Failed to verify understanding:", err);
            // Queue for retry when reconnected
            addPendingOperation({
                type: "verify",
                payload: {
                    user_id: context.user_id,
                    concept_id: currentVerifyConceptId,
                    answer: verificationAnswer
                }
            });
        } finally {
            setIsVerifying(false);
        }
    };

    const cancelVerification = () => {
        setIsCheckingUnderstanding(false);
        setVerificationQuestion(null);
        setCurrentVerifyConceptId(null);
        setVerificationAnswer("");
        setVerificationFeedback(null);
        setPendingNextSubconcept(null);
    };

    // Handler for "Continue to Next Concept" button - delegates to parent via callback
    const continueToNextSubconcept = async () => {
        if (!pendingNextSubconcept) return;

        // Delegate to parent component which handles streaming properly
        if (onTeachSubconcept) {
            onTeachSubconcept(pendingNextSubconcept.id);
        } else {
            // Fallback: use suggestion click to trigger teaching
            onSuggestionClick?.(`teach me ${pendingNextSubconcept.id}`);
        }

        // Close the verification modal
        setIsCheckingUnderstanding(false);
        setVerificationQuestion(null);
        setVerificationFeedback(null);
        setPendingNextSubconcept(null);
        await fetchSectionStatus();
    };

    // Auto-scroll to bottom when messages change - scroll the container, not the element
    useEffect(() => {
        const container = scrollContainerRef.current;
        if (container) {
            // Use requestAnimationFrame to ensure DOM has updated
            requestAnimationFrame(() => {
                container.scrollTop = container.scrollHeight;
            });
        }
    }, [messages, isTyping, verificationQuestion]);

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
                    {/* Section status indicator */}
                    {sectionStatus && sectionStatus.total_count > 0 && (
                        <div className="flex items-center gap-1.5 text-xs">
                            {sectionStatus.all_verified ? (
                                <span className="flex items-center gap-1 text-green-400 bg-green-500/10 px-2 py-1 rounded-full">
                                    <CheckCircle className="w-3 h-3" />
                                    Mastered
                                </span>
                            ) : (
                                <span className="text-white/40 bg-white/5 px-2 py-1 rounded-full">
                                    {sectionStatus.verified_count}/{sectionStatus.total_count} verified
                                </span>
                            )}
                        </div>
                    )}
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

            {/* Messages or Verification UI */}
            <div
                ref={scrollContainerRef}
                className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-white/40 hover:scrollbar-thumb-white/60 min-h-0"
            >
                {isCheckingUnderstanding && verificationQuestion ? (
                    // Verification Mode
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="space-y-4"
                    >
                        <div className="flex items-center gap-2 text-purple-400">
                            <Brain className="w-5 h-5" />
                            <span className="font-medium">Understanding Check</span>
                        </div>

                        <div className="bg-purple-500/10 border border-purple-500/30 rounded-2xl p-4">
                            <p className="text-white/90">{verificationQuestion}</p>
                        </div>

                        {verificationFeedback && (
                            <motion.div
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                className={`p-4 rounded-xl border ${verificationFeedback.isCorrect
                                    ? "bg-green-500/10 border-green-500/30"
                                    : "bg-amber-500/10 border-amber-500/30"
                                    }`}
                            >
                                <div className="flex items-center gap-2 mb-2">
                                    {verificationFeedback.isCorrect ? (
                                        <CheckCircle className="w-5 h-5 text-green-400" />
                                    ) : (
                                        <Brain className="w-5 h-5 text-amber-400" />
                                    )}
                                    <span className={verificationFeedback.isCorrect ? "text-green-400" : "text-amber-400"}>
                                        {verificationFeedback.isCorrect ? "Correct!" : "Keep Learning"}
                                    </span>
                                </div>
                                <p className="text-white/70 text-sm mb-4">{verificationFeedback.feedback}</p>

                                {/* Navigation buttons based on result */}
                                <div className="flex gap-2 pt-2 border-t border-white/10">
                                    {verificationFeedback.isCorrect ? (
                                        <>
                                            <button
                                                onClick={continueToNextSubconcept}
                                                disabled={!pendingNextSubconcept}
                                                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-green-500/20 border border-green-500/30 rounded-xl text-green-400 hover:bg-green-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                            >
                                                <ArrowRight className="w-4 h-4" />
                                                {pendingNextSubconcept
                                                    ? `Continue to: ${pendingNextSubconcept.title}`
                                                    : "Section Complete!"}
                                            </button>
                                        </>
                                    ) : (
                                        <>
                                            <button
                                                onClick={() => {
                                                    setVerificationFeedback(null);
                                                    setVerificationAnswer("");
                                                }}
                                                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-amber-500/20 border border-amber-500/30 rounded-xl text-amber-400 hover:bg-amber-500/30 transition-colors"
                                            >
                                                Try Again
                                            </button>
                                            <button
                                                onClick={() => {
                                                    setIsCheckingUnderstanding(false);
                                                    setVerificationFeedback(null);
                                                    // Trigger a help request - send a message asking for clarification
                                                    onSuggestionClick?.("Can you explain this concept again? I'm having trouble understanding.");
                                                }}
                                                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-500/20 border border-blue-500/30 rounded-xl text-blue-400 hover:bg-blue-500/30 transition-colors"
                                            >
                                                <MessageCircle className="w-4 h-4" />
                                                Ask for Help
                                            </button>
                                        </>
                                    )}
                                </div>
                            </motion.div>
                        )}

                        {!verificationFeedback && (
                            <div className="space-y-2">
                                <textarea
                                    value={verificationAnswer}
                                    onChange={(e) => setVerificationAnswer(e.target.value)}
                                    placeholder="Explain in your own words..."
                                    className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-white placeholder-white/30 resize-none focus:outline-none focus:border-purple-500/50"
                                    rows={3}
                                />
                                <div className="flex gap-2">
                                    <button
                                        onClick={submitVerificationAnswer}
                                        disabled={!verificationAnswer.trim() || isVerifying}
                                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-purple-500/20 border border-purple-500/30 rounded-xl text-purple-400 hover:bg-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                    >
                                        {isVerifying ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                        ) : (
                                            <CheckCircle className="w-4 h-4" />
                                        )}
                                        Submit
                                    </button>
                                    <button
                                        onClick={cancelVerification}
                                        className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-white/60 hover:bg-white/10 transition-colors"
                                    >
                                        Cancel
                                    </button>
                                </div>
                            </div>
                        )}
                    </motion.div>
                ) : messages.length === 0 ? (
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

            {/* Footer with Check Understanding button and suggestions */}
            <div className="flex-shrink-0 p-4 border-t border-white/10 space-y-3">
                {/* Check Understanding Button - only show if there are unverified explained concepts */}
                {sectionStatus && sectionStatus.explained_count > 0 && (sectionStatus.explained_count - sectionStatus.verified_count) > 0 && !sectionStatus.all_verified && !isCheckingUnderstanding && (
                    <button
                        onClick={startUnderstandingCheck}
                        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-purple-500/20 to-blue-500/20 border border-purple-500/30 rounded-xl text-purple-300 hover:from-purple-500/30 hover:to-blue-500/30 transition-all"
                    >
                        <Brain className="w-4 h-4" />
                        Check Understanding ({sectionStatus.explained_count - sectionStatus.verified_count} to verify)
                    </button>
                )}

                {/* All verified celebration */}
                {sectionStatus?.all_verified && (
                    <div className="space-y-2">
                        <div className="flex items-center justify-center gap-2 px-4 py-2 bg-green-500/10 border border-green-500/30 rounded-xl text-green-400">
                            <CheckCircle className="w-4 h-4" />
                            <span className="text-sm">Section Mastered! 🎉</span>
                        </div>
                        {onNextSection && (
                            <button
                                onClick={onNextSection}
                                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-green-500/20 to-emerald-500/20 border border-green-500/30 rounded-xl text-green-300 hover:from-green-500/30 hover:to-emerald-500/30 transition-all"
                            >
                                <ArrowRight className="w-4 h-4" />
                                Continue to Next Section
                            </button>
                        )}
                    </div>
                )}

                {/* Suggestions */}
                {suggestions.length > 0 && !isCheckingUnderstanding && (
                    <div>
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
            </div>
        </motion.div>
    );
}

function renderMessageContent(content: ContentItem[] | string) {
    // Handle null/undefined
    if (!content) {
        return <p className="text-white/80">...</p>;
    }

    // If content is a string, check if it's a stringified array
    if (typeof content === "string") {
        // Check if it looks like a stringified array/object (Python or JSON format)
        const trimmed = content.trim();

        // Check for Python dict-style content without brackets (legacy format)
        // Pattern: {'type': 'text', 'text': '...'}, {'type': 'latex', ...}
        if (trimmed.includes("'type':") && trimmed.includes("'text':")) {
            try {
                // Wrap in brackets if not already wrapped
                const toWrap = trimmed.startsWith("[") ? trimmed : `[${trimmed}]`;
                // Convert Python-style to JSON-style
                const fixed = toWrap
                    .replace(/\\'/g, '___ESCAPED_QUOTE___')  // Protect escaped quotes
                    .replace(/'/g, '"')                       // Convert structural quotes
                    .replace(/___ESCAPED_QUOTE___/g, "'")     // Restore as regular apostrophes
                    .replace(/True/g, 'true')
                    .replace(/False/g, 'false')
                    .replace(/None/g, 'null')
                    // Clean up trailing commas in arrays/objects
                    .replace(/,\s*([}\]])/g, '$1');
                let parsed = JSON.parse(fixed);
                if (Array.isArray(parsed)) {
                    content = parsed;
                }
            } catch {
                // If parsing fails, show as plain text (remove the dict formatting)
                const plainText = trimmed
                    .replace(/\{['"]*type['"]*:\s*['"]*text['"]*,\s*['"]*text['"]*:\s*/g, '')
                    .replace(/\},\s*\{['"]*type['"]*:\s*['"]*latex['"]*,\s*['"]*content['"]*:\s*/g, '\n')
                    .replace(/\}[,\s]*/g, ' ')
                    .replace(/['"]/g, '');
                return <p className="text-white/80">{parseInlineLatex(plainText)}</p>;
            }
        }
        else if (trimmed.startsWith("[{") || trimmed.startsWith('[{"') || trimmed.startsWith("[{'")) {
            try {
                // Try parsing as JSON first
                let parsed = JSON.parse(trimmed);
                if (Array.isArray(parsed)) {
                    content = parsed;
                }
            } catch {
                // Try fixing Python-style single quotes to JSON double quotes
                try {
                    // More careful conversion: preserve escaped quotes in text content
                    const fixed = trimmed
                        .replace(/\\'/g, '___ESCAPED_QUOTE___')  // Protect escaped quotes
                        .replace(/'/g, '"')                       // Convert structural quotes
                        .replace(/___ESCAPED_QUOTE___/g, "'")     // Restore as regular apostrophes
                        .replace(/True/g, 'true')
                        .replace(/False/g, 'false')
                        .replace(/None/g, 'null');
                    let parsed = JSON.parse(fixed);
                    if (Array.isArray(parsed)) {
                        content = parsed;
                    }
                } catch {
                    // If parsing fails, treat as regular text
                    return <div className="text-white/80">{parseMarkdownText(trimmed)}</div>;
                }
            }
        } else {
            // Regular string content
            return <div className="text-white/80">{parseMarkdownText(content)}</div>;
        }
    }

    // Final check: ensure content is actually an array
    if (!Array.isArray(content)) {
        console.warn("Content is not an array:", content);
        return <div className="text-white/80">{parseMarkdownText(String(content))}</div>;
    }

    return (
        <div className="space-y-3">
            {content.map((item, i) => {
                switch (item.type) {
                    case "text":
                        return (
                            <div key={i} className="text-white/80 leading-relaxed">
                                {parseMarkdownText(item.text || item.content || "")}
                            </div>
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
                    case "equation":
                        // Similar to latex but uses 'equation' property
                        return (
                            <div key={i} className="p-3 bg-purple-500/10 rounded-xl overflow-x-auto">
                                <BlockMath>{item.equation || item.content || ""}</BlockMath>
                            </div>
                        );
                    case "listItem":
                        return (
                            <div key={i} className="flex gap-2 text-white/70">
                                <span className="text-blue-400">{item.label || "•"}</span>
                                <span>{parseInlineLatex(item.text || item.content || "")}</span>
                            </div>
                        );
                    case "list":
                        // Handle list type with items array
                        if (item.items && Array.isArray(item.items)) {
                            return (
                                <ul key={i} className="space-y-1 ml-4">
                                    {item.items.map((listItem: string, j: number) => (
                                        <li key={j} className="flex gap-2 text-white/70">
                                            <span className="text-blue-400">•</span>
                                            <span>{parseInlineLatex(listItem)}</span>
                                        </li>
                                    ))}
                                </ul>
                            );
                        }
                        return null;
                    default:
                        // For unknown types, try to extract text content if available
                        const textContent = item.text || item.content;
                        if (textContent) {
                            return (
                                <p key={i} className="text-white/60">
                                    {parseInlineLatex(textContent)}
                                </p>
                            );
                        }
                        // Only show JSON for truly unknown structures
                        console.warn("Unknown content type:", item.type, item);
                        return null;
                }
            })}
        </div>
    );
}

