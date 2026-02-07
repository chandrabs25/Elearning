"""Generate a visual diagram of the tutor LangGraph."""
import sys
sys.path.insert(0, '/Users/srichandrasamanapalli/Elearning/elearning-backend')

from app.agents.tutor_agent import tutor_agent

# Get the graph as a Mermaid diagram
mermaid_png = tutor_agent.get_graph().draw_mermaid_png()

# Save to file
with open('/Users/srichandrasamanapalli/Elearning/elearning-backend/tutor_graph.png', 'wb') as f:
    f.write(mermaid_png)

print("✅ Graph saved to tutor_graph.png")

# Also print the Mermaid code for text representation
mermaid_code = tutor_agent.get_graph().draw_mermaid()
print("\nMermaid diagram code:")
print(mermaid_code)
