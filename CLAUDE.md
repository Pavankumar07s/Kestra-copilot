# CLAUDE.md — Project Context for Claude Code

> Claude Code: this file is your contract. Read it once at the start of every session. If anything here conflicts with what the user just said, the user wins, but flag the conflict.

## Mission (one sentence)

Build an autonomous multi-agent system in Kestra 1.0 that turns a natural-language hackathon brief into a working GitHub repo + Slack announcement, with the entire run rendered as a live graph in the user's Obsidian vault. Demo target: a 30-second video, ready to post to LinkedIn/X with `#KestraAcademy`.

## Why this exists

Entry submission for the WeMakeDevs × Kestra Orchestration Challenge. Cert and initial post are already done. This build is the social-share follow-up that drives reach. Optimize for **demo-ability**, not feature breadth. If a feature isn't visible in the 30-second video, don't build it.

## Install the Kestra agent skills FIRST

Before writing any flow YAML, install Kestra's official Claude Code skills. They give you live schema validation against `https://api.kestra.io/v1/plugins/schemas/flow` and access to the `kestractl` CLI for deploy/validate/run.

1. Visit https://kestra.io/docs/ai-tools/agent-skills and follow the install instructions for **both** `kestra-flow` and `kestra-ops` skills.
2. Install `kestractl` and point it at `http://localhost:8080`.
3. After install, when generating any flow YAML, prefix your work with: *"Use the kestra-flow skill to validate this against the live schema before writing to disk."*

If you skip this step you will burn hours debugging YAML schema errors that the skill would have caught instantly.

## Stack (use only these — do not add)

- **Orchestrator:** Kestra 1.0+ (Docker-compose, local)
- **LLM:** Google Gemini 2.5 Flash via `io.kestra.plugin.ai.provider.GoogleGemini` (free tier; generous quota)
- **Code execution:** Judge0 via RapidAPI, called from `io.kestra.plugin.ai.tool.CodeExecution`
- **Subflow spawning:** `io.kestra.plugin.ai.tool.KestraFlow` attached to the Planner's AIAgent
- **Memory:** Kestra KV store + Obsidian markdown vault (no Weaviate in v1; defer)
- **Notifications:** Slack incoming webhook, GitHub REST API
- **Glue:** Python 3.11 scripts via `io.kestra.plugin.scripts.python.Script`

## Directory contract

```
kestra-copilot/
├── CLAUDE.md                 # this file
├── instruction.md            # human-facing brief — DO NOT EDIT during build
├── plan.md                   # phase-wise tasks — mark off as you complete
├── README.md
├── docker-compose.yml
├── .env                      # gitignored, copied from .env.example
├── .env.example
├── .gitignore
├── flows/                    # all Kestra YAML
│   ├── 00_setup.yml          # one-off: seeds KV from env
│   ├── 01_planner.yml        # root agent
│   ├── 02_researcher.yml
│   ├── 03_coder.yml
│   ├── 04_reviewer.yml
│   ├── 05_communicator.yml
│   └── _reference_*.example  # syntax references, not auto-loaded
├── scripts/
│   ├── obsidian_sync.py      # writes markdown notes + git auto-commit
│   └── ...
└── obsidian_seed/            # initial notes copied into the user's vault
    └── README.md
```

## Environment (read from .env)

| Var | Purpose |
|-----|---------|
| `GEMINI_API_KEY` | Google AI Studio — https://aistudio.google.com/apikey |
| `RAPID_API_KEY` | RapidAPI key for Judge0 |
| `GITHUB_TOKEN` | Fine-grained PAT, scopes: repo write, contents write |
| `GITHUB_USERNAME` | Used in repo URLs |
| `SLACK_WEBHOOK_URL` | Incoming webhook for the announcement channel |
| `OBSIDIAN_VAULT_PATH` | Absolute host path to the vault root (mounted into container) |
| `OBSIDIAN_PROJECT_FOLDER` | Folder inside the vault for our notes (default: `kestra-copilot`) |
| `OBSIDIAN_GIT_AUTOCOMMIT` | `true`/`false` — auto-commit on every write |
| `GRAPHIFY_REMOTE` | Optional: extra git remote to push notes to |
| `KESTRA_NAMESPACE` | `hackathon.copilot` — don't change |

