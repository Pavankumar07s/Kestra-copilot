# Project Brief — Hackathon Co-Pilot

## One-line pitch

An autonomous multi-agent Kestra workflow that turns a natural-language hackathon brief into a scaffolded GitHub starter project, announced on Slack, with the entire agent collaboration graph rendering in real time inside Obsidian.

## The 30-second demo (the only thing that matters)

A screen recording showing three panels:

| Time | Left panel: Kestra UI | Center: Obsidian graph | Right: Slack/Discord |
|------|----------------------|------------------------|---------------------|
| 0–3s | (empty) | (empty) | User pastes brief: *"Build a real-time collaborative whiteboard with WebSockets and Postgres"* |
| 3–12s | Planner execution kicks off, fans out to Researcher, Coder, Reviewer, Communicator subflows. Tree visibly grows. | Goal node appears, then Planner, then four specialists branch off. Edges connect. | (idle) |
| 12–22s | More tool calls inside each specialist. Reviewer loops back to Coder once. | Tree continues blossoming. Tool nodes attach. | (idle) |
| 22–28s | Final Communicator execution turns green. | Final report node appears, links to everything. | "✓ Repo: github.com/.../whiteboard-starter — Tests passing — Stack: Express + ws + pg" |
| 28–30s | (cursor clicks the GitHub link) | | (real repo, real code, real README) |

That's the package. **Kestra cascade + Obsidian graph + real GitHub artifact.**

## Demo scenario chosen: Hackathon Co-Pilot

Of the four scenarios I floated (Hackathon Co-Pilot, GitHub Triage Bot, Slack-to-Ship, Market Research Analyst), I'm proceeding with **Hackathon Co-Pilot** because:

1. It's meta — a hackathon project that helps you start hackathon projects. Highly shareable.
2. The WeMakeDevs audience is hackathon-native; this lands hard.
3. The output (a real GitHub repo) is a tangible artifact viewers can click.

If you want a different scenario, change this section before any code is written. The flow YAML, the demo script, and even the Slack message template all key off this choice.

## Hard constraints

- **Time:** 7 days from May 9 to May 17 (challenge end). Day 7 is recording day.
- **Solo developer.**
- **Free-tier APIs** wherever possible. Gemini, GitHub, Slack are free. Judge0 via RapidAPI has a generous free tier; budget ~50 calls/day during dev, ~10 for demo.
- **Local-only.** Single laptop, `docker-compose up`. No cloud deploy.
- **No web frontend.** The Kestra UI plus Obsidian graph view are the entire UI surface.

## What "wow" looks like (and what is NOT wow)

**Wow:**
- The cascade in Kestra is *because the LLM decided it*. The Planner's AIAgent picks which subflow to spawn from the natural-language brief — not because we hardcoded a fan-out. Different brief → different cascade.
- The Obsidian graph is not pre-built. Every node and edge is written by the running flow. Re-run with a different brief and a different graph emerges.
- The GitHub repo at the end is real. It has a README, source files, a passing test. Reviewers can click and inspect.

**Not wow (don't bother):**
- Pretty progress bars.
- A custom React dashboard.
- Sound effects on the demo.
- 3D visualizations of the agent graph.
- Any tweet thread explaining how it works — let the artifact speak.

## What we explicitly do NOT build

- Custom web frontend
- Vercel auto-deploy
- Self-healing pipelines
- Multi-tenant auth
- Long-term memory beyond Obsidian markdown
- RAG over external docs
- A pretty landing page
- Test coverage of the Co-Pilot itself (it's a demo, not a product)

These will be cut even if there is time. Use any spare hours for demo polish, not feature growth.

## Success criteria (binary check, end of Day 7)

- [ ] `docker-compose up` brings the stack up clean from a fresh clone in <2 minutes.
- [ ] Triggering the Planner with a real brief produces ≥5 subflow executions visible in the Kestra UI tree.
- [ ] After one run, the Obsidian graph view (filtered to `kestra-copilot/`) shows ≥10 connected nodes in a clear tree shape.
- [ ] A GitHub repo is created in the user's account with at least 3 files (README, source, test) and at least one passing automated test.
- [ ] Slack channel receives the announcement message with the repo link.
- [ ] 30-second clip is recorded, edited to length, and posted with `#KestraAcademy`.

If any of those fail by Day 7, Day 7 becomes recovery day and the post slips to Day 8 (still inside the May 17 deadline).

## Definition of done for this submission

The user has posted a 30-second video on LinkedIn and X. The video shows the cascade, the graph, and the GitHub repo. The post tags `@kestra_io` and `#KestraAcademy` and links to this project's repo. That's the win condition. Everything else is in service of this.
