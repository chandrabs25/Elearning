"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import InputBar from "@/components/InputBar";
import DynamicPanel from "@/components/DynamicPanel";
import CelebrationModal from "@/components/CelebrationModal";
import ProgressBar from "@/components/ProgressBar";
import { ChatMessage } from "@/components/cards/ChatPanel";

type LayoutMode = "focus" | "split" | "compare" | "stack" | "dynamic";
type PanelRole = "primary" | "secondary" | "auxiliary";

interface Panel {
    type: string;
    props: Record<string, unknown>;
    pinned?: boolean;
    animation?: string;
    role?: PanelRole;
    width?: string;
}

interface ProgressData {
    lifetime_mastery: number;
    current_section_id?: string;
    current_section_mastery?: number;
    exploration_points?: number;
    sections_progress: Array<{
        id: string;
        title: string;
        mastery: number;
        completed: boolean;
    }>;
}

interface CelebrationData {
    show: boolean;
    section_title: string;
    mastery_percent: number;
    next_section_id?: string;
    next_section_title?: string;
}

interface SuggestedAction {
    label: string;
    action: string;
    primary?: boolean;
}

interface UISchema {
    layout: LayoutMode;
    panels: Panel[];
    input_placeholder?: string;
    next_prompt?: string;
    progress?: ProgressData;
    celebration?: CelebrationData;
    suggested_actions?: SuggestedAction[];
}

