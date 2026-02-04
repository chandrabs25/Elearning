"use client";

import { motion } from "framer-motion";
import WelcomeCard from "./cards/WelcomeCard";
import ExplanationPanel from "./cards/ExplanationPanel";
import NavigationMap from "./cards/NavigationMap";
import DerivationBlock from "./cards/DerivationBlock";
import QuizCard from "./cards/QuizCard";
import MCQCard from "./cards/MCQCard";
import SummaryCard from "./cards/SummaryCard";
import ChatPanel, { ChatMessage } from "./cards/ChatPanel";
import ExercisePanel from "./cards/ExercisePanel";

type LayoutMode = "focus" | "split" | "compare" | "stack" | "dynamic";
type PanelRole = "primary" | "secondary" | "auxiliary";

interface Panel {
    type: string;
    props: Record<string, unknown>;
    pinned?: boolean;
    animation?: string;
    role?: PanelRole;
    width?: string;
    loading?: boolean;  // Added loading state for skeleton rendering
}

interface DynamicPanelProps {
    panel: Panel;
    index: number;
    totalPanels: number;
    layout: LayoutMode;
    onAction: (action: string) => void;
    calculatedWidth?: string;
    isFocused?: boolean;
    onFocus?: () => void;
    onClose?: () => void;
    // Chat-specific props (passed to ChatPanel)
    chatMessages?: ChatMessage[];
    isChatTyping?: boolean;
    chatSuggestions?: string[];
    onChatSuggestionClick?: (suggestion: string) => void;
    onNextSection?: () => void;  // Continue to next section
    onAddMessages?: (messages: ChatMessage[]) => void;  // Add messages to chat
    // Exercise-specific props
    onExerciseSubmit?: (exerciseLabel: string, answer: string) => Promise<{
        isCorrect: boolean;
        score: number;
        feedback: string;
        correctSolution: string;
        comparison: string;
        masteryChange: number;
        newMastery: number;
    }>;
}

// Animation variants
const animations = {
    fadeIn: {
        initial: { opacity: 0 },
        animate: { opacity: 1 },
        exit: { opacity: 0 },
        transition: { duration: 0.5 },
    },
    scaleIn: {
        initial: { opacity: 0, scale: 0.9 },
        animate: { opacity: 1, scale: 1 },
        exit: { opacity: 0, scale: 0.9 },
        transition: { duration: 0.5, type: "spring" as const, bounce: 0.3 },
    },
    slideInLeft: {
        initial: { opacity: 0, x: -100 },
        animate: { opacity: 1, x: 0 },
        exit: { opacity: 0, x: -100 },
        transition: { duration: 0.5, type: "spring" as const, bounce: 0.2 },
    },
    slideInRight: {
        initial: { opacity: 0, x: 100 },
        animate: { opacity: 1, x: 0 },
        exit: { opacity: 0, x: 100 },
        transition: { duration: 0.5, type: "spring" as const, bounce: 0.2 },
    },
    pulseIn: {
        initial: { opacity: 0, scale: 0.95 },
        animate: {
            opacity: 1,
            scale: 1,
            boxShadow: ["0 0 0 0 rgba(59, 130, 246, 0)", "0 0 0 20px rgba(59, 130, 246, 0)"],
        },
        exit: { opacity: 0, scale: 0.95 },
        transition: { duration: 0.8 },
    },
    shrinkLeft: {
        initial: { opacity: 1, scale: 1 },
        animate: { opacity: 0.8, scale: 0.9 },
        transition: { duration: 0.3 },
    },
    expandRight: {
        initial: { opacity: 0, x: 50, scale: 0.95 },
        animate: { opacity: 1, x: 0, scale: 1 },
        transition: { duration: 0.5, delay: 0.2 },
    },
};

