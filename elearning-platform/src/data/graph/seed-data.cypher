// Neo4j Seed Data for Gravity Chapter
// Run this in Neo4j Browser or via driver

// ============================================
// CLEAR EXISTING DATA (use with caution)
// ============================================
// MATCH (n) DETACH DELETE n

// ============================================
// NODE TYPES
// ============================================

// Chapter node
CREATE (chapter:Chapter {
  id: "gravity",
  number: "7",
  title: "Gravitation",
  subject: "Physics"
})

// ============================================
// PREREQUISITE CONCEPTS (From earlier chapters)
// ============================================

CREATE (circular_motion:Concept {
  id: "prereq-circular-motion",
  title: "Circular Motion",
  chapter: "5",
  section: "5.4",
  description: "Motion in a circular path with centripetal acceleration",
  isPrerequisite: true
})

CREATE (vectors:Concept {
  id: "prereq-vectors",
  title: "Vectors and Vector Operations",
  chapter: "4",
  section: "4.2",
  description: "Vector addition, subtraction, and components",
  isPrerequisite: true
})

CREATE (newtons_laws:Concept {
  id: "prereq-newtons-laws",
  title: "Newton's Laws of Motion",
  chapter: "5",
  section: "5.1-5.3",
  description: "Laws governing motion and forces",
  isPrerequisite: true
})

CREATE (work_energy:Concept {
  id: "prereq-work-energy",
  title: "Work and Energy",
  chapter: "6",
  section: "6.1-6.8",
  description: "Work, kinetic energy, potential energy, conservation",
  isPrerequisite: true
})

CREATE (angular_momentum:Concept {
  id: "prereq-angular-momentum",
  title: "Angular Momentum",
  chapter: "6",
  section: "6.9",
  description: "Rotational analogue of linear momentum",
  isPrerequisite: true
})

// ============================================
// GRAVITY CHAPTER CONCEPTS
// ============================================

CREATE (intro:Concept {
  id: "7.1",
  title: "Introduction to Gravitation",
  sectionId: "7.1",
  description: "Historical context of gravitational observations from Galileo to Kepler",
  difficulty: 1,
  estimatedMinutes: 10
})

CREATE (kepler:Concept {
  id: "7.2",
  title: "Kepler's Laws",
  sectionId: "7.2",
  description: "Three laws governing planetary motion: orbits, areas, and periods",
  difficulty: 2,
  estimatedMinutes: 25
})

CREATE (universal_law:Concept {
  id: "7.3",
  title: "Universal Law of Gravitation",
  sectionId: "7.3",
  description: "Newton's law of gravitational attraction between masses",
  difficulty: 2,
  estimatedMinutes: 30
})

CREATE (grav_constant:Concept {
  id: "7.4",
  title: "The Gravitational Constant",
  sectionId: "7.4",
  description: "Cavendish experiment and measuring G",
  difficulty: 2,
  estimatedMinutes: 15
})

CREATE (accel_surface:Concept {
  id: "7.5",
  title: "Acceleration Due to Gravity at Earth's Surface",
  sectionId: "7.5",
  description: "Deriving g from gravitational law",
  difficulty: 2,
  estimatedMinutes: 20
})

CREATE (accel_above_below:Concept {
  id: "7.6",
  title: "Acceleration Due to Gravity: Above and Below Surface",
  sectionId: "7.6",
  description: "How g varies with height and depth",
  difficulty: 3,
  estimatedMinutes: 25
})

CREATE (grav_potential:Concept {
  id: "7.7",
  title: "Gravitational Potential Energy",
  sectionId: "7.7",
  description: "Potential energy in gravitational field",
  difficulty: 3,
  estimatedMinutes: 30
})

CREATE (escape_speed:Concept {
  id: "7.8",
  title: "Escape Speed",
  sectionId: "7.8",
  description: "Minimum speed to escape gravitational pull",
  difficulty: 3,
  estimatedMinutes: 20
})

CREATE (satellites:Concept {
  id: "7.9",
  title: "Earth Satellites",
  sectionId: "7.9",
  description: "Orbital mechanics of artificial satellites",
  difficulty: 3,
  estimatedMinutes: 25
})

CREATE (orbital_energy:Concept {
  id: "7.10",
  title: "Energy of an Orbiting Satellite",
  sectionId: "7.10",
  description: "Kinetic and potential energy balance in orbits",
  difficulty: 3,
  estimatedMinutes: 20
})

// ============================================
// PREREQUISITE RELATIONSHIPS
// ============================================

CREATE (intro)-[:REQUIRES]->(newtons_laws)
CREATE (kepler)-[:REQUIRES]->(circular_motion)
CREATE (kepler)-[:REQUIRES]->(angular_momentum)
CREATE (universal_law)-[:REQUIRES]->(vectors)
CREATE (universal_law)-[:REQUIRES]->(newtons_laws)
CREATE (accel_surface)-[:REQUIRES]->(universal_law)
CREATE (accel_above_below)-[:REQUIRES]->(accel_surface)
CREATE (grav_potential)-[:REQUIRES]->(work_energy)
CREATE (grav_potential)-[:REQUIRES]->(universal_law)
CREATE (escape_speed)-[:REQUIRES]->(grav_potential)
CREATE (satellites)-[:REQUIRES]->(kepler)
CREATE (satellites)-[:REQUIRES]->(circular_motion)
CREATE (orbital_energy)-[:REQUIRES]->(satellites)
CREATE (orbital_energy)-[:REQUIRES]->(grav_potential)

