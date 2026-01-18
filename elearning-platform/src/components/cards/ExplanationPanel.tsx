"use client";

import { motion } from "framer-motion";
import "katex/dist/katex.min.css";
import React from "react";

// Dynamic import to avoid SSR issues
import dynamic from "next/dynamic";
const BlockMath = dynamic(
    () => import("react-katex").then((mod) => mod.BlockMath),
    { ssr: false, loading: () => <div className="animate-pulse h-8 bg-white/10 rounded" /> }
);
const InlineMath = dynamic(
    () => import("react-katex").then((mod) => mod.InlineMath),
    { ssr: false, loading: () => <span className="animate-pulse bg-white/10 rounded px-2">...</span> }
);

// Helper to clean LaTeX for rendering
const cleanLatex = (latex: string) => {
    return latex.replace(/\$\$/g, "").trim();
};

// Helper to parse text with inline LaTeX ($...$) and render InlineMath components
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
        parts.push(
            <InlineMath key={key++}>{match[1]}</InlineMath>
        );
        lastIndex = regex.lastIndex;
    }

    if (lastIndex < text.length) {
        parts.push(text.slice(lastIndex));
    }

    return parts.length > 0 ? parts : text;
};

interface ContentItem {
    type: string;
    content?: string;
    label?: string;
    latex?: string;
    description?: string;
    figure?: string;
    caption?: string;
    title?: string;
    headers?: string[];
    rows?: string[][];
    question?: string;
    solution?: any;
}

interface ExplanationPanelProps {
    title: string;
    content: ContentItem[];
    animated?: boolean;
    onAction?: (action: string) => void;
}

export default function ExplanationPanel({
    title,
    content,
    animated = true,
}: ExplanationPanelProps) {
    return (
        <div className="p-6 bg-neutral-900/50 rounded-2xl border border-white/5 h-full max-h-full min-h-0 overflow-y-auto scrollbar-thin scrollbar-thumb-white/40 hover:scrollbar-thumb-white/60 flex flex-col">
            {/* Title */}
            <motion.h2
                initial={animated ? { opacity: 0, y: -10 } : false}
                animate={{ opacity: 1, y: 0 }}
                className="text-2xl font-medium mb-6 text-white"
            >
                {title}
            </motion.h2>

            {/* Content */}
            <div className="space-y-6">
                {content.map((item, index) => (
                    <motion.div
                        key={index}
                        initial={animated ? { opacity: 0, y: 20 } : false}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.1 }}
                    >
                        {renderContentItem(item)}
                    </motion.div>
                ))}
            </div>
        </div>
    );
}

function renderContentItem(item: ContentItem) {
    switch (item.type) {
        case "paragraph":
            return (
                <p className="text-white/70 leading-relaxed text-lg">
                    {parseInlineLatex(item.content || "")}
                </p>
            );

        case "listItem":
            return (
                <div className="flex gap-4 p-4 bg-white/5 rounded-xl border-l-2 border-white/20">
                    <span className="text-white/60 font-semibold whitespace-nowrap">
                        {item.label}
                    </span>
                    <p className="text-white/60">{parseInlineLatex(item.content || "")}</p>
                </div>
            );

        case "latex":
            return (
                <div className="p-6 bg-black/30 rounded-xl border border-white/5 overflow-x-auto">
                    <BlockMath>{cleanLatex(item.content || "")}</BlockMath>
                    {item.description && (
                        <p className="mt-3 text-sm text-white/40 italic">{item.description}</p>
                    )}
                </div>
            );

        case "diagram":
            return (
                <div className="p-6 bg-white/5 rounded-xl border border-dashed border-white/10 text-center">
                    <div className="text-4xl mb-3 opacity-50">📊</div>
                    <p className="text-white/30 font-mono text-sm mb-2">Fig. {item.figure}</p>
                    <p className="text-white/50 text-sm">{item.caption}</p>
                </div>
            );

        case "table":
            return (
                <div className="overflow-x-auto">
                    <p className="text-sm text-white/40 mb-3">{item.title}</p>
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-white/10">
                                {item.headers?.map((h, i) => (
                                    <th key={i} className="text-left p-3 text-white/50 font-medium">
                                        {h}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {item.rows?.map((row, i) => (
                                <tr key={i} className="border-b border-white/5 hover:bg-white/5">
                                    {row.map((cell, j) => (
                                        <td key={j} className="p-3 text-white/70">
                                            {cell}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            );

        case "example":
            return (
                <div className="p-6 bg-white/5 rounded-xl border border-white/10">
                    <div className="flex items-center gap-2 mb-3">
                        <span className="px-2 py-1 bg-white/10 rounded-lg text-white/60 text-xs font-medium uppercase tracking-wide">
                            {item.label}
                        </span>
                    </div>
                    <p className="text-white/70">{parseInlineLatex(item.question || "")}</p>
                </div>
            );

        default:
            return (
                <p className="text-white/50">{item.content || JSON.stringify(item)}</p>
            );
    }
}
