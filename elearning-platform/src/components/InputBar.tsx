"use client";

import { forwardRef, useState, useImperativeHandle, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Sparkles, MessageCircle, BookOpen, Mic, MicOff, Volume2 } from "lucide-react";

type FocusTarget = "tutor" | "chat" | null;

interface InputBarProps {
    placeholder?: string;
    onSend: (message: string) => void;
    isProcessing?: boolean;
    hint?: string | null;
    focusTarget?: FocusTarget;
    focusLabel?: string;
}

// Type for SpeechRecognition (not available in all browsers)
interface SpeechRecognitionEvent extends Event {
    results: SpeechRecognitionResultList;
    resultIndex: number;
}

interface SpeechRecognitionErrorEvent extends Event {
    error: string;
    message: string;
}

const InputBar = forwardRef<HTMLInputElement, InputBarProps>(
    ({ placeholder = "Talk to me...", onSend, isProcessing, hint, focusTarget = "tutor", focusLabel }, ref) => {
        const [value, setValue] = useState("");
        const [isListening, setIsListening] = useState(false);
        const [speechSupported, setSpeechSupported] = useState(false);
        const [interimTranscript, setInterimTranscript] = useState("");
        const [voiceError, setVoiceError] = useState<string | null>(null);
        
        const inputRef = useRef<HTMLInputElement>(null);
        const recognitionRef = useRef<any>(null);

        useImperativeHandle(ref, () => inputRef.current!);

        // Check for speech recognition support
        useEffect(() => {
            if (typeof window !== "undefined") {
                const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
                setSpeechSupported(!!SpeechRecognition);
            }
        }, []);

        // Initialize speech recognition
        const initSpeechRecognition = useCallback(() => {
            if (typeof window === "undefined") return null;
            
            const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
            if (!SpeechRecognition) return null;

            const recognition = new SpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = "en-US";

            recognition.onstart = () => {
                setIsListening(true);
                setVoiceError(null);
            };

            recognition.onresult = (event: SpeechRecognitionEvent) => {
                let interim = "";
                let final = "";

                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        final += transcript;
                    } else {
                        interim += transcript;
                    }
                }

                if (final) {
                    setValue(prev => prev + final);
                    setInterimTranscript("");
                } else {
                    setInterimTranscript(interim);
                }
            };

            recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
                console.error("Speech recognition error:", event.error);
                setIsListening(false);
                
                switch (event.error) {
                    case "no-speech":
                        setVoiceError("No speech detected. Try again.");
                        break;
                    case "audio-capture":
                        setVoiceError("No microphone found.");
                        break;
                    case "not-allowed":
                        setVoiceError("Microphone access denied.");
                        break;
                    default:
                        setVoiceError("Voice input error. Try again.");
                }
                
                setTimeout(() => setVoiceError(null), 3000);
            };

            recognition.onend = () => {
                setIsListening(false);
                setInterimTranscript("");
            };

            return recognition;
        }, []);

        // Toggle listening
        const toggleListening = useCallback(() => {
            if (isListening) {
                recognitionRef.current?.stop();
                setIsListening(false);
            } else {
                if (!recognitionRef.current) {
                    recognitionRef.current = initSpeechRecognition();
                }
                try {
                    recognitionRef.current?.start();
                } catch (e) {
                    // Recognition might already be running
                    recognitionRef.current?.stop();
                    setTimeout(() => recognitionRef.current?.start(), 100);
                }
            }
        }, [isListening, initSpeechRecognition]);

        // Cleanup on unmount
        useEffect(() => {
            return () => {
                recognitionRef.current?.stop();
            };
        }, []);

        const handleSubmit = (e: React.FormEvent) => {
            e.preventDefault();
            if (value.trim() && !isProcessing) {
                // Stop listening when submitting
                if (isListening) {
                    recognitionRef.current?.stop();
                }
                onSend(value);
                setValue("");
            }
        };

        const getPlaceholder = () => {
            if (isListening) return "Listening...";
            if (placeholder) return placeholder;
            switch (focusTarget) {
                case "chat":
                    return "Ask a question about the topic...";
                case "tutor":
                default:
                    return "Talk to me...";
            }
        };

        const getFocusIcon = () => {
            switch (focusTarget) {
                case "chat":
                    return <MessageCircle className="w-4 h-4" />;
                case "tutor":
                default:
                    return <BookOpen className="w-4 h-4" />;
            }
        };

        return (
            <div className="flex-shrink-0 border-t border-white/5 bg-black/80 backdrop-blur-xl p-6">
                <div className="max-w-3xl mx-auto">
                    {/* Focus indicator */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex items-center justify-between mb-3"
                    >
                        <div className="flex items-center gap-2">
                            <div className="p-1.5 rounded-lg bg-white/5 text-white/40">
                                {getFocusIcon()}
                            </div>
                            <span className="text-sm text-white/50">
                                {focusLabel || (focusTarget === "chat" ? "AI Chat" : "Tutor")}
                            </span>
                        </div>
                        <div className="flex items-center gap-3">
                            {speechSupported && (
                                <span className="text-xs text-white/30 flex items-center gap-1">
                                    <Volume2 className="w-3 h-3" /> Voice enabled
                                </span>
                            )}
                            <span className="text-xs text-white/30">
                                Press Tab to switch panels
                            </span>
                        </div>
                    </motion.div>

                    {/* Hint or Voice Error */}
                    <AnimatePresence mode="wait">
                        {voiceError ? (
                            <motion.div
                                key="error"
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -10 }}
                                className="flex items-center gap-2 text-sm text-red-400 mb-3"
                            >
                                <MicOff className="w-4 h-4" />
                                <span>{voiceError}</span>
                            </motion.div>
                        ) : hint ? (
                            <motion.div
                                key="hint"
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -10 }}
                                className="flex items-center gap-2 text-sm text-white/40 mb-3"
                            >
                                <Sparkles className="w-4 h-4" />
                                <span>{hint}</span>
                            </motion.div>
                        ) : null}
                    </AnimatePresence>

                    {/* Input with Voice */}
                    <form onSubmit={handleSubmit} className="relative">
                        {/* Listening indicator */}
                        <AnimatePresence>
                            {isListening && (
                                <motion.div
                                    initial={{ opacity: 0, scale: 0.95 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.95 }}
                                    className="absolute -top-12 left-0 right-0 flex items-center justify-center"
                                >
                                    <div className="flex items-center gap-2 px-4 py-2 bg-blue-500/20 border border-blue-500/30 rounded-full">
                                        <motion.div
                                            animate={{ scale: [1, 1.2, 1] }}
                                            transition={{ repeat: Infinity, duration: 1 }}
                                            className="w-2 h-2 bg-blue-400 rounded-full"
                                        />
                                        <span className="text-sm text-blue-400">Listening...</span>
                                        {interimTranscript && (
                                            <span className="text-sm text-white/60 italic max-w-xs truncate">
                                                {interimTranscript}
                                            </span>
                                        )}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        <input
                            ref={inputRef}
                            type="text"
                            value={value}
                            onChange={(e) => setValue(e.target.value)}
                            placeholder={getPlaceholder()}
                            disabled={isProcessing}
                            className={`
                                w-full px-6 py-4 pr-28
                                bg-white/5 border rounded-2xl
                                text-white placeholder:text-white/30
                                focus:outline-none focus:bg-white/10 focus:border-white/20
                                transition-all duration-200
                                ${isProcessing ? "opacity-50 cursor-wait" : ""}
                                ${isListening 
                                    ? "border-blue-500/50 bg-blue-500/5" 
                                    : "border-white/10"
                                }
                            `}
                        />

                        {/* Voice Button */}
                        {speechSupported && (
                            <button
                                type="button"
                                onClick={toggleListening}
                                disabled={isProcessing}
                                className={`
                                    absolute right-16 top-1/2 -translate-y-1/2
                                    p-3 rounded-xl
                                    transition-all duration-200
                                    ${isListening
                                        ? "bg-blue-500 text-white"
                                        : "bg-white/5 text-white/40 hover:bg-white/10 hover:text-white/60"
                                    }
                                `}
                            >
                                {isListening ? (
                                    <motion.div
                                        animate={{ scale: [1, 1.1, 1] }}
                                        transition={{ repeat: Infinity, duration: 0.5 }}
                                    >
                                        <Mic className="w-5 h-5" />
                                    </motion.div>
                                ) : (
                                    <Mic className="w-5 h-5" />
                                )}
                            </button>
                        )}

                        {/* Send Button */}
                        <button
                            type="submit"
                            disabled={!value.trim() || isProcessing}
                            className={`
                                absolute right-3 top-1/2 -translate-y-1/2
                                p-3 rounded-xl
                                transition-all duration-200
                                ${value.trim() && !isProcessing
                                    ? "bg-white text-black hover:bg-white/90"
                                    : "bg-white/5 text-white/30"
                                }
                            `}
                        >
                            {isProcessing ? (
                                <motion.div
                                    animate={{ rotate: 360 }}
                                    transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                                >
                                    <Sparkles className="w-5 h-5" />
                                </motion.div>
                            ) : (
                                <Send className="w-5 h-5" />
                            )}
                        </button>
                    </form>

                    {/* Voice tips */}
                    {speechSupported && !isListening && !value && (
                        <motion.p 
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="text-[10px] text-white/20 text-center mt-2"
                        >
                            Click the microphone or type your command
                        </motion.p>
                    )}
                </div>
            </div>
        );
    }
);

InputBar.displayName = "InputBar";

export default InputBar;
