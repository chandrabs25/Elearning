import re
import os

file_path = '/Users/srichandrasamanapalli/Elearning/solutions.json'
backup_path = '/Users/srichandrasamanapalli/Elearning/solutions_backup.json'

# Backup first
if not os.path.exists(backup_path):
    with open(file_path, 'r') as f:
        original = f.read()
    with open(backup_path, 'w') as f:
        f.write(original)
    print("Backup created.")

with open(file_path, 'r') as f:
    content = f.read()

# Pattern to find "content": "..." where ... can be multi-line
# We look for "content": " ... " followed by a closing brace or comma.
# This assumes "content" values do not contain unescaped quotes.
pattern = r'("content":\s*")([\s\S]*?)("(?=\s*\}))'

def replacement(match):
    prefix = match.group(1)
    body = match.group(2)
    suffix = match.group(3)
    # Escape backslashes first (for LaTeX etc)
    # This must be done before escaping newlines, otherwise we break the newlines we create
    # Wait, newlines in the string are actual control characters. replace('\\', '\\\\') works on the string literals.
    new_body = body.replace('\\', '\\\\')
    # Replace literal newlines with escaped newline characters
    new_body = new_body.replace('\n', '\\n')
    # Also escape double quotes if they exist inside the content (except the ones we matched as delimiters)
    # But wait, our regex extracts the *inner* content, so any quote inside IS part of the content.
    new_body = new_body.replace('"', '\\"')
    return prefix + new_body + suffix

new_content = re.sub(pattern, replacement, content)

with open(file_path, 'w') as f:
    f.write(new_content)

print("Fixed solutions.json")
