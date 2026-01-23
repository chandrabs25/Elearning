import json

# Load both JSON files
with open('gravity.json', 'r', encoding='utf-8') as f:
    gravity_data = json.load(f)

with open('solutions.json', 'r', encoding='utf-8') as f:
    solutions_data = json.load(f)

# Create a mapping of solution IDs to solution content
solutions_map = {sol['id']: sol['content'] for sol in solutions_data['solutions']}

# Find the EXERCISES section and add solutions to exercise_items
for section in gravity_data['sections']:
    if section['section_id'] == 'EXERCISES':
        for item in section['content']:
            if item['type'] == 'exercise_item':
                # Extract the exercise number from the label (e.g., "7.1" -> "1")
                label = item['label']
                exercise_num = label.split('.')[-1]  # Get the number after the dot
                
                # Get the corresponding solution
                if exercise_num in solutions_map:
                    # Add the solution key with the content from solutions.json
                    item['solution'] = solutions_map[exercise_num]
                    print(f"Added solution to exercise {label}")
                else:
                    print(f"Warning: No solution found for exercise {label}")

# Write the updated data back to gravity.json
with open('gravity.json', 'w', encoding='utf-8') as f:
    json.dump(gravity_data, f, ensure_ascii=False, indent=2)

print("\nSuccessfully updated gravity.json with solutions!")
