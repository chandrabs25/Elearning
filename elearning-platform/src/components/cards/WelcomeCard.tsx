"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, BookOpen, PlayCircle, ChevronDown, Terminal } from "lucide-react";

interface WelcomeCardProps {
    title: string;
    subtitle: string;
    topics?: { id: string; title: string }[];
    actions?: { label: string; action: string }[];
    lastSection?: { id: string; title: string };
    glow?: boolean;
    onAction?: (action: string) => void;
}

const ALL_COMMANDS = [
    {
        category: "Navigation", commands: [
            { cmd: "open 7.2", use: "Go to a specific section" },
            { cmd: "next", use: "Go to next section" },
            { cmd: "previous", use: "Go to previous section" },
            { cmd: "resume", use: "Continue where you left off" },
        ]
    },
    {
        category: "Learning", commands: [
            { cmd: "open chat", use: "Open tutor chat panel" },
            { cmd: "teach me", use: "Start teaching current section" },
            { cmd: "explain this", use: "Get detailed explanation" },
        ]
    },
    {
        category: "Practice", commands: [
            { cmd: "quiz", use: "In-chapter example problems" },
            { cmd: "mcqs", use: "AI-generated MCQs" },
            { cmd: "exercise", use: "End-of-chapter problems" },
        ]
    },
    {
        category: "Layout", commands: [
            { cmd: "focus", use: "Single panel view" },
            { cmd: "show chapters", use: "Show navigation panel" },
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
    const [commandsExpanded, setCommandsExpanded] = useState(false);

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="relative p-6 md:p-8 bg-neutral-900/50 rounded-2xl border border-white/5 overflow-hidden w-full h-full"
        >
            <div className="relative h-full overflow-y-auto scrollbar-thin scrollbar-thumb-white/40 scrollbar-track-transparent hover:scrollbar-thumb-white/60">
                {/* Header */}
                <div className="flex items-start justify-between gap-4 mb-6">
                    <div className="flex items-start gap-4">
                        <div className="p-2 bg-white/5 rounded-lg border border-white/10 flex-shrink-0">
                            <BookOpen className="w-6 h-6 text-white/60" />
                        </div>
                        <div>
                            <h1 className="text-2xl md:text-3xl font-light text-white mb-1">
                                {title}
                            </h1>
                            <p className="text-white/50">{subtitle}</p>
                        </div>
                    </div>

                    {/* Continue Button */}
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

                {/* How to Navigate - Clear Instructions */}
                <div className="mb-6 p-5 bg-black/30 rounded-xl border border-white/10">
                    <h3 className="text-sm font-medium text-white/80 mb-4 flex items-center gap-2">
                        <span className="text-lg">📖</span> How to Navigate
                    </h3>

                    <div className="space-y-3 text-sm text-white/60">
                        <p>
                            <span className="text-white/80">Click the buttons</span> or <span className="text-white/80">type commands</span> in the input bar below.
                        </p>

                        <div className="grid gap-2 mt-4">
                            <div className="flex items-start gap-3 p-3 bg-white/5 rounded-lg">
                                <code className="text-blue-400 font-mono text-xs bg-blue-500/10 px-2 py-1 rounded">resume</code>
                                <span className="text-white/50">Continue from where you left off</span>
                            </div>

                            <div className="flex items-start gap-3 p-3 bg-white/5 rounded-lg">
                                <code className="text-green-400 font-mono text-xs bg-green-500/10 px-2 py-1 rounded">open chat</code>
                                <span className="text-white/50">Open the tutor chat panel for teaching or doubts</span>
                            </div>

                            <div className="flex items-start gap-3 p-3 bg-white/5 rounded-lg">
                                <code className="text-amber-400 font-mono text-xs bg-amber-500/10 px-2 py-1 rounded">quiz</code>
                                <code className="text-amber-400 font-mono text-xs bg-amber-500/10 px-2 py-1 rounded ml-1">mcqs</code>
                                <code className="text-amber-400 font-mono text-xs bg-amber-500/10 px-2 py-1 rounded ml-1">exercise</code>
                                <span className="text-white/50">Practice problems</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Tab Mode Tip */}
                <div className="mb-6 p-4 bg-gradient-to-r from-purple-500/10 to-blue-500/10 rounded-xl border border-purple-500/20">
                    <p className="text-sm text-white/70">
                        <span className="text-white font-medium">💡 Tip:</span> Press <kbd className="px-2 py-0.5 bg-white/10 rounded text-xs mx-1">Tab</kbd> to switch between
                        <span className="text-blue-400"> 📖 Textbook</span> (navigation) and
                        <span className="text-green-400"> 🎓 Tutor</span> (chat/doubts).
                    </p>
                    <p className="text-xs text-white/40 mt-2">
                        Use Textbook mode for navigation commands. Use Tutor mode for asking doubts.
                    </p>
                </div>

                {/* All Commands Dropdown */}
                <div className="mb-6">
                    <button
                        onClick={() => setCommandsExpanded(!commandsExpanded)}
                        className="w-full flex items-center justify-between p-4 bg-black/20 hover:bg-black/30 rounded-xl border border-white/5 transition-all"
                    >
                        <div className="flex items-center gap-2">
                            <Terminal className="w-4 h-4 text-white/40" />
                            <span className="text-sm text-white/60">All Commands</span>
                        </div>
                        <ChevronDown className={`w-4 h-4 text-white/40 transition-transform ${commandsExpanded ? "rotate-180" : ""}`} />
                    </button>

                    <AnimatePresence>
                        {commandsExpanded && (
                            <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                exit={{ opacity: 0, height: 0 }}
                                className="overflow-hidden"
                            >
                                <div className="p-4 bg-black/20 rounded-b-xl border border-t-0 border-white/5 grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {ALL_COMMANDS.map((cat) => (
                                        <div key={cat.category}>
                                            <h4 className="text-[10px] uppercase tracking-wider text-white/30 mb-2">{cat.category}</h4>
                                            <div className="space-y-1">
                                                {cat.commands.map((item) => (
                                                    <div key={item.cmd} className="flex items-center gap-2 text-xs">
                                                        <code className="text-white/60 font-mono bg-white/5 px-1.5 py-0.5 rounded">{item.cmd}</code>
                                                        <span className="text-white/30">— {item.use}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* Topics */}
                {topics && topics.length > 0 && (
                    <div>
                        <h3 className="text-xs uppercase tracking-wider text-white/40 mb-3 font-medium">
                            Select a Topic to Start
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            {topics.map((topic, i) => (
                                <motion.button
                                    key={topic.id}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.2 + i * 0.03 }}
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
            </div>
        </motion.div>
    );
}
