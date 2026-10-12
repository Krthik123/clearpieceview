# clearpieceview

Make the best videos in our niche and make money from them.

## Start here

| I want to... | Go to |
|---|---|
| See the plan to $1,000 a month | [docs/PLAN.md](docs/PLAN.md) |
| Know what we make and how it pays | [docs/STRATEGY.md](docs/STRATEGY.md) |
| Pick the next video | [docs/IDEAS.md](docs/IDEAS.md) |
| Make a video | [docs/PIPELINE.md](docs/PIPELINE.md) |
| Check a video is good enough to ship | [docs/QUALITY_BAR.md](docs/QUALITY_BAR.md) |
| See what earns money | [docs/MONETIZATION.md](docs/MONETIZATION.md) |
| See what is working | [docs/METRICS.md](docs/METRICS.md) |
| See the whole flow as a picture | [docs/diagrams/video-pipeline.md](docs/diagrams/video-pipeline.md) |

## Make a video

```bash
slug=2026-10-12-my-video-title
mkdir -p videos/$slug
cp templates/video-brief.md       videos/$slug/brief.md
cp templates/script.md            videos/$slug/script.md
cp templates/publish-checklist.md videos/$slug/publish.md
```

Fill in `brief.md` first. The title and thumbnail concept come before the script.

## Layout

```
docs/        strategy, pipeline, quality bar, monetization, metrics, ideas
templates/   brief, script, publish checklist
videos/      one folder per video (media inside is not committed)
```

Agent rules live in [AGENTS.md](AGENTS.md).
