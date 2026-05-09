# kestra-copilot — agent run log

This folder is auto-populated by the **Kestra Hackathon Co-Pilot** project.

Every time you trigger a planner run, a markdown note is written here for each
agent execution in the cascade. The wiki-links between notes are what render
the live agent collaboration graph in Obsidian's graph view.

## Subfolders

- **`goals/`** — one note per natural-language brief you ran the planner on.
- **`executions/`** — one note per agent execution (planner, researcher, coder, reviewer, communicator).
- **`tools/`** — one stub note per tool *type* used (KestraFlow, CodeExecution, WebSearch, etc.).
- **`reports/`** — final summary written by the Communicator at the end of each goal run.

## Tips for the demo

1. Open the graph view (cmd/ctrl-G) and filter to `path:kestra-copilot`.
2. Set graph depth to 3.
3. Hide tags. Show attachments off.
4. Color group: `path:kestra-copilot/executions` warm, `path:kestra-copilot/tools` cool.
5. Save the view so you can return to it instantly during recording.

## To start fresh

Delete this entire folder. The next planner run will recreate it cleanly.

```bash
rm -rf kestra-copilot/
```

(Or right-click → delete in Obsidian.)