// FeedbackCard component with mastery change display
const FeedbackCard = ({
    message,
    status,
    masteryChange,
    newMastery,
    actions,
    onAction
}: {
    message: string;
    status: string;
    masteryChange?: number;
    newMastery?: number;
    actions?: Array<{ label: string; action: string }>;
    onAction?: (action: string) => void;
}) => {
    const statusStyles = {
        success: "border-green-500/30 bg-green-500/10",
        error: "border-red-500/30 bg-red-500/10",
        warning: "border-yellow-500/30 bg-yellow-500/10",
        info: "border-blue-500/30 bg-blue-500/10",
        thinking: "border-white/10 bg-white/5"
    };

    const style = statusStyles[status as keyof typeof statusStyles] || statusStyles.info;

    return (
        <div className={`p-8 rounded-3xl border ${style}`}>
            <p className="text-white/80 whitespace-pre-wrap">{message}</p>

            {/* Mastery Change Display */}
            {masteryChange !== undefined && (
                <div className="mt-4 flex items-center gap-4">
                    <span className={`text-lg font-bold ${masteryChange > 0 ? "text-green-400" : "text-red-400"}`}>
                        {masteryChange > 0 ? "+" : ""}{masteryChange} mastery
                    </span>
                    {newMastery !== undefined && (
                        <span className="text-white/40">
                            → {newMastery}% total
                        </span>
                    )}
                </div>
            )}

            {/* Action Buttons */}
            {actions && actions.length > 0 && (
                <div className="mt-6 flex gap-3">
                    {actions.map((action, idx) => (
                        <button
                            key={idx}
                            onClick={() => onAction?.(action.action)}
                            className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-xl text-white/80 hover:text-white transition-all text-sm"
                        >
                            {action.label}
                        </button>
                    ))}
                </div>
            )}

            {status === "thinking" && (
                <div className="mt-4 flex gap-2">
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" />
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce delay-100" />
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce delay-200" />
                </div>
            )}
        </div>
    );
};

// Component registry
const componentRegistry: Record<string, React.ComponentType<any>> = {
    WelcomeCard,
    ExplanationPanel,
    NavigationMap,
    DerivationBlock,
    QuizCard,
    MCQCard,
    SummaryCard,
    ChatPanel,
    ExercisePanel,
    FeedbackCard,
    PinnedPreview: ({ title, minimized }: { title: string; minimized: boolean }) => (
        <div className={`p-4 bg-white/5 rounded-2xl border border-white/10 ${minimized ? "opacity-60" : ""}`}>
            <p className="text-sm text-white/60">{title}</p>
        </div>
    ),
};

export default function DynamicPanel({
    panel,
    index,
    totalPanels,
    layout,
    onAction,
    calculatedWidth,
    isFocused,
    onFocus,
    onClose,
    chatMessages,
    isChatTyping,
    chatSuggestions,
    onChatSuggestionClick,
    onExerciseSubmit,
    onNextSection,
    onAddMessages,
}: DynamicPanelProps) {
    const Component = componentRegistry[panel.type];
    const animationPreset = panel.animation || "fadeIn";
    const animation = animations[animationPreset as keyof typeof animations] || animations.fadeIn;

    if (!Component) {
        console.warn(`Unknown component type: ${panel.type}`);
        return null;
    }

    // For grid layout, we don't need inline width styles - grid handles it
    const widthStyle = {};

    // Build props for the component - use Record to allow dynamic props
    let componentProps: Record<string, unknown> = { ...panel.props, onAction, loading: panel.loading };

    // Special handling for ChatPanel - pass controlled props
    if (panel.type === "ChatPanel") {
        // Ensure user_id is in the context for section status queries
        const chatContext = {
            ...(panel.props.context as Record<string, unknown> || {}),
            user_id: "demo-user"  // Match the USER_ID from tutor/page.tsx
        };
        componentProps = {
            ...componentProps,
            context: chatContext,
            messages: chatMessages || [],
            isTyping: isChatTyping || false,
            suggestions: chatSuggestions || [],
            isFocused,
            onFocus,
            onClose,
            onSuggestionClick: onChatSuggestionClick,
            onNextSection,
            onAddMessages,
        };
    } else if (panel.type === "ExercisePanel") {
        // Exercise panel needs async submit handler for LLM evaluation
        componentProps = {
            ...componentProps,
            onSubmitAnswer: onExerciseSubmit,
            onRequestHint: (exerciseLabel: string) => {
                onAction(`hint for ${exerciseLabel}`);
            },
        };
    } else {
        // For other panels that support focus
        componentProps = {
            ...componentProps,
            isFocused,
            onFocus,
        };
    }

    return (
        <motion.div
            {...animation}
            layout
            onClick={onFocus}
            className={`
                relative h-full min-h-0 overflow-hidden flex flex-col
                ${layout === "focus" ? "w-full flex-1" : ""}
                ${panel.pinned ? "ring-2 ring-white/20" : ""}
                ${isFocused && panel.type !== "ChatPanel" && totalPanels > 1
                    ? "ring-2 ring-blue-500/30 rounded-2xl border border-blue-500/50"
                    : ""
                }
            `}
            style={{
                transformOrigin: index === 0 ? "center left" : "center right",
            }}
        >

            <div className="relative flex-1 min-h-0 flex flex-col overflow-hidden">
                <Component {...componentProps} />
            </div>

            {/* Pin indicator */}
            {panel.pinned && (
                <div className="absolute top-2 right-2 px-2 py-1 bg-white/10 rounded-full text-xs text-white/60">
                    Pinned
                </div>
            )}
        </motion.div>
    );
}