// ============================================
// CHAPTER FLOW (Next concept in sequence)
// ============================================

CREATE (intro)-[:NEXT]->(kepler)
CREATE (kepler)-[:NEXT]->(universal_law)
CREATE (universal_law)-[:NEXT]->(grav_constant)
CREATE (grav_constant)-[:NEXT]->(accel_surface)
CREATE (accel_surface)-[:NEXT]->(accel_above_below)
CREATE (accel_above_below)-[:NEXT]->(grav_potential)
CREATE (grav_potential)-[:NEXT]->(escape_speed)
CREATE (escape_speed)-[:NEXT]->(satellites)
CREATE (satellites)-[:NEXT]->(orbital_energy)

// ============================================
// CHAPTER CONTAINS CONCEPTS
// ============================================

CREATE (chapter)-[:CONTAINS]->(intro)
CREATE (chapter)-[:CONTAINS]->(kepler)
CREATE (chapter)-[:CONTAINS]->(universal_law)
CREATE (chapter)-[:CONTAINS]->(grav_constant)
CREATE (chapter)-[:CONTAINS]->(accel_surface)
CREATE (chapter)-[:CONTAINS]->(accel_above_below)
CREATE (chapter)-[:CONTAINS]->(grav_potential)
CREATE (chapter)-[:CONTAINS]->(escape_speed)
CREATE (chapter)-[:CONTAINS]->(satellites)
CREATE (chapter)-[:CONTAINS]->(orbital_energy)

// ============================================
// EXERCISE NODES
// ============================================

CREATE (ex_7_1:Exercise { id: "7.1", question: "Shielding from gravity and detection in orbits" })
CREATE (ex_7_2:Exercise { id: "7.2", question: "Choose correct: g with altitude/depth" })
CREATE (ex_7_3:Exercise { id: "7.3", question: "Planet orbital size at 2x speed" })
CREATE (ex_7_4:Exercise { id: "7.4", question: "Io orbital data to find Jupiter's mass" })
CREATE (ex_7_5:Exercise { id: "7.5", question: "Galactic revolution period" })
CREATE (ex_7_6:Exercise { id: "7.6", question: "Satellite total energy relations" })
CREATE (ex_7_7:Exercise { id: "7.7", question: "Escape speed dependencies" })
CREATE (ex_7_8:Exercise { id: "7.8", question: "Comet conserved quantities" })
CREATE (ex_7_12:Exercise { id: "7.12", question: "Rocket toward sun - zero gravity point" })
CREATE (ex_7_13:Exercise { id: "7.13", question: "Weigh the sun" })
CREATE (ex_7_14:Exercise { id: "7.14", question: "Saturn distance from sun" })
CREATE (ex_7_15:Exercise { id: "7.15", question: "Weight at height = R/2" })
CREATE (ex_7_16:Exercise { id: "7.16", question: "Weight at depth = R/2" })
CREATE (ex_7_17:Exercise { id: "7.17", question: "Rocket max height" })
CREATE (ex_7_18:Exercise { id: "7.18", question: "Speed far from Earth at 3x escape" })
CREATE (ex_7_19:Exercise { id: "7.19", question: "Energy to escape satellite from orbit" })
CREATE (ex_7_20:Exercise { id: "7.20", question: "Two star collision speed" })
CREATE (ex_7_21:Exercise { id: "7.21", question: "Two spheres equilibrium" })

// ============================================
// EXERCISE-CONCEPT MAPPINGS (Manual)
// ============================================

CREATE (ex_7_1)-[:TESTS]->(universal_law)
CREATE (ex_7_2)-[:TESTS]->(accel_above_below)
CREATE (ex_7_3)-[:TESTS]->(kepler)
CREATE (ex_7_4)-[:TESTS]->(kepler)
CREATE (ex_7_4)-[:TESTS]->(satellites)
CREATE (ex_7_5)-[:TESTS]->(kepler)
CREATE (ex_7_6)-[:TESTS]->(orbital_energy)
CREATE (ex_7_7)-[:TESTS]->(escape_speed)
CREATE (ex_7_8)-[:TESTS]->(kepler)
CREATE (ex_7_8)-[:TESTS]->(grav_potential)
CREATE (ex_7_12)-[:TESTS]->(universal_law)
CREATE (ex_7_13)-[:TESTS]->(kepler)
CREATE (ex_7_14)-[:TESTS]->(kepler)
CREATE (ex_7_15)-[:TESTS]->(accel_above_below)
CREATE (ex_7_16)-[:TESTS]->(accel_above_below)
CREATE (ex_7_17)-[:TESTS]->(escape_speed)
CREATE (ex_7_17)-[:TESTS]->(grav_potential)
CREATE (ex_7_18)-[:TESTS]->(escape_speed)
CREATE (ex_7_19)-[:TESTS]->(orbital_energy)
CREATE (ex_7_20)-[:TESTS]->(grav_potential)
CREATE (ex_7_21)-[:TESTS]->(universal_law)
