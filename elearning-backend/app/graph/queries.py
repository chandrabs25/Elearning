"""Neo4j query functions for knowledge graph operations."""
from app.graph.client import neo4j_client
from app.graph.models import ConceptNode, ExerciseNode


async def get_concept(concept_id: str) -> ConceptNode | None:
    """Get a concept by ID."""
    result = await neo4j_client.execute_read_single(
        """
        MATCH (c:Concept {id: $concept_id})
        RETURN c {.*} as concept
        """,
        concept_id=concept_id
    )
    return ConceptNode(**result["concept"]) if result else None


async def get_concept_with_prerequisites(concept_id: str) -> dict:
    """Get a concept with its prerequisites."""
    result = await neo4j_client.execute_read_single(
        """
        MATCH (c:Concept {id: $concept_id})
        OPTIONAL MATCH (c)-[:REQUIRES]->(prereq:Concept)
        RETURN c {.*} as concept, collect(prereq {.*}) as prerequisites
        """,
        concept_id=concept_id
    )
    if not result:
        return {"concept": None, "prerequisites": []}
    
    return {
        "concept": ConceptNode(**result["concept"]),
        "prerequisites": [ConceptNode(**p) for p in result["prerequisites"] if p]
    }


async def get_next_concept(concept_id: str) -> ConceptNode | None:
    """Get the next concept in the learning path."""
    result = await neo4j_client.execute_read_single(
        """
        MATCH (c:Concept {id: $concept_id})-[:NEXT]->(next:Concept)
        RETURN next {.*} as concept
        """,
        concept_id=concept_id
    )
    return ConceptNode(**result["concept"]) if result else None


async def get_previous_concept(concept_id: str) -> ConceptNode | None:
    """Get the previous concept in the learning path."""
    result = await neo4j_client.execute_read_single(
        """
        MATCH (prev:Concept)-[:NEXT]->(c:Concept {id: $concept_id})
        RETURN prev {.*} as concept
        """,
        concept_id=concept_id
    )
    return ConceptNode(**result["concept"]) if result else None


async def get_all_prerequisites(concept_id: str) -> list[ConceptNode]:
    """Get all prerequisites (transitive) for a concept."""
    results = await neo4j_client.execute_read(
        """
        MATCH (c:Concept {id: $concept_id})-[:REQUIRES*]->(prereq:Concept)
        RETURN DISTINCT prereq {.*} as concept
        """,
        concept_id=concept_id
    )
    return [ConceptNode(**r["concept"]) for r in results]


async def get_exercises_for_concept(concept_id: str) -> list[ExerciseNode]:
    """Get exercises that test a specific concept."""
    results = await neo4j_client.execute_read(
        """
        MATCH (e:Exercise)-[:TESTS]->(c:Concept {id: $concept_id})
        RETURN e {.*} as exercise
        """,
        concept_id=concept_id
    )
    return [ExerciseNode(**r["exercise"]) for r in results]


async def get_learning_path() -> list[ConceptNode]:
    """Get all concepts in the learning path order."""
    results = await neo4j_client.execute_read(
        """
        MATCH (chapter:Chapter {id: 'gravity'})-[:CONTAINS]->(c:Concept)
        OPTIONAL MATCH path = (start:Concept)-[:NEXT*]->(c)
        WITH c, length(path) as depth
        ORDER BY COALESCE(depth, 0)
        RETURN DISTINCT c {.*} as concept
        """
    )
    return [ConceptNode(**r["concept"]) for r in results]
