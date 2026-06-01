#!/usr/bin/env python3
"""Manage the player profile used to personalize the patch digest.

The profile is created only after conversational confirmation. A valid first-run
profile includes the user's current mains, frequent bans/watch targets, last
played date, and a max patch batch size:

    {
      "heroes": ["D.Va", "Kiriko"],
      "bans": ["Sombra", "Widowmaker"],
      "last_played": "2026-02-20",
      "max_patches": 8,
      "notes": "freeform context from onboarding"
    }

Commands:
    init      --heroes "D.Va, Kiriko" --bans "Sombra, Widow" --last-played 2026-02-20 [--max-patches 8] [--notes "..."] [--path profile.json]
    show      [--path profile.json]
    set       [--heroes ...] [--bans ...] [--last-played YYYY-MM-DD] [--max-patches N] [--notes ...] [--path profile.json]
    normalize --name "soldier"

Use --bans "none" when the user explicitly says they do not have frequent bans
or watch targets. Omitting --bans on init is an error because the assistant must
ask the question instead of guessing.

Hero matching is intentionally roster-agnostic: this file does not hardcode the
live roster. normalize_name() lowercases, strips punctuation/spaces, and applies
a few stable shorthand aliases. Actual hero validation happens at filter time
against the hero names found in fetched patch notes.
"""
import argparse
import json
import re
from datetime import date

# Stable shorthand only, not a roster.
ALIASES = {
    "soldier": "soldier76",
    "soldier 76": "soldier76",
    "76": "soldier76",
    "dva": "dva",
    "d va": "dva",
    "lucio": "lucio",
    "torb": "torbjorn",
    "sym": "symmetra",
    "rein": "reinhardt",
    "hog": "roadhog",
    "ball": "wreckingball",
    "wrecking ball": "wreckingball",
    "hammond": "wreckingball",
    "kiri": "kiriko",
    "bap": "baptiste",
    "cass": "cassidy",
    "mccree": "cassidy",
    "queen": "junkerqueen",
    "jq": "junkerqueen",
    "weaver": "lifeweaver",
}

NONE_VALUES = {
    "none",
    "no",
    "no bans",
    "no frequent bans",
    "n/a",
    "na",
    "nothing",
    "nobody",
}


def normalize_name(name):
    """Return a loose comparison key for a hero name or shorthand."""
    raw = (name or "").strip().lower()
    key = re.sub(r"[^a-z0-9]", "", raw)
    return ALIASES.get(raw, ALIASES.get(key, key))


def valid_date(value):
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"error: '{value}' is not a valid YYYY-MM-DD date") from exc
    return value


def valid_max_patches(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"error: max_patches must be an integer, got {value!r}") from exc
    if parsed < 0:
        raise SystemExit("error: max_patches must be 0 or greater")
    return parsed


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: '{path}' is not valid JSON: {exc}") from exc


def save(path, profile):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
        f.write("\n")


def split_names(value):
    value = (value or "").strip()
    if not value:
        return []
    if value.lower() in NONE_VALUES:
        return []
    return [h.strip() for h in re.split(r"[,;]", value) if h.strip()]


def default_profile():
    return {"heroes": [], "bans": [], "last_played": None, "max_patches": 8, "notes": ""}


def ensure_defaults(profile):
    merged = default_profile()
    merged.update(profile or {})
    merged["heroes"] = merged.get("heroes") or []
    merged["bans"] = merged.get("bans") or []
    merged["notes"] = merged.get("notes") or ""
    if merged.get("max_patches") is None:
        merged["max_patches"] = 8
    else:
        merged["max_patches"] = valid_max_patches(merged["max_patches"])
    return merged


def main():
    parser = argparse.ArgumentParser(description="Manage an Overwatch patch digest profile")
    parser.add_argument("cmd", choices=["init", "show", "set", "normalize"])
    parser.add_argument("--path", default="profile.json")
    parser.add_argument("--heroes")
    parser.add_argument("--bans")
    parser.add_argument("--last-played")
    parser.add_argument("--max-patches")
    parser.add_argument("--notes")
    parser.add_argument("--name")
    args = parser.parse_args()

    if args.cmd == "normalize":
        print(normalize_name(args.name or ""))
        return

    if args.cmd == "show":
        profile = load(args.path)
        print(json.dumps(ensure_defaults(profile), indent=2, ensure_ascii=False) if profile else '{"_status": "no profile found"}')
        return

    if args.cmd == "set":
        profile = load(args.path)
        if profile is None:
            raise SystemExit("error: no profile to update; run 'init' after conversational intake first")
        profile = ensure_defaults(profile)
    else:
        profile = default_profile()

    if args.heroes is not None:
        profile["heroes"] = split_names(args.heroes)
    if args.bans is not None:
        profile["bans"] = split_names(args.bans)
    if args.last_played is not None:
        profile["last_played"] = valid_date(args.last_played)
    if args.max_patches is not None:
        profile["max_patches"] = valid_max_patches(args.max_patches)
    if args.notes is not None:
        profile["notes"] = args.notes

    if args.cmd == "init":
        missing = []
        if args.heroes is None or not profile.get("heroes"):
            missing.append("--heroes")
        if args.bans is None:
            missing.append("--bans or --bans none")
        if args.last_played is None or not profile.get("last_played"):
            missing.append("--last-played")
        if missing:
            raise SystemExit(
                "error: init needs confirmed conversational intake for " + ", ".join(missing)
            )

    save(args.path, profile)
    print(json.dumps(profile, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
