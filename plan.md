# Plan — Phase-wise Implementation

> Claude Code: work top to bottom. Don't skip phases. Each phase ends with a binary acceptance check — if it doesn't pass, fix before moving on. Mark tasks `[x]` as you complete them; commit after each phase.

---

## Phase 0 — Bootstrap (target: 2 hours)

**Goal:** Local Kestra is running. Hello-world flow executes. KV secrets are seeded.

- [ ] Verify Docker + docker-compose installed (`docker --version && docker-compose --version`).
- [ ] Install Kestra agent skills `kestra-flow` and `kestra-ops` per https://kestra.io/docs/ai-tools/agent-skills.
- [ ] Install `kestractl` and verify it can hit `http://localhost:8080` once Kestra is up.
- [ ] Copy `.env.example` to `.env`. Prompt the user to fill in: `GEMINI_API_KEY`, `RAPID_API_KEY`, `OBSIDIAN_VAULT_PATH`. Don't proceed until at least these three are set.
- [ ] Run `docker-compose up -d`. Wait for `localhost:8080` to respond (poll every 5s for up to 90s).
- [ ] In Kestra UI, manually create a hello-world flow with a single Log task. Run it. Confirm green check.
- [ ] Write `flows/00_setup.yml` — a one-off flow that uses `io.kestra.plugin.core.kv.Set` tasks to write each env var into the KV store under namespace `hackathon.copilot`. Use the `kestra-flow` skill to validate before saving.
- [ ] Trigger `00_setup` once. Confirm in Kestra UI's KV namespace view that all keys are present.

**Acceptance:** `kestractl flows list` shows `hackathon.copilot.setup` and the KV namespace shows all 5+ keys.

---

## Phase 1 — Planner + Coder end-to-end (target: 1 day)

**Goal:** A single-loop run works. Goal in → Planner agent decomposes → Coder subflow generates code → Coder runs it via Judge0 → result logged to Obsidian + a markdown note appears in the vault.

- [ ] Write `scripts/obsidian_sync.py` (full impl). Test it locally on the host: `python obsidian_sync.py --agent test --execution-id abc --status completed --input "hi" --output "world"` should write a note to `$OBSIDIAN_VAULT_PATH/kestra-copilot/executions/`.
- [ ] Verify the script also runs from inside the Kestra container: `docker-compose exec kestra python /app/scripts/obsidian_sync.py --help`.
- [ ] Write `flows/03_coder.yml`:
  - Input: `task_description: STRING`
  - One AIAgent task with provider=GoogleGemini, modelName=gemini-2.5-flash, `CodeExecution` tool attached.
  - System message: terse, focused on "write code, run it, return result + code".
  - Final task: Python script call to `obsidian_sync.py` with `--agent coder`, current execution ID, parent (received from Planner), tools used, status.
- [ ] Write `flows/01_planner.yml`:
  - Input: `goal: STRING`, `goal_id: STRING` (default `{{ execution.id }}`)
  - One AIAgent task with `KestraFlow` tool pointing at `hackathon.copilot.coder`.
  - System message: "Decompose goal, call the coder once, then stop."
  - Final task: `obsidian_sync.py` with `--agent planner`, children list (extracted from `outputs.agent.toolExecutions`).
- [ ] Test: `kestractl executions run hackathon.copilot planner --inputs goal="Write a Python function that reverses a string and verify with two test cases"`.
- [ ] Verify in Kestra UI: planner execution shows nested coder subflow execution.
- [ ] Verify in Obsidian: 2 markdown notes exist; opening the planner note shows a `[[wikilink]]` to the coder note; graph view shows them connected.

**Acceptance:** Open Obsidian graph, filter to `kestra-copilot/`, see exactly 3 nodes (1 goal + 2 executions) connected in a tree.

---

## Phase 2 — Add Researcher, Reviewer, Communicator (target: 1.5 days)

**Goal:** Full 4-specialist team. Planner picks among them dynamically based on the brief.

