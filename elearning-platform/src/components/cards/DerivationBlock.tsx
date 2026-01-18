"use client";

import { motion } from "framer-motion";
import "katex/dist/katex.min.css";
import { Sigma } from "lucide-react";
import dynamic from "next/dynamic";

const BlockMath = dynamic(
    () => import("react-katex").then((mod) => mod.BlockMath),
    { ssr: false, loading: () => <div className="animate-pulse h-8 bg-white/10 rounded" /> }
);

// Helper to clean LaTeX for rendering
const cleanLatex = (latex: string) => {
    return latex.replace(/\$\$/g, "").trim();
};

interface Derivation {
    latex: string;
    description?: string;
}

interface DerivationBlockProps {
    title?: string;
    derivations: Derivation[];
    onAction?: (action: string) => void;
}

export default function DerivationBlock({
    title = "Derivation",
    derivations,
}: DerivationBlockProps) {
    return (
        <div className="p-6 bg-gradient-to-br from-blue-500/10 to-purple-500/10 rounded-3xl border border-white/10 backdrop-blur-sm">
            {/* Header */}
            <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-blue-500/20 rounded-lg">
                    <Sigma className="w-5 h-5 text-blue-400" />
                </div>
                <h3 className="text-lg font-medium bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                    {title}
                </h3>
            </div>

            {/* Derivations */}
            <div className="space-y-6">
                {derivations.map((d, i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.15 }}
                        className="p-4 bg-black/30 rounded-2xl border border-white/5"
                    >
                        <div className="overflow-x-auto text-lg">
                            <BlockMath>{cleanLatex(d.latex)}</BlockMath>
                        </div>
                        {d.description && (
                            <motion.p
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: 0.3 }}
                                className="mt-3 text-sm text-white/50 italic border-t border-white/5 pt-3"
                            >
                                {d.description}
                            </motion.p>
                        )}
                    </motion.div>
                ))}
            </div>
        </div>
    );
}