interface ConversationContext {
    [key: string]: unknown;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const USER_ID = "demo-user";

export default function TutorV2Page() {
    const [ui, setUI] = useState<UISchema | null>(null);
    const [loading, setLoading] = useState(true);
    const [context, setContext] = useState<ConversationContext>({});
    const [error, setError] = useState<string | null>(null);
    const [isProcessing, setIsProcessing] = useState(false);
    const [focusedPanelIndex, setFocusedPanelIndex] = useState<number | null>(null);
    const [inputMode, setInputMode] = useState<"answer" | "ask">("ask"); // For quiz/mcq input control
    const inputRef = useRef<HTMLInputElement>(null);

    // Chat-specific state (managed here, passed to ChatPanel)
    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
    const [isChatTyping, setIsChatTyping] = useState(false);
    const [chatSuggestions, setChatSuggestions] = useState<string[]>([]);

    // Celebration modal state
    const [showCelebration, setShowCelebration] = useState(false);
    const [celebrationData, setCelebrationData] = useState<CelebrationData | null>(null);

    // Progress state
    const [progress, setProgress] = useState<ProgressData>({
        lifetime_mastery: 0,
        sections_progress: []
    });

    // Voice feedback state
    const [voiceEnabled, setVoiceEnabled] = useState(true);
    const audioRef = useRef<HTMLAudioElement | null>(null);

    // Text-to-Speech function using Groq Orpheus API
    const speak = useCallback(async (text: string) => {
        if (!voiceEnabled || !text) return;

        try {
            const response = await fetch(`${BACKEND_URL}/api/tutor/speak`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text })
            });

            if (response.ok && response.status !== 204) {
                const audioBlob = await response.blob();
                if (audioBlob.size > 0) {
                    const audioUrl = URL.createObjectURL(audioBlob);

                    // Stop any currently playing audio
                    if (audioRef.current) {
                        audioRef.current.pause();
                        audioRef.current = null;
                    }

                    const audio = new Audio(audioUrl);
                    audioRef.current = audio;
                    audio.volume = 0.8;
                    audio.play().catch(err => console.log("Audio playback failed:", err));

                    // Cleanup URL after playback
                    audio.onended = () => URL.revokeObjectURL(audioUrl);
                }
            }
        } catch (err) {
            console.log("TTS error:", err);
        }
    }, [voiceEnabled]);

    // Initialize session
    useEffect(() => {
        initSession();
    }, []);

    // Determine if a ChatPanel exists and which panel is focused
    const chatPanelIndex = ui?.panels.findIndex(p => p.type === "ChatPanel") ?? -1;
    const hasChatPanel = chatPanelIndex >= 0;
    const isChatFocused = hasChatPanel && focusedPanelIndex === chatPanelIndex;

    // Get focused panel type for InputBar styling
    const focusedPanelType = focusedPanelIndex !== null && ui?.panels[focusedPanelIndex]
        ? ui.panels[focusedPanelIndex].type
        : null;

    // Keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Tab to switch focus between panels
            if (e.key === "Tab" && ui && ui.panels.length > 1) {
                e.preventDefault();
                setFocusedPanelIndex(prev => {
                    if (prev === null) return 0;
                    return (prev + 1) % ui.panels.length;
                });
            }

            // Cmd/Ctrl + J to open chat panel
            if (e.key === "j" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                if (!hasChatPanel) {
                    sendTutorMessage("open chat");
                } else {
                    // Focus chat panel if it exists
                    setFocusedPanelIndex(chatPanelIndex);
                }
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [ui, hasChatPanel, chatPanelIndex]);

    // Auto-focus chat panel when it's added
    useEffect(() => {
        if (hasChatPanel && focusedPanelIndex === null) {
            setFocusedPanelIndex(chatPanelIndex);
        }
    }, [hasChatPanel, chatPanelIndex, focusedPanelIndex]);

    // Auto-switch input mode based on focused panel
    // Default to "answer" when quiz/mcq is focused, "ask" otherwise
    useEffect(() => {
        const isQuizFocused = focusedPanelType === "QuizCard" || focusedPanelType === "MCQCard";
        setInputMode(isQuizFocused ? "answer" : "ask");
    }, [focusedPanelType]);

    // Handle celebration data from API response
    useEffect(() => {
        if (ui?.celebration?.show) {
            setCelebrationData(ui.celebration);
            setShowCelebration(true);
        }
    }, [ui?.celebration]);

    // Handle progress data from API response
    useEffect(() => {
        if (ui?.progress) {
            setProgress(ui.progress);
        }
    }, [ui?.progress]);

    const initSession = async () => {
        try {
            setLoading(true);
            const res = await fetch(`${BACKEND_URL}/api/tutor/init/${USER_ID}`);
            if (!res.ok) throw new Error("Failed to initialize session");
            const data = await res.json();
            setUI(data.ui);
            setContext(data.conversation_context || {});

            // Set initial progress
            if (data.ui?.progress) {
                setProgress(data.ui.progress);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setLoading(false);
        }
    };

    // Fetch progress separately (for updates after actions)
    const fetchProgress = async () => {
        try {
            const res = await fetch(`${BACKEND_URL}/api/tutor/progress/${USER_ID}`);
            if (res.ok) {
                const data = await res.json();
                setProgress({
                    lifetime_mastery: data.lifetime_mastery,
                    current_section_id: context.current_section as string,
                    exploration_points: data.exploration_points || 0,
                    sections_progress: data.sections_progress
                });
            }
        } catch (err) {
            console.error("Failed to fetch progress:", err);
        }
    };

    // Get voice feedback message based on command
    const getVoiceFeedback = (message: string, responseData: any): string => {
        const msg = message.toLowerCase();

        // Check what kind of response we got
        const panelTypes = responseData.ui?.panels?.map((p: Panel) => p.type) || [];

        if (msg.includes("quiz") || msg.includes("test me")) {
            return "Here's a quiz question for you.";
        }
        if (msg.includes("mcq") || msg.includes("multiple choice")) {
            return "Here are some multiple choice questions.";
        }
        if (msg.includes("teach") || msg.includes("go to") || msg.includes("next") || msg.includes("previous")) {
            const title = responseData.conversation_context?.section_title || "the section";
            return `Loading ${title}.`;
        }
        if (msg.includes("exercise") || msg.includes("practice")) {
            return "Here are the practice exercises.";
        }
        if (msg.includes("chat") || msg.includes("help")) {
            return "Chat is ready. Ask me anything.";
        }
        if (msg.includes("progress") || msg.includes("summary")) {
            return "Here's your progress summary.";
        }
        if (msg.includes("also show") || msg.includes("compare")) {
            return "Showing comparison view.";
        }
        if (panelTypes.includes("ExplanationPanel")) {
            return "Content loaded.";
        }

        return "Done.";
    };

    // Send message to tutor conversation endpoint
    // isAction=true for button clicks (skips LLM on backend)
    const sendTutorMessage = useCallback(async (message: string, isAction: boolean = false) => {
        if (!message.trim() || isProcessing) return;

        setIsProcessing(true);

        try {
            // Map panel type to focused_panel value for backend
            const panelTypeToFocusedPanel: Record<string, string> = {
                ChatPanel: "chat",
                QuizCard: "quiz",
                MCQCard: "mcq",
                ExercisePanel: "exercise",
            };
            const focused_panel = focusedPanelType
                ? panelTypeToFocusedPanel[focusedPanelType] || "main"
                : "main";

            // Build request body - use action for button clicks, message for free-form text
            const requestContext = { ...context, focused_panel, input_mode: inputMode };
            const body = isAction
                ? { user_id: USER_ID, action: message, context: requestContext }
                : { user_id: USER_ID, message, context: requestContext };

            const res = await fetch(`${BACKEND_URL}/api/tutor/converse`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });

            if (!res.ok) throw new Error("Failed to process message");
            const data = await res.json();
            setUI(data.ui);
            setContext(data.conversation_context || {});

            // Speak feedback based on the response
            const feedback = getVoiceFeedback(message, data);
            speak(feedback);

            // Reset chat state when UI changes (new chat panel might be added)
            if (data.ui?.panels?.some((p: Panel) => p.type === "ChatPanel")) {
                // Check if this is a newly opened chat
                if (!hasChatPanel) {
                    setChatMessages([]);
                    setChatSuggestions([]);
                }
                // Don't auto-focus chat panel - let user control focus
                // User can Tab to switch panels or click on the chat panel
            }

            // Refresh progress after any action
            await fetchProgress();
        } catch (err) {
            console.error(err);
            speak("Something went wrong. Please try again.");
        } finally {
            setIsProcessing(false);
        }
    }, [context, isProcessing, hasChatPanel, speak]);

    // Send message to chat endpoint
    const sendChatMessage = useCallback(async (message: string) => {
        if (!message.trim() || isChatTyping) return;

        // Add user message immediately
        const userMessage: ChatMessage = { role: "user", content: message };
        setChatMessages(prev => [...prev, userMessage]);
        setIsChatTyping(true);
        setChatSuggestions([]);

        try {
            const res = await fetch(`${BACKEND_URL}/api/tutor/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: USER_ID,
                    message,
                    context: {
                        current_section_id: context.current_section,
                        current_section_title: context.section_title
                    },
                    history: chatMessages.slice(-10)
                }),
            });

            if (!res.ok) throw new Error("Failed to get response");
            const data = await res.json();

            // Add assistant message
            setChatMessages(prev => [...prev, data.message]);
            setChatSuggestions(data.suggestions || []);

            // Update progress if mastery changed from chat
            if (data.mastery_update) {
                await fetchProgress();
            }
        } catch (err) {
            console.error(err);
            setChatMessages(prev => [...prev, {
                role: "assistant",
                content: [{ type: "text", text: "Sorry, I encountered an error. Please try again." }]
            }]);
        } finally {
            setIsChatTyping(false);
        }
    }, [context, chatMessages, isChatTyping]);

    // Check if message is a tutor command (should always go to tutor endpoint)
    const isTutorCommand = (message: string): boolean => {
        const msg = message.toLowerCase().trim();
        const commandPrefixes = [
            "remove", "hide", "close", "teach", "go to", "next", "previous",
            "quiz", "mcq", "exercise", "show", "open book", "compare"
        ];
        return commandPrefixes.some(prefix => msg.startsWith(prefix));
    };

    // Unified message handler - routes to appropriate endpoint based on focus
    const handleSendMessage = useCallback((message: string) => {
        // Tutor commands always go to tutor endpoint, even when chat is focused
        if (isTutorCommand(message)) {
            sendTutorMessage(message);
        } else if (isChatFocused) {
            sendChatMessage(message);
        } else {
            sendTutorMessage(message);
        }
    }, [isChatFocused, sendChatMessage, sendTutorMessage]);

    // Handle closing a panel
    const handleClosePanel = (panelIndex: number) => {
        if (!ui) return;

        const closingPanel = ui.panels[panelIndex];

        // Clear chat state if closing chat panel
        if (closingPanel.type === "ChatPanel") {
            setChatMessages([]);
            setChatSuggestions([]);
            setIsChatTyping(false);
        }

        const newPanels = ui.panels.filter((_, i) => i !== panelIndex);
        setUI({ ...ui, panels: newPanels });

        // Reset focus
        if (focusedPanelIndex === panelIndex) {
            setFocusedPanelIndex(newPanels.length > 0 ? 0 : null);
        } else if (focusedPanelIndex !== null && focusedPanelIndex > panelIndex) {
            setFocusedPanelIndex(focusedPanelIndex - 1);
        }
    };

    // Handle suggestion click from chat
    const handleChatSuggestionClick = (suggestion: string) => {
        sendChatMessage(suggestion);
    };

    // Handle navigation to next section after celebration
    const handleNavigateNext = () => {
        if (celebrationData?.next_section_id) {
            sendTutorMessage(`teach me ${celebrationData.next_section_id}`);
        }
        setShowCelebration(false);
        setCelebrationData(null);
    };

    // Handle section click from progress bar
    const handleSectionClick = (sectionId: string) => {
        sendTutorMessage(`teach me ${sectionId}`);
    };

    // Handle exercise answer submission for LLM evaluation
    const handleExerciseSubmit = useCallback(async (exerciseLabel: string, answer: string) => {
        try {
            const response = await fetch(`${BACKEND_URL}/api/tutor/evaluate-exercise`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: USER_ID,
                    exercise_label: exerciseLabel,
                    student_answer: answer,
                    is_bonus: true
                })
            });

            if (!response.ok) {
                throw new Error("Failed to evaluate exercise");
            }

            const data = await response.json();

            // Refresh progress after exercise attempt
            await fetchProgress();

            return {
                isCorrect: data.is_correct,
                score: data.score,
                feedback: data.feedback,
                correctSolution: data.correct_solution,
                comparison: data.comparison,
                masteryChange: data.mastery_change,
                newMastery: data.new_mastery
            };
        } catch (error) {
            console.error("Exercise evaluation error:", error);
            // Return a fallback response
            return {
                isCorrect: false,
                score: 0,
                feedback: "Unable to evaluate your answer. Please try again.",
                correctSolution: "",
                comparison: "",
                masteryChange: 0,
                newMastery: 0
            };
        }
    }, []);

    // Get appropriate placeholder for InputBar
    const getInputPlaceholder = () => {
        if (isChatFocused) {
            return "Ask a question about the topic...";
        }
        return ui?.input_placeholder || "Talk to me...";
    };

    // Get focus label for InputBar
    const getFocusLabel = () => {
        if (isChatFocused) {
            const chatPanel = ui?.panels[chatPanelIndex];
            const sectionTitle = (chatPanel?.props?.context as any)?.current_section_title;
            return sectionTitle ? `Chat: ${sectionTitle}` : "AI Chat";
        }
        if (context.section_title) {
            return `Tutor: ${context.section_title}`;
        }
        return "Tutor";
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-black flex items-center justify-center">
                <motion.div
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="relative"
                >
                    <div className="w-24 h-24 rounded-full border-2 border-white/10 animate-pulse" />
                    <div className="absolute inset-0 w-24 h-24 rounded-full border-t-2 border-white/50 animate-spin" />
                    <motion.p
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.5 }}
                        className="mt-8 text-white/50 text-center font-light tracking-widest"
                    >
                        INITIALIZING
                    </motion.p>
                </motion.div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen bg-black flex items-center justify-center">
                <div className="text-red-400 text-center">
                    <p className="text-xl mb-4">Connection Failed</p>
                    <button
                        onClick={initSession}
                        className="px-6 py-3 bg-red-500/20 border border-red-500/50 rounded-full hover:bg-red-500/30 transition"
                    >
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="h-screen bg-black text-white flex flex-col overflow-hidden">
            {/* Header with Progress Bar */}
            <header className="flex-shrink-0 border-b border-white/5 backdrop-blur-xl bg-black/50 z-50">
                <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
                    <motion.h1
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="text-xl font-light tracking-tight"
                    >
                        <span className="text-white/60">AI</span>
                        <span className="text-white">Tutor</span>
                        <span className="text-white/40">.gen</span>
                    </motion.h1>

                    {/* Progress Bar */}
                    <div className="flex items-center gap-6">
                        <ProgressBar
                            currentSectionId={context.current_section as string}
                            lifetimeMastery={progress.lifetime_mastery}
                            sectionsProgress={progress.sections_progress}
                            explorationPoints={progress.exploration_points}
                            onSectionClick={handleSectionClick}
                        />

                        <nav className="flex gap-4 text-sm text-white/40 items-center">
                            <button
                                onClick={() => sendTutorMessage("show exercises")}
                                className="hover:text-white transition-colors duration-300"
                            >
                                Exercises
                            </button>
                            <button
                                onClick={() => sendTutorMessage("show topics")}
                                className="hover:text-white transition-colors duration-300"
                            >
                                Topics
                            </button>
                            <div className="w-px h-4 bg-white/10" />
                            <button
                                onClick={() => setVoiceEnabled(prev => !prev)}
                                className={`flex items-center gap-1.5 transition-colors duration-300 ${voiceEnabled ? 'text-emerald-400' : 'text-white/40 hover:text-white'}`}
                                title={voiceEnabled ? "Voice feedback enabled" : "Voice feedback disabled"}
                            >
                                {voiceEnabled ? (
                                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                                        <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                                        <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
                                    </svg>
                                ) : (
                                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                                        <line x1="23" y1="9" x2="17" y2="15" />
                                        <line x1="17" y1="9" x2="23" y2="15" />
                                    </svg>
                                )}
                                <span className="text-xs">Voice</span>
                            </button>
                        </nav>
                    </div>
                </div>
            </header>

            {/* Dynamic Content Area */}
            <main className="flex-1 overflow-hidden relative min-h-0">
                <AnimatePresence mode="wait">
                    {ui && (
                        <motion.div
                            key={JSON.stringify(ui.layout)}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className={`h-full p-6 overflow-hidden ${getLayoutClasses(ui.layout)}`}
                            style={ui.layout === "dynamic" ? {
                                gridTemplateColumns: calculateGridColumns(ui.panels)
                            } : undefined}
                        >
                            {ui.panels.map((panel, index) => (
                                <DynamicPanel
                                    key={`${panel.type}-${index}`}
                                    panel={panel}
                                    index={index}
                                    totalPanels={ui.panels.length}
                                    layout={ui.layout}
                                    onAction={(action) => sendTutorMessage(action, true)}
                                    calculatedWidth={ui.layout === "dynamic" ? calculatePanelWidth(panel, ui.panels) : undefined}
                                    isFocused={focusedPanelIndex === index}
                                    onFocus={() => setFocusedPanelIndex(index)}
                                    onClose={() => handleClosePanel(index)}
                                    // Chat-specific props
                                    chatMessages={panel.type === "ChatPanel" ? chatMessages : undefined}
                                    isChatTyping={panel.type === "ChatPanel" ? isChatTyping : undefined}
                                    chatSuggestions={panel.type === "ChatPanel" ? chatSuggestions : undefined}
                                    onChatSuggestionClick={panel.type === "ChatPanel" ? handleChatSuggestionClick : undefined}
                                    // Exercise-specific props
                                    onExerciseSubmit={panel.type === "ExercisePanel" ? handleExerciseSubmit : undefined}
                                />
                            ))}
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Subtle Background Grid */}
                <div className="absolute inset-0 pointer-events-none overflow-hidden -z-10">
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_white_1px,_transparent_1px)] bg-[size:40px_40px] opacity-[0.02]" />
                </div>
            </main>

            {/* Suggested Action Buttons - use isAction=true to skip LLM */}
            {ui?.suggested_actions && ui.suggested_actions.length > 0 && (
                <div className="flex justify-center gap-3 py-3 px-6 bg-black/20 backdrop-blur-sm border-t border-white/10">
                    {ui.suggested_actions.map((action, idx) => (
                        <button
                            key={idx}
                            onClick={() => sendTutorMessage(action.action, true)}
                            disabled={isProcessing}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${action.primary
                                ? 'bg-gradient-to-r from-violet-600 to-purple-600 text-white hover:from-violet-500 hover:to-purple-500 shadow-lg shadow-violet-500/25'
                                : 'bg-white/10 text-white/80 hover:bg-white/20 hover:text-white border border-white/20'
                                } disabled:opacity-50 disabled:cursor-not-allowed`}
                        >
                            {action.label}
                        </button>
                    ))}
                </div>
            )}

            {/* Input Mode Toggle - Only shown when quiz/mcq is focused */}
            {(focusedPanelType === "QuizCard" || focusedPanelType === "MCQCard") && (
                <div className="flex items-center gap-2 mb-2 px-4">
                    <span className="text-xs text-white/40">Mode:</span>
                    <button
                        onClick={() => setInputMode("answer")}
                        className={`px-3 py-1.5 rounded-lg text-sm transition-all ${inputMode === "answer"
                            ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                            : "bg-white/5 text-white/50 hover:bg-white/10"
                            }`}
                    >
                        📝 Answer
                    </button>
                    <button
                        onClick={() => setInputMode("ask")}
                        className={`px-3 py-1.5 rounded-lg text-sm transition-all ${inputMode === "ask"
                            ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                            : "bg-white/5 text-white/50 hover:bg-white/10"
                            }`}
                    >
                        💬 Ask
                    </button>
                </div>
            )}

            {/* Unified Input Bar - Always visible */}
            <InputBar
                ref={inputRef}
                placeholder={getInputPlaceholder()}
                onSend={handleSendMessage}
                isProcessing={isProcessing || isChatTyping}
                hint={ui?.next_prompt}
                focusTarget={isChatFocused ? "chat" : "tutor"}
                focusLabel={getFocusLabel()}
            />

            {/* Celebration Modal */}
            <CelebrationModal
                isOpen={showCelebration}
                onClose={() => {
                    setShowCelebration(false);
                    setCelebrationData(null);
                }}
                sectionTitle={celebrationData?.section_title || ""}
                masteryPercent={celebrationData?.mastery_percent || 0}
                nextSectionTitle={celebrationData?.next_section_title}
                onNavigateNext={handleNavigateNext}
                autoNavigateDelay={5000}
            />
        </div>
    );
}

