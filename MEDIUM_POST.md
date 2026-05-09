# I built an AI agent that builds hackathon projects — using Kestra, Obsidian, and a lot of duct tape

### Day 1 of the WeMakeDevs × Kestra Orchestration Challenge: a Planner LLM that decomposes a one-line brief into a real GitHub repo, a Slack announcement, and a live agent graph in Obsidian.

---

## TL;DR

I paste a sentence like *"build a real-time collaborative whiteboard with WebSockets and Postgres"* into Kestra. ~60 seconds later:

- A **GitHub repo** exists in my account ([Pavankumar07s/realtime-whiteboard](https://github.com/Pavankumar07s/realtime-whiteboard)) with a README, a source file, and a stack rationale.
- My **Slack channel** has an announcement message linking to the repo.
- My **Obsidian vault** has a fresh tree of markdown notes — one per agent execution — wiki-linked into a graph that renders live as the cascade runs.
- The **Kestra UI** shows a Planner execution that fanned out to four specialist subflows: a Researcher, a Coder, a Reviewer, and a Communicator.

The trick: the cascade you see in the Kestra UI is whatever the LLM **chose**. Different brief → different cascade. That's the whole product. The LLM is in the loop, dispatching real Kestra subflows as tool calls, and every dispatch is visible.

If you want to skip the story: [the repo](https://github.com/Pavankumar07s/kestra-copilot), the [generated demo project](https://github.com/Pavankumar07s/realtime-whiteboard), or scroll to **"Things that nearly killed the build"** for the war stories you'd actually want to read.

---

## The brief that started this

The [WeMakeDevs × Kestra Orchestration Challenge](https://kestra.io) gives developers about a week to ship something interesting on Kestra and post it. I'd already done the cert + an intro post. This was the social-share follow-up — the part that drives reach.

I had four scenarios on a sticky note:

1. **Hackathon Co-Pilot** — paste a brief, get a starter repo. Meta. Self-referential.
2. **GitHub Triage Bot** — auto-label issues + nudge stale PRs.
3. **Slack-to-Ship** — turn a Slack thread into a deploy.
4. **Market Research Analyst** — fan out across web sources, summarize.

I picked Co-Pilot because it's **shareable**. A hackathon project that helps you start hackathon projects is the kind of thing that gets reposted. The output (a real GitHub repo) is something a viewer can actually click. And the WeMakeDevs audience is hackathon-native — this lands hard.

The constraint I imposed on myself before writing a line of code: **if it doesn't show up in the 30-second screen recording, don't build it.**

That single rule killed scope-creep before it started. No web frontend. No Vercel auto-deploy. No self-healing pipelines. No multi-tenant auth. No tweet-thread explainers. Just: cascade visible, graph visible, repo visible. Three panels of a screen recording, three things to point a camera at.

---

## What I actually built

```
hackathon.copilot.planner   ←  AIAgent (Gemini 2.5 Flash + 4× KestraFlow tool)
    ├─ hackathon.copilot.researcher    →  picks LANGUAGE / FRAMEWORK / DEPS
    ├─ hackathon.copilot.coder         →  writes a self-contained source file
    ├─ hackathon.copilot.reviewer      →  Python script — runs the code in a sandbox, captures pass/fail
    └─ hackathon.copilot.communicator  →  Python script — creates GitHub repo, posts to Slack, writes a final report
```

Five Kestra flows, all in one namespace. The Planner is the only one that uses tool-calling — the other four are leaf agents (Researcher, Coder) or deterministic glue (Reviewer, Communicator).

The key Kestra plugin is **`io.kestra.plugin.ai.tool.KestraFlow`**. You attach it to an `AIAgent` and now the LLM has *flows* as tools. When the LLM decides to call `call_coder(task_description="…")`, Kestra trigger an execution of `hackathon.copilot.coder` and feeds the result back into the LLM's context. To the user it looks like an agent calling a function. To Kestra it's just another flow execution — visible, observable, retryable, the whole package.

Here's the planner's tool spec, abbreviated:

```yaml
- id: plan_and_route
  type: io.kestra.plugin.ai.agent.AIAgent
  allowFailure: true
  provider:
    type: io.kestra.plugin.ai.provider.GoogleGemini
    apiKey: "{{ kv('GEMINI_API_KEY') }}"
    modelName: gemini-2.5-flash
  maxSequentialToolsInvocations: 6
  systemMessage: |
    You drive a team of FOUR specialist agents that run as Kestra
    subflow executions. Each tool call shows up as a nested execution
    in the Kestra UI — that visible cascade IS the product.

    ABSOLUTE RULE — STRICTLY SEQUENTIAL: Call EXACTLY ONE tool per turn.
    WAIT for that tool's RESULT. READ the result. THEN decide the next.
    NEVER call multiple tools in the same turn.

    Order:
      Turn 1: call_researcher(brief=<the user's brief verbatim>)
      Turn 2: call_coder(task_description=<rephrase, mention the LANGUAGE>)
      Turn 3: call_reviewer(language, source_code, filename)
      Turn 4: call_communicator(project_name, brief, stack_summary,
                                source_filename, source_code, review_summary)
      Turn 5: Reply with a 2-3 sentence summary including the repo URL.
  prompt: "{{ inputs.goal }}"
  tools:
    - type: io.kestra.plugin.ai.tool.KestraFlow
      namespace: hackathon.copilot
      flowId: researcher
      kestraUrl: http://localhost:8080
      auth:
        username: "{{ kv('KESTRA_USERNAME') }}"
        password: "{{ kv('KESTRA_PASSWORD') }}"
      inheritLabels: true
      labels:
        copilot_goal_id: "{{ inputs.goal_id }}"
        copilot_parent_id: "{{ execution.id }}"
    # … three more KestraFlow tools, one per specialist
```

A few things worth noting about that snippet, because each one cost me time:

- `kestraUrl: http://localhost:8080` — when the KestraFlow tool fires a subflow, it calls Kestra's own REST API to do it. Inside the container, Kestra binds `:8080`; the host port mapping is `:18080`. If you don't override `kestraUrl`, Kestra defaults to whatever `kestra.url` is configured to and the call hits a non-existent port. You get "connection refused" with no obvious culprit.
- `auth: { username, password }` — Kestra OSS 1.3 forces basic-auth on. The KestraFlow tool needs credentials to call its own API. If you skip this block you get a silent 401 — the AIAgent fails with no useful error.
- `allowFailure: true` on the planner — if the LLM's *final* summary call rate-limits, the AIAgent ends in WARNING instead of FAILED. The cascade still ends green, the obsidian-sync still runs, the demo still works.
- `maxSequentialToolsInvocations: 6` — small cap. The Planner makes ~5 tool decisions max. Setting this prevents runaway loops if the LLM gets confused.
- `inheritLabels: true` plus per-tool `labels` — this is how I tie all child executions to the same goal. Every subflow execution carries `copilot_goal_id` and `copilot_parent_id` labels, set by the parent. The Obsidian sync script reads these labels to draw the right wiki-links.

Each specialist flow ends with a Python script that calls `obsidian_sync.py`:

```yaml
- id: sync_to_obsidian
  type: io.kestra.plugin.scripts.python.Script
  taskRunner:
    type: io.kestra.plugin.core.runner.Process
  env:
    AGENT: researcher
    EXEC_ID: "{{ execution.id }}"
    GOAL_ID: "{{ labels.copilot_goal_id ?? trigger.executionId ?? execution.id }}"
    PARENT_ID: "{{ labels.copilot_parent_id ?? trigger.executionId ?? '' }}"
    TASK_INPUT: "{{ inputs.brief }}"
    AGENT_OUTPUT: "{{ outputs.pick_stack.textOutput ?? '' }}"
  script: |
    import os, subprocess, sys
    def cap(s, n): return (s or "")[:n]
    subprocess.run([
        sys.executable, "/app/scripts/obsidian_sync.py",
        "--agent", os.environ["AGENT"],
        "--execution-id", os.environ["EXEC_ID"],
        "--goal-id", os.environ["GOAL_ID"],
        "--parent-id", os.environ["PARENT_ID"],
        "--input", cap(os.environ.get("TASK_INPUT"), 300),
        "--output", cap(os.environ.get("AGENT_OUTPUT"), 800),
        "--tools-used", "AIAgent",
        "--children", "",
        "--status", "completed",
    ], check=False)
```

There's a reason it's wired this way and not as a Pebble template. **Pebble (Kestra's templating engine) has no `truncate` filter.** I tried `slice(0, 300)` — that errors when the input is shorter than 300 characters. The clean solution: pass everything through the `env:` block as a string, then truncate in Python where I have a real language. Bonus: zero quoting issues with arbitrary user input. The LLM's brief can contain backticks, quotes, code, whatever — env vars don't care.

---

## The Obsidian graph trick

This is the part most of the build time went into, and it's the part the demo screen-recording sells.

Every flow's final task writes one markdown note into a folder structure inside the user's Obsidian vault:

```
$VAULT/kestra-copilot/
├── goals/
│   └── goal_<execution_id>.md
├── executions/
│   └── 2026-05-09T10-22-15Z_researcher_2fgmeeae.md
│   └── 2026-05-09T10-22-29Z_reviewer_yudxcled.md
│   └── ...
├── tools/
│   └── tool_kestraflow.md
│   └── tool_aiagent.md
│   └── ...
└── reports/
    └── report_<goal_id>.md   ← written only by Communicator at the end
```

Each note has YAML frontmatter (so Obsidian's Dataview/graph features can filter on `type: agent_execution` etc.) and a body full of Obsidian wiki-links (`[[goal_xyz]]`, `[[2026-05-09T10-22-15Z_researcher_2fgmeeae]]`).

The wiki-links are everything. Obsidian's graph view doesn't render edges from frontmatter — it renders edges from `[[wiki-links]]` in the body of the note. So my notes look like:

```markdown
---
type: agent_execution
agent: coder
execution_id: 7UJLdCOCQf1RqIbjFGJyOh
goal_id: 6ZVvUI6iwed6xRt37PVZDY
parent_id: 6ZVvUI6iwed6xRt37PVZDY
status: completed
---

# coder — 2026-05-09T10-07-41Z

**Goal:** [[goal_6zvvui6iwed6xrt37pvzdy]]
**Parent:** [[6ZVvUI6iwed6xRt37PVZDY]]
**Status:** `completed`

## Output

LANGUAGE: Python
FRAMEWORK: FastAPI
SOURCE:
```python
from fastapi import FastAPI, WebSocket
import asyncpg, asyncio
…
```

## Tools used

[[tool_aiagent]]
```

When the cascade runs, notes appear in the vault one at a time. The graph re-renders. Edges blossom outward from the goal node. It feels alive — and that's what the screen recording captures.

A couple of things I had to figure out for this to look right in the graph view:

- **Tool stub notes are deduped by tool *type*, not per-call.** If I created one tool note per AIAgent invocation, the graph would be a hairball. Instead, `tool_aiagent.md` is created once and every execution that used an AIAgent wiki-links to it. It becomes a hub node. The graph shape stays clean.
- **The goal note is the second hub.** Every execution under a goal links back to it. The Communicator at the end writes a "final report" note that *also* links to every execution (so you have one node that points to the whole journey).
- **Filenames matter.** Obsidian only renders wiki-link edges where both endpoints exist as `.md` files in the vault. Timestamped IDs (`2026-05-09T10-22-15Z_researcher_2fgmeeae`) are a pain to type but solve idempotency: re-running a flow never overwrites an old note, and the graph builds incrementally instead of mutating in place.
- **Color groups in Obsidian's graph view settings:** `path:kestra-copilot/executions` warm, `path:kestra-copilot/tools` cool. Save the view. Now during the demo recording, one click shows the right shape.

---

## What the 30 seconds shows

Three panels, side by side:

| Time | Left half: Kestra UI | Top right: Obsidian graph | Bottom right: Slack |
|------|----------------------|----------------------------|---------------------|
| 0–3s | (empty) | (empty) | I paste the brief into Slack: *"Build a real-time collaborative whiteboard with WebSockets and Postgres"* |
| 3–12s | Planner kicks off, fans out to Researcher / Coder / Reviewer / Communicator subflows. Tree visibly grows. | Goal node appears, then Planner, then four specialists branch off. | (idle) |
| 12–22s | More tool calls inside each specialist. | Tree continues blossoming. Tool nodes attach. | (idle) |
| 22–28s | Final Communicator turns green. | Final report node appears. | "✓ Repo: github.com/.../realtime-whiteboard — Stack: FastAPI + websockets + asyncpg" |
| 28–30s | (cursor clicks the GitHub link) | | (a real repo with a real README and real source code) |

The whole package: the cascade tree, the live graph, and the clickable artifact. No voiceover — captions only. Silence + on-screen text reads better on social.

---

## Things that nearly killed the build (the LLM provider trenches)

This was the hardest part. Not the architecture, not the YAML, not the Obsidian sync. The hardest part was getting an LLM to **reliably drive a 4-step tool-call cascade** on free tiers.

I'll just give you the full matrix. Save someone else a day:

| Provider | Model | What happened |
|---|---|---|
| **Direct Gemini** | `gemini-2.5-flash` | ✅ The only model that reliably drives all 4 children sequentially. Free tier is **20 requests per day** though. Each cascade burns ~5 calls (4 tool decisions + final summary). |
| Direct Gemini | `gemini-2.5-flash-lite` | ⚠️ Has the daily quota headroom, but only emits **one tool call** before stopping. The model isn't smart enough for the multi-step plan even with explicit instructions. |
| Direct Gemini | `gemini-3-flash-preview` | ❌ Returns 400 with *"Function call is missing a thought_signature in functionCall parts"*. Gemini 3 wants its tool-call signatures echoed back; Kestra's langchain4j adapter doesn't yet send them. |
| OpenRouter | `openai/gpt-oss-120b:free` | ⚠️ Got 2-3 tool calls deep then died silently. Inconsistent rate-limit behavior on the free tier. |
| OpenRouter | `google/gemini-2.5-flash` (paid) | 💰 Would Just Work. Costs ~$0.005 per cascade. $1 of credit = ~200 demo runs. |
| Groq | `llama-3.3-70b-versatile` | ❌ Tool-call args trigger `Text "" could not be parsed at index 0` in Kestra. The `KestraFlow` tool exposes an optional `scheduleDate` field; llama emits `""` for it; Java's `Instant` parser crashes. |
| Groq | `meta-llama/llama-4-scout-17b-16e-instruct` | ❌ Same date-parse crash. |
| GitHub Models | `openai/gpt-4o-mini` (free with PAT) | ❌ "Bad credentials" with my fine-grained PAT, even after explicitly adding `Models: Read` permission. Pretty sure GitHub Models still wants a classic PAT for inference. |
| Local Ollama | `mistral:7b` | ❌ Has `tools` capability but emits *prose* — literally writes "Turn 1: call_researcher(brief='…')" as text instead of emitting a structured tool call. |
| Local Ollama | `qwen2.5:3b` | ❌ Same — too small for Kestra's complex KestraFlow JSON schema. |

The combinations of failures here are educational on their own. A few patterns worth pointing out:

1. **"Has tools capability" is not the same as "can drive a multi-step cascade."** Mistral 7B and Qwen 2.5 3B both expose `capabilities: ['tools']` in Ollama. Both write tool-call-shaped *prose* instead of actual structured tool calls when given a non-trivial schema like KestraFlow's.
2. **Free tier daily quotas are the silent killer.** Per-minute rate limits you can dance around with retries. Daily limits just stop you. Gemini's 20/day on flash means after 4 demo runs you're out for the day.
3. **Tool-call hygiene varies wildly.** Llama 3.3 confidently emits empty strings for optional date fields. Gemini correctly omits them. The Kestra schema doesn't tolerate `""` where it expects `null`. So you end up with model-specific failures that have nothing to do with model intelligence.
4. **Parallel tool calls are a problem.** Some models (gpt-oss-120b in particular) like to fire multiple tool calls in a single turn instead of waiting for the first result. If your schema requires the second tool's input to come *from* the first tool's output, you get garbage. The fix in the system prompt: explicit "ONE tool per turn, wait for result."

What I ended up shipping with: direct Gemini 2.5 Flash, with `allowFailure: true` on the planner so the cascade still ends green when the final summary call rate-limits.

The pragmatic insight: **the planner LLM is responsible for the *visible cascade*. As long as the four children spawn correctly, the rest of the demo doesn't depend on the LLM's final summary.** I configured the cascade to survive a half-failed planner and the demo kept its narrative.

---

## Things I deliberately didn't build

I want to call these out because the discipline is what made this shippable in a week.

- **No custom web frontend.** The Kestra UI plus Obsidian graph view *are* the entire UI surface. Building a React dashboard would have eaten 2 days. Not worth it for a 30s demo.
- **No Vercel auto-deploy.** A clickable repo URL is enough. If a viewer wants to deploy the generated project, they can.
- **No self-healing pipelines.** The Reviewer flags failures. The cascade doesn't loop forever. Good enough.
- **No multi-tenant auth.** Local-only, single laptop, `docker-compose up`. The hackathon is a demo, not a SaaS.
- **No long-term memory beyond Obsidian.** I considered Weaviate. Cut it. The vault notes carry the entire history.
- **No RAG over external docs.** The Researcher works from training data. Tavily web search exists in Kestra (`io.kestra.plugin.ai.tool.TavilyWebSearch`) but adding it would have meant another API key, another rate limit. Cut.
- **No tests of the Co-Pilot itself.** The product *is* a demo. Reviewing my reviewer would have been navel-gazing.

The hard rule I came back to every time I felt scope-creep: *"if it doesn't show up in the 30-second video, don't build it."* That single rule saved this build.

---

## A few hard-won gotchas

If you're trying to do something like this on Kestra, here are the things that cost me time and that the docs don't cover well:

1. **Pebble has no `truncate` filter.** Pass values through `env:` blocks and truncate in Python.
2. **AIAgent's output field is `outputs.<task>.textOutput`**, not `.completion`. Tool execution results land in `outputs.<task>.toolExecutions[].result` as a JSON-encoded string with `flowId` and `id`.
3. **`io.kestra.plugin.ai.tool.KestraFlow` needs `kestraUrl: http://localhost:8080` plus an `auth:` block** (when basic-auth is on) — without these, the tool's call to spawn a subflow returns 401 and the AIAgent silently fails.
4. **`io.kestra.plugin.core.kv.Set` doesn't need an explicit `namespace:`** — it defaults to the flow's namespace. Saves a few lines per setup task.
5. **Kestra OSS 1.3.x forces basic-auth on,** even with `kestra.server.basicAuth.enabled: false` in the config. The first browser visit prompts for an email + password and stashes a hash in the `settings` table. To reset programmatically: `DELETE FROM settings WHERE key='kestra.server.basic-auth';` and then `POST /api/v1/main/basicAuth` with the desired creds.
6. **Port 8080 is everyone's default.** I had something on 8080 already, so Kestra is remapped to host port `18080` → container `:8080`. Critically, the in-container `kestra.url` config must stay `http://localhost:8080/` (not `:18080`) — that's the URL Kestra uses to call itself for subflow lookups. If you set it to the host port, the KestraFlow tool tries to call back through the bridge and gets connection refused.
7. **The vault is mounted via Docker volume,** which means the `.git` directory at the vault root is invisible to git running inside the container if the project subfolder is mounted instead. Mount the whole vault.

These are the kinds of things that, in hindsight, you'd put in a "Read me first" doc. So I wrote one — the `CLAUDE.md` in the repo has the running list.

---

## How to try it yourself

The repo is at [github.com/Pavankumar07s/kestra-copilot](https://github.com/Pavankumar07s/kestra-copilot). Five-minute setup:

```bash
git clone https://github.com/Pavankumar07s/kestra-copilot.git
cd kestra-copilot
cp .env.example .env
$EDITOR .env  # paste GEMINI_API_KEY, GITHUB_TOKEN, SLACK_WEBHOOK_URL, OBSIDIAN_VAULT_PATH

docker compose up -d                                # Kestra UI: http://localhost:18080
                                                    # First visit prompts you to set basic-auth creds

kestractl flows deploy ./flows/ --override
kestractl executions run hackathon.copilot setup --wait

# Now run a brief through it:
./play.sh "Build a Pomodoro timer in Python that logs sessions to CSV"
# or with the full UX:
./play.sh --warmup --open
```

You'll need:

- Docker + Docker Compose
- An [Obsidian](https://obsidian.md) vault path
- A free [Google AI Studio key](https://aistudio.google.com/apikey)
- A GitHub fine-grained PAT with `Administration: Write` + `Contents: Write` + `Metadata: Read`
- A Slack [incoming webhook](https://api.slack.com/messaging/webhooks)

A run takes ~60-90 seconds and produces a real repo, a real Slack message, and ~6 fresh notes in your vault. Open the graph view (`Cmd/Ctrl-G`), filter to `path:kestra-copilot`, and watch it grow.

---

## What's next

A few directions, in priority order:

1. **The 30-second demo video.** That's literally the only "feature" I haven't shipped yet — the recording itself. Coming this week.
2. **A Reviewer that actually *fixes* code.** Right now it runs the code and reports pass/fail. The next step is to feed failure output back to the Coder for a retry loop. That's a 4-line change to the planner's system prompt.
3. **Web search in the Researcher.** Kestra has `io.kestra.plugin.ai.tool.TavilyWebSearch` built in. Plugging it in would let the Researcher pull *current* dependency versions instead of relying on training-data cutoffs. One YAML change, one new API key.
4. **Replace the LLM-driven cascade with a hybrid model.** Right now the Planner LLM has to drive 4 steps in sequence — when it rate-limits halfway, things get weird. A cleaner design: the LLM picks the *first* step and *strategy*, and a deterministic Subflow chain fans out from there. That keeps the "LLM in the loop" claim real but makes the cascade rock-solid.

If any of that is interesting, the code is open. Drop a brief into an issue and I'll point the Planner at it.

---

## Credits

Built for the [WeMakeDevs × Kestra Orchestration Challenge](https://kestra.io). Thanks to the [Kestra](https://kestra.io) team for an orchestrator that ships an `AIAgent` task with a `KestraFlow` tool out of the box — the whole "LLM dispatching subflows" thing is barely 10 lines of YAML because of that. And to [WeMakeDevs](https://wemakedevs.org) for putting up the challenge. The hashtag for the contest is `#KestraAcademy`.

The repo: [Pavankumar07s/kestra-copilot](https://github.com/Pavankumar07s/kestra-copilot)
The generated demo project: [Pavankumar07s/realtime-whiteboard](https://github.com/Pavankumar07s/realtime-whiteboard)
The 30s clip: coming this week.

If you build something with this, tag me — would love to see what cascade falls out of *your* brief.