- [ ] Write `flows/02_researcher.yml`:
  - AIAgent with `io.kestra.plugin.ai.tool.WebSearch` tool (use Tavily or whatever Kestra's WebSearch uses by default — check `kestra-flow` skill for the exact properties).
  - System message: "Pick a tech stack and key libraries for the brief. Return a one-paragraph rationale + a list of 3-7 dependencies."
  - Final task: `obsidian_sync.py`.
- [ ] Write `flows/04_reviewer.yml`:
  - Two-step deterministic flow (no AIAgent needed; we want predictable behavior here):
    1. `io.kestra.plugin.scripts.python.Script` that takes the generated code as input, writes it to a temp dir, runs whatever test framework matches the language, captures stdout/stderr.
    2. `obsidian_sync.py` with status reflecting pass/fail.
  - For v1, support Python (`pytest`) and Node (`npm test`). Skip others.
- [ ] Write `flows/05_communicator.yml`:
  - Deterministic flow (no AIAgent):
    1. Use `io.kestra.plugin.core.http.Request` (or the GitHub plugin if available — check schema) to create a new repo in `$GITHUB_USERNAME` named after the brief slug.
    2. Push files using GitHub Contents API: README.md (auto-generated from brief + tech stack), source files (from Coder output), test files (from Reviewer).
    3. Post to Slack via `io.kestra.plugin.notifications.slack.SlackIncomingWebhook` with the repo URL.
    4. `obsidian_sync.py` with status `completed`.
- [ ] Update `flows/01_planner.yml`:
  - Register all 4 KestraFlow tools.
  - Update system message: "You drive 4 specialist tools: call_researcher (call FIRST), call_coder, call_reviewer, call_communicator (call LAST). Loop coder+reviewer up to 3 times until tests pass. Be terse with tool inputs — one paragraph max."
- [ ] Test with brief: `"Build a real-time chat app using WebSockets in Node"`.
- [ ] Watch the cascade in Kestra UI. Watch the graph in Obsidian. Verify Slack receives a message and a real repo exists.

**Acceptance:** End-to-end run completes in <90s, produces ≥4 subflow executions (one of each type, plus possibly extra Coder/Reviewer cycles), and produces a clickable GitHub repo.

---

## Phase 3 — Obsidian graph polish + auto-commit (target: 0.5 day)

**Goal:** The Obsidian graph view is *demo-pretty*. Backlinks are dense and clean. Auto-commit works reliably.

- [ ] Audit `obsidian_sync.py`. Every note must link to:
  - The goal note (one per run, written by Planner before fan-out)
  - Its parent execution
  - Its children (when known from `toolExecutions` output)
  - Each tool used (one stub note per tool *type*, idempotent)
- [ ] Add a "final report" note written by Communicator. It links to the goal, every execution, and includes the GitHub repo URL.
- [ ] Configure git auto-commit. If the user's vault is git-tracked (`git -C $OBSIDIAN_VAULT_PATH rev-parse --git-dir` succeeds), every `obsidian_sync.py` call appends a commit.
- [ ] If `$GRAPHIFY_REMOTE` is set, push to that remote in addition to the default. (Treat "Graphify" as either a separate git remote the user has configured for graph visualization, or as Obsidian's built-in graph view — the script supports both.)
- [ ] Run a clean demo: `rm -rf $OBSIDIAN_VAULT_PATH/kestra-copilot/`, trigger one fresh goal, verify the graph view renders cleanly with no orphan nodes.
- [ ] Tune: in Obsidian's graph view settings, set "depth: 3", "tags: hide", and apply a color group on `path:kestra-copilot/executions` (warm) vs `path:kestra-copilot/tools` (cool). Save the view.

**Acceptance:** Open Obsidian graph view filtered to `path:kestra-copilot` after one goal run. Shape is unmistakably a tree: 1 goal → 1 planner → 4 specialists → tool nodes underneath. Looks clean enough for a screen recording.

---

## Phase 4 — Demo polish + recording (target: 1 day)

**Goal:** A 30-second video clip ready to post.

- [ ] Pick the *one* hackathon brief that produces the prettiest cascade. Test 5 different briefs. Tune the Planner's system prompt until the run takes 25-45s and produces ≥5 subflow executions.
- [ ] Pre-warm: run the chosen brief once, throw away the output, then delete its notes. (This warms LLM API caches and Docker volumes for a snappier recording.)
- [ ] Set up the 3-pane recording layout:
  - Left half: Kestra UI on `/executions`, filtered to today, sorted ascending. Auto-refresh on.
  - Top right: Obsidian graph view, filtered to `path:kestra-copilot`, depth 3.
  - Bottom right: Slack channel where the announcement will land.
- [ ] Practice the run 3 times back-to-back to lock the timing.
- [ ] Record (OBS, Loom, or native screen recorder). Edit to exactly 30 seconds. Add captions (no voiceover — silence with text on screen reads better on social).
- [ ] Write the social caption:
  - LinkedIn: 2-3 paragraphs, lead with the meta-angle, link to repo, tag `@kestra` and `@WeMakeDevs`, hashtag `#KestraAcademy`.
  - X: punchy 1-2 sentences, attach the clip, same tags.
- [ ] Post both. Drop the URLs into a `POSTED.md` file as the final commit.

**Acceptance:** Two posts live. Clip is 30s. GitHub repo of this project is public and linked from both posts.

---

## Out-of-band tasks (do these in parallel when blocked on the main path)

- Document any non-obvious config in `README.md` as you discover it.
- If a phase reveals a Kestra quirk, append a one-line entry under "Gotchas" in `CLAUDE.md`.
- Cache LLM responses during dev if Gemini quota becomes an issue (`scripts/llm_cache.py` middleware — only build this if needed).
- Set up a separate "demo" git branch for the version that has hardcoded brief defaults; main branch stays generic.

## Failure modes (read before debugging)

- **AIAgent doesn't call its tool** → system message is too soft. Make it explicit and use uppercase: *"You MUST call call_coder for any code task."*
- **Subflows don't show as nested in UI tree** → ensure `KestraFlow` tool is used inside the AIAgent, not a deterministic `Subflow` task. The whole point of nesting is that the LLM dispatched it.
- **Obsidian graph looks like a hairball** → too many tool notes. Group by tool *type* (one node per tool kind), not per call.
- **Demo run takes 90+ seconds** → switch Planner from `gemini-2.5-flash` to `gemini-2.5-flash-lite`. Check `kestra-flow` skill for the latest model name.
- **Judge0 quota exhausted** → during demo prep, stub the Coder's CodeExecution by setting an input flag `dry_run: true` that returns a canned response.
- **Obsidian sync writes happen but graph doesn't render** → confirm the wiki-link target notes actually exist as files. Obsidian only renders edges where both nodes are real `.md` files in the vault.
- **Auto-commit fails silently** → check the vault directory's git status from inside the container: `docker-compose exec kestra git -C /obsidian status`.

## QUESTIONS.md

If you (Claude Code) hit a decision point that needs the user, write to `QUESTIONS.md` and continue with a parallel task. The user will check this file regularly. Format:

```
## YYYY-MM-DD HH:MM — <topic>
Question: ...
Context: ...
What I tried: ...
What I'd do absent guidance: ...
```
