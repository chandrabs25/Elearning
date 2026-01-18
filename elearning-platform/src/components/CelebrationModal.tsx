"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState, useCallback } from "react";

interface CelebrationModalProps {
    isOpen: boolean;
    onClose: () => void;
    sectionTitle: string;
    masteryPercent: number;
    nextSectionTitle?: string;
    onNavigateNext: () => void;
    autoNavigateDelay?: number; // ms before auto-navigation
}

// Confetti particle component
const Confetti = ({ index }: { index: number }) => {
    const colors = [
        "#FFD700", "#FF6B6B", "#4ECDC4", "#45B7D1", "#96E6A1",
        "#DDA0DD", "#F7DC6F", "#BB8FCE", "#85C1E9", "#F8B500"
    ];
    
    const randomX = Math.random() * 100;
    const randomDelay = Math.random() * 0.5;
    const randomDuration = 2 + Math.random() * 2;
    const randomRotation = Math.random() * 360;
    const color = colors[index % colors.length];
    const size = 8 + Math.random() * 8;
    const shape = Math.random() > 0.5 ? "circle" : "square";
    
    return (
        <motion.div
            initial={{ 
                y: -20, 
                x: `${randomX}vw`,
                rotate: 0,
                opacity: 1 
            }}
            animate={{ 
                y: "100vh", 
                rotate: randomRotation + 360,
                opacity: 0 
            }}
            transition={{ 
                duration: randomDuration,
                delay: randomDelay,
                ease: "easeIn"
            }}
            className="fixed pointer-events-none z-[100]"
            style={{
                width: size,
                height: size,
                backgroundColor: color,
                borderRadius: shape === "circle" ? "50%" : "2px",
                top: 0
            }}
        />
    );
};

export default function CelebrationModal({
    isOpen,
    onClose,
    sectionTitle,
    masteryPercent,
    nextSectionTitle,
    onNavigateNext,
    autoNavigateDelay = 5000
}: CelebrationModalProps) {
    const [countdown, setCountdown] = useState(autoNavigateDelay / 1000);
    const [confettiCount] = useState(50);

    const handleNavigateNext = useCallback(() => {
        onNavigateNext();
        onClose();
    }, [onNavigateNext, onClose]);

    // Countdown and auto-navigation
    useEffect(() => {
        if (!isOpen || !nextSectionTitle) return;

        const countdownInterval = setInterval(() => {
            setCountdown(prev => {
                if (prev <= 1) {
                    clearInterval(countdownInterval);
                    handleNavigateNext();
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(countdownInterval);
    }, [isOpen, nextSectionTitle, handleNavigateNext]);

    // Reset countdown when modal opens
    useEffect(() => {
        if (isOpen) {
            setCountdown(autoNavigateDelay / 1000);
        }
    }, [isOpen, autoNavigateDelay]);

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Confetti */}
                    {[...Array(confettiCount)].map((_, i) => (
                        <Confetti key={i} index={i} />
                    ))}

                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50"
                        onClick={onClose}
                    />

                    {/* Modal */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.8, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.8, y: 20 }}
                        transition={{ type: "spring", damping: 25, stiffness: 300 }}
                        className="fixed inset-0 flex items-center justify-center z-50 p-4 pointer-events-none"
                    >
                        <div className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-3xl p-8 max-w-md w-full border border-white/10 shadow-2xl pointer-events-auto">
                            {/* Trophy Icon */}
                            <motion.div
                                initial={{ scale: 0 }}
                                animate={{ scale: 1, rotate: [0, -10, 10, 0] }}
                                transition={{ delay: 0.2, duration: 0.5 }}
                                className="text-center mb-6"
                            >
                                <div className="w-24 h-24 mx-auto bg-gradient-to-br from-yellow-400 to-amber-600 rounded-full flex items-center justify-center shadow-lg shadow-yellow-500/30">
                                    <svg className="w-12 h-12 text-white" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M12 2C7.58 2 4 5.58 4 10c0 2.03.76 3.87 2 5.28V20c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2v-4.72c1.24-1.41 2-3.25 2-5.28 0-4.42-3.58-8-8-8zm0 2c3.31 0 6 2.69 6 6 0 1.66-.67 3.16-1.76 4.24l-.24.24V18h-8v-3.52l-.24-.24C6.67 13.16 6 11.66 6 10c0-3.31 2.69-6 6-6z"/>
                                        <path d="M11 10h2v6h-2zm0-4h2v2h-2z"/>
                                    </svg>
                                </div>
                            </motion.div>

                            {/* Celebration Text */}
                            <motion.div
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.3 }}
                                className="text-center space-y-3"
                            >
                                <h2 className="text-3xl font-bold bg-gradient-to-r from-yellow-400 via-amber-400 to-orange-400 bg-clip-text text-transparent">
                                    Section Complete! 🎉
                                </h2>
                                <p className="text-white/60 text-lg">
                                    {sectionTitle}
                                </p>
                            </motion.div>

                            {/* Mastery Badge */}
                            <motion.div
                                initial={{ opacity: 0, scale: 0.8 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ delay: 0.4 }}
                                className="my-6"
                            >
                                <div className="bg-white/5 rounded-2xl p-4 border border-white/10">
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="text-white/60 text-sm">Mastery Achieved</span>
                                        <span className="text-2xl font-bold text-green-400">{masteryPercent}%</span>
                                    </div>
                                    <div className="h-3 bg-white/10 rounded-full overflow-hidden">
                                        <motion.div
                                            initial={{ width: 0 }}
                                            animate={{ width: `${masteryPercent}%` }}
                                            transition={{ delay: 0.5, duration: 1, ease: "easeOut" }}
                                            className="h-full bg-gradient-to-r from-green-400 to-emerald-500 rounded-full"
                                        />
                                    </div>
                                </div>
                            </motion.div>

                            {/* Next Section Info */}
                            {nextSectionTitle && (
                                <motion.div
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    transition={{ delay: 0.6 }}
                                    className="text-center space-y-4"
                                >
                                    <p className="text-white/40 text-sm">
                                        Up next:
                                    </p>
                                    <p className="text-white text-lg font-medium">
                                        {nextSectionTitle}
                                    </p>
                                    
                                    {/* Countdown */}
                                    <div className="flex items-center justify-center gap-2 text-white/50 text-sm">
                                        <span>Auto-continuing in</span>
                                        <span className="bg-white/10 px-3 py-1 rounded-full font-mono text-white">
                                            {countdown}s
                                        </span>
                                    </div>
                                </motion.div>
                            )}

                            {/* Action Buttons */}
                            <motion.div
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.7 }}
                                className="mt-6 flex gap-3"
                            >
                                <button
                                    onClick={onClose}
                                    className="flex-1 py-3 px-4 rounded-xl bg-white/5 border border-white/10 text-white/60 hover:bg-white/10 hover:text-white transition-all duration-200"
                                >
                                    Stay Here
                                </button>
                                {nextSectionTitle && (
                                    <button
                                        onClick={handleNavigateNext}
                                        className="flex-1 py-3 px-4 rounded-xl bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-medium hover:from-blue-600 hover:to-indigo-700 transition-all duration-200 shadow-lg shadow-blue-500/25"
                                    >
                                        Continue Now →
                                    </button>
                                )}
                            </motion.div>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}
