"use client";

import { motion } from "framer-motion";
import { ArrowRight, Terminal, Sparkles, BookOpen, PlayCircle } from "lucide-react";

interface WelcomeCardProps {
    title: string;
    subtitle: string;
    topics?: { id: string; title: string }[];
    actions?: { label: string; action: string }[];
    lastSection?: { id: string; title: string };
    glow?: boolean;
    onAction?: (action: string) => void;
}

const COMMAND_CATEGORIES = [
    {
        category: "Navigation",
        commands: [
            { cmd: "teach me [topic]", desc: "Start learning a section", clickable: false },
            { cmd: "next", desc: "Go to next section", clickable: true },
            { cmd: "previous", desc: "Go to previous section", clickable: true },
            { cmd: "go to 7.3", desc: "Jump to specific section", clickable: true },
        ]
    },
    {
        category: "Testing",
        commands: [
            { cmd: "quiz me", desc: "Open-ended problem (closed book)", clickable: true },
            { cmd: "open book quiz", desc: "Problem with content visible", clickable: true },
            { cmd: "give me MCQs", desc: "Multiple choice (closed book)", clickable: true },
            { cmd: "open book MCQs", desc: "MCQs with content visible", clickable: true },
        ]
    },
    {
        category: "AI & Chat",
        commands: [
            { cmd: "open chat", desc: "Chat with AI tutor", clickable: true },
            { cmd: "explain this", desc: "Get detailed explanation", clickable: true },
            { cmd: "show derivation", desc: "See mathematical derivation", clickable: true },
            { cmd: "help me", desc: "Get assistance", clickable: true },
        ]
    },
    {
        category: "Practice",
        commands: [
            { cmd: "show exercises", desc: "Chapter practice problems", clickable: true },
            { cmd: "show my progress", desc: "View mastery summary", clickable: true },
        ]
    },
    {
        category: "Layout",
        commands: [
            { cmd: "also show [topic]", desc: "Compare sections side-by-side", clickable: false },
            { cmd: "remove chapter sections", desc: "Hide navigation panel", clickable: true },
            { cmd: "show chapters", desc: "Restore navigation panel", clickable: true },
            { cmd: "focus", desc: "Single panel view", clickable: true },
        ]
    },
];

export default function WelcomeCard({
    title,
    subtitle,
    topics,
    lastSection,
    onAction,
}: WelcomeCardProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="relative p-6 md:p-8 bg-neutral-900/50 rounded-2xl border border-white/5 overflow-hidden w-full h-full"
        >
            <div className="relative h-full overflow-y-auto scrollbar-thin scrollbar-thumb-white/40 scrollbar-track-transparent hover:scrollbar-thumb-white/60">
                {/* Header with Continue Button */}
                <div className="flex items-start justify-between gap-4 mb-6">
                    <div className="flex items-start gap-4">
                        <div className="p-2 bg-white/5 rounded-lg border border-white/10 flex-shrink-0">
                            <Sparkles className="w-6 h-6 text-white/60" />
                        </div>
                        <div>
                            <h1 className="text-2xl md:text-3xl font-light text-white mb-1">
                                {title}
                            </h1>
                            <p className="text-white/50">{subtitle}</p>
                        </div>
                    </div>

                    {/* Continue Button - Context Aware (Blue for action) */}
                    {lastSection && (
                        <motion.button
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: 0.3 }}
                            onClick={() => onAction?.(`start:${lastSection.id}`)}
                            className="flex-shrink-0 flex items-center gap-3 px-4 py-3 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 hover:border-blue-500/50 rounded-xl transition-all group"
                        >
                            <PlayCircle className="w-5 h-5 text-blue-400" />
                            <div className="text-left">
                                <p className="text-xs text-blue-400/80 uppercase tracking-wide">Continue</p>
                                <p className="text-sm text-white/80 group-hover:text-white">
                                    {lastSection.title}
                                </p>
                            </div>
                            <ArrowRight className="w-4 h-4 text-blue-400/50 group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
                        </motion.button>
                    )}
                </div>

                {/* Source Attribution */}
                <div className="mb-6 p-4 bg-black/30 rounded-xl border border-white/5">
                    <div className="flex items-start gap-3">
                        <BookOpen className="w-5 h-5 text-white/40 flex-shrink-0 mt-0.5" />
                        <div>
                            <p className="text-white/60 text-sm leading-relaxed mb-2">
                                This AI tutor is built on <span className="text-white/80 font-medium">Chapter 7: Gravitation</span> from
                                the <span className="text-white/80">Class 11 NCERT Physics</span> textbook.
                            </p>
                            <p className="text-white/40 text-xs">
                                The interface uses <span className="text-white/60">generative UI</span> — it adapts dynamically based on your commands.
                                Type natural language to navigate, test yourself, or chat with AI.
                            </p>
                        </div>
                    </div>
                </div>

                {/* Command Reference */}
                <div className="mb-6">
                    <div className="flex items-center gap-2 mb-4">
                        <Terminal className="w-4 h-4 text-white/40" />
                        <span className="text-xs uppercase tracking-wider text-white/40 font-medium">
                            Command Reference
                        </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {COMMAND_CATEGORIES.map((cat, catIndex) => (
                            <motion.div
                                key={cat.category}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.1 + catIndex * 0.05 }}
                                className="bg-black/20 rounded-xl border border-white/5 p-4"
                            >
                                <h3 className="text-xs uppercase tracking-wider text-white/30 mb-3 font-medium">
                                    {cat.category}
                                </h3>
                                <div className="space-y-2">
                                    {cat.commands.map((item) => (
                                        <button
                                            key={item.cmd}
                                            onClick={() => item.clickable && onAction?.(item.cmd)}
                                            disabled={!item.clickable}
                                            className={`w-full text-left p-2 rounded-lg transition-all ${item.clickable
                                                    ? "hover:bg-white/5 cursor-pointer"
                                                    : "cursor-default opacity-70"
                                                }`}
                                        >
                                            <code className="text-white/70 text-xs font-mono block">
                                                {item.cmd}
                                            </code>
                                            <p className="text-white/30 text-[10px] mt-0.5">{item.desc}</p>
                                        </button>
                                    ))}
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>

                {/* Topics */}
                {topics && topics.length > 0 && (
                    <div>
                        <h3 className="text-xs uppercase tracking-wider text-white/40 mb-3 font-medium">
                            Quick Start — Select a Topic
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                            {topics.map((topic, i) => (
                                <motion.button
                                    key={topic.id}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.3 + i * 0.03 }}
                                    onClick={() => onAction?.(`start:${topic.id}`)}
                                    className="group flex items-center gap-3 p-3 bg-white/5 hover:bg-white/10 rounded-xl border border-white/5 hover:border-white/20 transition-all duration-200"
                                >
                                    <span className="text-white/40 font-mono text-xs">
                                        {topic.id}
                                    </span>
                                    <span className="text-white/60 group-hover:text-white text-sm transition-colors truncate">
                                        {topic.title}
                                    </span>
                                    <ArrowRight className="w-3 h-3 text-white/20 group-hover:text-white/50 ml-auto flex-shrink-0 transition-all group-hover:translate-x-0.5" />
                                </motion.button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Footer */}
                <div className="mt-8 pt-4 border-t border-white/5 text-center">
                    <p className="text-[10px] text-white/20">
                        Type a command in the input bar below or click any topic to begin
                    </p>
                </div>
            </div>
        </motion.div>
    );
}
