import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import { PromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";

const HINT_PROMPT = `You are a helpful physics tutor providing progressive hints for a problem.
Your goal is to guide the student without giving away the answer directly.
Use the Socratic method where appropriate.

Question: {question}
Related Concepts: {relatedConcepts}

Student's Approach (if any): {studentApproach}
Previous Hints Given: {previousHints}

Current Hint Level: {hintLevel} (1=Vague/Conceptual, 5=Almost the solution)

Generate a single, concise hint appropriate for Level {hintLevel}.
- Level 1: Point to the general physical principle or concept.
- Level 2: Suggest a starting point or formula to consider.
- Level 3: Guide them on how to apply the formula or concept.
- Level 4: Point out a specific step or calculation they might need.
- Level 5: Walk through the logic of the final step (but don't give the final number).

Output ONLY the hint text.
`;

export async function generateHint(
    question: string,
    relatedConcepts: string[],
    studentApproach: string = "None provided",
    hintLevel: number,
    previousHints: string[] = []
): Promise<string> {
    const model = new ChatGoogleGenerativeAI({
        model: "gemini-2.5-flash",
        maxOutputTokens: 1024,
    });

    const prompt = PromptTemplate.fromTemplate(HINT_PROMPT);
    const parser = new StringOutputParser();

    const chain = prompt.pipe(model).pipe(parser);

    try {
        const result = await chain.invoke({
            question,
            relatedConcepts: relatedConcepts.join(", "),
            studentApproach,
            hintLevel,
            previousHints: previousHints.join(" | "),
        });

        const cleanedResult = result.replace(/```\w*\n?|\n?```/g, "").trim();
        return cleanedResult;
    } catch (error) {
        console.error("Error generating hint:", error);
        // Fallback hints in case of API failure
        const fallbacks = [
            "Think about the fundamental forces involved.",
            "Check which conservation laws might apply here.",
            "Draw a diagram to visualize the vectors.",
            "Review the formula for gravitational force.",
            "Consider the relationship between energy and distance."
        ];
        return fallbacks[hintLevel - 1] || "Try breaking the problem into smaller steps.";
    }
}
