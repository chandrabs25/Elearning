"use client";

import { motion } from "framer-motion";
import { HelpCircle } from "lucide-react";

interface QuizCardProps {
    question: string;
    concept_id: string;
    type?: string;
    glow?: boolean;
    onAction?: (action: string) => void;
}

export default function QuizCard({
    question,
    concept_id,
    type = "open",
}: QuizCardProps) {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="relative p-8 bg-gradient-to-br from-amber-500/10 to-orange-500/10 rounded-3xl border border-amber-500/20 backdrop-blur-sm overflow-hidden"
        >
            {/* Decorative pulse */}
            <motion.div
                animate={{
                    scale: [1, 1.2, 1],
                    opacity: [0.3, 0.1, 0.3],
                }}
                transition={{ repeat: Infinity, duration: 3 }}
                className="absolute inset-0 bg-gradient-to-r from-amber-500/10 to-orange-500/10 rounded-3xl"
            />

            <div className="relative">
                {/* Header */}
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 bg-amber-500/20 rounded-lg">
                        <HelpCircle className="w-6 h-6 text-amber-400" />
                    </div>
                    <div>
                        <span className="text-xs text-amber-400/60 uppercase tracking-wider">
                            Concept Check
                        </span>
                        <p className="text-xs text-white/40 font-mono">{concept_id}</p>
                    </div>
                </div>

                {/* Question */}
                <p className="text-xl text-white/90 leading-relaxed mb-4">{question}</p>

                {/* Hint */}
                <p className="text-sm text-white/40">
                    Type your answer below. Think through the problem step by step.
                </p>
            </div>
        </motion.div>
    );
}
