"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import "katex/dist/katex.min.css";
import { Sigma, ChevronLeft, ChevronRight } from "lucide-react";
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
    stepByStep?: boolean;  // Enable carousel mode
    loading?: boolean;  // Show skeleton loading state
    onAction?: (action: string) => void;
}

// Skeleton loading component for derivation
const DerivationSkeleton = () => (
    <div className="p-6 bg-gradient-to-br from-blue-500/10 to-purple-500/10 rounded-3xl border border-white/10 backdrop-blur-sm">
        <div className="animate-pulse space-y-6">
            {/* Header skeleton */}
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-white/10 rounded-lg"></div>
                <div className="h-6 bg-white/10 rounded w-32"></div>
            </div>

            {/* Formula skeletons */}
            <div className="space-y-4">
                <div className="h-16 bg-white/10 rounded-lg w-4/5 mx-auto"></div>
                <div className="h-4 bg-white/10 rounded w-2/3 mx-auto"></div>
            </div>

            <div className="space-y-4">
                <div className="h-16 bg-white/10 rounded-lg w-3/4 mx-auto"></div>
                <div className="h-4 bg-white/10 rounded w-1/2 mx-auto"></div>
            </div>

            <div className="space-y-4">
                <div className="h-16 bg-white/10 rounded-lg w-5/6 mx-auto"></div>
                <div className="h-4 bg-white/10 rounded w-3/5 mx-auto"></div>
            </div>
        </div>
    </div>
);

export default function DerivationBlock({
    title = "Derivation",
    derivations,
    stepByStep = false,
    loading = false,
}: DerivationBlockProps) {
    const [currentStep, setCurrentStep] = useState(0);
    const totalSteps = derivations?.length || 0;

    const goToNext = () => {
        if (currentStep < totalSteps - 1) {
            setCurrentStep(currentStep + 1);
        }
    };

    const goToPrev = () => {
        if (currentStep > 0) {
            setCurrentStep(currentStep - 1);
        }
    };

    // Show skeleton loader if loading
    if (loading) {
        return <DerivationSkeleton />;
    }

    // Step-by-step mode (carousel)
    if (stepByStep && totalSteps > 0) {
        const currentDerivation = derivations[currentStep];

        return (
            <div className="p-6 bg-gradient-to-br from-blue-500/10 to-purple-500/10 rounded-3xl border border-white/10 backdrop-blur-sm">
                {/* Header with step indicator */}
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-500/20 rounded-lg">
                            <Sigma className="w-5 h-5 text-blue-400" />
                        </div>
                        <h3 className="text-lg font-medium bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                            {title}
                        </h3>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-white/40">
                            Step {currentStep + 1} of {totalSteps}
                        </span>
                        {/* Progress dots */}
                        <div className="flex gap-1">
                            {derivations.map((_, i) => (
                                <button
                                    key={i}
                                    onClick={() => setCurrentStep(i)}
                                    className={`w-2 h-2 rounded-full transition-all ${i === currentStep
                                        ? "bg-blue-400 w-4"
                                        : i < currentStep
                                            ? "bg-blue-400/50"
                                            : "bg-white/20"
                                        }`}
                                />
                            ))}
                        </div>
                    </div>
                </div>

                {/* Current Step Content */}
                <AnimatePresence mode="wait">
                    <motion.div
                        key={currentStep}
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        transition={{ duration: 0.3 }}
                        className="p-6 bg-black/30 rounded-2xl border border-white/5 min-h-[150px]"
                    >
                        <div className="overflow-x-auto text-xl">
                            <BlockMath>{cleanLatex(currentDerivation.latex)}</BlockMath>
                        </div>
                        {currentDerivation.description && (
                            <motion.p
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: 0.2 }}
                                className="mt-4 text-base text-white/60 italic border-t border-white/5 pt-4"
                            >
                                {currentDerivation.description}
                            </motion.p>
                        )}
                    </motion.div>
                </AnimatePresence>

                {/* Navigation Buttons */}
                <div className="flex justify-between items-center mt-6">
                    <button
                        onClick={goToPrev}
                        disabled={currentStep === 0}
                        className={`flex items-center gap-2 px-4 py-2 rounded-xl transition-all ${currentStep === 0
                            ? "opacity-30 cursor-not-allowed"
                            : "bg-white/10 hover:bg-white/20 text-white/80 hover:text-white"
                            }`}
                    >
                        <ChevronLeft className="w-4 h-4" />
                        Previous
                    </button>

                    <button
                        onClick={goToNext}
                        disabled={currentStep === totalSteps - 1}
                        className={`flex items-center gap-2 px-4 py-2 rounded-xl transition-all ${currentStep === totalSteps - 1
                            ? "opacity-30 cursor-not-allowed"
                            : "bg-blue-500/20 hover:bg-blue-500/30 text-blue-300 hover:text-blue-200"
                            }`}
                    >
                        Next Step
                        <ChevronRight className="w-4 h-4" />
                    </button>
                </div>
            </div>
        );
    }

    // Default mode (all at once)
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
