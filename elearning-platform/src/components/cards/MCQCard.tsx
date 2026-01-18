"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Circle } from "lucide-react";

interface MCQCardProps {
    question: string;
    options: string[]; // e.g., ["Option A", "Option B", ...]
    concept_id: string;
    glow?: boolean;
    onAction?: (action: string) => void;
}

export default function MCQCard({
    question,
    options,
    concept_id,
    onAction,
}: MCQCardProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="relative p-8 bg-gradient-to-br from-purple-500/10 to-blue-500/10 rounded-3xl border border-purple-500/20 backdrop-blur-sm overflow-hidden"
        >
            {/* Header */}
            <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-purple-500/20 rounded-lg">
                    <CheckCircle2 className="w-6 h-6 text-purple-400" />
                </div>
                <div>
                    <span className="text-xs text-purple-400/60 uppercase tracking-wider">
                        Quick Check
                    </span>
                    <p className="text-xs text-white/40 font-mono">{concept_id}</p>
                </div>
            </div>

            {/* Question */}
            <p className="text-xl text-white/90 leading-relaxed mb-6 font-medium">
                {question}
            </p>

            {/* Options */}
            <div className="space-y-3">
                {options.map((option, index) => (
                    <motion.button
                        key={index}
                        whileHover={{ scale: 1.02, backgroundColor: "rgba(168, 85, 247, 0.15)" }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => onAction?.(option)}
                        className="w-full text-left p-4 rounded-xl border border-white/10 bg-white/5 hover:border-purple-500/30 transition-all group flex items-start gap-4"
                    >
                        <div className="mt-0.5">
                            <Circle className="w-5 h-5 text-white/20 group-hover:text-purple-400 transition-colors" />
                        </div>
                        <span className="text-white/80 group-hover:text-white transition-colors">
                            {option}
                        </span>
                    </motion.button>
                ))}
            </div>

            <p className="text-xs text-white/30 mt-6 text-center">
                Select an option to submit your answer.
            </p>
        </motion.div>
    );
}
