---
name: fun-qa
description: Build code in a quest loop so that human review is explicit, chunked, and tracked instead of rubber-stamped. Use this skill when the user explicitly asks for fun-qa, quest-based QA, or wants their review of a coding task to be tracked. Trigger on phrases like "use fun-qa", "build this as quests", "I want to review this in chunks", or "track my QA on this". This skill restructures how a coding task is built and paced; it is not a general coding mode and should only be used when explicitly requested.
---

# fun-qa

## The problem this solves

Coding agents are fast, and that speed quietly breaks human review. The agent produces a large diff all at once, the human skims it, says "looks good," and bugs slip through — not because the human is lazy, but because a 600-line diff with no structure is genuinely hard to review. The review was never really *done*; it was rubber-stamped.

fun-qa fixes the pacing. Instead of building everything and handing over one undifferentiated pile, the agent breaks the work into small, independently reviewable units called **quests**, builds them a piece at a time, and stops at each natural boundary to hand that piece to the human with a precise "here's what to check." A lightweight log tracks which quests have been reviewed and cleared.

The result is review that actually happens, on pieces small enough to review well, with a record of what was checked.

## The one principle that matters most

**Every mechanic must make review better. If it doesn't, cut it.**

The "quest" framing is useful because it does real work: it forces the task into review-sized chunks, gives the human a clear queue and a sense of progress, and creates natural stop points where review fits. That is the entire justification for it.

What this framing must *not* become is decoration. XP, levels, badges, points, story lore, flavor text — none of that makes a diff easier to review or a bug easier to catch. Adding it makes QA *longer and more annoying*, which is the opposite of fun. So: no scorekeeping, no leveling, no narrative. The fun comes from clarity and momentum, not ornamentation. When in doubt, ask "does this help the human review, or is it just theming?" and drop the theming.

## The quest loop

When invoked, work like this:

### 1. Plan the quests

Decompose the task into quests before writing code. A good quest is:

- **Independently reviewable** — the human can look at it and judge it on its own, without holding five other unfinished things in their head.
- **Small** — roughly a sitting's worth of review. If a quest's diff would be hundreds of lines or touch many unrelated concerns, split it.
- **Verifiable** — it comes with a concrete way to check it's right (a command to run, a behavior to click through, a specific output to eyeball). "Looks fine" is not verification.

Order quests so that foundational pieces come before the things that depend on them. A quest that something else builds on should be cleared before you build the dependent quest, so a flaw doesn't propagate into work the human then has to re-review.

Write the plan into `QUESTS.md` (see the template in `assets/QUESTS_template.md`) and show it to the human before building. This is the cheapest possible moment to catch a bad decomposition.

### 2. Build one quest

Build a single quest (or a small, tightly related batch if they're trivial). Then **stop.** Do not roll forward into the next quest before the current one is reviewed, unless the human has told you to batch them.

### 3. Hand it over for review

This handoff is where review either happens or doesn't, so make it easy. Give the human:

- **What changed** — the files and the gist, in a sentence or two, not a re-paste of the diff.
- **What to check** — the concrete verification from the plan. Point them at the exact thing: "run `npm test -- auth`", "click Save and confirm the toast appears", "check that line 40 handles the empty-array case."
- **Anything you're unsure about** — if you made a judgment call or took a shortcut, flag it. Hiding the soft spots defeats the point.

Then update the quest's status to awaiting review in `QUESTS.md`.

### 4. Record the outcome

The human clears the quest or sends it back.

- **Cleared** → mark it cleared in `QUESTS.md` and move to the next available quest.
- **Sent back** → note what was wrong, fix it, and hand it back for re-review. Don't advance to dependent quests until it's cleared.

Keep `QUESTS.md` current as you go — it is the single source of truth for what's been reviewed. An out-of-date log is worse than none, because it makes review look done when it isn't.

## Status vocabulary

Use a small, legible set of statuses. The point is that the human can glance at `QUESTS.md` and instantly see what needs their attention.

- ⬜ **Available** — planned, not started.
- 🔨 **In progress** — being built right now.
- 👀 **Awaiting review** — built, handed off, needs the human.
- ✅ **Cleared** — reviewed and accepted.
- ↩️ **Sent back** — reviewed, needs changes (note why).

## Scaling to the task

Match the ceremony to the job. A two-file change doesn't need an elaborate board — a single quest with a clear "check this" is fine, and forcing more structure onto it is the gimmick trap again. A large feature with many moving parts is where the loop earns its keep. Read the situation and use the lightest version that still makes review real.
