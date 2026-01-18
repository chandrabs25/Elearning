import neo4j, { Driver, Session } from "neo4j-driver";

let driver: Driver | null = null;

export function getDriver(): Driver {
    if (!driver) {
        const uri = process.env.NEO4J_URI || "bolt://localhost:7687";
        const user = process.env.NEO4J_USER || "neo4j";
        const password = process.env.NEO4J_PASSWORD || "password";

        driver = neo4j.driver(uri, neo4j.auth.basic(user, password));
    }
    return driver;
}

export async function getSession(): Promise<Session> {
    const driver = getDriver();
    return driver.session();
}

export async function closeDriver(): Promise<void> {
    if (driver) {
        await driver.close();
        driver = null;
    }
}

// Health check
export async function checkConnection(): Promise<boolean> {
    const session = await getSession();
    try {
        await session.run("RETURN 1");
        return true;
    } catch {
        return false;
    } finally {
        await session.close();
    }
}
