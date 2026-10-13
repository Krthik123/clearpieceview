# Handoff note

Written 11 Oct 2026 when work moved from the desktop to the laptop. Delete or rewrite this note once it is out of date.

## Where things stand

- **Goal:** earn money with AI, selling to businesses in other countries from India.
- **Research done:** 37 videos from the `clearpieceview` YouTube playlist were read and sorted into eight income paths. The result is `AI_INCOME_PATHS.md`.
- **Path, decided 13 Oct 2026:** path 1 only: AI ad creative (image and video ads) for consumer brands, found through cold outreach. No client has been contacted yet.
- **Markets, decided 13 Oct 2026:** Kuwait, the UK, Switzerland, Ireland and the US, chosen by how strong each currency is against the rupee. The rates, and why a strong currency does not mean a bigger sale, are in `ROADMAP.md`, Part 2.
- **Decision still open:** no product category has been picked.

## Next step

The goal, set 12 Oct 2026, is at least $1,000 received every month, with nothing spent before money is earned. The plan is `PLAN.md`; its path is accepted, its timetable and numbers are still proposed.

`ROADMAP.md`, written 13 Oct 2026 and also proposed, maps the whole business in 26 dots and lists 13 the plan leaves out. The path and the markets are decided. Next is dot 2: pick one product category with its six questions, counting brands in each of the five countries. Then go to dot 4: read each free tool's terms, and make 1 image ad and 1 video ad with free tools only.

## What is in this repo

| File | What it holds |
|---|---|
| `ROADMAP.md` | The whole business in four parts, the dots missing between them, and the order to do everything in |
| `PLAN.md` | The goal, the no-spend rule, the 90-day plan and the 12-month plan |
| `AI_INCOME_PATHS.md` | The eight paths, the evidence per video and the recommendation |
| `VIDEO_BUSINESS_MODELS.md` | Earlier research on how people and agencies earn from video |
| `STRATEGY.md` | Business model row is set to path 1; the rows below it still assume an audience-first channel |

## What is not in this repo

These live only on the desktop. The laptop will not have them unless they are copied over.

- **Transcripts:** 37 notes with full timestamped transcripts, in the Obsidian vault at `Clippings/YouTube/clearpieceview/` (seven folders and an `Index` note). They are not committed in the vault repo. Video 01 has no transcript because YouTube has no captions for it.
- **Working files:** the script that built the notes and the raw transcript data were in a temporary folder and will be gone.
- **Claude's memory:** the saved founder profile and the transcript method are stored per machine. The points that matter are repeated below.

## Things a new session should know

- **Web Clipper:** Claude cannot trigger the Obsidian Web Clipper from Chrome. To get a transcript, open the video in Chrome, open its transcript panel and read the text from the page.
- **Terminal fetches fail:** YouTube blocks transcript downloads from the terminal after about 20 videos.
- **Read depth:** only 13 of the 37 videos were read in full. `AI_INCOME_PATHS.md` lists the depth for each one.
- **Figures are claims:** every price and result is what the video maker says. Most of these channels earn from tool affiliate links or their own course.
- **Two practices not to copy:** ads with an invented customer praising a product, and a cold message that opens with a made-up line about having ordered from the store.

## Git state

- `main` was created on 13 Oct 2026 from `docs/ai-income-paths`; both are on GitHub at the same commit.
- GitHub's default branch is still `docs/ai-income-paths`, because it was the first branch pushed.
- No pull request is open.

## Agent harness

Added 12 Oct 2026. The checker is in `.harness/`; hooks and deny rules for secret files are in `.claude/settings.json`. It checks links in every doc after each edit, before the agent stops and before each commit. Run `./setup.sh` once on each machine to get the pre-commit check. Commands are in `AGENTS.md` under Verification.

Still open, all for the founder: set a permission mode, pin the Python version or not, and have someone other than the writer review a piece of work and log it in `.harness/reviews.md`.
