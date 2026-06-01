#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURE = ROOT / "tests" / "fixtures" / "sample_patch_notes.md"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ParsePatchNotesTests(unittest.TestCase):
    def test_parses_hero_update_container_and_plural_roles(self):
        parser = load_module("parse_patch_notes", SCRIPTS / "parse_patch_notes.py")
        parsed = parser.parse(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(len(parsed), 2)

        may_21 = next(p for p in parsed if p["date"] == "2026-05-21")
        self.assertIn("D.Va", may_21["hero_changes"])
        self.assertIn("Kiriko", may_21["hero_changes"])
        self.assertIn("Fusion Cannons\nPrimary Fire", may_21["hero_changes"]["D.Va"])
        self.assertIn("Bug Fixes", may_21["general_changes"])
        self.assertIn("Heroes\nJunker Queen", may_21["general_changes"]["Bug Fixes"])

        may_12 = next(p for p in parsed if p["date"] == "2026-05-12")
        self.assertIn("Roadhog", may_12["hero_changes"])
        self.assertIn("Kiriko", may_12["hero_changes"])


class ProfileTests(unittest.TestCase):
    def test_init_requires_explicit_bans_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = pathlib.Path(tmp) / "profile.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "profile.py"),
                    "init",
                    "--heroes",
                    "D.Va",
                    "--last-played",
                    "2026-05-01",
                    "--path",
                    str(profile),
                ],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--bans", result.stderr)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "profile.py"),
                    "init",
                    "--heroes",
                    "D.Va",
                    "--bans",
                    "none",
                    "--last-played",
                    "2026-05-01",
                    "--max-patches",
                    "4",
                    "--path",
                    str(profile),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            data = json.loads(result.stdout)
            self.assertEqual(data["bans"], [])
            self.assertEqual(data["max_patches"], 4)


class EndToEndTests(unittest.TestCase):
    def test_filter_outputs_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            patches = tmp_path / "patches.json"
            profile = tmp_path / "profile.json"

            parse_result = subprocess.run(
                [sys.executable, str(SCRIPTS / "parse_patch_notes.py"), str(FIXTURE)],
                check=True,
                text=True,
                capture_output=True,
            )
            patches.write_text(parse_result.stdout, encoding="utf-8")
            profile.write_text(
                json.dumps(
                    {
                        "heroes": ["D.Va", "Kiriko"],
                        "bans": ["Roadhog"],
                        "last_played": "2026-05-01",
                        "notes": "test profile",
                    }
                ),
                encoding="utf-8",
            )

            digest = subprocess.run(
                [sys.executable, str(SCRIPTS / "filter_patches.py"), str(patches), str(profile), "--asc"],
                check=True,
                text=True,
                capture_output=True,
            ).stdout

        self.assertIn("# Your Overwatch catch-up", digest)
        self.assertIn("## Flattened update for this batch", digest)
        self.assertIn("# Patch detail", digest)
        self.assertIn("**D.Va**", digest)
        self.assertIn("**Kiriko**", digest)
        self.assertIn("### Watched heroes", digest)
        self.assertIn("**Roadhog**", digest)
        self.assertIn("### System & general", digest)

    def test_filter_respects_profile_max_patches(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            patches = tmp_path / "patches.json"
            profile = tmp_path / "profile.json"

            parse_result = subprocess.run(
                [sys.executable, str(SCRIPTS / "parse_patch_notes.py"), str(FIXTURE)],
                check=True,
                text=True,
                capture_output=True,
            )
            patches.write_text(parse_result.stdout, encoding="utf-8")
            profile.write_text(
                json.dumps(
                    {
                        "heroes": ["D.Va", "Kiriko"],
                        "bans": ["Roadhog"],
                        "last_played": "2026-05-01",
                        "max_patches": 1,
                    }
                ),
                encoding="utf-8",
            )

            digest = subprocess.run(
                [sys.executable, str(SCRIPTS / "filter_patches.py"), str(patches), str(profile), "--asc"],
                check=True,
                text=True,
                capture_output=True,
            ).stdout

        self.assertIn("Batch: showing 1 of 2 parsed patches", digest)
        self.assertIn("Overwatch Retail Patch Notes – May 12, 2026", digest)
        self.assertNotIn("Overwatch Retail Patch Notes - May 21, 2026", digest)

    def test_zero_override_means_no_cap(self):
        filter_module = load_module("filter_patches_zero_override", SCRIPTS / "filter_patches.py")
        patches = [
            {"date": "2026-01-01", "title": "A"},
            {"date": "2026-01-02", "title": "B"},
            {"date": "2026-01-03", "title": "C"},
        ]
        profile = {"last_played": "2026-01-01", "max_patches": 1}

        kept, total, cap = filter_module.select_patches(patches, profile, asc=True, max_patches_override=0)

        self.assertEqual(total, 3)
        self.assertEqual(cap, 0)
        self.assertEqual([p["title"] for p in kept], ["A", "B", "C"])


class RenderPageTests(unittest.TestCase):
    def test_render_outputs_static_html_page(self):
        parser = load_module("parse_patch_notes_render", SCRIPTS / "parse_patch_notes.py")
        renderer = load_module("render_page", SCRIPTS / "render_page.py")
        parsed = parser.parse(FIXTURE.read_text(encoding="utf-8"))
        profile = {
            "heroes": ["D.Va", "Kiriko"],
            "bans": ["Roadhog"],
            "last_played": "2026-05-01",
            "notes": "test profile",
        }
        page = renderer.render_html(parsed, profile, asc=True)
        self.assertIn("<!doctype html>", page)
        self.assertIn("Your catch-up", page)
        self.assertIn("Flattened batch", page)
        self.assertIn("What changed since you played", page)
        self.assertIn("D.Va", page)
        self.assertIn("Watched heroes", page)
        self.assertIn("System & general", page)


if __name__ == "__main__":
    unittest.main()
