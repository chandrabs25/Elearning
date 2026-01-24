"use client";

import { motion } from "framer-motion";
import { HelpCircle } from "lucide-react";
import "katex/dist/katex.min.css";
import dynamic from "next/dynamic";

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

                {/* Question with LaTeX support */}
                <p className="text-xl text-white/90 leading-relaxed mb-4">{parseInlineLatex(question)}</p>

                {/* Hint */}
                <p className="text-sm text-white/40">
                    Type your answer below. Think through the problem step by step.
                </p>
            </div>
        </motion.div>
    );
}

