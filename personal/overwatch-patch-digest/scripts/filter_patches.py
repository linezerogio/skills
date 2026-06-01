#!/usr/bin/env python3
"""Build a personalized digest from parsed patches and a confirmed player profile.

Inputs:
    patches.json   (from parse_patch_notes.py)
    profile.json   (from profile.py)
Output:
    A markdown digest to stdout.

The digest covers only patches on/after last_played, applies the profile's
max_patches batch cap, then flattens the batch into a current-player catch-up:
mained heroes first, watched/frequent-ban heroes second, system/general changes
third, with the patch-by-patch timeline retained as source detail.
"""
import argparse
import json
import os
import signal
import sys

try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from profile import normalize_name  # noqa: E402


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise SystemExit(f"error: file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid JSON in {path}: {exc}") from exc


def format_list(items, empty="(none set)"):
    return ", ".join(items) if items else empty


def patch_heading(patch):
    date_label = patch.get("date") or "undated"
    title = patch.get("title") or "Patch notes"
    if patch.get("date") and patch["date"] in title:
        return f"## {title}"
    if title.lower() == "patch notes":
        return f"## {date_label}"
    return f"## {date_label} — {title}"


def patch_label(patch):
    date_label = patch.get("date") or "undated"
    title = patch.get("title") or "Patch notes"
    if title.lower() == "patch notes" or (patch.get("date") and patch["date"] in title):
        return date_label
    return f"{date_label} — {title}"


def coerce_max_patches(value):
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"error: max_patches must be an integer, got {value!r}") from exc
    if parsed < 0:
        raise SystemExit("error: max_patches must be 0 or greater")
    return parsed


def select_patches(patches, profile, asc=False, max_patches_override=None):
    since = profile.get("last_played")
    kept_all = [p for p in patches if (not since) or (not p.get("date")) or p["date"] >= since]
    kept_all.sort(key=lambda p: p.get("date") or "", reverse=not asc)

    max_patches = coerce_max_patches(max_patches_override)
    if max_patches is None:
        max_patches = coerce_max_patches(profile.get("max_patches"))

    if max_patches and max_patches > 0:
        return kept_all[:max_patches], len(kept_all), max_patches
    return kept_all, len(kept_all), max_patches


def append_flattened_change(bucket, hero, patch, text):
    bucket.setdefault(hero, []).append((patch, text))


def flattened_groups(kept, mains, watched):
    main_keys = {normalize_name(hero): hero for hero in mains}
    watched_keys = {normalize_name(hero): hero for hero in watched if normalize_name(hero) not in main_keys}
    main_flat = {hero: [] for hero in mains}
    watched_flat = {hero: [] for hero in watched if normalize_name(hero) in watched_keys}
    system_flat = []

    for patch in kept:
        hero_changes = patch.get("hero_changes", {}) or {}
        for hero, text in hero_changes.items():
            key = normalize_name(hero)
            if key in main_keys:
                append_flattened_change(main_flat, main_keys[key], patch, text)
            elif key in watched_keys:
                append_flattened_change(watched_flat, watched_keys[key], patch, text)
        for section, text in (patch.get("general_changes", {}) or {}).items():
            system_flat.append((patch, section, text))

    return main_flat, watched_flat, system_flat


def render_flat_hero_section(out, title, groups):
    out.append(f"### {title}")
    if not groups:
        out.append("_(none set)_\n")
        return

    any_changes = False
    for hero, entries in groups.items():
        out.append(f"**{hero}**")
        if not entries:
            out.append("_No direct parsed changes in this batch._\n")
            continue
        any_changes = True
        for patch, text in entries:
            out.append(f"_{patch_label(patch)}_")
            out.append(text)
            out.append("")
    if not any_changes:
        out.append("_No direct parsed hero changes in this batch._\n")


def render_flat_system_section(out, system_flat):
    out.append("### System & general")
    if not system_flat:
        out.append("_No parsed system/general changes in this batch._\n")
        return
    for patch, section, text in system_flat:
        out.append(f"**{patch_label(patch)} — {section}**")
        out.append(text)
        out.append("")


