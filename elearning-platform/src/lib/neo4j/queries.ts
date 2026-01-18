import { getSession } from "./client";
import { Integer } from "neo4j-driver";

// Helper to convert Neo4j integers to plain numbers
function toPlainObject(obj: Record<string, unknown>): Record<string, unknown> {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj)) {
        if (Integer.isInteger(value)) {
            result[key] = (value as Integer).toNumber();
        } else if (value && typeof value === "object" && !Array.isArray(value)) {
            result[key] = toPlainObject(value as Record<string, unknown>);
        } else {
            result[key] = value;
        }
    }
    return result;
}

// Types
export interface ConceptNode {
    id: string;
    title: string;
    sectionId?: string;
    description: string;
    difficulty?: number;
    estimatedMinutes?: number;
    isPrerequisite?: boolean;
}

export interface PrerequisiteInfo {
    id: string;
    title: string;
}

export interface ExerciseInfo {
    id: string;
    question: string;
}

// Get concept with its prerequisites
export async function getConceptWithPrerequisites(conceptId: string): Promise<{
    concept: ConceptNode | null;
    prerequisites: PrerequisiteInfo[];
}> {
    const session = await getSession();
    try {
        const result = await session.run(
            `
      MATCH (c:Concept {id: $conceptId})
      OPTIONAL MATCH (c)-[:REQUIRES]->(prereq:Concept)
      RETURN c, collect(prereq) as prerequisites
      `,
            { conceptId }
        );

        if (result.records.length === 0) {
            return { concept: null, prerequisites: [] };
        }

        const record = result.records[0];
        const conceptProps = toPlainObject(record.get("c").properties);
        const prereqNodes = record.get("prerequisites");

        return {
            concept: conceptProps as unknown as ConceptNode,
            prerequisites: prereqNodes
                .filter((n: unknown) => n !== null)
                .map((n: { properties: PrerequisiteInfo }) => ({
                    id: n.properties.id,
                    title: n.properties.title,
                })),
        };
    } finally {
        await session.close();
    }
}

// Get exercises related to a concept
export async function getRelatedExercises(conceptId: string): Promise<ExerciseInfo[]> {
    const session = await getSession();
    try {
        const result = await session.run(
            `
      MATCH (e:Exercise)-[:TESTS]->(c:Concept {id: $conceptId})
      RETURN e.id as id, e.question as question
      `,
            { conceptId }
        );

        return result.records.map((record) => ({
            id: record.get("id"),
            question: record.get("question"),
        }));
    } finally {
        await session.close();
    }
}

// Get the next concept in sequence
export async function getNextConcept(conceptId: string): Promise<ConceptNode | null> {
    const session = await getSession();
    try {
        const result = await session.run(
            `
      MATCH (c:Concept {id: $conceptId})-[:NEXT]->(next:Concept)
      RETURN next
      `,
            { conceptId }
        );

        if (result.records.length === 0) return null;
        return result.records[0].get("next").properties as ConceptNode;
    } finally {
        await session.close();
    }
}

// Get the previous concept in sequence
export async function getPreviousConcept(conceptId: string): Promise<ConceptNode | null> {
    const session = await getSession();
    try {
        const result = await session.run(
            `
      MATCH (prev:Concept)-[:NEXT]->(c:Concept {id: $conceptId})
      RETURN prev
      `,
            { conceptId }
        );

        if (result.records.length === 0) return null;
        return result.records[0].get("prev").properties as ConceptNode;
    } finally {
        await session.close();
    }
}

// Get the learning path (all concepts in order)
export async function getLearningPath(chapterId: string): Promise<ConceptNode[]> {
    const session = await getSession();
    try {
        const result = await session.run(
            `
      MATCH (ch:Chapter {id: $chapterId})-[:CONTAINS]->(c:Concept)
      RETURN c
      ORDER BY c.sectionId
      `,
            { chapterId }
        );

        return result.records.map((record) => record.get("c").properties as ConceptNode);
    } finally {
        await session.close();
    }
}

// Find prerequisite path when student is confused
export async function findPrerequisitePath(
    conceptId: string,
    weakAreas: string[] = []
): Promise<PrerequisiteInfo[]> {
    const session = await getSession();
    try {
        const result = await session.run(
            `
      MATCH (c:Concept {id: $conceptId})-[:REQUIRES*1..3]->(prereq:Concept)
      WHERE prereq.isPrerequisite = true OR prereq.id IN $weakAreas
      RETURN DISTINCT prereq
      ORDER BY prereq.sectionId
      `,
            { conceptId, weakAreas }
        );

        return result.records.map((record) => ({
            id: record.get("prereq").properties.id,
            title: record.get("prereq").properties.title,
        }));
    } finally {
        await session.close();
    }
}

// Get all prerequisites (both direct and transitive) for a concept
export async function getAllPrerequisites(conceptId: string): Promise<PrerequisiteInfo[]> {
    const session = await getSession();
    try {
        const result = await session.run(
            `
      MATCH (c:Concept {id: $conceptId})-[:REQUIRES*1..]->(prereq:Concept)
      RETURN DISTINCT prereq
      `,
            { conceptId }
        );

        return result.records.map((record) => ({
            id: record.get("prereq").properties.id,
            title: record.get("prereq").properties.title,
        }));
    } finally {
        await session.close();
    }
}
