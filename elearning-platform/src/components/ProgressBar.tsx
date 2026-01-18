"use client";

import { motion } from "framer-motion";
import { useState } from "react";

interface SectionProgress {
    id: string;
    title: string;
    mastery: number;
    completed: boolean;
}

interface ProgressBarProps {
    currentSectionId?: string;
    lifetimeMastery: number;
    sectionsProgress: SectionProgress[];
    explorationPoints?: number;
    onSectionClick?: (sectionId: string) => void;
}

// Context-aware color helpers
const getMasteryBarColor = (mastery: number) => {
    if (mastery >= 70) return "bg-emerald-500";  // Success - mastered
    if (mastery >= 40) return "bg-amber-500";    // Warning - in progress
    return "bg-white/40";                         // Default - low
};

const getMasteryTextColor = (mastery: number) => {
    if (mastery >= 70) return "text-emerald-400";
    if (mastery >= 40) return "text-amber-400";
    return "text-white/60";
};

const getMasteryRingColor = (mastery: number) => {
    if (mastery >= 70) return "#10b981"; // emerald-500
    if (mastery >= 40) return "#f59e0b"; // amber-500
    return "rgba(255,255,255,0.4)";
};

export default function ProgressBar({
    currentSectionId,
    lifetimeMastery,
    sectionsProgress,
    explorationPoints = 0,
    onSectionClick
}: ProgressBarProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    
    const completedSections = sectionsProgress.filter(s => s.completed).length;
    const totalSections = sectionsProgress.length;

    return (
        <div className="relative">
            {/* Main Progress Bar */}
            <div 
                className="flex items-center gap-3 cursor-pointer group"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                {/* Progress Ring - Context aware color */}
                <div className="relative w-10 h-10">
                    <svg className="w-10 h-10 transform -rotate-90">
                        <circle
                            cx="20"
                            cy="20"
                            r="16"
                            stroke="currentColor"
                            strokeWidth="3"
                            fill="transparent"
                            className="text-white/10"
                        />
                        <motion.circle
                            cx="20"
                            cy="20"
                            r="16"
                            stroke={getMasteryRingColor(lifetimeMastery)}
                            strokeWidth="3"
                            fill="transparent"
                            strokeLinecap="round"
                            initial={{ strokeDasharray: "0 100" }}
                            animate={{ 
                                strokeDasharray: `${lifetimeMastery} ${100 - lifetimeMastery}` 
                            }}
                            transition={{ duration: 1, ease: "easeOut" }}
                        />
                    </svg>
                    <span className={`absolute inset-0 flex items-center justify-center text-xs font-bold ${getMasteryTextColor(lifetimeMastery)}`}>
                        {Math.round(lifetimeMastery)}
                    </span>
                </div>

                {/* Text Info */}
                <div className="hidden sm:flex flex-col">
                    <span className="text-xs text-white/40">Progress</span>
                    <span className="text-sm text-white/80">
                        {completedSections}/{totalSections} sections
                    </span>
                </div>

                {/* Expand Icon */}
                <motion.svg
                    animate={{ rotate: isExpanded ? 180 : 0 }}
                    className="w-4 h-4 text-white/40 group-hover:text-white/60 transition-colors"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </motion.svg>
            </div>

            {/* Expanded Dropdown */}
            <motion.div
                initial={{ opacity: 0, y: -10, height: 0 }}
                animate={{ 
                    opacity: isExpanded ? 1 : 0, 
                    y: isExpanded ? 0 : -10,
                    height: isExpanded ? "auto" : 0
                }}
                className="absolute top-full right-0 mt-2 z-50 overflow-hidden"
            >
                <div className="bg-neutral-900/95 backdrop-blur-xl border border-white/10 rounded-2xl p-4 w-80 shadow-2xl">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-white font-medium">Your Progress</h3>
                        <span className={`text-lg font-bold ${getMasteryTextColor(lifetimeMastery)}`}>
                            {Math.round(lifetimeMastery)}%
                        </span>
                    </div>

                    {/* Overall Progress Bar - Context aware */}
                    <div className="mb-4">
                        <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${lifetimeMastery}%` }}
                                transition={{ duration: 0.5 }}
                                className={`h-full ${getMasteryBarColor(lifetimeMastery)} rounded-full`}
                            />
                        </div>
                    </div>

                    {/* Section List */}
                    <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-thin scrollbar-thumb-white/40 hover:scrollbar-thumb-white/60">
                        {sectionsProgress.map((section, index) => {
                            const isCurrent = section.id === currentSectionId;
                            
                            return (
                                <motion.div
                                    key={section.id}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: index * 0.05 }}
                                    onClick={() => onSectionClick?.(section.id)}
                                    className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-all ${
                                        isCurrent 
                                            ? "bg-blue-500/20 border border-blue-500/30" 
                                            : "hover:bg-white/5"
                                    }`}
                                >
                                    {/* Status Icon - Context-aware */}
                                    <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${
                                        section.completed 
                                            ? "bg-emerald-500/20 text-emerald-400"
                                            : isCurrent
                                                ? "bg-blue-500/20 text-blue-400"
                                                : "bg-white/5 text-white/30"
                                    }`}>
                                        {section.completed ? (
                                            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                            </svg>
                                        ) : isCurrent ? (
                                            <span className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
                                        ) : (
                                            <span className="w-2 h-2 bg-white/20 rounded-full" />
                                        )}
                                    </div>

                                    {/* Section Info */}
                                    <div className="flex-1 min-w-0">
                                        <p className={`text-sm truncate ${
                                            isCurrent ? "text-white" : "text-white/60"
                                        }`}>
                                            {section.id}. {section.title}
                                        </p>
                                        <div className="flex items-center gap-2 mt-1">
                                            <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
                                                <div 
                                                    className={`h-full ${getMasteryBarColor(section.mastery)} rounded-full transition-all duration-500`}
                                                    style={{ width: `${section.mastery}%` }}
                                                />
                                            </div>
                                            <span className={`text-xs w-8 ${getMasteryTextColor(section.mastery)}`}>
                                                {section.mastery}%
                                            </span>
                                        </div>
                                    </div>
                                </motion.div>
                            );
                        })}
                    </div>

                    {/* Exploration Points */}
                    {explorationPoints > 0 && (
                        <div className="mt-4 pt-4 border-t border-white/10">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <span className="text-white/60">🔭</span>
                                    <span className="text-sm text-white/60">Exploration Points</span>
                                </div>
                                <span className="text-amber-400 font-medium">{explorationPoints}</span>
                            </div>
                            <p className="text-xs text-white/30 mt-1">
                                Earned by exploring related topics
                            </p>
                        </div>
                    )}

                    {/* Legend - Context aware */}
                    <div className="mt-4 pt-4 border-t border-white/10 flex items-center justify-between text-xs text-white/40">
                        <div className="flex items-center gap-4">
                            <span className="flex items-center gap-1">
                                <span className="w-2 h-2 bg-emerald-500 rounded-full" /> Mastered
                            </span>
                            <span className="flex items-center gap-1">
                                <span className="w-2 h-2 bg-amber-500 rounded-full" /> Progress
                            </span>
                            <span className="flex items-center gap-1">
                                <span className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" /> Current
                            </span>
                        </div>
                    </div>
                </div>
            </motion.div>
        </div>
    );
}
