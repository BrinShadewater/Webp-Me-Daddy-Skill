from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPT_PATH = Path(__file__).with_name("webp_me_daddy.py")
LEGACY_SCRIPT_PATH = Path(__file__).with_name("prepare_image.py")


def create_image(path: Path, size: tuple[int, int] = (1200, 900)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(80, 120, 180)).save(path)


def create_split_image(path: Path, size: tuple[int, int] = (2400, 1200)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size)
    midpoint = size[0] // 2
    for x in range(size[0]):
        color = (220, 40, 40) if x < midpoint else (40, 90, 220)
        for y in range(size[1]):
            image.putpixel((x, y), color)
    image.save(path)


def create_vertical_split_image(path: Path, size: tuple[int, int] = (1200, 1800)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size)
    midpoint = size[1] // 2
    for y in range(size[1]):
        color = (220, 40, 40) if y < midpoint else (40, 90, 220)
        for x in range(size[0]):
            image.putpixel((x, y), color)
    image.save(path)


def create_logo_image(path: Path, size: tuple[int, int] = (600, 200)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    margin_x = 40
    margin_y = 30
    for x in range(margin_x, size[0] - margin_x):
        for y in range(margin_y, size[1] - margin_y):
            image.putpixel((x, y), (220, 70, 70, 255))
    image.save(path)


def create_animated_webp(path: Path, size: tuple[int, int] = (240, 240)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_a = Image.new("RGBA", size, (220, 70, 70, 255))
    frame_b = Image.new("RGBA", size, (70, 120, 220, 255))
    frame_a.save(
        path,
        save_all=True,
        append_images=[frame_b],
        duration=[40, 40],
        loop=0,
        format="WEBP",
    )


class WebpMeDaddyTests(unittest.TestCase):
    def run_script(
        self,
        *args: str,
        check: bool = True,
        legacy: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        script = LEGACY_SCRIPT_PATH if legacy else SCRIPT_PATH
        result = subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            raise AssertionError(
                f"Command failed with {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        return result

    def test_help_lists_subcommands(self) -> None:
        result = self.run_script("--help")
        self.assertIn("prepare", result.stdout)
        self.assertIn("batch", result.stdout)
        self.assertIn("lint", result.stdout)
        self.assertIn("audit", result.stdout)
        self.assertIn("seo-handoff", result.stdout)
        self.assertIn("cleanup", result.stdout)
        self.assertIn("snippets", result.stdout)
        self.assertIn("proof", result.stdout)
        self.assertIn("animate", result.stdout)
        self.assertIn("logo-lockup", self.run_script("prepare", "--help").stdout)
        self.assertIn("review-hero", self.run_script("prepare", "--help").stdout)

    def test_seo_handoff_applies_ready_items_and_reports_manual_ones(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "hero.jpg"
            handoff_path = root / "seo-image-handoff.json"
            report_path = root / "seo-image-apply-report.json"
            create_image(source_path, size=(1800, 1200))

            handoff = {
                "version": "1.0",
                "generated_at": "2026-03-15T00:00:00+00:00",
                "page": {
                    "url": "https://example.com",
                    "title": "Home",
                    "context": "Home",
                    "slug": "home",
                },
                "defaults": {
                    "public_root": str(public_dir),
                    "write_sidecar": True,
                    "overwrite_recommended": True,
                },
                "items": [
                    {
                        "id": "home.hero",
                        "status": "ready",
                        "priority": "high",
                        "recipe": "hero-banner",
                        "reasons": ["missing_alt", "next_gen_format_recommended"],
                        "source": {
                            "src": "/hero.jpg",
                            "url": "https://example.com/hero.jpg",
                            "path": str(source_path),
                            "public_relative_path": "hero.jpg",
                            "resolved": True,
                            "format": "jpg",
                        },
                        "metadata": {
                            "accessibility_mode": "descriptive",
                            "subject": "Launch hero art",
                            "context": "Home",
                            "purpose": "hero image",
                            "visible_text": None,
                            "usage_key": "home.hero",
                            "usage_alt": "Launch hero art for Home",
                        },
                        "markup": {
                            "loading": "eager",
                            "fetch_priority": "high",
                            "needs_dimensions": True,
                            "needs_responsive_variants": True,
                            "has_srcset": False,
                            "has_sizes": False,
                            "sizes": "100vw",
                        },
                        "notes": [],
                    },
                    {
                        "id": "home.remote-card",
                        "status": "manual",
                        "priority": "low",
                        "reasons": ["unresolved_source"],
                        "notes": ["Local public asset could not be resolved from the image src."],
                    },
                ],
            }
            handoff_path.write_text(json.dumps(handoff, indent=2), encoding="utf-8")

            result = self.run_script(
                "seo-handoff",
                str(handoff_path),
                "--yes",
                "--overwrite",
                "--json",
                str(report_path),
            )

            self.assertIn("SEO handoff summary:", result.stdout)
            self.assertTrue((public_dir / "hero.webp").exists())
            self.assertTrue((public_dir / "hero.json").exists())

            sidecar = json.loads((public_dir / "hero.json").read_text())
            self.assertEqual(sidecar["recipe"]["name"], "hero-banner")
            self.assertEqual(sidecar["metadata"]["usage_overrides"]["home.hero"]["alt"], "Launch hero art for Home")

            report = json.loads(report_path.read_text())
            self.assertEqual(report["summary"]["applied_count"], 1)
            self.assertEqual(report["summary"]["manual_count"], 1)
            self.assertEqual(report["summary"]["failed_count"], 0)

    def test_prepare_writes_v2_sidecar_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "hero-source.jpg"
            manifest_path = root / "image-manifest.json"
            create_image(source_path, size=(1800, 1200))

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "hero-banner",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--manifest",
                str(manifest_path),
                "--overwrite",
            )

            sidecar = json.loads((public_dir / "hero-source.json").read_text())
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(sidecar["version"], "2.3.0")
            self.assertEqual(sidecar["recipe"]["name"], "hero-banner")
            self.assertEqual(sidecar["metadata"]["accessibility_mode"], "descriptive")
            self.assertTrue(sidecar["snippets"]["enabled"])
            self.assertIn("html", sidecar["snippets"]["targets"])
            self.assertIn("react", sidecar["snippets"]["targets"])
            self.assertIn("next", sidecar["snippets"]["targets"])
            self.assertIn("astro", sidecar["snippets"]["targets"])
            self.assertGreater(len(sidecar["output"]["variants"]), 0)
            self.assertEqual(manifest["version"], "2.3.0")
            self.assertEqual(manifest["run"]["command"], "prepare")
            self.assertEqual(manifest["summary"]["image_count"], 1)

    def test_small_sources_do_not_upscale_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "small-cover.jpg"
            create_image(source_path, size=(460, 215))

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "blog-cover",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )

            sidecar = json.loads((public_dir / "small-cover.json").read_text())
            self.assertEqual((sidecar["output"]["main"]["width"], sidecar["output"]["main"]["height"]), (460, 215))
            self.assertEqual(sidecar["output"]["variants"], [])
            self.assertNotIn("no_responsive_variants", sidecar["analysis"]["lints"]["warnings"])

    def test_allow_upscale_restores_recipe_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "small-cover.jpg"
            create_image(source_path, size=(460, 215))

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "blog-cover",
                "--allow-upscale",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )

            sidecar = json.loads((public_dir / "small-cover.json").read_text())
            self.assertEqual((sidecar["output"]["main"]["width"], sidecar["output"]["main"]["height"]), (1600, 900))
            self.assertGreater(len(sidecar["output"]["variants"]), 0)

    def test_recipe_defaults_drive_loading_and_snippet_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            hero_source = public_dir / "hero.jpg"
            poster_source = public_dir / "poster.jpg"
            create_image(hero_source, size=(1800, 1200))
            create_image(poster_source, size=(900, 1600))

            self.run_script(
                "prepare",
                str(hero_source),
                "--recipe",
                "hero-banner",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )
            self.run_script(
                "prepare",
                str(poster_source),
                "--recipe",
                "poster",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )

            hero_sidecar = json.loads((public_dir / "hero.json").read_text())
            poster_sidecar = json.loads((public_dir / "poster.json").read_text())
            self.assertEqual(hero_sidecar["snippets"]["loading"], "eager")
            self.assertEqual(hero_sidecar["snippets"]["fetch_priority"], "high")
            self.assertTrue(hero_sidecar["snippets"]["enabled"])
            self.assertFalse(poster_sidecar["snippets"]["enabled"])
            self.assertEqual(poster_sidecar["output"]["variants"], [])

    def test_review_hero_defaults_to_subject_framing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "review.jpg"
            create_image(source_path, size=(1800, 1200))

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "review-hero",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )

            sidecar = json.loads((public_dir / "review.json").read_text())
            self.assertEqual(sidecar["recipe"]["name"], "review-hero")
            self.assertEqual(sidecar["recipe"]["default_framing"], "subject")
            self.assertEqual(sidecar["metadata"]["inputs"]["framing"], "subject")

    def test_logo_grid_recipe_defaults_to_decorative_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "badge.png"
            create_logo_image(source_path, size=(420, 180))

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "logo-grid",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )

            sidecar = json.loads((public_dir / "badge.json").read_text())
            self.assertEqual(sidecar["recipe"]["name"], "logo-grid")
            self.assertEqual(sidecar["recipe"]["default_accessibility_mode"], "decorative")
            self.assertEqual(sidecar["metadata"]["accessibility_mode"], "decorative")
            self.assertEqual(sidecar["metadata"]["generated"]["alt"], "")

    def test_batch_requires_dry_run_or_yes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            create_image(public_dir / "one.jpg")

            result = self.run_script(
                "batch",
                str(public_dir),
                "--recipe",
                "blog-cover",
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("require --dry-run or explicit confirmation", result.stderr)

    def test_batch_dry_run_does_not_write_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            manifest_path = root / "image-manifest.json"
            proof_path = root / "batch-proof.png"
            create_image(public_dir / "cover.jpg")

            result = self.run_script(
                "batch",
                str(public_dir),
                "--recipe",
                "blog-cover",
                "--dry-run",
                "--proof-contact-sheet",
                str(proof_path),
                "--write-sidecar",
                "--manifest",
                str(manifest_path),
            )

            self.assertFalse((public_dir / "cover.webp").exists())
            self.assertFalse((public_dir / "cover.json").exists())
            self.assertFalse(manifest_path.exists())
            self.assertTrue(proof_path.exists())
            with Image.open(proof_path) as rendered:
                self.assertEqual(rendered.format, "PNG")
                self.assertGreater(rendered.size[0], 800)
                self.assertGreater(rendered.size[1], 600)
            self.assertIn("Dry-run proof summary:", result.stdout)
            self.assertIn("Batch proof contact sheet:", result.stdout)
            self.assertIn("cover.jpg", result.stdout)
            self.assertIn("cover.webp", result.stdout)
            self.assertIn("status", result.stdout.lower())
            self.assertIn("dark, light", result.stdout)
            self.assertIn("Manifest (dry-run)", result.stdout)

    def test_batch_dry_run_summary_shows_warning_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            create_image(public_dir / "cover.jpg", size=(1800, 1200))

            result = self.run_script(
                "batch",
                str(public_dir),
                "--recipe",
                "blog-cover",
                "--dry-run",
                "--accessibility-mode",
                "text-bearing",
            )

            self.assertIn("warning", result.stdout.lower())
            self.assertIn("text-bearing image is missing visible text", result.stdout.lower())
            self.assertIn("add visible_text", result.stdout.lower())

    def test_json_errors_are_machine_readable(self) -> None:
        result = self.run_script("prepare", "--json-errors", check=False)

        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stderr)
        self.assertEqual(payload["error"]["type"], "UsageError")
        self.assertEqual(payload["error"]["exit_code"], 2)
        self.assertIn("the following arguments are required: input", payload["error"]["message"])

    def test_text_bearing_mode_and_snippet_escaping_are_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "hero-source.jpg"
            create_image(source_path)

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "hero-banner",
                "--seo-subject",
                'Hero "quoted" & bright',
                "--seo-context",
                'Brin "Launch" page',
                "--accessibility-mode",
                "text-bearing",
                "--visible-text",
                'Join "now"',
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )

            sidecar = json.loads((public_dir / "hero-source.json").read_text())
            self.assertEqual(sidecar["metadata"]["accessibility_mode"], "text-bearing")
            self.assertIn('Text reads "Join "now""', sidecar["metadata"]["generated"]["alt"])
            self.assertIn("&quot;quoted&quot; &amp; bright", sidecar["snippets"]["targets"]["html"]["markup"])
            self.assertIn('alt={"Hero \\"quoted\\" & bright.', sidecar["snippets"]["targets"]["react"]["markup"])
            self.assertIn('import Image from "next/image";', sidecar["snippets"]["targets"]["next"]["markup"])
            self.assertIn('loading="eager"', sidecar["snippets"]["targets"]["astro"]["markup"])

    def test_lint_strict_promotes_metadata_warnings_to_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "hero-source.jpg"
            manifest_path = root / "image-manifest.json"
            create_image(source_path, size=(1800, 1200))

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "hero-banner",
                "--public-root",
                str(public_dir),
                "--manifest",
                str(manifest_path),
                "--overwrite",
            )

            manifest = json.loads(manifest_path.read_text())
            image = manifest["images"][0]
            image["metadata"]["accessibility_mode"] = "text-bearing"
            image["metadata"]["inputs"]["visible_text"] = ""
            image["metadata"]["generated"]["alt"] = "Image of hero banner banner banner"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            normal_result = self.run_script("lint", str(manifest_path), check=False)
            strict_result = self.run_script("lint", str(manifest_path), "--strict", check=False)

            self.assertEqual(normal_result.returncode, 0)
            self.assertIn("alt text starts with a redundant prefix", normal_result.stdout)
            self.assertIn("text-bearing image is missing visible text input", normal_result.stdout)

            self.assertEqual(strict_result.returncode, 1)
            self.assertIn("Lint status: FAIL (strict)", strict_result.stdout)
            self.assertIn("alt text starts with a redundant prefix", strict_result.stdout)
            self.assertIn("text-bearing image is missing visible text input", strict_result.stdout)

    def test_proof_generates_png_from_sidecar_usage_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "logo.png"
            proof_path = root / "logo-proof.png"
            create_logo_image(source_path, size=(420, 180))

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "logo-lockup",
                "--public-root",
                str(public_dir),
                "--usage-key",
                "pdf.cover",
                "--usage-alt",
                "Labs lockup on dark cover",
                "--write-sidecar",
                "--overwrite",
            )

            result = self.run_script(
                "proof",
                str(public_dir / "logo.json"),
                "--usage-key",
                "pdf.cover",
                "--output",
                str(proof_path),
            )

            self.assertTrue(proof_path.exists())
            with Image.open(proof_path) as rendered:
                self.assertGreater(rendered.size[0], 1000)
                self.assertGreater(rendered.size[1], 900)
            self.assertIn("Proof sheet:", result.stdout)
            self.assertIn("Usage key: pdf.cover", result.stdout)

    def test_usage_override_is_stored_and_used_for_snippets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "hero-source.jpg"
            create_image(source_path)

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "hero-banner",
                "--seo-subject",
                "Brin hero art",
                "--usage-key",
                "home.hero",
                "--usage-alt",
                "Brin Shadewater homepage hero art",
                "--usage-title",
                "Homepage hero",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )

            sidecar = json.loads((public_dir / "hero-source.json").read_text())
            self.assertIn("home.hero", sidecar["metadata"]["usage_overrides"])
            self.assertEqual(
                sidecar["metadata"]["usage_overrides"]["home.hero"]["alt"],
                "Brin Shadewater homepage hero art",
            )
            self.assertEqual(sidecar["snippets"]["usage_key"], "home.hero")
            self.assertIn("Brin Shadewater homepage hero art", sidecar["snippets"]["targets"]["html"]["markup"])

    def test_snippets_helper_generates_usage_specific_markup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "hero-source.jpg"
            export_path = root / "snippets.json"
            create_image(source_path)

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "hero-banner",
                "--usage-key",
                "home.hero",
                "--usage-alt",
                "Homepage hero alt",
                "--usage-title",
                "Homepage hero title",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )

            result = self.run_script(
                "snippets",
                str(public_dir / "hero-source.json"),
                "--usage-key",
                "home.hero",
                "--target",
                "next",
                "--json",
                str(export_path),
            )

            self.assertIn("Usage key: home.hero", result.stdout)
            self.assertIn("Homepage hero alt", result.stdout)
            self.assertIn('import Image from "next/image";', result.stdout)
            export = json.loads(export_path.read_text())
            self.assertEqual(export["run"]["command"], "snippets")
            self.assertEqual(export["run"]["usage_key"], "home.hero")
            self.assertIn("next", export["snippets"]["targets"])

    def test_proof_generates_surface_check_png_from_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "logo.png"
            proof_path = root / "logo-proof.png"
            create_logo_image(source_path, size=(520, 220))

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "logo-lockup",
                "--usage-key",
                "pdf.cover",
                "--usage-alt",
                "Shadewater Labs logo lockup on a dark document cover",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )

            result = self.run_script(
                "proof",
                str(public_dir / "logo.json"),
                "--usage-key",
                "pdf.cover",
                "--output",
                str(proof_path),
            )

            self.assertTrue(proof_path.exists())
            with Image.open(proof_path) as image:
                self.assertEqual(image.format, "PNG")
                self.assertGreater(image.size[0], 1000)
            self.assertIn("Proof sheet:", result.stdout)
            self.assertIn("Usage key: pdf.cover", result.stdout)

    def test_focus_controls_shift_crop_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "focus-source.png"
            create_split_image(source_path)

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "profile-avatar",
                "--slug",
                "focus-left",
                "--focus-x",
                "0.1",
                "--focus-y",
                "0.5",
                "--lossless",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )
            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "profile-avatar",
                "--slug",
                "focus-right",
                "--focus-preset",
                "right",
                "--lossless",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )

            left_image = Image.open(public_dir / "focus-left.webp")
            right_image = Image.open(public_dir / "focus-right.webp")
            left_center = left_image.getpixel((left_image.width // 2, left_image.height // 2))
            right_center = right_image.getpixel((right_image.width // 2, right_image.height // 2))
            left_sidecar = json.loads((public_dir / "focus-left.json").read_text())
            right_sidecar = json.loads((public_dir / "focus-right.json").read_text())

            self.assertGreater(left_center[0], left_center[2])
            self.assertGreater(right_center[2], right_center[0])
            self.assertEqual(left_sidecar["output"]["focus"]["preset"], "custom")
            self.assertEqual(right_sidecar["output"]["focus"]["preset"], "right")

    def test_framing_text_and_subject_shift_portrait_to_landscape_crop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "poster-source.png"
            create_vertical_split_image(source_path)

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "review-hero",
                "--slug",
                "subject-framing",
                "--framing",
                "subject",
                "--lossless",
                "--allow-upscale",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )
            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "review-hero",
                "--slug",
                "text-framing",
                "--framing",
                "text",
                "--lossless",
                "--allow-upscale",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )

            with Image.open(public_dir / "subject-framing.webp") as subject_image:
                subject_center = subject_image.getpixel((subject_image.width // 2, subject_image.height // 2))
            with Image.open(public_dir / "text-framing.webp") as text_image:
                text_center = text_image.getpixel((text_image.width // 2, text_image.height // 2))
            subject_sidecar = json.loads((public_dir / "subject-framing.json").read_text())
            text_sidecar = json.loads((public_dir / "text-framing.json").read_text())

            self.assertGreater(subject_center[0], subject_center[2])
            self.assertGreater(text_center[2], text_center[0])
            self.assertEqual(subject_sidecar["metadata"]["inputs"]["framing"], "subject")
            self.assertEqual(text_sidecar["metadata"]["inputs"]["framing"], "text")
            self.assertEqual(subject_sidecar["output"]["focus"]["framing"], "subject")
            self.assertEqual(text_sidecar["output"]["focus"]["framing"], "text")

    def test_auto_framing_biases_subject_for_poster_to_landscape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "poster-source.png"
            create_vertical_split_image(source_path)

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "blog-cover",
                "--slug",
                "auto-framing",
                "--lossless",
                "--allow-upscale",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )

            sidecar = json.loads((public_dir / "auto-framing.json").read_text())
            with Image.open(public_dir / "auto-framing.webp") as output_image:
                center = output_image.getpixel((output_image.width // 2, output_image.height // 2))

            self.assertGreater(center[0], center[2])
            self.assertEqual(sidecar["metadata"]["inputs"]["framing"], "subject")
            self.assertEqual(sidecar["output"]["focus"]["framing"], "subject")

    def test_logo_lockup_recipe_uses_contain_and_preserves_transparency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "logo-source.png"
            create_logo_image(source_path)

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "logo-lockup",
                "--accessibility-mode",
                "logo",
                "--lossless",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )

            sidecar = json.loads((public_dir / "logo-source.json").read_text())
            output_image = Image.open(public_dir / "logo-source.webp")
            corner = output_image.getpixel((10, 10))
            center = output_image.getpixel((output_image.width // 2, output_image.height // 2))

            self.assertEqual(sidecar["recipe"]["name"], "logo-lockup")
            self.assertEqual(sidecar["recipe"]["fit_mode"], "contain")
            self.assertEqual(sidecar["output"]["fit_mode"], "contain")
            self.assertEqual((sidecar["output"]["main"]["width"], sidecar["output"]["main"]["height"]), (1200, 900))
            self.assertEqual(corner[3], 0)
            self.assertGreater(center[0], 150)

    def test_lint_blocks_missing_alt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "hero.jpg"
            manifest_path = root / "image-manifest.json"
            create_image(source_path)

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "hero-banner",
                "--public-root",
                str(public_dir),
                "--manifest",
                str(manifest_path),
                "--overwrite",
            )

            manifest = json.loads(manifest_path.read_text())
            manifest["images"][0]["metadata"]["generated"]["alt"] = ""
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            result = self.run_script("lint", str(manifest_path), check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("missing alt text", result.stdout)
            self.assertIn("Lint status: FAIL", result.stdout)

    def test_lint_warns_but_passes_on_missing_responsive_variants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "hero.jpg"
            manifest_path = root / "image-manifest.json"
            create_image(source_path)

            self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "hero-banner",
                "--no-responsive",
                "--public-root",
                str(public_dir),
                "--manifest",
                str(manifest_path),
                "--overwrite",
            )

            result = self.run_script("lint", str(manifest_path), check=False)
            self.assertEqual(result.returncode, 0)
            self.assertIn("missing responsive variants for hero-like recipe", result.stdout)
            self.assertIn("Lint status: OK", result.stdout)

    def test_legacy_prepare_image_shim_translates_old_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "avatar.jpg"
            create_image(source_path)

            self.run_script(
                str(source_path),
                "--preset",
                "square",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
                legacy=True,
            )

            sidecar = json.loads((public_dir / "avatar.json").read_text())
            self.assertEqual(sidecar["recipe"]["name"], "profile-avatar")

    def test_prepare_rejects_animated_webp_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            public_dir = root / "public"
            source_path = public_dir / "animated.webp"
            create_animated_webp(source_path)

            result = self.run_script(
                "prepare",
                str(source_path),
                "--recipe",
                "hero-banner",
                "--public-root",
                str(public_dir),
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("webp-me-daddy animate", result.stderr)

    def test_animate_handoff_accepts_animated_webp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_path = root / "animated.webp"
            output_path = root / "animated-cleaned.webp"
            create_animated_webp(source_path)

            result = self.run_script(
                "animate",
                str(source_path),
                str(output_path),
                "--size",
                "96",
                "--bridge-frames",
                "2",
                "--bridge-duration",
                "20",
            )

            self.assertIn("Animated output:", result.stdout)
            self.assertTrue(output_path.exists())
            with Image.open(output_path) as output:
                self.assertGreater(getattr(output, "n_frames", 1), 1)

    def test_audit_reports_live_png_and_unused_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src_dir = root / "src"
            public_dir = root / "public"
            report_path = root / "audit.json"
            src_dir.mkdir(parents=True, exist_ok=True)
            public_dir.mkdir(parents=True, exist_ok=True)

            create_logo_image(public_dir / "logo.png")
            create_image(public_dir / "unused.jpg")
            (src_dir / "Home.tsx").write_text(
                """
export default function Home() {
  return <img src="/logo.png" alt="Logo" />;
}
""".strip(),
                encoding="utf-8",
            )
            (src_dir / "Sponsor.tsx").write_text(
                """
export default function Sponsor() {
  return <img src="/logo.png" alt="" role="presentation" loading="lazy" decoding="async" />;
}
""".strip(),
                encoding="utf-8",
            )

            result = self.run_script(
                "audit",
                str(root),
                "--emit-fix-plan",
                "--json",
                str(report_path),
            )

            self.assertIn("1 live PNG assets", result.stdout)
            self.assertIn("1 unused public assets", result.stdout)
            self.assertIn("1 shared assets used across multiple source files", result.stdout)
            self.assertIn("2 image tags with autofix suggestions", result.stdout)
            self.assertIn("2 file-specific codemod patches", result.stdout)
            self.assertIn("suggested fix plan", result.stdout.lower())
            self.assertIn("python", result.stdout.lower())
            report = json.loads(report_path.read_text())
            self.assertEqual(report["version"], "2.3.0")
            self.assertEqual(report["summary"]["live_png_count"], 1)
            self.assertEqual(report["summary"]["unused_asset_count"], 1)
            self.assertEqual(report["summary"]["shared_asset_count"], 1)
            self.assertEqual(report["summary"]["autofixable_tag_count"], 2)
            self.assertEqual(report["summary"]["codemod_patch_count"], 2)
            self.assertGreaterEqual(report["summary"]["fix_plan_count"], 3)
            self.assertIn("fix_plan", report)
            suggestion = report["markup"]["autofix_suggestions"][0]
            self.assertEqual(suggestion["attributes"]["width"], 600)
            self.assertEqual(suggestion["attributes"]["height"], 200)
            self.assertEqual(suggestion["attributes"]["decoding"], "async")
            self.assertIn("jsx_patch", suggestion)
            self.assertIn('width={600}', suggestion["jsx_patch"])
            codemod_patch = report["markup"]["codemod_patches"][0]
            self.assertTrue(codemod_patch["file"].endswith("Home.tsx"))
            self.assertIn('<img src="/logo.png" alt="Logo" />', codemod_patch["old_str"])
            self.assertIn('width={600}', codemod_patch["new_str"])
            self.assertIn('decoding={"async"}', suggestion["jsx_patch"])
            prepare_step = next(step for step in report["fix_plan"] if step["kind"] == "prepare")
            self.assertEqual(prepare_step["asset"], "logo.png")
            self.assertIn("--recipe logo-lockup", prepare_step["command"])
            self.assertIn("--apply-autofix", next(step for step in report["fix_plan"] if step["kind"] == "autofix")["command"])

    def test_audit_reports_next_image_component_fixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src_dir = root / "src"
            public_dir = root / "public"
            report_path = root / "audit.json"
            src_dir.mkdir(parents=True, exist_ok=True)
            public_dir.mkdir(parents=True, exist_ok=True)

            create_image(public_dir / "hero.png", size=(1600, 900))
            (src_dir / "Hero.tsx").write_text(
                """
import Image from "next/image";

export default function Hero() {
  return <Image src={"/hero.png"} alt="Hero art" />;
}
""".strip(),
                encoding="utf-8",
            )

            result = self.run_script(
                "audit",
                str(root),
                "--json",
                str(report_path),
            )

            self.assertIn("1 next/image tags scanned", result.stdout)
            report = json.loads(report_path.read_text())
            self.assertEqual(report["summary"]["next_image_tag_count"], 1)
            suggestion = report["markup"]["autofix_suggestions"][0]
            self.assertEqual(suggestion["component_kind"], "next-image")
            self.assertIn('width={1600}', suggestion["jsx_patch"])
            self.assertIn('height={900}', suggestion["jsx_patch"])
            self.assertIn('loading={"eager"}', suggestion["jsx_patch"])
            self.assertIn('fetchPriority={"high"}', suggestion["jsx_patch"])
            self.assertNotIn('decoding={"async"}', suggestion["jsx_patch"])

    def test_audit_shared_asset_includes_usage_override_suggestions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src_dir = root / "src"
            public_dir = root / "public"
            report_path = root / "audit.json"
            src_dir.mkdir(parents=True, exist_ok=True)
            public_dir.mkdir(parents=True, exist_ok=True)

            create_image(public_dir / "shared-hero.jpg")
            self.run_script(
                "prepare",
                str(public_dir / "shared-hero.jpg"),
                "--recipe",
                "hero-banner",
                "--public-root",
                str(public_dir),
                "--write-sidecar",
                "--overwrite",
            )

            (src_dir / "Home.tsx").write_text(
                """
export default function Home() {
  return <img src="/shared-hero.webp" alt="Shared hero" />;
}
""".strip(),
                encoding="utf-8",
            )
            (src_dir / "SponsorDeck.tsx").write_text(
                """
export default function SponsorDeck() {
  return <img src="/shared-hero.webp" alt="Shared hero" />;
}
""".strip(),
                encoding="utf-8",
            )

            result = self.run_script(
                "audit",
                str(root),
                "--json",
                str(report_path),
            )

            self.assertIn("usage_key: home.shared-hero", result.stdout)
            report = json.loads(report_path.read_text())
            candidate = report["assets"]["shared_usage_candidates"][0]
            suggestions = candidate["usage_override_suggestions"]
            self.assertEqual(suggestions[0]["usage_key"], "home.shared-hero")
            self.assertIn("snippets", suggestions[0]["snippet_command"])
            self.assertEqual(suggestions[1]["usage_key"], "sponsor-deck.shared-hero")

    def test_audit_apply_autofix_updates_img_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src_dir = root / "src"
            public_dir = root / "public"
            report_path = root / "audit.json"
            src_dir.mkdir(parents=True, exist_ok=True)
            public_dir.mkdir(parents=True, exist_ok=True)

            create_logo_image(public_dir / "logo.png")
            home_path = src_dir / "Home.tsx"
            home_path.write_text(
                """
export default function Home() {
  return <img src="/logo.png" alt="Logo" />;
}
""".strip(),
                encoding="utf-8",
            )

            result = self.run_script(
                "audit",
                str(root),
                "--apply-autofix",
                "--json",
                str(report_path),
            )

            updated = home_path.read_text(encoding="utf-8")
            self.assertIn('width={600}', updated)
            self.assertIn('height={200}', updated)
            self.assertIn('loading={"lazy"}', updated)
            self.assertIn('decoding={"async"}', updated)
            self.assertIn("1 codemod patches applied", result.stdout)
            report = json.loads(report_path.read_text())
            self.assertEqual(report["summary"]["applied_patch_count"], 1)
            self.assertEqual(report["summary"]["skipped_patch_count"], 0)

    def test_audit_apply_autofix_skips_ambiguous_duplicate_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src_dir = root / "src"
            public_dir = root / "public"
            report_path = root / "audit.json"
            src_dir.mkdir(parents=True, exist_ok=True)
            public_dir.mkdir(parents=True, exist_ok=True)

            create_logo_image(public_dir / "logo.png")
            home_path = src_dir / "Home.tsx"
            home_path.write_text(
                """
export default function Home() {
  return (
    <>
      <img src="/logo.png" alt="Logo" />
      <img src="/logo.png" alt="Logo" />
    </>
  );
}
""".strip(),
                encoding="utf-8",
            )

            result = self.run_script(
                "audit",
                str(root),
                "--apply-autofix",
                "--json",
                str(report_path),
            )

            unchanged = home_path.read_text(encoding="utf-8")
            self.assertEqual(unchanged.count('<img src="/logo.png" alt="Logo" />'), 2)
            self.assertIn("2 codemod patches skipped", result.stdout)
            report = json.loads(report_path.read_text())
            self.assertEqual(report["summary"]["applied_patch_count"], 0)
            self.assertEqual(report["summary"]["skipped_patch_count"], 2)
            self.assertEqual(report["autofix"]["skipped"][0]["reason"], "multiple_matches")

    def test_cleanup_requires_dry_run_or_yes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src_dir = root / "src"
            public_dir = root / "public"
            src_dir.mkdir(parents=True, exist_ok=True)
            public_dir.mkdir(parents=True, exist_ok=True)

            create_image(public_dir / "unused.jpg")
            (src_dir / "Home.tsx").write_text("export default function Home() { return null; }", encoding="utf-8")

            result = self.run_script("cleanup", str(root), check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("require --dry-run or explicit confirmation", result.stderr)

    def test_cleanup_dry_run_keeps_unused_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src_dir = root / "src"
            public_dir = root / "public"
            report_path = root / "cleanup-report.json"
            src_dir.mkdir(parents=True, exist_ok=True)
            public_dir.mkdir(parents=True, exist_ok=True)

            create_logo_image(public_dir / "logo.png")
            create_image(public_dir / "unused.jpg")
            (src_dir / "Home.tsx").write_text(
                """
export default function Home() {
  return <img src="/logo.png" alt="Logo" loading="lazy" decoding="async" width={300} height={100} />;
}
""".strip(),
                encoding="utf-8",
            )

            result = self.run_script(
                "cleanup",
                str(root),
                "--dry-run",
                "--json",
                str(report_path),
            )

            self.assertTrue((public_dir / "unused.jpg").exists())
            self.assertIn("Dry run only", result.stdout)
            report = json.loads(report_path.read_text())
            self.assertEqual(report["summary"]["candidate_count"], 1)
            self.assertEqual(report["summary"]["deleted_count"], 0)

    def test_cleanup_yes_deletes_unused_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src_dir = root / "src"
            public_dir = root / "public"
            report_path = root / "cleanup-report.json"
            src_dir.mkdir(parents=True, exist_ok=True)
            public_dir.mkdir(parents=True, exist_ok=True)

            create_logo_image(public_dir / "logo.png")
            create_image(public_dir / "unused.jpg")
            (src_dir / "Home.tsx").write_text(
                """
export default function Home() {
  return <img src="/logo.png" alt="Logo" loading="lazy" decoding="async" width={300} height={100} />;
}
""".strip(),
                encoding="utf-8",
            )

            result = self.run_script(
                "cleanup",
                str(root),
                "--yes",
                "--json",
                str(report_path),
            )

            self.assertFalse((public_dir / "unused.jpg").exists())
            self.assertTrue((public_dir / "logo.png").exists())
            self.assertIn("Deleted 1 unused public assets", result.stdout)
            report = json.loads(report_path.read_text())
            self.assertEqual(report["summary"]["candidate_count"], 1)
            self.assertEqual(report["summary"]["deleted_count"], 1)


if __name__ == "__main__":
    unittest.main()
