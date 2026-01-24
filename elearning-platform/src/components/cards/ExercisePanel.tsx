"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import "katex/dist/katex.min.css";
import dynamic from "next/dynamic";

const InlineMath = dynamic(
    () => import("react-katex").then((mod) => mod.InlineMath),
    { ssr: false, loading: () => <span className="animate-pulse bg-white/10 rounded px-2">...</span> }
);
const BlockMath = dynamic(
    () => import("react-katex").then((mod) => mod.BlockMath),
    { ssr: false, loading: () => <div className="animate-pulse h-8 bg-white/10 rounded" /> }
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

interface Exercise {
    label: string;
    question: string;
    sub_questions?: { label: string; body: string }[];
    body?: string;
    hint?: string;
}

interface EvaluationResult {
    isCorrect: boolean;
    score: number;
    feedback: string;
    correctSolution: string;
    comparison: string;
    masteryChange: number;
    newMastery: number;
}

interface ExercisePanelProps {
    title: string;
    sectionId: string;
    sectionTitle: string;
    exercises: Exercise[];
    onSubmitAnswer: (exerciseLabel: string, answer: string) => Promise<EvaluationResult>;
    onRequestHint: (exerciseLabel: string) => void;
    completedExercises?: string[];
    bonusAvailable?: boolean;
}

export default function ExercisePanel({
    title,
    sectionId,
    sectionTitle,
    exercises,
    onSubmitAnswer,
    onRequestHint,
    completedExercises = [],
    bonusAvailable = true
}: ExercisePanelProps) {
    const [selectedExercise, setSelectedExercise] = useState<Exercise | null>(null);
    const [userAnswer, setUserAnswer] = useState("");
    const [showHint, setShowHint] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [evaluationResult, setEvaluationResult] = useState<EvaluationResult | null>(null);
    const [showSolution, setShowSolution] = useState(false);

    const handleSubmit = async () => {
        if (selectedExercise && userAnswer.trim() && !isSubmitting) {
            setIsSubmitting(true);
            try {
                const result = await onSubmitAnswer(selectedExercise.label, userAnswer);
                setEvaluationResult(result);
                setShowSolution(true);
            } catch (error) {
                console.error("Failed to submit answer:", error);
            } finally {
                setIsSubmitting(false);
            }
        }
    };

    const handleRequestHint = () => {
        if (selectedExercise) {
            onRequestHint(selectedExercise.label);
            setShowHint(true);
        }
    };

    const handleSelectExercise = (exercise: Exercise) => {
        setSelectedExercise(exercise);
        setShowHint(false);
        setUserAnswer("");
        setEvaluationResult(null);
        setShowSolution(false);
    };

    const handleTryAgain = () => {
        setUserAnswer("");
        setEvaluationResult(null);
        setShowSolution(false);
    };

    const isCompleted = (label: string) => completedExercises.includes(label);

    return (
        <div className="h-full flex flex-col bg-gradient-to-br from-gray-900/50 to-black/50 rounded-2xl border border-white/10 overflow-hidden">
            {/* Header */}
            <div className="flex-shrink-0 p-4 border-b border-white/10 bg-gradient-to-r from-purple-500/10 to-indigo-500/10">
                <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                            <svg className="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                            </svg>
                            {title}
                        </h3>
                        <p className="text-sm text-white/50 mt-1">
                            Related to: {sectionTitle}
                        </p>
                    </div>
                    {bonusAvailable && (
                        <div className="px-3 py-1 bg-yellow-500/20 border border-yellow-500/30 rounded-full">
                            <span className="text-xs text-yellow-400 font-medium">⭐ Bonus Available</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 flex overflow-hidden min-h-0">
                {/* Exercise List */}
                <div className="w-1/3 border-r border-white/10 overflow-y-auto scrollbar-thin scrollbar-thumb-white/40 hover:scrollbar-thumb-white/60 p-3 space-y-2">
                    {exercises.map((exercise, index) => (
                        <motion.button
                            key={exercise.label}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: index * 0.05 }}
                            onClick={() => handleSelectExercise(exercise)}
                            className={`w-full text-left p-3 rounded-xl transition-all ${selectedExercise?.label === exercise.label
                                ? "bg-purple-500/20 border border-purple-500/30"
                                : "bg-white/5 hover:bg-white/10 border border-transparent"
                                }`}
                        >
                            <div className="flex items-center justify-between">
                                <span className={`text-sm font-medium ${selectedExercise?.label === exercise.label
                                    ? "text-purple-400"
                                    : "text-white/80"
                                    }`}>
                                    {exercise.label}
                                </span>
                                {isCompleted(exercise.label) && (
                                    <span className="w-5 h-5 bg-green-500/20 rounded-full flex items-center justify-center">
                                        <svg className="w-3 h-3 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                        </svg>
                                    </span>
                                )}
                            </div>
                            <p className="text-xs text-white/40 mt-1 line-clamp-2">
                                {exercise.question.substring(0, 60)}...
                            </p>
                        </motion.button>
                    ))}
                </div>

                {/* Exercise Detail */}
                <div className="flex-1 p-4 overflow-y-auto scrollbar-thin scrollbar-thumb-white/40 hover:scrollbar-thumb-white/60">
                    <AnimatePresence mode="wait">
                        {selectedExercise ? (
                            <motion.div
                                key={selectedExercise.label}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -10 }}
                                className="space-y-4"
                            >
                                {/* Question */}
                                <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                                    <h4 className="text-purple-400 font-medium mb-2">{selectedExercise.label}</h4>
                                    <p className="text-white/80 leading-relaxed">{parseInlineLatex(selectedExercise.question)}</p>

                                    {selectedExercise.body && (
                                        <p className="text-white/60 mt-2">{parseInlineLatex(selectedExercise.body)}</p>
                                    )}

                                    {/* Sub Questions */}
                                    {selectedExercise.sub_questions && selectedExercise.sub_questions.length > 0 && (
                                        <div className="mt-4 space-y-2 pl-4 border-l-2 border-purple-500/30">
                                            {selectedExercise.sub_questions.map((sq, i) => (
                                                <div key={i} className="text-sm">
                                                    <span className="text-purple-400 font-medium">{sq.label}</span>
                                                    <span className="text-white/60 ml-2">{parseInlineLatex(sq.body)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {/* Hint */}
                                {showHint && selectedExercise.hint && (
                                    <motion.div
                                        initial={{ opacity: 0, height: 0 }}
                                        animate={{ opacity: 1, height: "auto" }}
                                        className="bg-yellow-500/10 rounded-xl p-4 border border-yellow-500/20"
                                    >
                                        <div className="flex items-center gap-2 text-yellow-400 text-sm font-medium mb-2">
                                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                                            </svg>
                                            Hint
                                        </div>
                                        <p className="text-yellow-200/70 text-sm">{selectedExercise.hint}</p>
                                    </motion.div>
                                )}

                                {/* Evaluation Result */}
                                {evaluationResult && (
                                    <motion.div
                                        initial={{ opacity: 0, scale: 0.95 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        className={`rounded-xl p-4 border ${evaluationResult.isCorrect
                                            ? "bg-emerald-500/10 border-emerald-500/30"
                                            : "bg-orange-500/10 border-orange-500/30"
                                            }`}
                                    >
                                        {/* Score Header */}
                                        <div className="flex items-center gap-4 mb-3">
                                            <div className={`text-3xl font-bold ${evaluationResult.isCorrect ? "text-emerald-400" : "text-orange-400"
                                                }`}>
                                                {evaluationResult.score}%
                                            </div>
                                            <div className="flex-1">
                                                <div className={`text-sm font-medium ${evaluationResult.isCorrect ? "text-emerald-400" : "text-orange-400"
                                                    }`}>
                                                    {evaluationResult.isCorrect ? "✓ Correct!" : "✗ Needs Improvement"}
                                                </div>
                                                <div className="text-white/60 text-sm mt-1">
                                                    {evaluationResult.feedback}
                                                </div>
                                            </div>
                                            <div className={`px-2 py-1 rounded text-xs font-medium ${evaluationResult.masteryChange > 0
                                                ? "bg-green-500/20 text-green-400"
                                                : "bg-red-500/20 text-red-400"
                                                }`}>
                                                {evaluationResult.masteryChange > 0 ? "+" : ""}{evaluationResult.masteryChange} mastery
                                            </div>
                                        </div>

                                        {/* Comparison (if not fully correct) */}
                                        {evaluationResult.comparison && !evaluationResult.isCorrect && (
                                            <div className="text-sm text-yellow-200/70 mb-3 p-2 bg-yellow-500/5 rounded-lg">
                                                💡 {evaluationResult.comparison}
                                            </div>
                                        )}

                                        {/* Solution Reveal */}
                                        <details className="mt-3 group" open={showSolution}>
                                            <summary className="cursor-pointer text-emerald-400 font-medium text-sm hover:text-emerald-300 transition-colors list-none flex items-center gap-2">
                                                <svg className="w-4 h-4 transition-transform group-open:rotate-90" fill="currentColor" viewBox="0 0 20 20">
                                                    <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                                                </svg>
                                                📖 View Correct Solution
                                            </summary>
                                            <motion.div
                                                initial={{ opacity: 0 }}
                                                animate={{ opacity: 1 }}
                                                className="mt-3 pl-4 border-l-2 border-emerald-500/30 text-white/80 text-sm leading-relaxed whitespace-pre-wrap"
                                            >
                                                {evaluationResult.correctSolution}
                                            </motion.div>
                                        </details>

                                        {/* Try Again Button */}
                                        {!evaluationResult.isCorrect && (
                                            <button
                                                onClick={handleTryAgain}
                                                className="mt-4 w-full px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-white/70 hover:bg-white/10 hover:text-white transition-all text-sm"
                                            >
                                                🔄 Try Again
                                            </button>
                                        )}
                                    </motion.div>
                                )}

                                {/* Answer Input - only show if not evaluated yet */}
                                {!evaluationResult && (
                                    <div className="space-y-3">
                                        <textarea
                                            value={userAnswer}
                                            onChange={(e) => setUserAnswer(e.target.value)}
                                            placeholder="Describe your approach to solving this problem..."
                                            className="w-full h-32 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:outline-none focus:border-purple-500/50 resize-none"
                                            disabled={isSubmitting}
                                        />

                                        <div className="flex gap-3">
                                            <button
                                                onClick={handleRequestHint}
                                                disabled={isSubmitting}
                                                className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-white/60 hover:bg-white/10 hover:text-white transition-all text-sm disabled:opacity-50"
                                            >
                                                💡 Get Hint
                                            </button>
                                            <button
                                                onClick={handleSubmit}
                                                disabled={!userAnswer.trim() || isSubmitting}
                                                className="flex-1 px-4 py-2 bg-gradient-to-r from-purple-500 to-indigo-600 rounded-xl text-white font-medium hover:from-purple-600 hover:to-indigo-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                            >
                                                {isSubmitting ? (
                                                    <>
                                                        <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                                        Evaluating...
                                                    </>
                                                ) : (
                                                    "Submit Answer"
                                                )}
                                            </button>
                                        </div>
                                    </div>
                                )}

                                {/* Bonus Info */}
                                {bonusAvailable && !isCompleted(selectedExercise.label) && !evaluationResult && (
                                    <div className="text-center text-xs text-white/40 pt-2">
                                        ⭐ Correctly solving this earns <span className="text-yellow-400">+5 bonus mastery</span>
                                    </div>
                                )}
                            </motion.div>
                        ) : (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="h-full flex items-center justify-center"
                            >
                                <div className="text-center text-white/40">
                                    <svg className="w-16 h-16 mx-auto mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                                    </svg>
                                    <p>Select an exercise to begin</p>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </div>
    );
}

