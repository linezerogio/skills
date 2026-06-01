#!/usr/bin/env python3
"""Render a personalized Overwatch patch digest as a self-contained HTML page.

Inputs:
    patches.json   (from parse_patch_notes.py)
    profile.json   (from profile.py)
Output:
    Static HTML to stdout, or to --out when provided.

The page uses the same filtering semantics as filter_patches.py: patches on/after
last_played, mained heroes first, watched heroes second, system/general changes
always included, and other hero changes collapsed for context.
"""
import argparse
import html
import json
import os
import re
import signal
import sys
from datetime import datetime, timezone

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


def e(value):
    return html.escape(str(value or ""), quote=True)


def format_list(items, empty="None set"):
    return ", ".join(items) if items else empty


def patch_title(patch):
    date_label = patch.get("date") or "undated"
    title = patch.get("title") or "Patch notes"
    if patch.get("date") and patch["date"] in title:
        return title
    if title.lower() == "patch notes":
        return date_label
    return f"{date_label} — {title}"


def chip_list(items, kind="neutral"):
    if not items:
        return '<span class="chip muted">None set</span>'
    return "\n".join(f'<span class="chip {kind}">{e(item)}</span>' for item in items)


def render_change_text(text):
    """Render simple markdown-ish change text into labels and bullet lists."""
    lines = [line.rstrip() for line in (text or "").splitlines()]
    out = []
    bullets = []

    def flush_bullets():
        nonlocal bullets
        if bullets:
            out.append('<ul class="change-list">')
            out.extend(f"<li>{e(item)}</li>" for item in bullets)
            out.append("</ul>")
            bullets = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_bullets()
            continue
        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
        else:
            flush_bullets()
            out.append(f'<p class="change-label">{e(stripped)}</p>')
    flush_bullets()
    return "\n".join(out) if out else '<p class="empty">No parsed details.</p>'


def render_hero_card(hero, text, kind):
    label = "Main" if kind == "main" else "Watched"
    return f"""
    <article class="hero-card {kind}">
      <div class="hero-card__head">
        <h4>{e(hero)}</h4>
        <span class="pill {kind}">{label}</span>
      </div>
      <div class="change-body">{render_change_text(text)}</div>
    </article>
    """


def render_general_card(section, text):
    return f"""
    <details class="general-card" open>
      <summary>{e(section)}</summary>
      <div class="change-body">{render_change_text(text)}</div>
    </details>
    """


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


def patch_label(patch):
    date_label = patch.get("date") or "undated"
    title = patch.get("title") or "Patch notes"
    if title.lower() == "patch notes" or (patch.get("date") and patch["date"] in title):
        return date_label
    return f"{date_label} — {title}"


def build_view_model(patches, profile, asc=False, max_patches_override=None):
    since = profile.get("last_played")
    mains = profile.get("heroes", []) or []
    watched = profile.get("bans", []) or []
    main_keys = {normalize_name(hero): hero for hero in mains}
    watched_keys = {normalize_name(hero): hero for hero in watched if normalize_name(hero) not in main_keys}

    kept, total_in_window, max_patches = select_patches(
        patches, profile, asc=asc, max_patches_override=max_patches_override
    )

    patch_views = []
    main_flat = {hero: [] for hero in mains}
    watched_flat = {hero: [] for hero in watched if normalize_name(hero) in watched_keys}
    touched_main = set()
    touched_watched = set()
    system_section_count = 0

    for patch in kept:
        hero_changes = patch.get("hero_changes", {}) or {}
        touched_keys = {normalize_name(hero) for hero in hero_changes}
        mine = [(hero, text) for hero, text in hero_changes.items() if normalize_name(hero) in main_keys]
        watched_changes = [
            (hero, text) for hero, text in hero_changes.items() if normalize_name(hero) in watched_keys
        ]
        general_changes = list((patch.get("general_changes", {}) or {}).items())
        others = [
            hero
            for hero in hero_changes
            if normalize_name(hero) not in main_keys and normalize_name(hero) not in watched_keys
        ]

        for hero, text in mine:
            key = normalize_name(hero)
            touched_main.add(key)
            main_flat.setdefault(main_keys[key], []).append((patch, text))
        for hero, text in watched_changes:
            key = normalize_name(hero)
            touched_watched.add(key)
            watched_flat.setdefault(watched_keys[key], []).append((patch, text))
        system_section_count += len(general_changes)

        patch_views.append(
            {
                "patch": patch,
                "title": patch_title(patch),
                "main_changes": mine,
                "watched_changes": watched_changes,
                "general_changes": general_changes,
                "others": others,
                "untouched_mains": [original for key, original in main_keys.items() if key not in touched_keys],
            }
        )

    return {
        "since": since,
        "mains": mains,
        "watched": watched,
        "notes": (profile.get("notes") or "").strip(),
        "patches": patch_views,
        "total_in_window": total_in_window,
        "max_patches": max_patches,
        "flat": {
            "main": main_flat,
            "watched": watched_flat,
            "system": [
                (view["patch"], section, text)
                for view in patch_views
                for section, text in view["general_changes"]
            ],
        },
        "stats": {
            "patch_count": len(kept),
            "main_hit_count": len(touched_main),
            "watched_hit_count": len(touched_watched),
            "system_section_count": system_section_count,
        },
        "unmatched_mains": [original for key, original in main_keys.items() if key not in touched_main],
        "unmatched_watched": [original for key, original in watched_keys.items() if key not in touched_watched],
    }


