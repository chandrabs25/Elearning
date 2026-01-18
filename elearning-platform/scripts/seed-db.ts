import { checkConnection } from "@/lib/neo4j/client";
import { getDriver } from "@/lib/neo4j/client";
import fs from "fs";
import path from "path";
import dotenv from "dotenv";

// Load environment variables
dotenv.config({ path: ".env.local" });

async function seedDatabase() {
    console.log("Checking Neo4j connection...");
    const isConnected = await checkConnection();
    if (!isConnected) {
        console.error("Failed to connect to Neo4j. Check if Docker container is running.");
        process.exit(1);
    }
    console.log("Connected to Neo4j successfully.");

    const driver = getDriver();
    const session = driver.session();

    try {
        // Read seed file
        const seedFilePath = path.join(process.cwd(), "src/data/graph/seed-data.cypher");
        const seedCypher = fs.readFileSync(seedFilePath, "utf-8");

        // Clean existing data
        console.log("Cleaning database...");
        await session.run("MATCH (n) DETACH DELETE n");

        // Split and run Cypher commands
        // Note: The driver can only run one statement at a time, so we need to split carefully
        // Simple splitting by double newline for this POC script
        const statements = seedCypher
            .split("\n\n")
            .map(s => s.trim())
            .filter(s => s.length > 0 && !s.startsWith("//"));

        console.log(`Found ${statements.length} blocks of Cypher to execute.`);

        for (const [index, statement] of statements.entries()) {
            // Skip comment-only blocks
            if (statement.startsWith("//")) continue;

            console.log(`Executing block ${index + 1}...`);
            await session.run(statement);
        }

        console.log("✅ Database seeded successfully!");

        // Verify counts
        const countResult = await session.run(`
      MATCH (n) 
      RETURN labels(n) as label, count(n) as count 
      ORDER BY count DESC
    `);

        console.log("Node counts:");
        countResult.records.forEach(record => {
            console.log(`${record.get("label")}: ${record.get("count")}`);
        });

    } catch (error) {
        console.error("Error seeding database:", error);
    } finally {
        await session.close();
        await driver.close();
    }
}

seedDatabase();
