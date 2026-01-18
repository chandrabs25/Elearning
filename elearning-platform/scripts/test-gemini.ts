import * as dotenv from "dotenv";

dotenv.config({ path: ".env.local" });

async function checkModels() {
    const apiKey = process.env.GOOGLE_API_KEY;
    console.log("Checking models for API key ending in:", apiKey?.slice(-4));

    try {
        const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`);

        if (!response.ok) {
            console.error(`API Error: ${response.status} ${response.statusText}`);
            const text = await response.text();
            console.error("Details:", text);
            return;
        }

        const data = await response.json();
        console.log("Available Models:");
        if (data.models) {
            data.models.forEach((m: any) => {
                if (m.supportedGenerationMethods?.includes("generateContent")) {
                    console.log(`- ${m.name}`); // format: models/model-name
                }
            });
        } else {
            console.log("No models returned in list.");
        }

    } catch (e: any) {
        console.error("Fetch error:", e.message);
    }
}

checkModels();