function getLayoutClasses(layout: LayoutMode): string {
    switch (layout) {
        case "focus":
            // Single panel fills the entire space
            return "flex h-full";
        case "split":
            return "grid grid-cols-2 gap-6 h-full";
        case "compare":
            return "grid grid-cols-[1fr_2fr] gap-6 h-full";
        case "stack":
            return "flex flex-col gap-4 items-center overflow-y-auto";
        case "dynamic":
            // Use grid for better height control - panels will fill available height
            return "grid gap-6 h-full";
        default:
            return "flex h-full";
    }
}

// Calculate grid-template-columns for dynamic layout
function calculateGridColumns(panels: Panel[]): string {
    return panels.map(panel => {
        if (panel.width) return panel.width;
        const role = panel.role || "primary";
        if (role === "auxiliary") return "minmax(200px, 25%)";
        return "1fr"; // Primary panels share remaining space equally
    }).join(" ");
}

// Calculate dynamic widths based on panel roles (for backwards compatibility)
function calculatePanelWidth(panel: Panel, allPanels: Panel[]): string {
    // If explicit width is provided, use it
    if (panel.width) return panel.width;

    const role = panel.role || "primary";
    const auxiliaryPanels = allPanels.filter(p => p.role === "auxiliary");
    const primaryPanels = allPanels.filter(p => (p.role || "primary") === "primary");

    // Auxiliary panels get fixed 25%
    if (role === "auxiliary") return "25%";

    // Calculate remaining space for primary panels
    const auxiliaryWidth = auxiliaryPanels.length * 25;
    const remainingWidth = 100 - auxiliaryWidth;
    const primaryWidth = remainingWidth / Math.max(primaryPanels.length, 1);

    return `${primaryWidth}%`;
}

export { calculatePanelWidth, calculateGridColumns };

