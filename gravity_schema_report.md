# Gravity JSON Schema Analysis

The `gravity.json` file represents a structured chapter from an educational textbook (specifically Chapter 7: Gravitation). It uses a custom schema designed to represent rich educational content including text, mathematical derivations, diagrams, worked examples, and exercises.

## Root Object Structure

| Field | Type | Description |
| :--- | :--- | :--- |
| `chapter_number` | `string` | The chapter designation (e.g., "Chapter Seven"). |
| `chapter_title` | `string` | The title of the chapter (e.g., "Gravitation"). |
| `table_of_contents` | `array` | A list of TOC objects defining the chapter flow. |
| `sections` | `array` | The core content, divided into distinct sections. |

## Table of Contents Item
Each item in the `table_of_contents` array has:
- `id`: identifier matching a `section_id` (e.g., "7.1", "Summary").
- `title`: Display title of the section.

## Section Object
Each item in the `sections` array has:
- `section_id`: Unique identifier (e.g., "7.1").
- `section_title`: Uppercase title of the section.
- `content`: An array of **Content Blocks**.

## Content Blocks
The schema uses a **polymorphic** `content` array where each object has a mandatory `type` field determining its structure.

### 1. Text
Standard paragraphs.
- `type`: `"text"`
- `body`: `string` (The actual text content).

### 2. List Item
Used for numbered or bulleted lists.
- `type`: `"list_item"`
- `label`: `string` (e.g., "1.", "2.", "(a)").
- `body`: `string` (The content of the list item).

### 3. Diagram
Represents figures and images.
- `type`: `"diagram"`
- `figure_number`: `string` (e.g., "7.1(a)").
- `meta`: `string` (Descriptive text or caption for the image).

### 4. Derivation
Mathematical formulas or proofs.
- `type`: `"derivation"`
- `latex`: `string` (The mathematical content in LaTeX syntax, often wrapped in `$$` for display math).
- `meta`: `string` (Explanation of what the derivation represents).

### 5. Table
Represents tabular data.
- `type`: `"table"`
- `title`: `string` (optional).
- `headers`: `array of strings` (Column headers).
- `rows`: `array of array of strings` (Data rows).
- `meta`: `string` (Description).

### 6. Example Box
Worked-out problems.
- `type`: `"example_box"`
- `label`: `string` (e.g., "Example 7.1").
- `question`: `string` (The problem statement).
- `solution`: `object` (The solution content).
  - **Note**: The `solution` field is flexible. It can be a single content block (like a `"derivation"`) OR a container type `"example_solution"` which itself has a simple `content` array.

### 7. Exercise Item
End-of-chapter questions.
- `type`: `"exercise_item"`
- `label`: `string` (e.g., "7.1").
- `question`: `string` (The main question text).
- `sub_questions`: `array` (Optional, list of sub-parts like (a), (b)).
- `content`: `array` (Optional, can contain diagrams relevant to the question).

## Key Observations
- **LaTeX Integration**: Mathematical expressions are heavily relied upon using the `"derivation"` type with LaTeX keys.
- **Accessibility/Context**: Almost every visual element (`diagram`, `derivation`, `table`) includes a `meta` field, which acts as a semantic description or caption, likely useful for accessibility or searching.
- **Nested Content**: The `example_box` and `exercise_item` types can contain nested content arrays, allowing for complex problem structures that include diagrams and multi-step solutions.
