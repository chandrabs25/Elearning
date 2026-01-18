"use client";

import { motion } from "framer-motion";
import { ChevronRight, BookOpen, CheckCircle, Circle, PlayCircle } from "lucide-react";

interface Section {
    id: string;
    title: string;
    relation?: string;
    mastery?: number;
    completed?: boolean;
    isCurrent?: boolean;
}

interface NavigationMapProps {
    title?: string;
    sections: Section[];
    currentSectionId?: string;
    onAction?: (action: string) => void;
}

// Context-aware color helper
const getMasteryColor = (mastery: number) => {
    if (mastery >= 70) return "bg-emerald-500"; // Success - mastered
    if (mastery >= 40) return "bg-amber-500";   // Warning - in progress
    return "bg-white/30";                        // Default - just started
};

export default function NavigationMap({
    title = "Chapter Sections",
    sections,
    currentSectionId,
    onAction,
}: NavigationMapProps) {
    return (
        <div className="h-full flex flex-col bg-neutral-900/50 rounded-2xl border border-white/5 overflow-hidden">
            {/* Header */}
            <div className="flex-shrink-0 flex items-center gap-3 p-4 border-b border-white/5">
                <div className="p-2 bg-white/5 rounded-lg">
                    <BookOpen className="w-5 h-5 text-white/40" />
                </div>
                <div>
                    <h3 className="text-base font-medium text-white/80">{title}</h3>
                    <p className="text-xs text-white/40">{sections.length} sections</p>
                </div>
            </div>

            {/* Sections List - Scrollable */}
            <div className="flex-1 overflow-y-auto p-3 space-y-1 scrollbar-thin scrollbar-thumb-white/40 hover:scrollbar-thumb-white/60">
                {sections.map((section, i) => {
                    const isCurrent = section.isCurrent || section.id === currentSectionId;
                    const isCompleted = section.completed || (section.mastery && section.mastery >= 70);
                    const isNext = section.relation === "next";
                    const isPrevious = section.relation === "previous";
                    
                    return (
                        <motion.button
                            key={section.id}
                            initial={{ opacity: 0, x: 10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.03 }}
                            onClick={() => onAction?.(`teach me ${section.id}`)}
                            className={`
                                group flex items-center gap-2 w-full p-3 rounded-xl transition-all duration-200
                                ${isCurrent 
                                    ? "bg-blue-500/10 border border-blue-500/30" 
                                    : "hover:bg-white/5 border border-transparent"
                                }
                            `}
                        >
                            {/* Status Icon - Context-aware colors */}
                            <div className="flex-shrink-0">
                                {isCompleted ? (
                                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                                ) : isCurrent ? (
                                    <PlayCircle className="w-4 h-4 text-blue-400 animate-pulse" />
                                ) : (
                                    <Circle className="w-4 h-4 text-white/20" />
                                )}
                            </div>

                            {/* Section Info */}
                            <div className="flex-1 min-w-0 text-left">
                                <div className="flex items-center gap-2">
                                    <span className={`font-mono text-xs ${
                                        isCurrent ? "text-blue-400" : "text-white/40"
                                    }`}>
                                        {section.id}
                                    </span>
                                    
                                    {/* Relation badge - context aware */}
                                    {isNext && (
                                        <span className="text-[10px] px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 rounded">
                                            next
                                        </span>
                                    )}
                                    {isPrevious && (
                                        <span className="text-[10px] px-1.5 py-0.5 bg-white/10 text-white/50 rounded">
                                            prev
                                        </span>
                                    )}
                                </div>
                                <p className={`text-sm truncate ${
                                    isCurrent ? "text-white" : "text-white/60 group-hover:text-white/80"
                                }`}>
                                    {section.title}
                                </p>
                                
                                {/* Mastery bar - context-aware colors */}
                                {section.mastery !== undefined && section.mastery > 0 && (
                                    <div className="mt-1.5 flex items-center gap-2">
                                        <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
                                            <div 
                                                className={`h-full rounded-full transition-all ${getMasteryColor(section.mastery)}`}
                                                style={{ width: `${section.mastery}%` }}
                                            />
                                        </div>
                                        <span className={`text-[10px] w-6 ${
                                            section.mastery >= 70 ? "text-emerald-400" :
                                            section.mastery >= 40 ? "text-amber-400" : "text-white/30"
                                        }`}>
                                            {section.mastery}%
                                        </span>
                                    </div>
                                )}
                            </div>

                            {/* Arrow */}
                            <ChevronRight className={`w-4 h-4 flex-shrink-0 transition-all ${
                                isCurrent 
                                    ? "text-blue-400" 
                                    : "text-white/20 group-hover:text-white/40 group-hover:translate-x-0.5"
                            }`} />
                        </motion.button>
                    );
                })}
            </div>

            {/* Footer legend - context aware */}
            <div className="flex-shrink-0 p-3 border-t border-white/5">
                <div className="flex items-center justify-center gap-4 text-[10px] text-white/30">
                    <span className="flex items-center gap-1">
                        <span className="w-2 h-2 bg-emerald-500 rounded-full" /> ≥70%
                    </span>
                    <span className="flex items-center gap-1">
                        <span className="w-2 h-2 bg-amber-500 rounded-full" /> 40-69%
                    </span>
                    <span className="flex items-center gap-1">
                        <span className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" /> Current
                    </span>
                </div>
            </div>
        </div>
    );
}