def render_html(patches, profile, asc=False, max_patches=None):
    vm = build_view_model(patches, profile, asc=asc, max_patches_override=max_patches)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = "Your Overwatch catch-up"
    if vm["since"]:
        title += f" since {vm['since']}"

    patch_sections = []
    if not vm["patches"]:
        patch_sections.append(
            '<section class="empty-state">No patches found in this window. Try widening the date range or re-fetching the source pages.</section>'
        )
    else:
        for view in vm["patches"]:
            patch = view["patch"]
            badges = []
            if view["main_changes"]:
                badges.append('<span class="badge hot">Main hero change</span>')
            if view["watched_changes"]:
                badges.append('<span class="badge watch">Watched hero change</span>')
            if view["general_changes"]:
                badges.append('<span class="badge system">System</span>')
            if not badges:
                badges.append('<span class="badge muted">Context only</span>')

            body_parts = []
            if view["main_changes"]:
                body_parts.append('<h3>Your heroes</h3>')
                body_parts.append('<div class="hero-grid">')
                body_parts.extend(render_hero_card(hero, text, "main") for hero, text in view["main_changes"])
                body_parts.append("</div>")
                if view["untouched_mains"]:
                    body_parts.append(
                        f'<p class="note">No direct changes for: {e(format_list(view["untouched_mains"]))}.</p>'
                    )
            elif vm["mains"]:
                body_parts.append('<p class="note">No direct changes for your mained heroes in this patch.</p>')

            if view["watched_changes"]:
                body_parts.append('<h3>Watched heroes</h3>')
                body_parts.append('<div class="hero-grid">')
                body_parts.extend(render_hero_card(hero, text, "watch") for hero, text in view["watched_changes"])
                body_parts.append("</div>")

            if view["general_changes"]:
                body_parts.append('<h3>System & general</h3>')
                body_parts.append('<div class="general-stack">')
                body_parts.extend(render_general_card(section, text) for section, text in view["general_changes"])
                body_parts.append("</div>")

            if view["others"]:
                body_parts.append(f'<p class="note">Other heroes changed: {e(format_list(view["others"]))}.</p>')

            undated = "<p class=\"warning\">The parser could not find a date in this patch title.</p>" if not patch.get("date") else ""
            patch_sections.append(
                f"""
                <section class="patch-card">
                  <div class="patch-card__head">
                    <div>
                      <p class="eyebrow">{e(patch.get('date') or 'Undated')}</p>
                      <h2>{e(view['title'])}</h2>
                    </div>
                    <div class="badges">{''.join(badges)}</div>
                  </div>
                  {undated}
                  {''.join(body_parts)}
                </section>
                """
            )

    def render_flat_hero_group(title, groups, kind):
        cards = []
        for hero, entries in groups.items():
            if entries:
                combined = []
                for patch, text in entries:
                    combined.append(f'<p class="source-label">{e(patch_label(patch))}</p>')
                    combined.append(render_change_text(text))
                body = "".join(combined)
            else:
                body = '<p class="empty">No direct parsed changes in this batch.</p>'
            label = "Main" if kind == "main" else "Watched"
            cards.append(
                f'''<article class="hero-card {kind}">
                  <div class="hero-card__head"><h4>{e(hero)}</h4><span class="pill {kind}">{label}</span></div>
                  <div class="change-body">{body}</div>
                </article>'''
            )
        if not cards:
            cards.append('<p class="note">None set.</p>')
        return f'<h3>{e(title)}</h3><div class="hero-grid">{"".join(cards)}</div>'

    flat_system_cards = []
    for patch, section, text in vm["flat"]["system"]:
        flat_system_cards.append(
            f'''<details class="general-card" open>
              <summary>{e(patch_label(patch))} — {e(section)}</summary>
              <div class="change-body">{render_change_text(text)}</div>
            </details>'''
        )
    flat_system = "".join(flat_system_cards) or '<p class="note">No parsed system/general changes in this batch.</p>'
    batch_note = ""
    if vm["total_in_window"] != vm["stats"]["patch_count"]:
        batch_note = f'<p class="note">Showing {vm["stats"]["patch_count"]} of {vm["total_in_window"]} parsed patches in the window. Increase max_patches or advance last_played after review for the next batch.</p>'

    flat_summary = f'''
    <section class="patch-card flattened">
      <div class="patch-card__head">
        <div>
          <p class="eyebrow">Flattened batch</p>
          <h2>What changed since you played</h2>
        </div>
        <div class="badges"><span class="badge hot">current-state summary</span></div>
      </div>
      <p class="note">Grouped by mains, watched heroes, and system changes instead of mirroring every patch page.</p>
      {batch_note}
      {render_flat_hero_group("Your heroes", vm["flat"]["main"], "main")}
      {render_flat_hero_group("Watched heroes / frequent bans", vm["flat"]["watched"], "watch")}
      <h3>System & general</h3>
      <div class="general-stack">{flat_system}</div>
    </section>
    '''

    unmatched = ""
    if vm["unmatched_mains"] or vm["unmatched_watched"]:
        lines = []
        if vm["unmatched_mains"]:
            lines.append(f"No direct parsed changes found for these mains: {e(format_list(vm['unmatched_mains']))}.")
        if vm["unmatched_watched"]:
            lines.append(f"No direct parsed changes found for these watched heroes: {e(format_list(vm['unmatched_watched']))}.")
        lines.append("If that seems wrong, inspect patches.json to check whether the source page used an unusual heading shape.")
        unmatched = f'<section class="parser-note">{"<br>".join(lines)}</section>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #090b10;
      --panel: #111620;
      --panel-2: #171d29;
      --text: #eef3ff;
      --muted: #9aa8bd;
      --line: rgba(255,255,255,.11);
      --accent: #f8a33a;
      --accent-2: #66d9ef;
      --good: #80ffb0;
      --watch: #b69cff;
      --shadow: 0 24px 80px rgba(0,0,0,.35);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(248,163,58,.24), transparent 32rem),
        radial-gradient(circle at 85% 10%, rgba(102,217,239,.16), transparent 30rem),
        linear-gradient(180deg, #0b0d13 0%, var(--bg) 48%, #07080c 100%);
      line-height: 1.55;
    }}
    a {{ color: inherit; }}
    .page {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 40px 0 64px; }}
    .hero {{
      border: 1px solid var(--line);
      background: linear-gradient(135deg, rgba(17,22,32,.92), rgba(17,22,32,.72));
      border-radius: 28px;
      padding: clamp(24px, 4vw, 44px);
      box-shadow: var(--shadow);
      overflow: hidden;
      position: relative;
    }}
    .hero:after {{
      content: "";
      position: absolute;
      inset: auto -10% -45% 45%;
      width: 420px;
      height: 420px;
      border-radius: 999px;
      background: rgba(248,163,58,.09);
      filter: blur(6px);
      pointer-events: none;
    }}
    .eyebrow {{ margin: 0 0 8px; color: var(--accent); font-size: .78rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }}
    h1 {{ font-size: clamp(2.4rem, 6vw, 5.5rem); line-height: .95; letter-spacing: -.06em; margin: 0; max-width: 12ch; }}
    h2 {{ margin: 2px 0 0; font-size: clamp(1.2rem, 2.6vw, 1.8rem); line-height: 1.15; letter-spacing: -.03em; }}
    h3 {{ margin: 28px 0 12px; font-size: .85rem; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }}
    h4 {{ margin: 0; font-size: 1.1rem; }}
    .subtitle {{ margin: 16px 0 0; max-width: 780px; color: #c7d2e3; font-size: 1.05rem; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }}
    .chip, .badge, .pill {{ display: inline-flex; align-items: center; border-radius: 999px; font-weight: 800; }}
    .chip {{ border: 1px solid var(--line); background: rgba(255,255,255,.05); padding: 8px 11px; font-size: .88rem; }}
    .chip.main {{ color: #ffe2bd; border-color: rgba(248,163,58,.3); }}
    .chip.watch {{ color: #ded4ff; border-color: rgba(182,156,255,.3); }}
    .muted {{ color: var(--muted); }}
    .meta-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 18px 0 24px; }}
    .stat {{ border: 1px solid var(--line); border-radius: 20px; background: rgba(255,255,255,.05); padding: 16px; }}
    .stat strong {{ display: block; font-size: 1.8rem; line-height: 1; }}
    .stat span {{ display: block; color: var(--muted); font-size: .85rem; margin-top: 5px; }}
    .section-label {{ margin: 30px 0 10px; color: var(--muted); font-size: .88rem; font-weight: 800; text-transform: uppercase; letter-spacing: .12em; }}
    .patch-stack {{ display: grid; gap: 18px; }}
    .patch-card, .parser-note, .empty-state {{
      border: 1px solid var(--line);
      background: rgba(17,22,32,.82);
      border-radius: 24px;
      padding: clamp(18px, 3vw, 28px);
      box-shadow: 0 16px 50px rgba(0,0,0,.2);
    }}
    .patch-card__head {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; border-bottom: 1px solid var(--line); padding-bottom: 18px; }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 7px; justify-content: flex-end; }}
    .badge {{ padding: 6px 9px; font-size: .72rem; border: 1px solid var(--line); background: rgba(255,255,255,.05); white-space: nowrap; }}
    .badge.hot {{ color: #ffe2bd; border-color: rgba(248,163,58,.34); }}
    .badge.watch {{ color: #ded4ff; border-color: rgba(182,156,255,.34); }}
    .badge.system {{ color: #c4f3ff; border-color: rgba(102,217,239,.3); }}
    .hero-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
    .hero-card, .general-card {{ border: 1px solid var(--line); background: var(--panel-2); border-radius: 20px; padding: 16px; }}
    .hero-card.main {{ border-color: rgba(248,163,58,.26); }}
    .hero-card.watch {{ border-color: rgba(182,156,255,.26); }}
    .hero-card__head {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }}
    .pill {{ padding: 4px 8px; font-size: .68rem; letter-spacing: .08em; text-transform: uppercase; border: 1px solid var(--line); }}
    .pill.main {{ color: #ffe2bd; background: rgba(248,163,58,.1); }}
    .pill.watch {{ color: #ded4ff; background: rgba(182,156,255,.1); }}
    .change-body {{ color: #dce6f5; }}
    .change-label {{ color: #ffffff; font-weight: 800; margin: 14px 0 6px; }}
    .change-label:first-child {{ margin-top: 0; }}
    .source-label {{ margin: 16px 0 6px; color: var(--accent); font-size: .78rem; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }}
    .flattened {{ margin-bottom: 18px; }}
    .change-list {{ margin: 0 0 12px 0; padding-left: 1.2rem; color: #cbd7e7; }}
    .change-list li {{ margin: 4px 0; }}
    .general-stack {{ display: grid; gap: 10px; }}
    .general-card summary {{ cursor: pointer; font-weight: 900; color: #ecf7ff; }}
    .general-card .change-body {{ margin-top: 12px; }}
    .note, .warning {{ color: var(--muted); margin: 14px 0 0; }}
    .warning {{ color: #ffd391; }}
    .parser-note {{ margin-top: 18px; color: #cbd7e7; }}
    footer {{ margin-top: 30px; color: var(--muted); font-size: .85rem; }}
    @media (max-width: 760px) {{
      .page {{ width: min(100% - 20px, 1120px); padding-top: 20px; }}
      .meta-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .hero-grid {{ grid-template-columns: 1fr; }}
      .patch-card__head {{ display: block; }}
      .badges {{ justify-content: flex-start; margin-top: 12px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <p class="eyebrow">Overwatch patch digest</p>
      <h1>Your catch-up</h1>
      <p class="subtitle">Personalized patch notes{f' since {e(vm["since"])}' if vm["since"] else ''}. Main hero changes are flattened across the selected batch, with patch detail below.</p>
      <div class="section-label">Mains</div>
      <div class="chips">{chip_list(vm['mains'], 'main')}</div>
      <div class="section-label">Watching</div>
      <div class="chips">{chip_list(vm['watched'], 'watch')}</div>
      {f'<p class="subtitle">{e(vm["notes"])}</p>' if vm['notes'] else ''}
    </section>

    <section class="meta-grid" aria-label="Digest stats">
      <div class="stat"><strong>{vm['stats']['patch_count']}</strong><span>Patches scanned</span></div>
      <div class="stat"><strong>{vm['stats']['main_hit_count']}</strong><span>Mains touched</span></div>
      <div class="stat"><strong>{vm['stats']['watched_hit_count']}</strong><span>Watched touched</span></div>
      <div class="stat"><strong>{vm['stats']['system_section_count']}</strong><span>System sections</span></div>
    </section>

    {flat_summary}

    <div class="section-label">Patch detail</div>
    <div class="patch-stack">
      {''.join(patch_sections)}
    </div>
    {unmatched}
    <footer>Generated {e(generated)} by the overwatch-patch-digest skill.</footer>
  </main>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Render a personalized Overwatch patch digest as HTML")
    parser.add_argument("patches")
    parser.add_argument("profile")
    parser.add_argument("--asc", action="store_true", help="oldest patch first, useful for catch-up order")
    parser.add_argument("--out", help="write HTML to this path instead of stdout")
    parser.add_argument("--max-patches", type=int, help="override profile max_patches for this batch; 0 means no cap")
    args = parser.parse_args()

    html_text = render_html(load_json(args.patches), load_json(args.profile), asc=args.asc, max_patches=args.max_patches)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(html_text)
    else:
        print(html_text)


if __name__ == "__main__":
    main()
