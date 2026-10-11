# Agent instructions

This repo runs a video business: make videos good enough to win attention, and turn that attention into revenue. Everything here serves one of those two things.

## Read first

- `docs/STRATEGY.md`: what we make, for whom, and how it pays. Open decisions are listed at the top.
- `docs/PIPELINE.md`: the stages every video goes through and what "done" means at each.
- `docs/QUALITY_BAR.md`: the bar a video must clear before it is published.

## Layout

```
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

## When a doc and reality disagree

Fix the doc in the same change. A stale strategy or checklist is worse than none.
