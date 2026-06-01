---
name: overwatch-patch-digest
description: Run a conversational Overwatch patch catch-up. Before fetching or summarizing, confirm the player's current mains, frequent bans/watch targets, and last-played date, then flatten official patch notes since that date into a personalized rendered page or markdown digest. Use when a user asks what's new or changed in Overwatch, wants patch notes summarized for their heroes, wants to catch up after a break, or mentions Overwatch balance changes, buffs, nerfs, hotfixes, or patch notes.
---
# Overwatch Patch Digest

Turn official Overwatch patch notes into a personalized "what changed since I last
played?" catch-up. The skill is conversational first: it must confirm the current
profile before fetching, parsing, or rendering.

Scripts live in `scripts/` and use Python 3 stdlib only. Run them from the skill
directory unless your tool environment gives you an absolute path.

## Non-negotiable intake gate

Do **not** infer the player's profile from memory, prior chats, public rank data,
or old `profile.json` without confirmation.

Before fetching patch notes, ask for or confirm exactly these three things:

1. **Current mains** — the heroes they care about most right now.
2. **Frequent bans / watch targets** — heroes they ban, hate playing into,
   counter-pick around, or want tracked. If they have none, record that explicitly.
3. **Last played** — the date or rough window to start the catch-up from.

Also ask or set a **max patch batch size**. Default to `8` if the user has no
preference. This prevents a long absence from turning into an unbounded fetch or
overloaded digest.

If the user already gave all of this in the same message, restate it briefly and
ask for confirmation before running. If a previous `profile.json` exists, show it
and ask whether it is still current. Do not silently use it.

Suggested first message:

> Before I run the digest, confirm three things: who are your current mains, who
> are your frequent bans/watch targets, and when did you last play? I can use a
> max batch of 8 patches unless you want a different cap.

## Workflow

1. **Conversational intake — required.**
   - Gather/confirm current mains, frequent bans or watch targets, last played,
     and max patch batch size.
   - Resolve vague timing, such as "a couple months ago," to a best-estimate ISO
     date and say the assumption back to the user.
   - If there are no frequent bans/watch targets, use `--bans none` so the profile
     records an explicit answer instead of an omission.

2. **Create or update `profile.json`.**
   ```bash
   python3 scripts/profile.py init \
     --heroes "D.Va, Kiriko" \
     --bans "Sombra, Widowmaker" \
     --last-played 2026-02-20 \
     --max-patches 8 \
     --notes "Support/tank player returning after a break" \
     --path profile.json
   ```

   If updating an existing confirmed profile:
   ```bash
   python3 scripts/profile.py set --heroes "Reinhardt, Wrecking Ball" --path profile.json
   ```

3. **Fetch official patch notes in bounded batches.**
   - Use the official Blizzard patch notes as the source of truth.
   - Fetch every monthly archive from the month containing `last_played` through
     the current month, but only process up to `max_patches` parsed patches in a
     single digest batch.
   - For catch-up order, process oldest-first using `--asc`; this makes the first
     batch start from the last-played date and move toward the present.
   - Save each fetched page to a `.md` file.
   - See `REFERENCE.md` for URL patterns and fallbacks.

4. **Parse.** Concatenate fetched markdown and pipe it through the parser:
   ```bash
   cat notes/*.md | python3 scripts/parse_patch_notes.py > patches.json
   ```

5. **Filter and flatten to the player.**
   ```bash
   python3 scripts/filter_patches.py patches.json profile.json --asc > digest.md
   ```
   The digest first gives a flattened batch summary grouped by:
   - the player's current mains,
   - frequent bans/watch targets,
   - system/general changes.

   Patch-by-patch detail remains below for traceability. Override the batch cap
   for one run with:
   ```bash
   python3 scripts/filter_patches.py patches.json profile.json --asc --max-patches 4 > digest.md
   ```

6. **Render a page when the user wants a visual output.**
   ```bash
   python3 scripts/render_page.py patches.json profile.json --asc --out digest.html
   ```
   The HTML page is self-contained: embedded CSS, no external assets, no
   JavaScript dependency, and no network calls. It includes a flattened summary
   first and patch detail below.

7. **Present.** Deliver `digest.md`, `digest.html`, or both depending on the
   user's request. Lead with the flattened summary. Avoid tier-list claims unless
   the user explicitly asks for interpretation. Offer to return the updated
   `profile.json` so the player can reuse it later.

## Grounding rules

- Prefer official Blizzard pages. If an unofficial mirror is used because official
  fetch failed, say so and treat it as a fallback.
- Report patch facts only by default. Do not claim a hero is "meta," "dead," or
  "good now" unless the user asks for analysis.
- Do not hardcode a live roster. Hero matching normalizes player-provided names
  against hero headers found in the fetched notes. A small set of stable
  shorthands lives in `profile.py`.
- If parsing looks sparse, compare `patches.json` against the source markdown
  before summarizing. The official site changes heading shapes occasionally;
  `REFERENCE.md` lists supported patterns and fallback options.
- If the profile is missing current mains, frequent bans/watch targets, or
  last-played date, stop and ask. Do not run a digest with inferred values.
