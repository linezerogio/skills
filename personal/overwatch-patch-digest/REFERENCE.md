# Reference

## Conversational intake contract

This skill starts with a profile confirmation, not a fetch.

Required fields:

1. `heroes` — current mains or heroes the user cares about most.
2. `bans` — frequent bans/watch targets/counters/annoying matchups. The user may
   answer "none," but the answer must be explicit.
3. `last_played` — ISO date used as the catch-up lower bound.
4. `max_patches` — maximum parsed patches to process in one batch. Default: `8`.

Do not fill these from assistant memory unless the user confirms them in the
current conversation. Previous profiles are candidates to confirm, not authority.

Good intake:

> Before I run this, confirm your current mains, frequent bans/watch targets, and
> when you last played. I can use a max batch of 8 patches unless you want a
> different cap.

Good confirmation when a profile exists:

> I found: mains D.Va/Kiriko, watching Sombra/Widowmaker, last played 2026-02-20,
> max batch 8. Still current?

Bad behavior:

- Inferring mains from previous unrelated conversations.
- Treating old profile data as current without asking.
- Running with no frequent-ban answer because that field was omitted.
- Fetching every patch since a very old date without a batch cap.

## Retrieval URLs (official)

Use the official Blizzard patch notes as the source of truth.

- **Latest live notes:** `https://overwatch.blizzard.com/en-us/news/patch-notes/live/`
- **Monthly archive:** `https://overwatch.blizzard.com/en-us/news/patch-notes/live/<YYYY>/<MM>/`
  - `<MM>` is the zero-padded month, e.g. `.../live/2026/03/` for March 2026.
  - One monthly archive can contain several patches, such as a major patch,
    balance hotfixes, and bug-fix hotfixes.

To cover a player who last played on `YYYY-MM-DD`, fetch every monthly archive
from that month through the current month. Also fetch the latest live page when
available. If the current-month archive says no patch notes were found, keep
going with the months that do contain notes.

When many patches are found, use `max_patches` to process a bounded batch. With
`--asc`, the first batch starts closest to `last_played`. After the user reviews a
batch, either increase the cap or advance `last_played` to the next unprocessed
patch date for another batch.

## Page structure the parser supports

Official pages are mostly server-rendered markdown-like text, but headings vary
across seasons. The parser supports these common patterns:

```md
### Overwatch Retail Patch Notes - March 10, 2026   # starts a patch
### Overwatch 2 Retail Patch Notes – May 14, 2024  # en dash also works

#### Tank | Tanks | Damage | Support               # role containers
##### D.Va                                          # hero inside a role
Boosters
* Cooldown increased from 3.5 to 4 seconds.

#### Hero Updates | Hero Balance Updates | Hero Balance Changes
##### Kiriko                                        # hero inside a hero-update container
Protection Suzu
* Cooldown reduced from 15 to 14 seconds.

#### Bug Fixes | General Updates | Stadium Updates    # general/system containers
General
* Fixed an issue affecting match UI.
Heroes
Junker Queen
* Fixed an issue with post-match stats.
```

The parser intentionally drops long developer-commentary paragraphs. It keeps
short labels immediately before bullet lists, including two-line labels such as
an ability name plus `Primary Fire`.

## Fallbacks

- **Official fetch is blocked or sparse:** retry with a search for the exact patch
  date, then open/fetch the official result again.
- **Still blocked:** use a reputable mirror only as a fallback, and say that the
  mirror was used because the official page could not be fetched. Prefer mirrors
  that link back to the official Blizzard page.
- **Pasted text:** pipe any markdown-ish text into the parser:
  ```bash
  cat raw.md | python3 scripts/parse_patch_notes.py > patches.json
  ```
  If necessary, lightly reformat pasted text into the `###/####/#####` + bullet
  shape above.
- **Unparseable date:** the patch is retained and marked `undated` in the digest.

## File schemas

**profile.json**
```json
{
  "heroes": ["D.Va", "Kiriko"],
  "bans": ["Sombra", "Widowmaker"],
  "last_played": "2026-02-20",
  "max_patches": 8,
  "notes": "free text"
}
```

Use `"bans": []` only when the user explicitly answers that they have no frequent
bans/watch targets. `profile.py init` requires `--bans` or `--bans none` to make
that explicit.

**patches.json**
```json
[
  {
    "date": "2026-03-10",
    "title": "Overwatch Retail Patch Notes - March 10, 2026",
    "hero_changes": {
      "D.Va": "Boosters\n- Cooldown increased from 3.5 to 4 seconds."
    },
    "general_changes": {
      "Bug Fixes": "General\n- Fixed an issue affecting match UI."
    }
  }
]
```

## Scripts

| Script | Purpose | Example |
|---|---|---|
| `profile.py` | init / show / set / normalize the confirmed profile | `python3 scripts/profile.py show --path profile.json` |
| `parse_patch_notes.py` | markdown -> structured `patches.json` | `cat notes.md \| python3 scripts/parse_patch_notes.py` |
| `filter_patches.py` | patches + profile -> flattened markdown digest | `python3 scripts/filter_patches.py patches.json profile.json --asc` |
| `render_page.py` | patches + profile -> self-contained HTML page | `python3 scripts/render_page.py patches.json profile.json --asc --out digest.html` |

`filter_patches.py` and `render_page.py` both respect `profile.max_patches` and
both support `--max-patches` to override it for one run. Use `--max-patches 0` to
remove the cap for a one-off run.

`render_page.py` does not convert markdown blindly; it renders structured patch
data into a flattened summary plus patch-detail cards. The generated HTML is
intended to be opened directly in a browser or attached as a static artifact.

`profile.py normalize --name "soldier"` echoes the match key used for hero
comparison. Use it to debug why a player-provided hero did or did not match a
patch-note header.