## Conventions (enforce strictly)

1. **Namespace:** every flow is in `hackathon.copilot`.
2. **Final task always:** every flow's last task is a Python script call to `obsidian_sync.py`. No exceptions. This is what creates the graph. If a flow has multiple branches, sync at every leaf.
3. **Secrets:** always `{{ kv('GEMINI_API_KEY') }}`, never literals.
4. **Task IDs:** `verb_noun` — `decompose_goal`, `run_tests`, `sync_to_obsidian`.
5. **Subflow calls:** use `KestraFlow` tool inside the Planner AIAgent, not hardcoded `Subflow` tasks. The whole point is dynamic dispatch by the LLM.
6. **Labels:** every flow has `labels: { project: copilot, phase: <N> }`.
7. **Description:** every flow has a one-line `description:` field.
8. **No silent failures:** Python scripts that fail must log to stderr and exit non-zero, not swallow errors. The Obsidian sync is the exception — it logs and continues even on git failures so it never blocks an execution.

## Reference syntax — KestraFlow tool

The Planner uses this exact pattern (verified against Kestra docs):

```yaml
- id: plan_and_route
  type: io.kestra.plugin.ai.agent.AIAgent
  provider:
    type: io.kestra.plugin.ai.provider.GoogleGemini
    apiKey: "{{ kv('GEMINI_API_KEY') }}"
    modelName: gemini-2.5-flash
  systemMessage: |
    [role + tool list + rules — see flows/_reference_planner.yml.example]
  prompt: "{{ inputs.goal }}"
  tools:
    - type: io.kestra.plugin.ai.tool.KestraFlow
      namespace: hackathon.copilot
      flowId: researcher
      description: "Picks stack, finds libs, checks docs."
    - type: io.kestra.plugin.ai.tool.KestraFlow
      namespace: hackathon.copilot
      flowId: coder
      description: "Generates code and runs it in a sandbox."
    # ... etc
```

The agent's outputs include `toolExecutions[]` with `{tenantId, flowId, id}` for each subflow it spawned — use this in `obsidian_sync.py` to create the parent→child links.

## How to run / test

- `docker-compose up -d` from project root
- Kestra UI: http://localhost:8080
- Trigger Planner: UI button, or `kestractl executions run hackathon.copilot planner --inputs goal="..."`
- Kestra logs: `docker-compose logs -f kestra`
- Obsidian: open vault, navigate to `kestra-copilot/`, open graph view (cmd/ctrl-G), filter `path:kestra-copilot` for the cleanest view

## Hard rules (do not break)

1. **Demo-first.** If it doesn't show up in the video, don't build it.
2. **Kestra UI is the hero.** Anything that adds visible subflow executions is good. Hidden fast paths are bad.
3. **Never break Obsidian sync.** Every agent execution writes one markdown note. Period.
4. **Idempotent.** Re-running a flow does not corrupt the vault. Notes use timestamped IDs, never overwrite.
5. **No scope creep.** Not in `plan.md` → don't do it. If you think something should be added, write a `QUESTIONS.md` entry instead and surface it.

## Gotchas (will be filled in as we discover them)

