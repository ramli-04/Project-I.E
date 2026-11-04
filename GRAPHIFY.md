# Graphify for Cabinet 2.0

Installed from https://github.com/Graphify-Labs/graphify.git at commit 0a8cd4e1e342235fe53e881fb5d591bf0460071f (Graphify 0.9.97).

Run these commands in this project directory using PowerShell:

```powershell
# Build the local code graph, with no external model or API key.
.\graphify.cmd extract . --code-only --max-workers 2
.\graphify.cmd cluster-only .
.\graphify.cmd export html

# Explore relationships.
.\graphify.cmd query "Prescription"
.\graphify.cmd explain "Prescription"

# Refresh after source changes.
.\graphify.cmd update .
```

Open `graphify-out/graph.html` in your browser. The graph data is in `graphify-out/graph.json`, and the report is in `graphify-out/GRAPH_REPORT.md`.

The Codex skill is installed at `.codex/skills/graphify/SKILL.md` and will be available on your next turn when this project is open. You can invoke `/graphify .`.

Graphify has its own `.graphify-venv`; the application environment is separate. `.graphifyignore` excludes dependencies and generated release assets. The environment and generated graph output are ignored by Git. This initial graph uses local structural code extraction; document and image semantic analysis is excluded.

To recreate the isolated installation:

```powershell
python -m venv .graphify-venv
.\.graphify-venv\Scripts\python.exe -m pip install "git+https://github.com/Graphify-Labs/graphify.git@0a8cd4e1e342235fe53e881fb5d591bf0460071f"
.\graphify.cmd install --project --platform codex
```
