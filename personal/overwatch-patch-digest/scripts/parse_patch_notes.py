#!/usr/bin/env python3
"""Parse Overwatch patch-note markdown into structured JSON.

Input : markdown text via a file-path argument, or stdin if no path is given.
Output: JSON to stdout -> a list of patches, newest first, shaped like:
    {
      "date": "2026-03-10",
      "title": "Overwatch Retail Patch Notes - March 10, 2026",
      "hero_changes": {"D.Va": "Boosters\n- Cooldown increased ..."},
      "general_changes": {"Bug Fixes": "General\n- Fixed an issue ..."}
    }

The parser targets official Blizzard patch-note pages after markdown extraction.
It is deliberately tolerant of heading variations such as Tank/Tanks, HERO UPDATES,
Hero Balance Changes, and en-dash date titles.
"""
import json
import re
import sys
from datetime import date

MONTHS = {
    month: i
    for i, month in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ],
        start=1,
    )
}

BULLET = re.compile(r"^\s*[\*\+\-]\s+(.*)$")
HEADER = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
MARKDOWN_IMAGE = re.compile(r"^\s*!\[.*?\]\(.*?\)\s*$")
DATE_RX = re.compile(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})")

ROLE_HEADINGS = {
    "tank",
    "tanks",
    "tank heroes",
    "damage",
    "damage heroes",
    "dps",
    "support",
    "supports",
    "support heroes",
}

HERO_CONTAINER_PHRASES = (
    "hero updates",
    "hero update",
    "hero balance updates",
    "hero balance update",
    "hero balance changes",
    "hero balance change",
    "heroes",
)


def parse_date(text):
    match = DATE_RX.search(text or "")
    if not match:
        return None
    month = MONTHS.get(match.group(1).strip().lower())
    if not month:
        return None
    try:
        return date(int(match.group(3)), month, int(match.group(2))).isoformat()
    except ValueError:
        return None


def header(line):
    match = HEADER.match(line)
    return (len(match.group(1)), match.group(2).strip()) if match else (None, None)


def clean_markdown(text):
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text or "")
    text = re.sub(r"[*_`]+", "", text)
    return text.strip()


def heading_key(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", clean_markdown(text).lower())).strip()


def is_patch_header(level, text):
    return level is not None and level <= 3 and "patch notes" in heading_key(text)


def is_role_section(text):
    return heading_key(text) in ROLE_HEADINGS


def is_hero_container(text):
    key = heading_key(text)
    return key in HERO_CONTAINER_PHRASES or any(phrase in key for phrase in HERO_CONTAINER_PHRASES)


def skip_plain_line(line):
    stripped = line.strip()
    if not stripped:
        return True
    if MARKDOWN_IMAGE.match(stripped):
        return True
    if re.match(r"^image\b\s*:?", stripped, flags=re.IGNORECASE):
        return True
    if stripped.lower() == "top of post":
        return True
    return False


def is_probable_label(text):
    """Keep short ability/subsection labels; drop long dev-commentary prose."""
    text = clean_markdown(text)
    words = text.split()
    if not text:
        return False
    if len(text) > 96 or len(words) > 14:
        return False
    if text.endswith(".") and len(words) > 6:
        return False
    return True


def append_block(bucket, key, block):
    if not block.strip():
        return
    bucket[key] = (bucket[key] + "\n\n" + block) if key in bucket else block


def parse(markdown):
    patches = []
    current = None
    section = None
    hero = None
    pending_label_lines = []
    bullet_lines = []

    def current_target():
        if current is None:
            return None, None
        if hero and (is_role_section(section) or is_hero_container(section)):
            return current["hero_changes"], hero
        return current["general_changes"], section or "General"

    def flush():
        nonlocal pending_label_lines, bullet_lines
        if bullet_lines and current is not None:
            label = "\n".join(pending_label_lines).strip()
            block = ((label + "\n") if label else "") + "\n".join(f"- {line}" for line in bullet_lines)
            bucket, key = current_target()
            append_block(bucket, key, block)
        pending_label_lines = []
        bullet_lines = []

    for raw in markdown.splitlines():
        level, text = header(raw)

        if is_patch_header(level, text):
            flush()
            current = {
                "date": parse_date(text),
                "title": clean_markdown(text),
                "hero_changes": {},
                "general_changes": {},
            }
            patches.append(current)
            section = None
            hero = None
            pending_label_lines = []
            continue

        if current is None:
            continue

        if level == 4:
            flush()
            section = clean_markdown(text)
            hero = None
            continue

        if level == 5:
            flush()
            cleaned = clean_markdown(text)
            if is_role_section(section) or is_hero_container(section):
                hero = cleaned
                pending_label_lines = []
            else:
                hero = None
                pending_label_lines = [cleaned]
            continue

        if level is not None:
            flush()
            pending_label_lines = []
            continue

        if skip_plain_line(raw):
            continue

        bullet_match = BULLET.match(raw)
        if bullet_match:
            bullet_lines.append(bullet_match.group(1).strip())
            continue

        # A plain line after bullets starts a new labeled block.
        if bullet_lines:
            flush()

        plain = clean_markdown(raw)
        if is_probable_label(plain):
            pending_label_lines.append(plain)
            # Ability labels are usually one or two lines; three keeps cases like
            # General -> Heroes -> HeroName in bug-fix sections without absorbing prose.
            pending_label_lines = pending_label_lines[-3:]
        else:
            pending_label_lines = []

    flush()
    parsed = [p for p in patches if p["hero_changes"] or p["general_changes"]]
    parsed.sort(key=lambda p: p["date"] or "", reverse=True)
    return parsed


def main():
    markdown = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else sys.stdin.read()
    json.dump(parse(markdown), sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
