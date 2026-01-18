import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import { PromptTemplate } from "@langchain/core/prompts";
import { StructuredOutputParser, StringOutputParser } from "@langchain/core/output_parsers";
import { z } from "zod";

// Define the schema for the evaluation result
const EvaluationSchema = z.object({
    overallScore: z.number().min(0).max(100).describe("Overall score from 0-100 based on accuracy, clarity, and completeness"),
    accuracyScore: z.number().min(0).max(100).describe("How factually correct the explanation is"),
    clarityScore: z.number().min(0).max(100).describe("How well explained and easy to understand"),
    completenessScore: z.number().min(0).max(100).describe("How effectively it covers the core concept"),
    weakAreas: z.array(z.object({
        concept: z.string().describe("Specific part of the concept that was misunderstood or missed"),
        explanation: z.string().describe("Why this part was considered weak"),
        severity: z.enum(["minor", "moderate", "major"]).describe("Severity of the misunderstanding")
    })).describe("List of weak areas or misunderstandings"),
    suggestions: z.array(z.string()).describe("Specific suggestions for improvement"),
    shouldReviewPrerequisites: z.boolean().describe("Whether the student should review prerequisite concepts"),
    prerequisitesToReview: z.array(z.string()).describe("List of prerequisite IDs to review if needed"),
    feedback: z.string().describe("Encouraging, constructive feedback addressing the student")
});

export type EvaluationResult = z.infer<typeof EvaluationSchema>;

const parser = StructuredOutputParser.fromZodSchema(EvaluationSchema);

const EVALUATION_PROMPT = `You are an expert physics tutor evaluating a student's explanation of a concept using the Feynman Technique.
The Feynman Technique involves explaining a concept in simple terms, as if teaching it to someone else.

Concept: {conceptTitle}
Target Audience: {targetAudience}
Official Description: {conceptDescription}

Student's Explanation:
"{studentExplanation}"

Evaluate the explanation based on:
1. Accuracy: Is the physics correct?
2. Clarity: Is it simple and easy to understand? Did they avoid jargon or explain it?
3. Completeness: Did they cover the main points?

If the student seems fundamentally confused about basic principles (like vectors, forces, energy), suggest checking prerequisites.

{format_instructions}
`;

export async function evaluateExplanation(
    conceptTitle: string,
    conceptDescription: string,
    studentExplanation: string,
    targetAudience: string = "a peer"
): Promise<EvaluationResult> {
    const model = new ChatGoogleGenerativeAI({
        model: "gemini-2.5-flash",
        maxOutputTokens: 2048,
    });

    const prompt = PromptTemplate.fromTemplate(EVALUATION_PROMPT);
    const outputParser = new StringOutputParser();

    const chain = prompt.pipe(model).pipe(outputParser);

    try {
        const rawResult = await chain.invoke({
            conceptTitle,
            conceptDescription,
            studentExplanation,
            targetAudience,
            format_instructions: parser.getFormatInstructions(),
        }) as string;

        // Clean up markdown code blocks if present
        const cleanedResult = rawResult.replace(/```json\n?|\n?```/g, "").trim();

        // Parse and validate
        const jsonResult = JSON.parse(cleanedResult);
        return EvaluationSchema.parse(jsonResult);
    } catch (error) {
        console.error("Error evaluating explanation:", error);
        throw new Error("Failed to evaluate explanation");
    }
}
