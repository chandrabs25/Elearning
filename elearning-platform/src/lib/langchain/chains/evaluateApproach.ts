import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import { PromptTemplate } from "@langchain/core/prompts";
import { StructuredOutputParser, StringOutputParser } from "@langchain/core/output_parsers";
import { z } from "zod";

// Schema for assessing problem-solving approach
const ApproachEvaluationSchema = z.object({
    valid: z.boolean().describe("Is the student's approach scientifically valid?"),
    feedback: z.string().describe("Specific feedback on their chosen method"),
    suggestedSteps: z.array(z.string()).describe("Recommended next steps based on their approach"),
    conceptRefinements: z.array(z.string()).optional().describe("Key concepts they might be misapplying"),
});

export type ApproachResult = z.infer<typeof ApproachEvaluationSchema>;

const parser = StructuredOutputParser.fromZodSchema(ApproachEvaluationSchema);

const APPROACH_PROMPT = `You are a physics tutor helping a student solve a problem. 
They have described how they plan to solve it. evaluating their strategy.

Problem: {question}
Student's Approach: "{studentApproach}"
Related Concepts: {relatedConcepts}

Determine if their approach is valid. 
- If valid, encourage them and suggest the next logical step.
- If invalid or inefficient, gently correct them and guide them toward the right principles (e.g., "Conservation of energy would be easier here than kinematics").

{format_instructions}
`;

export async function evaluateApproach(
    question: string,
    studentApproach: string,
    relatedConcepts: string[]
): Promise<ApproachResult> {
    const model = new ChatGoogleGenerativeAI({
        model: "gemini-2.5-flash",
        maxOutputTokens: 2048,
    });

    const prompt = PromptTemplate.fromTemplate(APPROACH_PROMPT);
    const outputParser = new StringOutputParser();

    const chain = prompt.pipe(model).pipe(outputParser);

    try {
        const rawResult = await chain.invoke({
            question,
            studentApproach,
            relatedConcepts: relatedConcepts.join(", "),
            format_instructions: parser.getFormatInstructions(),
        }) as string;

        // Clean up markdown code blocks if present
        const cleanedResult = rawResult.replace(/```json\n?|\n?```/g, "").trim();

        // Parse and validate
        const jsonResult = JSON.parse(cleanedResult);
        return ApproachEvaluationSchema.parse(jsonResult);
    } catch (error) {
        console.error("Error evaluating approach:", error);
        throw new Error("Failed to evaluate approach");
    }
}
