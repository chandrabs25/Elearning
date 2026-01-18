"use client";

import React from "react";
import dynamic from "next/dynamic";
import "katex/dist/katex.min.css";

// Dynamic import to avoid SSR issues with react-katex
const BlockMath = dynamic(
    () => import("react-katex").then((mod) => mod.BlockMath),
    { ssr: false, loading: () => <div className="animate-pulse h-8 bg-white/10 rounded" /> }
);

// Custom Components
const H1 = (props: { children: React.ReactNode }) => (
    <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent mb-6">
        {props.children}
    </h1>
);

const P = (props: { children: React.ReactNode }) => (
    <p className="text-lg text-zinc-300 leading-relaxed mb-4">
        {props.children}
    </p>
);

const LI = (props: { children: React.ReactNode }) => (
    <li className="text-lg text-zinc-400 mb-2 list-disc ml-6">
        {props.children}
    </li>
);

const LatexComponent = (props: { content: string }) => {
    return (
        <div className="my-4 p-4 bg-zinc-900 rounded-lg border border-zinc-800 overflow-x-auto">
            <BlockMath>{props.content}</BlockMath>
        </div>
    )
}

const Diagram = (props: { figure: string; caption?: string }) => (
    <div className="my-6 p-4 border border-zinc-700 rounded-lg bg-zinc-900/50">
        <div className="text-center text-zinc-500 italic">[Diagram: {props.figure}]</div>
        <p className="text-sm text-zinc-400 mt-2 text-center">{props.caption}</p>
    </div>
)

// Component Registry
const components = {
    h1: H1,
    p: P,
    li: LI,
    latex: LatexComponent,
    diagram: Diagram,
    // Fallback to defaults or add more
};

interface SchemaComponent {
    type: string;
    props: Record<string, unknown>;
}

interface Schema {
    components: SchemaComponent[];
}

export default function DynamicRenderer({ schema }: { schema: Schema | null }) {
    if (!schema) return null;

    return (
        <div className="max-w-3xl mx-auto p-8">
            {schema.components.map((comp: SchemaComponent, index: number) => {
                const Component = components[comp.type as keyof typeof components] || P;
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                return <Component key={index} {...(comp.props as any)} />;
            })}
        </div>
    );
}
