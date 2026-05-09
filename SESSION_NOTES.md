# Session Notes — 2026-05-09

> Where you left off. Read this first when you resume.

## TL;DR — what's already shippable

- **Full multi-agent cascade is proven end-to-end.** Two golden runs in your Kestra DB right now:
  - `yjcEFrIxI7ML9MXyM4CeY` — 91s, all 4 children SUCCESS, no repo (PAT scope was missing then)
  - `6ZVvUI6iwed6xRt37PVZDY` — 34s, all 4 children SUCCESS, **created [Pavankumar07s/realtime-whiteboard](https://github.com/Pavankumar07s/realtime-whiteboard)**, Slack delivered ✓
- **Obsidian graph is dense:** 22 goal notes, 44 execution notes, 6 tool stubs, 2 final reports — all wiki-linked.
- **6 flows deployed** in `hackathon.copilot` namespace, all using direct Gemini (`gemini-2.5-flash`). Will Just Work tomorrow when daily quota resets.

## How to start the stack from cold

```bash
cd /home/pavan/Desktop/kestra_hackathon/kestra-copilot
docker compose up -d
export PATH="$HOME/.local/bin:$PATH"
kestractl flows deploy ./flows/ --override   # idempotent
```

Access:
- **Kestra UI:** http://localhost:18080  (login: `admin@kestra.local` / `Hackathon2026!`)
- **Obsidian vault:** `/home/pavan/Documents/KestraCoPilotVault/kestra-copilot/`

## How to trigger a fresh demo run

```bash
./play.sh                                                # default whiteboard brief
./play.sh "Build a CLI todo app with SQLite persistence" # custom brief
./play.sh --warmup --open                                # warmup + spawn 3-pane browser tabs
```

Or via API:

```bash
curl -sS -u "admin@kestra.local:Hackathon2026!" \
  -X POST "http://localhost:18080/api/v1/main/executions/hackathon.copilot/planner?wait=true" \
  -F 'goal=Build a real-time collaborative whiteboard with WebSockets and Postgres'
```

Expect: ~30–90s wallclock, 4 children all SUCCESS, fresh notes in `goals/`/`executions/`/`reports/`, plus a Slack message and a new GitHub repo.

## LLM provider matrix (what we tried, what works)

| Provider | Model | Status |
|---|---|---|
| **Direct Gemini** | `gemini-2.5-flash` | ✅ **Works perfectly** (the golden runs use this). Free 20 req/day. Reliable when quota available. |
| Direct Gemini | `gemini-2.5-flash-lite` | ⚠️ Works but only emits 1 tool call before stopping. Not viable for the cascade. |
| Direct Gemini | `gemini-3-flash-preview` | ❌ Requires `thought_signature` field on tool replies; Kestra's langchain4j adapter doesn't send it. Errors out after first tool call. |
| OpenRouter | `openai/gpt-oss-120b:free` | ⚠️ Works for 2-3 tool calls, then gives up. Inconsistent. Free tier rate-limited. |
| OpenRouter | `google/gemini-2.5-flash` (paid) | 💰 Would Just Work. Account needs **$1 credit** added at https://openrouter.ai/settings/credits. ~$0.005 per demo run. |
| Groq | `llama-3.3-70b-versatile` | ❌ Tool-call args trigger `Text "" could not be parsed at index 0` in Kestra (KestraFlow's optional `scheduleDate` field). |
| Groq | `meta-llama/llama-4-scout-17b` | ❌ Same date-parse bug. |
| GitHub Models | `openai/gpt-4o-mini` | ❌ Returns "Bad credentials" with fine-grained PAT (even with `Models: Read` scope). May need a classic PAT. |
| Local Ollama | `mistral:7b` | ❌ Has `tools` capability but emits prose ("Turn 1: call_researcher(...)") instead of structured tool calls. |
| Local Ollama | `qwen2.5:3b` | ❌ Same — too small for Kestra's complex KestraFlow JSON schema. |

**Bottom line:** Direct Gemini `gemini-2.5-flash` is the only fully-working path. When quota resets tomorrow, the cascade will run reliably.

## Open issues / known limitations (in priority order)

1. **Gemini free-tier daily quota is 20 req/day on `gemini-2.5-flash`.** Each cascade burns ~5 calls (researcher + coder + planner's 3 decisions + summary). So ~4 cascades per day max on the free tier. **Resets at ~midnight Pacific (~12h from session end).** Two paths to avoid:
   - Add **$1 of credit** at https://openrouter.ai/settings/credits, then swap planner/researcher/coder providers to `io.kestra.plugin.ai.provider.OpenRouter` with `modelName: google/gemini-2.5-flash`. ~200 demo runs per $1.
   - Get a **classic PAT** from https://github.com/settings/tokens with `read:models` scope, then switch to GitHub Models provider. Free, 50 req/day per model.

2. **Auto-commit of vault** needs a Kestra container restart to pick up `OBSIDIAN_GIT_AUTOCOMMIT=true` from `.env` (env_file is read at container start). Manual commits work fine: `git -C /home/pavan/Documents/KestraCoPilotVault commit -am "…"`.

3. **The vault's `.git` directory is at the parent vault path**, not at `kestra-copilot/`. The `obsidian_sync.py` git logic checks the vault root which is `/obsidian` from inside the container. The "vault is not a git repo, skipping commit" warning is harmless; commits work from the host.

4. **CodeExecution / Judge0 sandbox not wired up.** `RAPID_API_KEY` is empty. The Coder is text-only today; the Reviewer does the actual code execution (deterministic Python script) which is more reliable for the demo anyway.

5. **Disk is at 96%** (only 6.4 GB free). Pulling a bigger Ollama model (e.g. `qwen2.5:7b` at 4.7 GB) is risky. If you want to try local LLM later, free up disk first.

## What's left (Phase 4 — demo recording)

1. **Pick the brief.** Default is the whiteboard one (works perfectly). Alternatives that produced clean cascades: `"Build a CLI todo app with SQLite persistence and a JSON export command"`, `"Build a Pomodoro timer in Python that logs sessions to CSV"`.

2. **Pre-warm:** trigger one run, throw away its notes (or commit + leave them), then trigger the *real* demo run. The first run after a cold start has cache-cold LLM latency; the second is snappy. The `play.sh --warmup` flag does this for you.

3. **3-pane recording layout** (per `instruction.md`):
   - **Left half:** Kestra UI on http://localhost:18080/ui/main/executions filtered to `namespace = hackathon.copilot`, sorted ascending, auto-refresh on
   - **Top right:** Obsidian graph view, filter `path:kestra-copilot`, depth 3, color group `path:kestra-copilot/executions` warm + `path:kestra-copilot/tools` cool
   - **Bottom right:** your Slack channel where the webhook lands

4. **Record** with OBS, Loom, or native screen recorder. **Edit to exactly 30 seconds.** Captions only (no voiceover — silent + text reads better on social).

5. **Caption draft (LinkedIn — 2-3 paragraphs):**
   > 🤖 Built a Kestra agent that turns *"build me a real-time whiteboard"* into a working starter project — in about a minute, end-to-end.
   >
   > A Planner LLM agent decides which specialist subflow to dispatch (researcher, coder, reviewer, communicator). The cascade you see in the Kestra UI is whatever the LLM chose — different brief → different cascade. Every step writes a markdown note into Obsidian, so the agent collaboration graph renders live.
   >
   > Output: a real GitHub repo, a Slack announcement, and a graph that proves the agents actually talked to each other.
   >
   > Repo: https://github.com/Pavankumar07s/kestra-copilot · Generated demo: https://github.com/Pavankumar07s/realtime-whiteboard
   >
   > `#KestraAcademy` `@kestra` `@WeMakeDevs`

6. **Caption draft (X — punchy):**
   > Built a Kestra agent that turns "build me an X" into a real GitHub repo + Slack announcement, with the whole cascade rendering live in Obsidian's graph view. 30s. `#KestraAcademy`

7. **Post both. Drop URLs into a new `POSTED.md` as the final commit.**

## Architecture cheat-sheet

```
hackathon.copilot.planner   (AIAgent: gemini-2.5-flash, allowFailure: true, 4× KestraFlow tool)
   ├─ hackathon.copilot.researcher    (AIAgent → picks LANGUAGE / FRAMEWORK / DEPS)
   ├─ hackathon.copilot.coder         (AIAgent → writes a self-contained source file)
   ├─ hackathon.copilot.reviewer      (Python — runs the generated code in a sandbox)
   └─ hackathon.copilot.communicator  (Python — GitHub repo + Slack + final report)
```

Every flow's last task is `obsidian_sync.py`, writing a markdown note with wiki-links to:
- the goal note (one per run, hub of the graph)
- the parent execution
- each tool used (one stub per tool TYPE, idempotent)

The Communicator's final task additionally writes `reports/report_<goal_id>.md` linking back to the goal + every execution under that goal — the "you reached the end of the journey" node in the graph.

## Files of note

| Path | What it does |
|---|---|
| `flows/00_setup.yml` | Seeds 8 KV entries from container env (`{{ envs.* }}`) |
| `flows/01_planner.yml` | Root AIAgent w/ 4 KestraFlow tools, `allowFailure: true` |
| `flows/02_researcher.yml` | Picks stack/libs (text-only AIAgent) |
| `flows/03_coder.yml` | Generates source (text-only AIAgent) |
| `flows/04_reviewer.yml` | Runs code in temp dir, captures pass/fail |
| `flows/05_communicator.yml` | GitHub repo + Slack + writes the final report (with parsed-markdown stack section) |
| `scripts/obsidian_sync.py` | Single source of truth for vault writes; supports `--report` mode |
| `play.sh` | One-command demo runner. `./play.sh --help` for options. |
| `README.md` | Project README, hackathon-judge ready |
| `docker-compose.yml` | Kestra remapped to host port **18080** (8080 was in use); `kestra.url: http://localhost:8080/` (in-container) |

## KV state snapshot (8+ entries, namespace `hackathon.copilot`)

| Key | Filled? |
|---|---|
| GEMINI_API_KEY | ✅ second key (first hit daily quota) |
| GITHUB_TOKEN | ✅ fine-grained PAT, scopes: Administration / Contents / Metadata / Models — repo creation works |
| GITHUB_USERNAME | ✅ `Pavankumar07s` |
| KESTRA_USERNAME | ✅ `admin@kestra.local` |
| KESTRA_PASSWORD | ✅ `Hackathon2026!` |
| OPENROUTER_API_KEY | ✅ key valid but account has 0 credits |
| GROQ_API_KEY | ✅ valid, but Groq+Kestra has the date-parse bug |
| RAPID_API_KEY | ❌ empty (Judge0 not wired up — Reviewer does code exec deterministically instead) |
| SLACK_WEBHOOK_URL | ✅ delivers correctly |

## Gotchas already documented in `CLAUDE.md`

(8 gotchas under the "Gotchas" section — most important to remember:)

- **Pebble has no `truncate` filter.** Use `s[:N]` in Python with values passed via the `env:` block.
- **`outputs.<task>.textOutput`** is the AIAgent completion field, NOT `.completion`. Tool execution results land in `outputs.<task>.toolExecutions[].result` as a JSON-string with `flowId` and `id`.
- **`kestraUrl: http://localhost:8080`** (in-container address) plus an `auth:` block on every KestraFlow tool — required for subflow trigger to work against basic-auth-protected Kestra.
- **`kv.Set` doesn't need `namespace:`** — defaults to flow's namespace.
- **Free-tier LLMs sometimes parallel-fire tools** — system prompt now hard-pins "ONE tool per turn, wait for result". `allowFailure: true` on Planner so cascade stays green even if the final summary call rate-limits.
- **Fine-grained GitHub PATs may not work with GitHub Models** — even with `Models: Read` scope, returns "Bad credentials". Use a classic PAT for inference.
- **Gemini-3 needs `thought_signature` field** that Kestra's langchain4j integration doesn't send. Stick with `gemini-2.5-flash`.

## Quick smoke test checklist

```bash
docker compose ps                             # both containers Up + (healthy)
curl -sS http://localhost:18080/api/v1/configs | python3 -m json.tool | head -3
kestractl flows list hackathon.copilot        # 6 flows
kestractl kv list hackathon.copilot           # 8+ entries

# Trigger a run (after Gemini quota reset):
curl -sS -u "admin@kestra.local:Hackathon2026!" \
  -X POST "http://localhost:18080/api/v1/main/executions/hackathon.copilot/planner?wait=true" \
  -F 'goal=Build a Pomodoro timer in Python that logs sessions to CSV' \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print('state:',d['state']['current'])"

# Verify fresh notes:
ls -t /home/pavan/Documents/KestraCoPilotVault/kestra-copilot/executions/ | head -5
ls -t /home/pavan/Documents/KestraCoPilotVault/kestra-copilot/reports/ | head -3

# Verify GitHub repo:
gh repo list Pavankumar07s --limit 5
```