def main():
    parser = argparse.ArgumentParser(description="Filter parsed Overwatch patch notes for a player")
    parser.add_argument("patches")
    parser.add_argument("profile")
    parser.add_argument("--asc", action="store_true", help="oldest patch first, useful for catch-up order")
    parser.add_argument("--max-patches", type=int, help="override profile max_patches for this batch; 0 means no cap")
    args = parser.parse_args()

    patches = load_json(args.patches)
    profile = load_json(args.profile)

    since = profile.get("last_played")
    mains = profile.get("heroes", []) or []
    watched = profile.get("bans", []) or []
    main_keys = {normalize_name(hero): hero for hero in mains}
    watched_keys = {normalize_name(hero): hero for hero in watched if normalize_name(hero) not in main_keys}

    kept, total_in_window, max_patches = select_patches(
        patches, profile, asc=args.asc, max_patches_override=args.max_patches
    )

    out = []
    header = "# Your Overwatch catch-up"
    if since:
        header += f" (since {since})"
    out.append(header)
    out.append(f"Mains: {format_list(mains)}")
    out.append(f"Watching / frequent bans: {format_list(watched)}")
    if max_patches:
        out.append(f"Batch cap: {max_patches} patches")
    notes = (profile.get("notes") or "").strip()
    if notes:
        out.append(f"Context: {notes}")
    if total_in_window != len(kept):
        out.append(
            f"Batch: showing {len(kept)} of {total_in_window} parsed patches in the window. "
            "Increase `max_patches` or advance `last_played` after review for the next batch."
        )
    out.append("")

    if not kept:
        out.append("_No patches found in this window. Try widening the date range or re-fetching the source pages._")
        print("\n".join(out))
        return

    main_flat, watched_flat, system_flat = flattened_groups(kept, mains, watched)

    out.append("## Flattened update for this batch")
    out.append("Changes are grouped by what matters now, not by patch-note page. Patch details remain below for traceability.\n")
    render_flat_hero_section(out, "Your heroes", main_flat)
    render_flat_hero_section(out, "Watched heroes / frequent bans", watched_flat)
    render_flat_system_section(out, system_flat)

    out.append("\n---")
    out.append("# Patch detail")

    ever_touched_main = set()
    ever_touched_watched = set()

    for patch in kept:
        out.append("")
        out.append(patch_heading(patch))
        if not patch.get("date"):
            out.append("_⚠️ Undated — the parser could not find a date in this patch title._")

        hero_changes = patch.get("hero_changes", {}) or {}
        touched_keys = {normalize_name(hero) for hero in hero_changes}

        mine = {hero: text for hero, text in hero_changes.items() if normalize_name(hero) in main_keys}
        if mine:
            out.append("### Your heroes")
            for hero, text in mine.items():
                ever_touched_main.add(normalize_name(hero))
                out.append(f"**{hero}**\n{text}\n")
        elif mains:
            out.append("_No direct changes for your mained heroes in this patch._\n")

        untouched = [original for key, original in main_keys.items() if key not in touched_keys]
        if mine and untouched:
            out.append(f"_No changes for: {', '.join(untouched)}._\n")

        watched_changes = {hero: text for hero, text in hero_changes.items() if normalize_name(hero) in watched_keys}
        if watched_changes:
            out.append("### Watched heroes / frequent bans")
            for hero, text in watched_changes.items():
                ever_touched_watched.add(normalize_name(hero))
                out.append(f"**{hero}**\n{text}\n")

        general_changes = patch.get("general_changes", {}) or {}
        if general_changes:
            out.append("### System & general")
            for section, text in general_changes.items():
                out.append(f"**{section}**\n{text}\n")

        others = [
            hero
            for hero in hero_changes
            if normalize_name(hero) not in main_keys and normalize_name(hero) not in watched_keys
        ]
        if others:
            out.append(f"_Other heroes changed: {', '.join(others)}._\n")

    unmatched_mains = [original for key, original in main_keys.items() if key not in ever_touched_main]
    unmatched_watched = [original for key, original in watched_keys.items() if key not in ever_touched_watched]
    if unmatched_mains or unmatched_watched:
        out.append("\n---")
        if unmatched_mains:
            out.append(f"No direct parsed changes found for these mains in this batch: {', '.join(unmatched_mains)}.")
        if unmatched_watched:
            out.append(f"No direct parsed changes found for these watched heroes in this batch: {', '.join(unmatched_watched)}.")
        out.append("If that seems wrong, inspect `patches.json` to check whether the source page used an unusual heading shape.")

    print("\n".join(out))


if __name__ == "__main__":
    main()
