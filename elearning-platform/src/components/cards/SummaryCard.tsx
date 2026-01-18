"use client";

import { motion } from "framer-motion";
import { TrendingUp, AlertTriangle, Award } from "lucide-react";

interface MasteryItem {
    concept: string;
    level: number;
    title: string;
}

interface WeakArea {
    id: string;
    title: string;
    level: number;
}

interface SummaryCardProps {
    title?: string;
    mastery: MasteryItem[];
    weak_areas: WeakArea[];
    onAction?: (action: string) => void;
}

export default function SummaryCard({
    title = "Your Progress",
    mastery,
    weak_areas,
    onAction,
}: SummaryCardProps) {
    const avgScore = mastery.length > 0
        ? Math.round(mastery.reduce((sum, m) => sum + m.level, 0) / mastery.length)
        : 0;

    return (
        <div className="p-6 bg-gradient-to-br from-white/5 to-transparent rounded-3xl border border-white/10 backdrop-blur-sm max-w-lg">
            {/* Header */}
            <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-green-500/20 rounded-lg">
                    <TrendingUp className="w-5 h-5 text-green-400" />
                </div>
                <h3 className="text-lg font-medium text-white/80">{title}</h3>
            </div>

            {/* Overall Score */}
            <div className="flex items-center justify-center p-6 bg-white/5 rounded-2xl mb-6">
                <div className="text-center">
                    <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        className="text-5xl font-light text-white mb-2"
                    >
                        {avgScore}
                        <span className="text-xl text-white/40">%</span>
                    </motion.div>
                    <p className="text-sm text-white/40">Average Mastery</p>
                </div>
            </div>

            {/* Mastery Bars */}
            {mastery.length > 0 && (
                <div className="space-y-3 mb-6">
                    {mastery.slice(0, 5).map((m, i) => (
                        <motion.div
                            key={m.concept}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.1 }}
                            className="space-y-1"
                        >
                            <div className="flex justify-between text-sm">
                                <span className="text-white/60">{m.title || m.concept}</span>
                                <span className="text-white/40">{m.level}%</span>
                            </div>
                            <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                                <motion.div
                                    initial={{ width: 0 }}
                                    animate={{ width: `${m.level}%` }}
                                    transition={{ delay: i * 0.1 + 0.2, duration: 0.5 }}
                                    className={`h-full rounded-full ${m.level >= 70
                                            ? "bg-green-500"
                                            : m.level >= 40
                                                ? "bg-amber-500"
                                                : "bg-red-500"
                                        }`}
                                />
                            </div>
                        </motion.div>
                    ))}
                </div>
            )}

            {/* Weak Areas */}
            {weak_areas.length > 0 && (
                <div>
                    <div className="flex items-center gap-2 mb-3">
                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                        <span className="text-sm text-amber-400">Focus Areas</span>
                    </div>
                    <div className="space-y-2">
                        {weak_areas.map((area) => (
                            <button
                                key={area.id}
                                onClick={() => onAction?.(`teach me ${area.id}`)}
                                className="flex items-center justify-between w-full p-3 bg-amber-500/10 hover:bg-amber-500/20 rounded-xl transition-colors"
                            >
                                <span className="text-white/70">{area.title}</span>
                                <span className="text-amber-400 text-sm">{area.level}%</span>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Empty State */}
            {mastery.length === 0 && (
                <div className="text-center py-8">
                    <Award className="w-12 h-12 text-white/20 mx-auto mb-4" />
                    <p className="text-white/40">Start learning to track your progress!</p>
                </div>
            )}
        </div>
    );
}
