// Proxy to Python backend for evaluation
import { NextResponse } from "next/server";

const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || "http://localhost:8000";

export async function POST(request: Request) {
    try {
        const body = await request.json();

        const response = await fetch(`${PYTHON_BACKEND_URL}/api/evaluate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                concept_title: body.conceptTitle,
                concept_description: body.conceptDescription,
                student_explanation: body.studentExplanation,
                target_audience: body.targetAudience,
            }),
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error("Python backend error:", errorText);
            return NextResponse.json(
                { error: "Evaluation failed" },
                { status: response.status }
            );
        }

        const data = await response.json();

        // Transform snake_case to camelCase for frontend compatibility
        return NextResponse.json({
            overallScore: data.overall_score,
            accuracyScore: data.accuracy_score,
            clarityScore: data.clarity_score,
            completenessScore: data.completeness_score,
            weakAreas: data.weak_areas,
            suggestions: data.suggestions,
            shouldReviewPrerequisites: data.should_review_prerequisites,
            prerequisitesToReview: data.prerequisites_to_review,
            feedback: data.feedback,
        });
    } catch (error) {
        console.error("Evaluation API Error:", error);
        return NextResponse.json(
            { error: "Failed to evaluate explanation" },
            { status: 500 }
        );
    }
}
