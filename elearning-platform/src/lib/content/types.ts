// Content type definitions matching gravity.json schema

export interface ChapterContent {
    chapter_number: string;
    chapter_title: string;
    table_of_contents: TOCItem[];
    sections: Section[];
}

export interface TOCItem {
    id: string;
    title: string;
}

export interface Section {
    section_id: string;
    section_title: string;
    content: ContentBlock[];
}

// Polymorphic content blocks
export type ContentBlock =
    | TextBlock
    | ListItemBlock
    | DiagramBlock
    | DerivationBlock
    | TableBlock
    | ExampleBoxBlock
    | ExerciseItemBlock;

export interface TextBlock {
    type: "text";
    body: string;
}

export interface ListItemBlock {
    type: "list_item";
    label: string;
    body: string;
}

export interface DiagramBlock {
    type: "diagram";
    figure_number: string;
    meta: string;
}

export interface DerivationBlock {
    type: "derivation";
    latex: string;
    meta: string;
}

export interface TableBlock {
    type: "table";
    title?: string;
    headers: string[];
    rows: string[][];
    meta: string;
}

export interface ExampleBoxBlock {
    type: "example_box";
    label: string;
    question: string;
    solution: ExampleSolution | DerivationBlock;
}

export interface ExampleSolution {
    type: "example_solution";
    content: ContentBlock[];
}

export interface ExerciseItemBlock {
    type: "exercise_item";
    label: string;
    question: string;
    body?: string;
    sub_questions?: SubQuestion[];
    content?: ContentBlock[];
}

export interface SubQuestion {
    label: string;
    body: string;
}
