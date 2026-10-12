# Agent instructions

This repo runs a video business: make videos good enough to win attention, and turn that attention into revenue. Everything here serves one of those two things.

## Read first

- `docs/HANDOFF.md`: where things stand and the next step. Update it when either changes.
- `docs/STRATEGY.md`: what we make, for whom, and how it pays. Open decisions are listed at the top.
- `docs/PIPELINE.md`: the stages every video goes through and what "done" means at each.
- `docs/QUALITY_BAR.md`: the bar a video must clear before it is published.

## Layout

```
README.md           where each doc is and how to start a video, for people
AGENTS.md           these rules; CLAUDE.md only imports this file
setup.sh            run once per clone; installs the pre-commit check
.harness/           the checker, its config, and the failure and review logs
.claude/            shared settings: hooks, deny rules for secret files, verify.sh
docs/               strategy, pipeline, quality bar, monetization, metrics, idea backlog
docs/diagrams/      Mermaid diagrams
templates/          copy these into a video folder; never edit a video in place here
videos/<date>-<slug>/   one folder per video: brief.md, script.md, publish.md
```

`videos/<date>-<slug>/assets/` and `renders/` hold media and are never committed.

## Rules

- A new video starts by copying `templates/video-brief.md` to `videos/YYYY-MM-DD-slug/brief.md`. No script before the brief has a title and thumbnail concept.
- Every factual claim in a script needs a source listed in that video's brief. If you cannot source it, cut it or mark it `[UNVERIFIED]`. Never invent statistics, quotes, or results.
- Never upload, publish, schedule, post, or message anyone on any platform unless asked in that session.
- Never commit media (video, audio, images, project files) or anything from `.env` / `.envrc`.
- Only use footage, music, and images we own or have a license for. Record the license in the brief.
- Numbers in `docs/METRICS.md` and `docs/MONETIZATION.md` come from the platform dashboards. Do not estimate and write it down as fact.
- Platform rules (monetization thresholds, disclosure requirements) change. Check the official page before relying on a number written in this repo.
- Search with `rg` before adding a doc; update the existing one instead of creating a near-duplicate.
- Commit on a branch. Do not push, merge to main, or open PRs unless asked.

## Setup

Markdown only: nothing to build or install. The checker needs `python3`, searching needs `rg`. Secrets, when there are any, go in `.envrc` or `.env`; both are git-ignored and denied to agents.

The pre-commit hook is not cloned with the repo. Add it once per clone:

```bash
./setup.sh
```

## Verification

Run this before saying a task is done. A failure prints the file, the problem and the fix.

```bash
python3 .harness/harness.py check --full   # links in every doc, plus any commands in .harness/harness.json
python3 .harness/harness.py audit          # score of the whole harness, by subsystem
```

The same check runs from hooks after every edit, before the agent stops, and before each commit. It does not check whether a claim is true or a video is good; `docs/QUALITY_BAR.md` and the sources table in each brief do that. Known debt is listed in `.harness/baseline.json`; add to it only when the user agrees. Log agent mistakes in `.harness/failures.md` and reviews in `.harness/reviews.md`.

## When a doc and reality disagree

Fix the doc in the same change. A stale strategy or checklist is worse than none.
