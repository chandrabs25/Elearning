import gravityData from "@/data/chapters/gravity.json";
import type { ChapterContent, Section, ContentBlock } from "./types";

// Load chapter content
export function loadChapter(chapterId: string): ChapterContent | null {
    // For POC, we only have gravity chapter
    if (chapterId === "gravity" || chapterId === "7") {
        return gravityData as ChapterContent;
    }
    return null;
}

// Get a specific section by ID
export function getSection(chapterId: string, sectionId: string): Section | null {
    const chapter = loadChapter(chapterId);
    if (!chapter) return null;

    return chapter.sections.find(s => s.section_id === sectionId) || null;
}

// Get section content blocks by type
export function getContentByType<T extends ContentBlock["type"]>(
    section: Section,
    type: T
): Extract<ContentBlock, { type: T }>[] {
    return section.content.filter(block => block.type === type) as Extract<ContentBlock, { type: T }>[];
}

// Get all derivations from a section
export function getDerivations(section: Section) {
    return getContentByType(section, "derivation");
}

// Get all diagrams from a section
export function getDiagrams(section: Section) {
    return getContentByType(section, "diagram");
}

// Get all examples from a section
export function getExamples(section: Section) {
    return getContentByType(section, "example_box");
}

// Get table of contents
export function getTableOfContents(chapterId: string) {
    const chapter = loadChapter(chapterId);
    return chapter?.table_of_contents || [];
}
