# Pipeline

Every video moves through the same stages. A stage is done only when its exit condition is met. Diagram: [diagrams/video-pipeline.md](diagrams/video-pipeline.md).

| # | Stage | Output | Done when |
|---|---|---|---|
| 1 | Idea | Row in `IDEAS.md` | Scored, and in the top of the backlog |
| 2 | Brief | `videos/<slug>/brief.md` | Title, thumbnail concept, hook, and money plan are written and you would click it yourself |
| 3 | Script | `videos/<slug>/script.md` | Read aloud once start to finish; every claim has a source in the brief |
| 4 | Record / gather | `assets/` | All footage, voice, and b-roll listed in the script exist, with licenses noted |
| 5 | Edit | `renders/` | Passes every line of `QUALITY_BAR.md` |
| 6 | Publish | `videos/<slug>/publish.md` | Checklist complete, links and disclosures in place |
| 7 | Review | Row in `METRICS.md` | Numbers logged at 48 hours, 7 days, and 28 days, with one lesson written down |

## Rules

- **Kill early.** If the brief does not produce a title you would click, drop the idea at stage 2. That is the cheap place to fail.
- **No skipping stage 7.** A video that is published and never reviewed teaches nothing.
- **One video in edit at a time.** Finish it before starting the next edit.
- **Shorts come from stage 5.** Cut them from the finished long video; do not script them separately unless one is the planned format.

## Folder per video

```
videos/2026-10-12-my-video-title/
  brief.md      from templates/video-brief.md
  script.md     from templates/script.md
  publish.md    from templates/publish-checklist.md
  assets/       raw footage, audio, images (not committed)
  renders/      exports (not committed)
```

## Status

Track status in the `Status` field at the top of each `brief.md`: `idea`, `brief`, `script`, `recording`, `editing`, `published`, `reviewed`, or `killed`.

```bash
rg -N "^Status:" videos/*/brief.md
```