- 2026-05-09: Port 8080 was occupied on this box; Kestra remapped to 18080 (host) → 8080 (container). `kestra.url` config must stay `http://localhost:8080/` (in-container) or KestraFlow tool's flow lookup fails with "connection refused".
- 2026-05-09: Kestra OSS 1.3.x requires basic-auth even with `kestra.server.basicAuth.enabled: false`. First-run UI prompts for an email + password and stashes a hash in the `settings` table. Reset by `DELETE FROM settings WHERE key='kestra.server.basic-auth';` in postgres, then `POST /api/v1/main/basicAuth` with `{username, password}` — returns 204 on first init.
- 2026-05-09: Pebble has NO `truncate` filter. Use `slice(0, N)` — but `slice` errors when input is shorter than `N`. Best: pass values via `env:` block and truncate in Python with `s[:N]`.
- 2026-05-09: AIAgent output is `outputs.<task>.textOutput`, NOT `.completion`. The `toolExecutions` array carries `result` strings (JSON) with `flowId` and `id` per spawned child.
- 2026-05-09: KestraFlow tool's `kestraUrl: http://localhost:8080` plus an `auth: {username, password}` block is REQUIRED for subflow trigger to work (the tool calls Kestra's REST API to spawn). Without auth, basic-auth-protected Kestra returns 401 and the AIAgent silently fails.
- 2026-05-09: Gemini free tier is 5 req/min on `gemini-2.5-flash`, 15 req/min on `gemini-2.5-flash-lite`. The Planner makes ~5 LLM calls per cascade (one per tool decision + final summary), so flash will rate-limit on the *final* summary call. Set `allowFailure: true` on the Planner AIAgent so the cascade still ends green and `obsidian_sync` still runs.
- 2026-05-09: `flash-lite` is too dumb for the multi-step plan — only calls one tool then stops. Stick with `flash` and accept the occasional final-summary rate-limit.
- 2026-05-09: OpenRouter `:free` models work (e.g. `openai/gpt-oss-120b:free`) but are inconsistent with Kestra's langchain4j tool-call adapter — sometimes parallel-fire tools without waiting for results. Direct Gemini is more reliable for the LLM-driven cascade.
- 2026-05-09: **`gemma-4-31b-it` is the winning free model.** Same Google AI Studio API key as Gemini, same `io.kestra.plugin.ai.provider.GoogleGemini` provider, just `modelName: gemma-4-31b-it`. Hits a separate "Other models" quota bucket (14,400 req/day on the free tier vs Gemini-flash's 20/day), emits proper structured tool calls, no `thought_signature` issue, no date-parse bug. Confirmed driving full 4-child cascade end-to-end (run `55j04PbVfAg05dLPFGkKOf`). Use this when Gemini quota is exhausted.
- 2026-05-09: GitHub fine-grained PATs **cannot have their permissions edited** — adding a scope after creation either silently fails or invalidates the existing token value. Always regenerate (full new token value) when changing scopes.
- 2026-05-09: GitHub Models API (`models.github.ai/inference`) returns "Bad credentials" with fine-grained PATs even when `Models: Read` permission is set. Use a classic PAT with `read:models` scope instead, or use a different LLM provider.
- 2026-05-09: Groq tool-call args break Kestra's KestraFlow tool — llama-3.3 and llama-4-scout emit `""` for the optional `scheduleDate` field, and Java's `Instant` parser throws `Text "" could not be parsed at index 0`. Avoid Groq for cascades that use KestraFlow.
- 2026-05-09: Gemini-3-flash-preview requires `thought_signature` field on tool replies; langchain4j doesn't send it. Use Gemini 2.5 Flash or Gemma 4 instead.
- 2026-05-09: Local Ollama models (`mistral:7b`, `qwen2.5:3b`) advertise `tools` capability but emit text-prose (e.g. "Turn 1: call_researcher(...)") rather than structured function calls when the schema is non-trivial. Need 12B+ tool-trained variants like `qwen2.5:7b` or `llama3.1:8b` for the KestraFlow schema.

## When in doubt, in this order

1. Read `instruction.md` for *what* and *why*.
2. Read `plan.md` for *what next*.
3. Use the `kestra-flow` agent skill to validate any YAML.
4. Check Kestra docs at https://kestra.io/docs/.
5. If still stuck, write the question to `QUESTIONS.md` and move to a parallel task.
