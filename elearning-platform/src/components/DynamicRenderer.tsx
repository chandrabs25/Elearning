import React from "react";
// @ts-ignore
import Latex from "react-katex";
import "katex/dist/katex.min.css";

// Custom Components
const H1 = (props: any) => (
    <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent mb-6">
        {props.children}
    </h1>
);

const P = (props: any) => (
    <p className="text-lg text-zinc-300 leading-relaxed mb-4">
        {props.children}
    </p>
);

const LI = (props: any) => (
    <li className="text-lg text-zinc-400 mb-2 list-disc ml-6">
        {props.children}
    </li>
);

const LatexComponent = (props: any) => {
    return (
        <div className="my-4 p-4 bg-zinc-900 rounded-lg border border-zinc-800 overflow-x-auto">
            <Latex>{props.content}</Latex>
        </div>
    )
}

const Diagram = (props: any) => (
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

export default function DynamicRenderer({ schema }: { schema: any }) {
    if (!schema) return null;

    // The 'components' prop in @json-render provider might be different based on version
    // Assuming generic provider usage
    // Actually, looking at @json-render docs (simulated), it usually takes a mapping.

    return (
        <div className="max-w-3xl mx-auto p-8">
            {schema.components.map((comp: any, index: number) => {
                const Component = components[comp.type as keyof typeof components] || P;
                return <Component key={index} {...comp.props} />;
            })}
        </div>
    );
}
