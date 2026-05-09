# Kestra Hackathon Co-Pilot

> An autonomous multi-agent Kestra workflow that turns a natural-language hackathon brief into a working GitHub starter project, announces it on Slack, and renders the entire agent collaboration graph in real time inside Obsidian.

Built for the [WeMakeDevs × Kestra Orchestration Challenge](https://kestra.io). The Planner is an `AIAgent` that *dynamically* dispatches subflows — the cascade you see in the Kestra UI is whatever the LLM decided, not a hardcoded fan-out. Different brief → different cascade.

## The 30-second demo

| Time | Kestra UI | Obsidian graph | Slack |
|------|-----------|----------------|-------|
| 0–3s | _(empty)_ | _(empty)_ | User pastes brief: *"Build a real-time collaborative whiteboard with WebSockets and Postgres"* |
| 3–12s | Planner kicks off, fans out to Researcher / Coder / Reviewer / Communicator subflows. | Goal node appears, then Planner, then four specialists branch off. | _(idle)_ |
| 12–22s | More tool calls inside each specialist; Reviewer can loop back to Coder. | Tree continues blossoming. Tool nodes attach. | _(idle)_ |
| 22–28s | Final Communicator turns green. | Final report node appears, links to everything. | "✓ Repo: github.com/.../whiteboard-starter — Tests passing — Stack: FastAPI + websockets + psycopg2" |
| 28–30s | _(cursor clicks the GitHub link)_ | | _(real repo, real code, real README)_ |

That's the package. **Kestra cascade + Obsidian graph + real GitHub artifact**, all driven by one LLM agent's tool choices.

## Architecture

```
hackathon.copilot.planner   (AIAgent — tool calls dispatch each child as a Kestra subflow)
    ├─ hackathon.copilot.researcher    (AIAgent → picks LANGUAGE / FRAMEWORK / DEPS)
    ├─ hackathon.copilot.coder         (AIAgent → writes a self-contained source file)
    ├─ hackathon.copilot.reviewer      (Python — runs the generated code in a sandbox)
    └─ hackathon.copilot.communicator  (Python — creates GitHub repo, posts to Slack, writes report)
```

Every flow's last task is `scripts/obsidian_sync.py`, which writes one markdown note per execution into the user's Obsidian vault. Wiki-links between notes are what render the live agent collaboration graph.

| | Plugin / tech | What it does |
|---|---|---|
| Orchestrator | [Kestra 1.0+](https://kestra.io) (Docker compose, local) | Dispatch + KV store + execution tree |
| LLM | `io.kestra.plugin.ai.agent.AIAgent` | Tool-using agent — drives the cascade |
| Tool spec | `io.kestra.plugin.ai.tool.KestraFlow` | Lets the LLM call other flows as tools |
| Code exec | `io.kestra.plugin.scripts.python.Script` | Runs generated code, captures pass/fail |
| GitHub | `urllib` against the GitHub REST API | Repo create + file PUT |
| Slack | `io.kestra.plugin.notifications.slack.SlackIncomingWebhook` | Announcement message |
| Memory | Kestra KV store + Obsidian markdown vault | Secrets + persistent run history |

## Quick start

### 1. Prereqs

- Docker + Docker Compose
- An [Obsidian](https://obsidian.md) vault (or any folder you'll point Obsidian at later)
- API keys (free tiers fine for everything):
  - **LLM:** [Google AI Studio](https://aistudio.google.com/apikey) for Gemini, OR [GitHub PAT with `Models: Read`](https://github.com/settings/tokens?type=beta), OR an [OpenRouter](https://openrouter.ai/keys) key
  - **GitHub fine-grained PAT** with `Administration: Write` + `Contents: Write` + `Metadata: Read` + `Models: Read`
  - **Slack** [incoming webhook](https://api.slack.com/messaging/webhooks)
  - _(optional)_ [RapidAPI key for Judge0](https://rapidapi.com/judge0-official/api/judge0-ce) if you want the Coder to also execute code

### 2. Setup

```bash
git clone https://github.com/Pavankumar07s/kestra-copilot.git
cd kestra-copilot
cp .env.example .env
$EDITOR .env                                  # paste keys + your vault path

docker compose up -d                          # Kestra UI: http://localhost:18080
# On first visit, the UI prompts you to set a basic-auth user. Pick one.

kestractl config add default --host http://localhost:18080 \
    --username <email>@<domain> --password '<your-password>'
kestractl flows deploy ./flows/ --override
kestractl executions run hackathon.copilot setup --wait    # one-time KV seed from .env
```

### 3. Run the demo

```bash
./play.sh                                     # default whiteboard brief
./play.sh "Build a CLI todo app with SQLite persistence and a JSON export command"
./play.sh --warmup --open                     # warmup + spawn 3-pane browser tabs
```

A run takes ~60–90 seconds and produces:

- ✅ One nested execution tree in the Kestra UI (Planner with 4 child specialists)
- ✅ ~6 markdown notes in your Obsidian vault under `kestra-copilot/`, all wiki-linked
- ✅ A new public repo in your GitHub account with a `README.md`, source file, and stack rationale
- ✅ A Slack announcement linking the repo

## Flows

| File | Type | What it does |
|---|---|---|
| [`flows/00_setup.yml`](flows/00_setup.yml) | one-off | Pulls 7 keys from container env into the `hackathon.copilot` KV namespace |
| [`flows/01_planner.yml`](flows/01_planner.yml) | root | LLM agent with 4× `KestraFlow` tool — drives the cascade |
| [`flows/02_researcher.yml`](flows/02_researcher.yml) | LLM | Picks language / framework / deps from the brief |
| [`flows/03_coder.yml`](flows/03_coder.yml) | LLM | Writes a self-contained source file |
| [`flows/04_reviewer.yml`](flows/04_reviewer.yml) | deterministic | Runs the code in a sandbox, returns pass/fail |
| [`flows/05_communicator.yml`](flows/05_communicator.yml) | deterministic | Creates GitHub repo + posts to Slack + writes the final report |

Reference example flows in `flows/_reference_*.example` show the canonical syntax for each pattern.

## Why "demo-first"?

This is a hackathon submission, not a product. Every decision was driven by *"does it show up in the 30-second screen recording?"* If yes, it stayed. If no, it got cut. See [`instruction.md`](instruction.md) for the full brief and [`plan.md`](plan.md) for the phase-by-phase build log.

## Gotchas worth knowing

- **Kestra rebinds 18080 → 8080** because port 8080 was in use on the dev box. The in-container `kestra.url` config stays `http://localhost:8080/` so subflow trigger calls work.
- **Pebble has no `truncate` filter.** Use Python `s[:N]` instead, with values passed via the `env:` block.
- **AIAgent output is `outputs.<task>.textOutput`**, not `.completion`. Tool execution results land in `outputs.<task>.toolExecutions[].result` as a JSON string with `flowId` and `id`.
- **Free-tier LLMs sometimes parallel-fire tools** instead of waiting for each result. The system prompt now hard-pins "ONE tool per turn, wait for result". `allowFailure: true` on the Planner AIAgent means the cascade stays green even when the final summary call rate-limits.
- **GitHub fine-grained PATs need `Models: Read`** for the GitHubModels provider, in addition to repo scopes.

More gotchas in [`CLAUDE.md`](CLAUDE.md), the working contract this project was built against.

## License

MIT. Take it, fork it, ship a better demo.
