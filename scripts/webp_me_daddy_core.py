from __future__ import annotations

import argparse
import html
import json
import math
import re
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageSequence


VERSION = "2.3.0"
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
RESAMPLE = Image.Resampling.LANCZOS
SUBCOMMANDS = {"prepare", "batch", "lint", "audit", "cleanup", "snippets", "animate", "proof", "seo-handoff"}
DEFAULT_HERO_KB = 250
DEFAULT_STANDARD_KB = 150
SEO_HANDOFF_VERSION = "1.0"
AUDIT_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".css", ".html"}
AUDIT_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
IMG_TAG_PATTERN = re.compile(r"<img\b[\s\S]*?>", re.IGNORECASE)
NEXT_IMAGE_IMPORT_PATTERN = re.compile(r'import\s+([A-Za-z_][A-Za-z0-9_]*)\s+from\s+[\'"]next/image[\'"]')
PATH_REFERENCE_PATTERN = re.compile(r"/([^\"'\s>]+?\.(?:png|jpg|jpeg|webp|gif|svg))", re.IGNORECASE)
ATTRIBUTE_PATTERN = re.compile(r"([A-Za-z_:][-A-Za-z0-9_:]*)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|\{([^}]*)\})", re.DOTALL)
# The `animate` command shells out to the companion transparent-gif-loop tool.
# Checked out as a sibling by default; override with TRANSPARENT_GIF_LOOP_DIR when it
# lives elsewhere. See https://github.com/BrinShadewater/Transparent-Gif-Loop-Skill
def _resolve_transparent_gif_script() -> Path:
    override = os.environ.get("TRANSPARENT_GIF_LOOP_DIR")
    roots = [Path(override)] if override else []
    # Sibling checkout. Covers the public repo name, the bare tool name, and the
    # casing git produces when cloning each.
    siblings = Path(__file__).resolve().parents[2]
    for name in (
        "Transparent-Gif-Loop-Skill",
        "transparent-gif-loop-skill",
        "transparent-gif-loop",
        "Transparent-Gif-Loop",
    ):
        roots.append(siblings / name)
    for root in roots:
        candidate = root / "scripts" / "process_gif.py"
        if candidate.exists():
            return candidate
    return roots[-1] / "scripts" / "process_gif.py"


TRANSPARENT_GIF_SCRIPT = _resolve_transparent_gif_script()
CLI_SCRIPT = Path(__file__).resolve().with_name("webp_me_daddy.py")
PROOF_SURFACE_COLORS = {
    "dark": ((8, 25, 37), "Dark surface"),
    "light": ((240, 236, 229), "Light surface"),
    "checker": (None, "Transparency check"),
}

FOCUS_PRESETS = {
    "center": (0.5, 0.5),
    "top": (0.5, 0.15),
    "bottom": (0.5, 0.85),
    "left": (0.15, 0.5),
    "right": (0.85, 0.5),
    "top-left": (0.15, 0.15),
    "top-right": (0.85, 0.15),
    "bottom-left": (0.15, 0.85),
    "bottom-right": (0.85, 0.85),
}

LEGACY_PRESET_TO_RECIPE = {
    "square": "profile-avatar",
    "landscape": "blog-cover",
    "portrait": "poster",
    "poster": "poster",
    "cover": "card-thumbnail",
    "story": "story-cover",
    "reel": "story-cover",
}

LEGACY_FLAG_TO_MODE = {
    "--decorative": "decorative",
    "--logo": "logo",
    "--contains-text": "text-bearing",
}

REDUNDANT_ALT_PREFIX_PATTERN = re.compile(
    r"^\s*(image|photo|picture|graphic|illustration)\s+of\b",
    re.IGNORECASE,
)
ALT_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "hero",
    "image",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
}
STRICT_LINT_CODES = {
    "alt_too_long",
    "filename_like_alt",
    "keyword_stuffed_alt",
    "redundant_alt_prefix",
    "text_bearing_missing_visible_text",
}


class WebpMeDaddyError(Exception):
    exit_code = 1


class UsageError(WebpMeDaddyError):
    exit_code = 2


class ManifestError(WebpMeDaddyError):
    exit_code = 2


class AuditError(WebpMeDaddyError):
    exit_code = 2


class SidecarError(WebpMeDaddyError):
    exit_code = 2


class HandoffError(WebpMeDaddyError):
    exit_code = 2


class WebpArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - argparse hook
        raise UsageError(message)


@dataclass(frozen=True)
class RecipeConfig:
    name: str
    width: int
    height: int
    aspect_ratio: str
    fit_mode: str
    default_accessibility_mode: str
    default_framing: str
    responsive_by_default: bool
    responsive_widths: tuple[int, ...]
    default_loading: str
    default_fetch_priority: str | None
    emit_snippets_by_default: bool
    hero_like: bool
    description: str


RECIPES = {
    "hero-banner": RecipeConfig(
        name="hero-banner",
        width=1600,
        height=900,
        aspect_ratio="16:9",
        fit_mode="cover",
        default_accessibility_mode="descriptive",
        default_framing="balanced",
        responsive_by_default=True,
        responsive_widths=(640, 960, 1280, 1600),
        default_loading="eager",
        default_fetch_priority="high",
        emit_snippets_by_default=True,
        hero_like=True,
        description="Wide hero banner with eager-loading defaults.",
    ),
    "blog-cover": RecipeConfig(
        name="blog-cover",
        width=1600,
        height=900,
        aspect_ratio="16:9",
        fit_mode="cover",
        default_accessibility_mode="descriptive",
        default_framing="balanced",
        responsive_by_default=True,
        responsive_widths=(480, 768, 1200, 1600),
        default_loading="lazy",
        default_fetch_priority=None,
        emit_snippets_by_default=True,
        hero_like=True,
        description="Editorial or blog cover image with responsive widths.",
    ),
    "review-hero": RecipeConfig(
        name="review-hero",
        width=1600,
        height=900,
        aspect_ratio="16:9",
        fit_mode="cover",
        default_accessibility_mode="descriptive",
        default_framing="subject",
        responsive_by_default=True,
        responsive_widths=(480, 768, 1200, 1600),
        default_loading="lazy",
        default_fetch_priority=None,
        emit_snippets_by_default=True,
        hero_like=False,
        description="Landscape review artwork tuned for card grids and article headers, with subject-first framing defaults.",
    ),
    "profile-avatar": RecipeConfig(
        name="profile-avatar",
        width=1200,
        height=1200,
        aspect_ratio="1:1",
        fit_mode="cover",
        default_accessibility_mode="descriptive",
        default_framing="balanced",
        responsive_by_default=True,
        responsive_widths=(256, 512, 768, 1200),
        default_loading="lazy",
        default_fetch_priority=None,
        emit_snippets_by_default=True,
        hero_like=False,
        description="Square avatar or thumbnail image.",
    ),
    "card-thumbnail": RecipeConfig(
        name="card-thumbnail",
        width=1200,
        height=1500,
        aspect_ratio="4:5",
        fit_mode="cover",
        default_accessibility_mode="descriptive",
        default_framing="balanced",
        responsive_by_default=True,
        responsive_widths=(320, 480, 768, 1200),
        default_loading="lazy",
        default_fetch_priority=None,
        emit_snippets_by_default=True,
        hero_like=False,
        description="Card or feed art with a 4:5 editorial crop.",
    ),
    "poster": RecipeConfig(
        name="poster",
        width=1200,
        height=1800,
        aspect_ratio="2:3",
        fit_mode="cover",
        default_accessibility_mode="descriptive",
        default_framing="balanced",
        responsive_by_default=False,
        responsive_widths=(400, 800, 1200),
        default_loading="lazy",
        default_fetch_priority=None,
        emit_snippets_by_default=False,
        hero_like=False,
        description="Vertical poster or print-style promo art.",
    ),
    "story-cover": RecipeConfig(
        name="story-cover",
        width=1080,
        height=1920,
        aspect_ratio="9:16",
        fit_mode="cover",
        default_accessibility_mode="descriptive",
        default_framing="balanced",
        responsive_by_default=False,
        responsive_widths=(360, 720, 1080),
        default_loading="lazy",
        default_fetch_priority=None,
        emit_snippets_by_default=False,
        hero_like=False,
        description="Story or reel cover art in a 9:16 crop.",
    ),
    "logo-lockup": RecipeConfig(
        name="logo-lockup",
        width=1200,
        height=900,
        aspect_ratio="4:3",
        fit_mode="contain",
        default_accessibility_mode="logo",
        default_framing="balanced",
        responsive_by_default=True,
        responsive_widths=(320, 640, 900, 1200),
        default_loading="lazy",
        default_fetch_priority=None,
        emit_snippets_by_default=True,
        hero_like=False,
        description="Transparent-safe logo or lockup art that preserves the full composition.",
    ),
    "logo-grid": RecipeConfig(
        name="logo-grid",
        width=640,
        height=480,
        aspect_ratio="4:3",
        fit_mode="contain",
        default_accessibility_mode="decorative",
        default_framing="balanced",
        responsive_by_default=False,
        responsive_widths=(240, 480, 640),
        default_loading="lazy",
        default_fetch_priority=None,
        emit_snippets_by_default=True,
        hero_like=False,
        description="Logo grid or partner badge art with contain sizing and decorative-first accessibility defaults.",
    ),
}


@dataclass(frozen=True)
class MetadataInputs:
    subject: str | None
    context: str | None
    purpose: str | None
    visible_text: str | None
    framing: str | None


@dataclass(frozen=True)
class SeoMetadata:
    slug: str
    alt: str
    title: str
    caption: str
    accessibility_mode: str
    provenance: str


@dataclass(frozen=True)
class ResponsiveAsset:
    path: Path
    src: str
    width: int
    height: int
    bytes: int | None


@dataclass(frozen=True)
class SnippetTarget:
    markup: str


@dataclass(frozen=True)
class SnippetSet:
    enabled: bool
    src: str
    srcset: str | None
    sizes: str | None
    loading: str
    fetch_priority: str | None
    targets: dict[str, SnippetTarget]


@dataclass(frozen=True)
class ProcessResult:
    mode: str
    source_path: Path
    input_format: str
    source_size: int
    output_path: Path
    output_size: int | None
    reduction: float | None
    width: int
    height: int
    metadata_inputs: MetadataInputs
    metadata: SeoMetadata
    usage_overrides: dict[str, SeoMetadata]
    active_usage_key: str | None
    snippets: SnippetSet
    responsive_assets: list[ResponsiveAsset]
    fit_mode: str
    framing: str
    focus_label: str
    focus_x: float
    focus_y: float
    has_transparency: bool
    dry_run: bool


@dataclass(frozen=True)
class ImgTagAudit:
    file: str
    line: int
    component_kind: str
    tag_name: str
    src: str | None
    alt: str | None
    tag_text: str
    has_fill: bool
    has_width: bool
    has_height: bool
    loading: str | None
    decoding: str | None
    has_srcset: bool
    has_sizes: bool


def build_parser() -> argparse.ArgumentParser:
    parser = WebpArgumentParser(
        prog="webp-me-daddy",
        description="Layout-aware image preparation for the web with WebP output, metadata, snippets, and linting.",
    )
    parser.add_argument(
        "--json-errors",
        action="store_true",
        help="Emit machine-readable JSON errors instead of plain stderr text.",
    )
    subparsers = parser.add_subparsers(dest="command", parser_class=WebpArgumentParser)
    subparsers.required = True

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Prepare one source image with a semantic recipe.",
    )
    prepare_parser.add_argument(
        "--json-errors",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    prepare_parser.add_argument("input", type=Path, help="Source image file to process.")
    add_processing_arguments(prepare_parser, include_batch_controls=False)

    batch_parser = subparsers.add_parser(
        "batch",
        help="Process all supported images in a directory.",
    )
    batch_parser.add_argument(
        "--json-errors",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    batch_parser.add_argument("input", type=Path, help="Directory containing source images.")
    add_processing_arguments(batch_parser, include_batch_controls=True)
    batch_parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search nested folders inside the batch directory.",
    )
    batch_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm that the batch run should write files when not using --dry-run.",
    )
    batch_parser.add_argument(
        "--proof-contact-sheet",
        type=Path,
        help="Optional PNG path for a visual proof contact sheet covering the whole batch.",
    )

    lint_parser = subparsers.add_parser(
        "lint",
        help="Lint a v2 manifest for blocking and warning-level image issues.",
    )
    lint_parser.add_argument(
        "--json-errors",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    lint_parser.add_argument("manifest", type=Path, help="Manifest JSON generated by Webp Me Daddy v2.")
    lint_parser.add_argument(
        "--max-hero-kb",
        type=int,
        default=DEFAULT_HERO_KB,
        help=f"Warn when hero-like recipes exceed this many KB. Defaults to {DEFAULT_HERO_KB}.",
    )
    lint_parser.add_argument(
        "--max-standard-kb",
        type=int,
        default=DEFAULT_STANDARD_KB,
        help=f"Warn when non-hero recipes exceed this many KB. Defaults to {DEFAULT_STANDARD_KB}.",
    )
    lint_parser.add_argument(
        "--strict",
        "--strict-a11y",
        dest="strict",
        action="store_true",
        help="Treat extra accessibility and SEO metadata issues as blocking failures.",
    )

    audit_parser = subparsers.add_parser(
        "audit",
        help="Audit a codebase for live image usage, oversized formats, and markup gaps.",
    )
    audit_parser.add_argument(
        "--json-errors",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    audit_parser.add_argument("root", type=Path, help="Project root containing src/ and public/ folders.")
    audit_parser.add_argument(
        "--src-dir",
        type=Path,
        help="Optional source directory. Defaults to <root>/src.",
    )
    audit_parser.add_argument(
        "--public-dir",
        type=Path,
        help="Optional public/assets directory. Defaults to <root>/public.",
    )
    audit_parser.add_argument(
        "--json",
        type=Path,
        help="Optional path for a JSON audit report.",
    )
    audit_parser.add_argument(
        "--apply-autofix",
        action="store_true",
        help="Apply the low-risk codemod patch suggestions for autofixable <img> tags.",
    )
    audit_parser.add_argument(
        "--emit-fix-plan",
        action="store_true",
        help="Emit a structured fix plan with suggested Webp Me Daddy commands for the audit findings.",
    )

    handoff_parser = subparsers.add_parser(
        "seo-handoff",
        help="Preview or apply an SEO-generated image remediation handoff JSON.",
    )
    handoff_parser.add_argument(
        "--json-errors",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    handoff_parser.add_argument("handoff", type=Path, help="SEO handoff JSON generated by image_handoff.py.")
    handoff_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the generated image outputs without writing files.",
    )
    handoff_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm that the handoff should write files when not using --dry-run.",
    )
    handoff_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing existing generated image outputs and sidecars.",
    )
    handoff_parser.add_argument(
        "--write-sidecar",
        action="store_true",
        help="Compatibility flag for SEO workflows. Sidecars are already written for applied handoff items.",
    )
    handoff_parser.add_argument(
        "--json",
        type=Path,
        help="Optional path for a JSON apply report.",
    )

    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="Preview or delete unused public assets discovered by the audit rules.",
    )
    cleanup_parser.add_argument(
        "--json-errors",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    cleanup_parser.add_argument("root", type=Path, help="Project root containing src/ and public/ folders.")
    cleanup_parser.add_argument(
        "--src-dir",
        type=Path,
        help="Optional source directory. Defaults to <root>/src.",
    )
    cleanup_parser.add_argument(
        "--public-dir",
        type=Path,
        help="Optional public/assets directory. Defaults to <root>/public.",
    )
    cleanup_parser.add_argument(
        "--json",
        type=Path,
        help="Optional path for a JSON cleanup report.",
    )
    cleanup_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview which unused public assets would be deleted without removing them.",
    )
    cleanup_parser.add_argument(
        "--yes",
        action="store_true",
        help="Delete the unused public assets discovered by the cleanup scan.",
    )

    snippets_parser = subparsers.add_parser(
        "snippets",
        help="Generate page-specific snippet markup from a v2 sidecar and usage key.",
    )
    snippets_parser.add_argument(
        "--json-errors",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    snippets_parser.add_argument("sidecar", type=Path, help="Per-image sidecar JSON generated by Webp Me Daddy v2.")
    snippets_parser.add_argument(
        "--usage-key",
        help="Optional named usage override to apply before generating snippets.",
    )
    snippets_parser.add_argument(
        "--target",
        choices=("all", "html", "react", "next", "astro"),
        default="all",
        help="Emit one snippet target or all available targets. Defaults to all.",
    )
    snippets_parser.add_argument(
        "--json",
        type=Path,
        help="Optional path for a JSON snippet export.",
    )

    proof_parser = subparsers.add_parser(
        "proof",
        help="Render a light/dark proof sheet for a final asset or sidecar.",
    )
    proof_parser.add_argument(
        "--json-errors",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    proof_parser.add_argument("input", type=Path, help="Output image or v2 sidecar to preview.")
    proof_parser.add_argument(
        "--usage-key",
        help="Optional usage override to apply when the proof source is a sidecar or has a sibling sidecar.",
    )
    proof_parser.add_argument(
        "--output",
        type=Path,
        help="Optional PNG path for the rendered proof sheet. Defaults beside the source asset.",
    )
    proof_parser.add_argument(
        "--surfaces",
        help="Comma-separated surface list: dark,light,checker. Defaults to dark+light and adds checker when the image has transparency.",
    )
    proof_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing proof PNG if one already exists.",
    )

    animate_parser = subparsers.add_parser(
        "animate",
        help="Hand GIF or animated WebP inputs to the transparent loop optimizer.",
    )
    animate_parser.add_argument(
        "--json-errors",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    animate_parser.add_argument("input", type=Path, help="Animated GIF or animated WebP source.")
    animate_parser.add_argument("output", type=Path, help="Output WebP path for the optimized loop or still.")
    animate_parser.add_argument(
        "--mode",
        choices=("animated", "still"),
        default="animated",
        help="Choose whether to create an animated loop or a still extraction. Defaults to animated.",
    )
    animate_parser.add_argument("--size", type=int, default=220, help="Maximum output dimension in pixels.")
    animate_parser.add_argument(
        "--threshold",
        type=int,
        default=10,
        help="Near-black alpha threshold. Lower values preserve more dark detail.",
    )
    animate_parser.add_argument(
        "--loop-start",
        type=int,
        default=None,
        help="Optional inclusive first frame index for trimming to a cleaner cycle.",
    )
    animate_parser.add_argument(
        "--loop-end",
        type=int,
        default=None,
        help="Optional inclusive last frame index for trimming to a cleaner cycle.",
    )
    animate_parser.add_argument(
        "--speed-scale",
        type=float,
        default=1.12,
        help="Playback scale. Greater than 1 slows playback, less than 1 speeds it up.",
    )
    animate_parser.add_argument(
        "--midpoint-frames",
        type=int,
        default=1,
        help="Number of interpolated frames inserted between adjacent source frames.",
    )
    animate_parser.add_argument(
        "--bridge-frames",
        type=int,
        default=8,
        help="Number of eased bridge frames appended from the last frame back to the first.",
    )
    animate_parser.add_argument(
        "--bridge-duration",
        type=int,
        default=38,
        help="Duration in milliseconds for each bridge frame.",
    )
    animate_parser.add_argument(
        "--quality",
        type=int,
        default=80,
        help="Animated WebP quality from 0-100.",
    )
    animate_parser.add_argument(
        "--method",
        type=int,
        default=0,
        help="Animated WebP encoding effort from 0-6.",
    )
    animate_parser.add_argument(
        "--still-frame",
        type=int,
        default=0,
        help="Frame index to extract when using --mode still.",
    )
    animate_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing animated output file.",
    )
    return parser


def add_processing_arguments(parser: argparse.ArgumentParser, include_batch_controls: bool) -> None:
    parser.add_argument(
        "--recipe",
        choices=sorted(RECIPES),
        required=True,
        help="Semantic recipe controlling crop, sizes, snippet defaults, and analysis.",
    )
    parser.add_argument("--width", type=int, help="Override the recipe width in pixels.")
    parser.add_argument("--height", type=int, help="Override the recipe height in pixels.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for generated files. Defaults to the source directory.",
    )
    parser.add_argument(
        "--focus-preset",
        choices=sorted(FOCUS_PRESETS),
        help="Convenience crop focus point such as center, top, or top-right.",
    )
    parser.add_argument(
        "--focus-x",
        type=float,
        help="Normalized crop focus on the x-axis from 0.0 (left) to 1.0 (right).",
    )
    parser.add_argument(
        "--focus-y",
        type=float,
        help="Normalized crop focus on the y-axis from 0.0 (top) to 1.0 (bottom).",
    )
    parser.add_argument(
        "--fit-mode",
        choices=("cover", "contain"),
        help="Override the recipe fit mode. Use contain for logos or artwork that should not be cropped.",
    )
    parser.add_argument(
        "--framing",
        choices=("auto", "subject", "text", "balanced"),
        default="auto",
        help="Hint whether the crop should prioritize the subject, visible text, or a balanced composition. Auto uses recipe defaults and portrait-to-landscape heuristics.",
    )
    if not include_batch_controls:
        parser.add_argument(
            "--slug",
            help="SEO-friendly base file name. Defaults to the source file name slugified.",
        )
    parser.add_argument(
        "--public-root",
        type=Path,
        help="Optional public folder root used to build src paths like /images/example.webp.",
    )
    parser.add_argument("--seo-subject", help="Primary thing shown in the image, used to build metadata text.")
    parser.add_argument("--seo-context", help="Short context like brand, page, or campaign name for metadata text.")
    parser.add_argument("--seo-purpose", help="Short intent like hero banner, blog cover, or profile avatar.")
    parser.add_argument(
        "--accessibility-mode",
        choices=("decorative", "logo", "descriptive", "text-bearing"),
        help="Accessibility intent for metadata generation.",
    )
    parser.add_argument(
        "--visible-text",
        help='Visible text to include when accessibility mode is text-bearing, for example "Join the adventure".',
    )
    parser.add_argument("--usage-key", help="Optional page or placement key for a usage-level metadata override, for example home.hero or sponsor.badge.")
    parser.add_argument("--usage-alt", help="Usage-specific alt text override for the active --usage-key.")
    parser.add_argument("--usage-title", help="Usage-specific title override for the active --usage-key.")
    parser.add_argument("--usage-caption", help="Usage-specific caption override for the active --usage-key.")
    parser.add_argument("--quality", type=int, default=82, help="WebP quality from 1-100. Defaults to 82.")
    parser.add_argument(
        "--lossless",
        action="store_true",
        help="Use lossless WebP output, useful for graphics with sharp edges.",
    )
    parser.add_argument(
        "--reencode-webp",
        action="store_true",
        help="Re-save existing WebP inputs instead of metadata-only handling.",
    )
    parser.add_argument(
        "--allow-upscale",
        action="store_true",
        help="Permit outputs larger than the source image dimensions.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing output with the same file name.")
    responsive_group = parser.add_mutually_exclusive_group()
    responsive_group.add_argument("--responsive", dest="responsive_mode", action="store_const", const="always", help="Always generate responsive width variants.")
    responsive_group.add_argument("--no-responsive", dest="responsive_mode", action="store_const", const="never", help="Disable responsive width variants even if the recipe would normally generate them.")
    parser.set_defaults(responsive_mode="auto")
    parser.add_argument("--responsive-widths", help="Comma-separated widths for responsive variants, for example 480,768,1200.")
    parser.add_argument("--sizes", help='Sizes attribute for responsive snippets. Defaults to "100vw" when responsive mode is enabled.')
    parser.add_argument("--loading", choices=("auto", "lazy", "eager"), default="auto", help="Loading strategy for generated snippets.")
    parser.add_argument("--fetch-priority", choices=("auto", "high", "low", "none"), default="auto", help="Fetch priority for generated snippets.")
    snippet_group = parser.add_mutually_exclusive_group()
    snippet_group.add_argument("--emit-snippets", dest="snippet_mode", action="store_const", const="always", help="Always emit snippet markup even when the recipe defaults to metadata-only output.")
    snippet_group.add_argument("--no-snippets", dest="snippet_mode", action="store_const", const="never", help="Suppress snippet markup even when the recipe normally emits it.")
    parser.set_defaults(snippet_mode="auto")
    parser.add_argument("--write-sidecar", action="store_true", help="Write a JSON sidecar with the v2 schema next to the output image.")
    parser.add_argument("--manifest", type=Path, help="Write a v2 manifest summarizing the run.")
    parser.add_argument("--dry-run", action="store_true", help="Preview file names, metadata, and snippets without writing files.")


def normalize_legacy_argv(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    first = argv[0]
    if first in SUBCOMMANDS or first in {"-h", "--help"}:
        return argv

    translated: list[str] = ["batch" if "--batch" in argv else "prepare"]
    mode_from_flags: str | None = None
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--batch":
            index += 1
            continue
        if arg == "--preset":
            if index + 1 >= len(argv):
                raise UsageError("Legacy --preset requires a value.")
            recipe = LEGACY_PRESET_TO_RECIPE.get(argv[index + 1], argv[index + 1])
            translated.extend(["--recipe", recipe])
            index += 2
            continue
        if arg in LEGACY_FLAG_TO_MODE:
            mode_from_flags = LEGACY_FLAG_TO_MODE[arg]
            index += 1
            continue
        translated.append(arg)
        index += 1

    if mode_from_flags:
        translated.extend(["--accessibility-mode", mode_from_flags])
    if "--recipe" not in translated:
        translated[1:1] = ["--recipe", "profile-avatar"]
    return translated


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    normalized_argv = normalize_legacy_argv(list(sys.argv[1:] if argv is None else argv))
    parser = build_parser()
    return parser.parse_args(normalized_argv)


def normalize_args(args: argparse.Namespace) -> argparse.Namespace:
    if getattr(args, "command", None) == "lint":
        if args.max_hero_kb <= 0 or args.max_standard_kb <= 0:
            raise UsageError("Lint thresholds must be positive integers.")
        return args
    if getattr(args, "command", None) == "snippets":
        args.sidecar = args.sidecar.resolve()
        if args.json:
            args.json = args.json.resolve()
        return args
    if getattr(args, "command", None) == "animate":
        args.input = args.input.resolve()
        args.output = args.output.resolve()
        if not args.input.exists():
            raise UsageError(f"Animated source not found: {args.input}")
        if args.output.suffix.lower() != ".webp":
            raise UsageError("Animated output must use a .webp extension.")
        if not TRANSPARENT_GIF_SCRIPT.exists():
            raise UsageError(
                "The `animate` command needs the companion transparent-gif-loop tool, "
                f"which was not found at: {TRANSPARENT_GIF_SCRIPT}\n"
                "Clone it next to this repo:\n"
                "  git clone https://github.com/BrinShadewater/Transparent-Gif-Loop-Skill\n"
                "or point TRANSPARENT_GIF_LOOP_DIR at an existing checkout."
            )
        if args.output.exists() and not args.overwrite:
            raise UsageError(f"Animated output already exists: {args.output}. Use --overwrite to replace it.")
        if args.size <= 0:
            raise UsageError("--size must be a positive integer.")
        if not 0 <= args.threshold <= 255:
            raise UsageError("--threshold must be between 0 and 255.")
        if args.loop_start is not None and args.loop_start < 0:
            raise UsageError("--loop-start must be 0 or greater.")
        if args.loop_end is not None and args.loop_end < 0:
            raise UsageError("--loop-end must be 0 or greater.")
        if args.loop_start is not None and args.loop_end is not None and args.loop_start > args.loop_end:
            raise UsageError("--loop-start cannot be greater than --loop-end.")
        if args.speed_scale <= 0:
            raise UsageError("--speed-scale must be greater than 0.")
        if args.midpoint_frames < 0 or args.bridge_frames < 0 or args.bridge_duration < 0:
            raise UsageError("--midpoint-frames, --bridge-frames, and --bridge-duration must be 0 or greater.")
        if not 0 <= args.quality <= 100:
            raise UsageError("--quality must be between 0 and 100.")
        if not 0 <= args.method <= 6:
            raise UsageError("--method must be between 0 and 6.")
        if args.still_frame < 0:
            raise UsageError("--still-frame must be 0 or greater.")
        return args
    if getattr(args, "command", None) == "proof":
        args.input = args.input.resolve()
        if not args.input.exists():
            raise UsageError(f"Proof source not found: {args.input}")
        if args.output:
            args.output = args.output.resolve()
            if args.output.suffix.lower() != ".png":
                raise UsageError("Proof output must use a .png extension.")
        return args
    if getattr(args, "command", None) == "seo-handoff":
        args.handoff = args.handoff.resolve()
        if not args.handoff.exists():
            raise HandoffError(f"SEO handoff not found: {args.handoff}")
        if args.json:
            args.json = args.json.resolve()
        if not args.dry_run and not args.yes:
            raise UsageError("SEO handoff runs require --dry-run or explicit confirmation with --yes.")
        return args
    if getattr(args, "command", None) in {"audit", "cleanup"}:
        root = args.root.resolve()
        args.root = root
        args.src_dir = (args.src_dir.resolve() if args.src_dir else root / "src")
        args.public_dir = (args.public_dir.resolve() if args.public_dir else root / "public")
        if not args.src_dir.exists():
            raise AuditError(f"Source directory not found: {args.src_dir}")
        if not args.public_dir.exists():
            raise AuditError(f"Public directory not found: {args.public_dir}")
        if args.command == "cleanup" and not args.dry_run and not args.yes:
            raise UsageError("Cleanup runs require --dry-run or explicit confirmation with --yes.")
        return args

    if (args.usage_alt or args.usage_title or args.usage_caption) and not args.usage_key:
        raise UsageError("--usage-alt, --usage-title, and --usage-caption require --usage-key.")
    if args.visible_text and args.accessibility_mode != "text-bearing":
        raise UsageError("--visible-text requires --accessibility-mode text-bearing.")
    for label, value in (("focus-x", args.focus_x), ("focus-y", args.focus_y)):
        if value is not None and not 0.0 <= value <= 1.0:
            raise UsageError(f"--{label} must be between 0.0 and 1.0.")
    if not 1 <= args.quality <= 100:
        raise UsageError("--quality must be between 1 and 100.")
    if args.responsive_widths or args.sizes:
        if args.responsive_mode == "never":
            raise UsageError("--responsive-widths and --sizes cannot be used with --no-responsive.")
        args.responsive_mode = "always"
    if args.command == "batch" and not args.dry_run and not args.yes:
        raise UsageError("Batch runs require --dry-run or explicit confirmation with --yes.")
    if getattr(args, "proof_contact_sheet", None):
        args.proof_contact_sheet = args.proof_contact_sheet.resolve()
        if args.proof_contact_sheet.suffix.lower() != ".png":
            raise UsageError("Proof contact sheet output must use a .png extension.")
    return args


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower().replace("&", " and ")
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text)
    slug = re.sub(r"-{2,}", "-", ascii_text).strip("-")
    return slug or "image"


def collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def title_case_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def build_dimensions(recipe: RecipeConfig, args: argparse.Namespace) -> tuple[int, int]:
    width = args.width or recipe.width
    height = args.height or recipe.height
    if width <= 0 or height <= 0:
        raise UsageError("Width and height must be positive integers.")
    return width, height


def cap_dimensions_to_source(
    requested_width: int,
    requested_height: int,
    source_width: int,
    source_height: int,
    allow_upscale: bool,
    fit_mode: str,
) -> tuple[int, int]:
    if allow_upscale or fit_mode == "contain":
        return requested_width, requested_height
    return min(requested_width, source_width), min(requested_height, source_height)


def resolve_fit_mode(recipe: RecipeConfig, args: argparse.Namespace) -> str:
    return args.fit_mode or recipe.fit_mode


def open_image(path: Path) -> Image.Image:
    if not path.exists():
        raise WebpMeDaddyError(f"Input file not found: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise UsageError("Input must be a PNG, JPG, JPEG, or WebP file.")
    with Image.open(path) as image:
        if getattr(image, "n_frames", 1) > 1:
            raise UsageError(
                "Animated assets are not supported by the still-image pipeline. Use `webp-me-daddy animate <input> <output>` for GIF/WebP loops."
            )
        image = ImageOps.exif_transpose(image)
        return image.convert("RGBA")


def resolve_framing(
    recipe: RecipeConfig,
    args: argparse.Namespace,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
    fit_mode: str,
) -> str:
    if args.framing != "auto":
        return args.framing
    if (
        fit_mode == "cover"
        and source_height > source_width
        and target_width > target_height
    ):
        return "subject"
    return recipe.default_framing


def framing_focus_defaults(
    framing: str,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
    fit_mode: str,
) -> tuple[float, float]:
    if fit_mode != "cover":
        return (0.5, 0.5)
    if source_height > source_width and target_width > target_height:
        mapping = {
            "subject": (0.5, 0.34),
            "text": (0.5, 0.72),
            "balanced": (0.5, 0.5),
        }
        return mapping.get(framing, (0.5, 0.5))
    return (0.5, 0.5)


def resolve_focus_point(
    recipe: RecipeConfig,
    args: argparse.Namespace,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
    fit_mode: str,
) -> tuple[str, str, float, float]:
    framing = resolve_framing(
        recipe=recipe,
        args=args,
        source_width=source_width,
        source_height=source_height,
        target_width=target_width,
        target_height=target_height,
        fit_mode=fit_mode,
    )
    focus_x, focus_y = framing_focus_defaults(
        framing=framing,
        source_width=source_width,
        source_height=source_height,
        target_width=target_width,
        target_height=target_height,
        fit_mode=fit_mode,
    )
    if args.focus_x is not None:
        focus_x = args.focus_x
    if args.focus_y is not None:
        focus_y = args.focus_y

    resolved_x = clamp(focus_x, 0.0, 1.0)
    resolved_y = clamp(focus_y, 0.0, 1.0)
    if args.focus_preset:
        label = args.focus_preset
    elif args.focus_x is not None or args.focus_y is not None:
        label = "custom"
    elif resolved_x == 0.5 and resolved_y == 0.5:
        label = "center"
    else:
        label = f"framing-{framing}"
    return framing, label, resolved_x, resolved_y


def resolve_accessibility_mode(recipe: RecipeConfig, args: argparse.Namespace) -> str:
    return args.accessibility_mode or recipe.default_accessibility_mode


def build_seo_metadata(
    slug: str,
    metadata_inputs: MetadataInputs,
    accessibility_mode: str,
) -> SeoMetadata:
    if accessibility_mode == "decorative":
        return SeoMetadata(
            slug=slug,
            alt="",
            title="",
            caption="",
            accessibility_mode=accessibility_mode,
            provenance="heuristic",
        )

    subject = (
        collapse_spaces(metadata_inputs.subject)
        if metadata_inputs.subject
        else title_case_from_slug(slug)
    )
    context = collapse_spaces(metadata_inputs.context) if metadata_inputs.context else ""
    purpose = collapse_spaces(metadata_inputs.purpose) if metadata_inputs.purpose else ""
    visible = collapse_spaces(metadata_inputs.visible_text) if metadata_inputs.visible_text else ""

    if accessibility_mode == "logo" and "logo" not in subject.lower():
        subject = f"{subject} logo"

    alt = subject
    if accessibility_mode == "text-bearing":
        if visible:
            alt = f'{alt}. Text reads "{visible}".'
        else:
            alt = f"{alt} with text"
    elif accessibility_mode != "logo" and context:
        alt = f"{alt} for {context}"

    title = subject if not purpose else f"{subject} - {purpose}"

    caption_parts = [subject]
    if purpose:
        caption_parts.append(f"used as a {purpose}")
    if context:
        caption_parts.append(f"for {context}")
    caption = " ".join(caption_parts)
    if accessibility_mode == "text-bearing":
        if visible:
            caption = f'{caption}. Text reads "{visible}".'
        else:
            caption = f"{caption}. Contains text."

    return SeoMetadata(
        slug=slug,
        alt=alt,
        title=title,
        caption=caption,
        accessibility_mode=accessibility_mode,
        provenance="heuristic",
    )


def build_usage_overrides(
    base_metadata: SeoMetadata,
    args: argparse.Namespace,
) -> tuple[dict[str, SeoMetadata], str | None, SeoMetadata]:
    if not args.usage_key:
        return {}, None, base_metadata

    usage_metadata = SeoMetadata(
        slug=base_metadata.slug,
        alt=collapse_spaces(args.usage_alt) if args.usage_alt else base_metadata.alt,
        title=collapse_spaces(args.usage_title) if args.usage_title else base_metadata.title,
        caption=collapse_spaces(args.usage_caption) if args.usage_caption else base_metadata.caption,
        accessibility_mode=base_metadata.accessibility_mode,
        provenance="manual" if any((args.usage_alt, args.usage_title, args.usage_caption)) else "contextual",
    )
    return {args.usage_key: usage_metadata}, args.usage_key, usage_metadata


def render_image(
    source: Image.Image,
    output_path: Path,
    width: int,
    height: int,
    fit_mode: str,
    allow_upscale: bool,
    focus_x: float,
    focus_y: float,
    quality: int,
    lossless: bool,
    dry_run: bool,
) -> int | None:
    if output_path.exists() and not dry_run:
        try:
            output_path.unlink()
        except OSError:
            pass  # FUSE filesystem; overwrite in-place
    if dry_run:
        return None

    fitted = render_processed_preview(
        source=source,
        width=width,
        height=height,
        fit_mode=fit_mode,
        allow_upscale=allow_upscale,
        focus_x=focus_x,
        focus_y=focus_y,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fitted.save(
        output_path,
        format="WEBP",
        quality=quality,
        method=6,
        lossless=lossless,
    )
    return output_path.stat().st_size


def render_processed_preview(
    source: Image.Image,
    width: int,
    height: int,
    fit_mode: str,
    allow_upscale: bool,
    focus_x: float,
    focus_y: float,
) -> Image.Image:
    if fit_mode == "contain":
        source_for_canvas = source
        if not allow_upscale and source.width <= width and source.height <= height:
            contained = source_for_canvas.copy()
        else:
            contained = ImageOps.contain(source_for_canvas, (width, height), method=RESAMPLE)
        fitted = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        offset_x = max(0, (width - contained.width) // 2)
        offset_y = max(0, (height - contained.height) // 2)
        fitted.paste(contained, (offset_x, offset_y), contained)
    else:
        fitted = ImageOps.fit(
            source,
            (width, height),
            method=RESAMPLE,
            centering=(focus_x, focus_y),
        )
    return fitted


def find_public_root(path: Path) -> Path | None:
    for candidate in [path, *path.parents]:
        if candidate.name.lower() == "public":
            return candidate
    return None


def build_public_src(output_path: Path, public_root: Path | None) -> str:
    root = public_root.resolve() if public_root else find_public_root(output_path)
    if root is not None:
        try:
            relative = output_path.resolve().relative_to(root)
            return "/" + relative.as_posix()
        except ValueError:
            pass
    return output_path.name


def resolve_loading(recipe: RecipeConfig, args: argparse.Namespace) -> tuple[str, str | None]:
    loading = recipe.default_loading if args.loading == "auto" else args.loading
    if args.fetch_priority == "auto":
        fetch_priority = recipe.default_fetch_priority
    elif args.fetch_priority == "none":
        fetch_priority = None
    else:
        fetch_priority = args.fetch_priority
    return loading, fetch_priority


def jsx_literal(value: str) -> str:
    return "{" + json.dumps(value) + "}"


def build_attr_string(name: str, value: str) -> str:
    return f'{name}="{html.escape(value, quote=True)}"'


def build_variant_path(output_path: Path, width: int) -> Path:
    return output_path.with_name(f"{output_path.stem}-{width}w{output_path.suffix}")


def resolve_responsive_enabled(recipe: RecipeConfig, args: argparse.Namespace) -> bool:
    if args.responsive_mode == "always":
        return True
    if args.responsive_mode == "never":
        return False
    return recipe.responsive_by_default


def resolve_snippet_enabled(recipe: RecipeConfig, args: argparse.Namespace) -> bool:
    if args.snippet_mode == "always":
        return True
    if args.snippet_mode == "never":
        return False
    return recipe.emit_snippets_by_default


def parse_responsive_widths(
    widths_text: str | None,
    base_width: int,
    recipe: RecipeConfig,
) -> list[int]:
    if widths_text:
        try:
            candidates = [int(part.strip()) for part in widths_text.split(",") if part.strip()]
        except ValueError as exc:
            raise UsageError("Responsive widths must be comma-separated integers.") from exc
    else:
        candidates = list(recipe.responsive_widths)

    filtered = sorted({width for width in candidates if 0 < width <= base_width})
    if base_width not in filtered:
        filtered.append(base_width)
    return sorted(filtered)


def serialize_srcset(assets: list[ResponsiveAsset]) -> str | None:
    if len(assets) < 2:
        return None
    ordered = sorted(assets, key=lambda asset: asset.width)
    return ", ".join(f"{asset.src} {asset.width}w" for asset in ordered)


def build_snippet_targets(
    src: str,
    metadata: SeoMetadata,
    width: int,
    height: int,
    srcset: str | None,
    effective_sizes: str | None,
    loading: str,
    fetch_priority: str | None,
) -> dict[str, SnippetTarget]:
    html_attrs = [
        build_attr_string("src", src),
        build_attr_string("alt", metadata.alt),
        build_attr_string("width", str(width)),
        build_attr_string("height", str(height)),
    ]
    react_attrs = [
        f"src={jsx_literal(src)}",
        f"alt={jsx_literal(metadata.alt)}",
        f"width={{{width}}}",
        f"height={{{height}}}",
    ]

    if metadata.title:
        html_attrs.append(build_attr_string("title", metadata.title))
        react_attrs.append(f"title={jsx_literal(metadata.title)}")
    if srcset:
        html_attrs.append(build_attr_string("srcset", srcset))
        react_attrs.append(f"srcSet={jsx_literal(srcset)}")
    if effective_sizes:
        html_attrs.append(build_attr_string("sizes", effective_sizes))
        react_attrs.append(f"sizes={jsx_literal(effective_sizes)}")

    html_attrs.append(build_attr_string("loading", loading))
    html_attrs.append(build_attr_string("decoding", "async"))
    react_attrs.append(f"loading={jsx_literal(loading)}")
    react_attrs.append(f"decoding={jsx_literal('async')}")

    if fetch_priority:
        html_attrs.append(build_attr_string("fetchpriority", fetch_priority))
        react_attrs.append(f"fetchPriority={jsx_literal(fetch_priority)}")

    if metadata.accessibility_mode == "decorative":
        html_attrs.append(build_attr_string("aria-hidden", "true"))
        html_attrs.append(build_attr_string("role", "presentation"))
        react_attrs.append("aria-hidden={true}")
        react_attrs.append(f"role={jsx_literal('presentation')}")

    next_attrs = [
        f"src={jsx_literal(src)}",
        f"alt={jsx_literal(metadata.alt)}",
        f"width={{{width}}}",
        f"height={{{height}}}",
    ]
    astro_attrs = [
        build_attr_string("src", src),
        build_attr_string("alt", metadata.alt),
        build_attr_string("width", str(width)),
        build_attr_string("height", str(height)),
    ]
    if metadata.title:
        next_attrs.append(f"title={jsx_literal(metadata.title)}")
        astro_attrs.append(build_attr_string("title", metadata.title))
    if effective_sizes:
        next_attrs.append(f"sizes={jsx_literal(effective_sizes)}")
        astro_attrs.append(build_attr_string("sizes", effective_sizes))
    if loading == "eager":
        next_attrs.append("priority")
    else:
        next_attrs.append(f"loading={jsx_literal(loading)}")
    next_attrs.append(f"decoding={jsx_literal('async')}")
    astro_attrs.append(build_attr_string("loading", loading))
    astro_attrs.append(build_attr_string("decoding", "async"))
    if fetch_priority:
        astro_attrs.append(build_attr_string("fetchpriority", fetch_priority))
        if loading != "eager":
            next_attrs.append(f"fetchPriority={jsx_literal(fetch_priority)}")
    if metadata.accessibility_mode == "decorative":
        astro_attrs.append(build_attr_string("aria-hidden", "true"))
        astro_attrs.append(build_attr_string("role", "presentation"))
        next_attrs.append("aria-hidden={true}")
        next_attrs.append(f"role={jsx_literal('presentation')}")

    return {
        "html": SnippetTarget(markup="<img " + " ".join(html_attrs) + " />"),
        "react": SnippetTarget(markup="<img " + " ".join(react_attrs) + " />"),
        "next": SnippetTarget(markup='import Image from "next/image";\n\n' + "<Image " + " ".join(next_attrs) + " />"),
        "astro": SnippetTarget(markup="<img " + " ".join(astro_attrs) + " />"),
    }


def build_snippets(
    output_path: Path,
    metadata: SeoMetadata,
    width: int,
    height: int,
    public_root: Path | None,
    loading: str,
    fetch_priority: str | None,
    sizes: str | None,
    responsive_assets: list[ResponsiveAsset],
    enabled: bool,
) -> SnippetSet:
    src = build_public_src(output_path, public_root)
    srcset = serialize_srcset(responsive_assets)
    effective_sizes = sizes if srcset else None
    if srcset and not effective_sizes:
        effective_sizes = "100vw"

    targets: dict[str, SnippetTarget] = {}
    if enabled:
        targets = build_snippet_targets(
            src=src,
            metadata=metadata,
            width=width,
            height=height,
            srcset=srcset,
            effective_sizes=effective_sizes,
            loading=loading,
            fetch_priority=fetch_priority,
        )

    return SnippetSet(
        enabled=enabled,
        src=src,
        srcset=srcset,
        sizes=effective_sizes,
        loading=loading,
        fetch_priority=fetch_priority,
        targets=targets,
    )


def iter_source_paths(input_path: Path, recursive: bool) -> list[Path]:
    resolved = input_path.resolve()
    if not resolved.is_dir():
        raise UsageError("Batch input must be a directory.")
    pattern = "**/*" if recursive else "*"
    return sorted(
        path
        for path in resolved.glob(pattern)
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def collapse_batch_paths(
    source_paths: list[Path],
    overwrite: bool,
    reencode_webp: bool,
) -> list[Path]:
    if overwrite or reencode_webp:
        return source_paths

    grouped: dict[tuple[Path, str], list[Path]] = {}
    for path in source_paths:
        key = (path.parent, slugify(path.stem))
        grouped.setdefault(key, []).append(path)

    collapsed: list[Path] = []
    for _, paths in sorted(grouped.items(), key=lambda item: (str(item[0][0]), item[0][1])):
        webp_path = next((path for path in paths if path.suffix.lower() == ".webp"), None)
        if webp_path is not None:
            collapsed.append(webp_path)
        else:
            collapsed.extend(sorted(paths))
    return collapsed


def resolve_output_path(
    source_path: Path,
    args: argparse.Namespace,
    slug: str,
) -> tuple[Path, bool]:
    if source_path.suffix.lower() == ".webp" and not args.reencode_webp:
        return source_path, False
    output_dir = args.output_dir.resolve() if args.output_dir else source_path.parent
    return output_dir / f"{slug}.webp", True


def ensure_writeable(path: Path, overwrite: bool, dry_run: bool) -> None:
    if path.exists() and not overwrite:
        raise WebpMeDaddyError(
            f"Output already exists: {path}. Use --overwrite to replace it."
        )
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)


def build_responsive_assets(
    image: Image.Image,
    output_path: Path,
    base_width: int,
    base_height: int,
    base_output_size: int | None,
    fit_mode: str,
    allow_upscale: bool,
    focus_x: float,
    focus_y: float,
    widths: list[int],
    args: argparse.Namespace,
) -> list[ResponsiveAsset]:
    assets: list[ResponsiveAsset] = []
    for width in widths:
        height = max(1, round(width * base_height / base_width))
        if width == base_width:
            asset_path = output_path
            asset_size = base_output_size
        else:
            asset_path = build_variant_path(output_path, width)
            ensure_writeable(asset_path, args.overwrite, args.dry_run)
            asset_size = render_image(
                source=image,
                output_path=asset_path,
                width=width,
                height=height,
                fit_mode=fit_mode,
                allow_upscale=allow_upscale,
                focus_x=focus_x,
                focus_y=focus_y,
                quality=args.quality,
                lossless=args.lossless,
                dry_run=args.dry_run,
            )
        assets.append(
            ResponsiveAsset(
                path=asset_path,
                src=build_public_src(asset_path, args.public_root),
                width=width,
                height=height,
                bytes=asset_size,
            )
        )
    return assets


def process_one(
    source_path: Path,
    recipe: RecipeConfig,
    args: argparse.Namespace,
) -> ProcessResult:
    source_path = source_path.resolve()
    slug = slugify(getattr(args, "slug", None) or source_path.stem)
    output_path, writes_base_image = resolve_output_path(source_path, args, slug)

    metadata_inputs = MetadataInputs(
        subject=collapse_spaces(args.seo_subject) if args.seo_subject else None,
        context=collapse_spaces(args.seo_context) if args.seo_context else None,
        purpose=collapse_spaces(args.seo_purpose) if args.seo_purpose else None,
        visible_text=collapse_spaces(args.visible_text) if args.visible_text else None,
        framing=None,
    )

    source_size = source_path.stat().st_size
    source_format = source_path.suffix.lower().lstrip(".")
    fit_mode = resolve_fit_mode(recipe, args)

    image_path = source_path
    if writes_base_image and output_path.exists() and not args.overwrite:
        if args.command == "batch" and output_path.suffix.lower() == ".webp":
            writes_base_image = False
            image_path = output_path
        else:
            raise WebpMeDaddyError(
                f"Output already exists: {output_path}. Use --overwrite to replace it."
            )

    image = open_image(image_path)
    source_has_transparency = has_transparency(image)
    requested_width, requested_height = build_dimensions(recipe, args)
    width, height = cap_dimensions_to_source(
        requested_width=requested_width,
        requested_height=requested_height,
        source_width=image.width,
        source_height=image.height,
        allow_upscale=args.allow_upscale,
        fit_mode=fit_mode,
    )
    framing, focus_label, focus_x, focus_y = resolve_focus_point(
        recipe=recipe,
        args=args,
        source_width=image.width,
        source_height=image.height,
        target_width=width,
        target_height=height,
        fit_mode=fit_mode,
    )
    metadata_inputs = MetadataInputs(
        subject=metadata_inputs.subject,
        context=metadata_inputs.context,
        purpose=metadata_inputs.purpose,
        visible_text=metadata_inputs.visible_text,
        framing=framing,
    )
    accessibility_mode = resolve_accessibility_mode(recipe, args)
    metadata = build_seo_metadata(
        slug=slug,
        metadata_inputs=metadata_inputs,
        accessibility_mode=accessibility_mode,
    )
    usage_overrides, active_usage_key, effective_metadata = build_usage_overrides(metadata, args)

    if writes_base_image:
        ensure_writeable(output_path, args.overwrite, args.dry_run)
        output_size = render_image(
            source=image,
            output_path=output_path,
            width=width,
            height=height,
            fit_mode=fit_mode,
            allow_upscale=args.allow_upscale,
            focus_x=focus_x,
            focus_y=focus_y,
            quality=args.quality,
            lossless=args.lossless,
            dry_run=args.dry_run,
        )
        final_width, final_height = width, height
        reduction = (
            None
            if output_size is None or source_size == 0
            else (1 - (output_size / source_size)) * 100
        )
        mode = "dry-run-generated" if args.dry_run else "generated"
    else:
        final_width, final_height = image.size
        output_size = output_path.stat().st_size
        reduction = 0.0
        mode = "metadata-only"
        if source_path != output_path:
            mode = "existing-webp-metadata-only"

    responsive_assets: list[ResponsiveAsset] = []
    if resolve_responsive_enabled(recipe, args):
        widths = parse_responsive_widths(args.responsive_widths, final_width, recipe)
        responsive_assets = build_responsive_assets(
            image=image,
            output_path=output_path,
            base_width=final_width,
            base_height=final_height,
            base_output_size=output_size,
            fit_mode=fit_mode,
            allow_upscale=args.allow_upscale,
            focus_x=focus_x,
            focus_y=focus_y,
            widths=widths,
            args=args,
        )

    loading, fetch_priority = resolve_loading(recipe, args)
    snippets = build_snippets(
        output_path=output_path,
        metadata=effective_metadata,
        width=final_width,
        height=final_height,
        public_root=args.public_root,
        loading=loading,
        fetch_priority=fetch_priority,
        sizes=args.sizes,
        responsive_assets=responsive_assets,
        enabled=resolve_snippet_enabled(recipe, args),
    )

    return ProcessResult(
        mode=mode,
        source_path=source_path,
        input_format=source_format,
        source_size=source_size,
        output_path=output_path,
        output_size=output_size,
        reduction=reduction,
        width=final_width,
        height=final_height,
        metadata_inputs=metadata_inputs,
        metadata=metadata,
        usage_overrides=usage_overrides,
        active_usage_key=active_usage_key,
        snippets=snippets,
        responsive_assets=responsive_assets,
        fit_mode=fit_mode,
        framing=framing,
        focus_label=focus_label,
        focus_x=focus_x,
        focus_y=focus_y,
        has_transparency=source_has_transparency,
        dry_run=args.dry_run,
    )


def serialize_recipe(recipe: RecipeConfig) -> dict[str, object]:
    return {
        "name": recipe.name,
        "description": recipe.description,
        "aspect_ratio": recipe.aspect_ratio,
        "fit_mode": recipe.fit_mode,
        "default_accessibility_mode": recipe.default_accessibility_mode,
        "default_framing": recipe.default_framing,
        "default_dimensions": {
            "width": recipe.width,
            "height": recipe.height,
        },
        "responsive_by_default": recipe.responsive_by_default,
        "responsive_widths": list(recipe.responsive_widths),
        "default_loading": recipe.default_loading,
        "default_fetch_priority": recipe.default_fetch_priority,
        "emit_snippets_by_default": recipe.emit_snippets_by_default,
    }


def serialize_asset(asset: ResponsiveAsset) -> dict[str, object]:
    return {
        "path": str(asset.path),
        "src": asset.src,
        "format": asset.path.suffix.lower().lstrip("."),
        "width": asset.width,
        "height": asset.height,
        "bytes": asset.bytes,
    }


def ensure_structured_fields(image: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    required_paths = [
        ("input", "path"),
        ("input", "bytes"),
        ("output", "main", "path"),
        ("output", "main", "src"),
        ("output", "fit_mode"),
        ("output", "focus", "x"),
        ("output", "focus", "y"),
        ("recipe", "name"),
        ("recipe", "default_accessibility_mode"),
        ("recipe", "default_framing"),
        ("metadata", "inputs"),
        ("metadata", "generated"),
        ("metadata", "usage_overrides"),
        ("snippets", "enabled"),
        ("snippets", "usage_key"),
        ("analysis", "compression"),
        ("analysis", "lints"),
    ]
    for path in required_paths:
        cursor: Any = image
        missing = False
        for part in path:
            if not isinstance(cursor, dict) or part not in cursor:
                missing = True
                break
            cursor = cursor[part]
        if missing:
            warnings.append(f"missing_structured_field:{'.'.join(path)}")
    return warnings


def tokenize_alt(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def significant_alt_tokens(text: str) -> list[str]:
    return [token for token in tokenize_alt(text) if token not in ALT_STOPWORDS and len(token) > 2]


def build_source_stem_tokens(image: dict[str, Any]) -> list[str]:
    input_payload = image.get("input", {}) if isinstance(image.get("input"), dict) else {}
    source_path = input_payload.get("path")
    if not isinstance(source_path, str) or not source_path.strip():
        return []
    stem = Path(source_path).stem
    stem = re.sub(r"-(?:\d+w)$", "", stem)
    return significant_alt_tokens(stem.replace("_", "-"))


def extra_metadata_warnings(image: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    metadata = image.get("metadata", {}) if isinstance(image.get("metadata"), dict) else {}
    generated = metadata.get("generated", {}) if isinstance(metadata.get("generated"), dict) else {}
    inputs = metadata.get("inputs", {}) if isinstance(metadata.get("inputs"), dict) else {}
    accessibility_mode = metadata.get("accessibility_mode")
    alt = str(generated.get("alt", "") or "").strip()

    if accessibility_mode == "decorative" or not alt:
        return warnings

    if len(alt) > 125:
        warnings.append("alt_too_long")

    if REDUNDANT_ALT_PREFIX_PATTERN.search(alt):
        warnings.append("redundant_alt_prefix")

    source_stem_tokens = build_source_stem_tokens(image)
    alt_tokens = significant_alt_tokens(alt)
    if source_stem_tokens and alt_tokens:
        if alt_tokens == source_stem_tokens:
            warnings.append("filename_like_alt")

    if alt_tokens:
        token_counter = Counter(alt_tokens)
        max_count = max(token_counter.values())
        if max_count >= 3:
            warnings.append("keyword_stuffed_alt")
        elif len(alt_tokens) >= 6 and (max_count / len(alt_tokens)) > 0.45:
            warnings.append("keyword_stuffed_alt")

    if accessibility_mode == "text-bearing" and not str(inputs.get("visible_text", "") or "").strip():
        warnings.append("text_bearing_missing_visible_text")

    return warnings


def lint_image_entry(
    image: dict[str, Any],
    max_hero_kb: int,
    max_standard_kb: int,
    *,
    strict: bool = False,
) -> tuple[list[str], list[str]]:
    blocking: list[str] = []
    warnings = ensure_structured_fields(image)

    metadata = image.get("metadata", {})
    generated = metadata.get("generated", {}) if isinstance(metadata, dict) else {}
    accessibility_mode = metadata.get("accessibility_mode")
    alt = generated.get("alt", "") if isinstance(generated, dict) else ""

    if accessibility_mode != "decorative" and not str(alt).strip():
        blocking.append("missing_alt")
    if accessibility_mode == "decorative" and str(alt).strip():
        blocking.append("decorative_has_alt")
    warnings.extend(extra_metadata_warnings(image))

    recipe = image.get("recipe", {}) if isinstance(image.get("recipe"), dict) else {}
    recipe_name = recipe.get("name")
    output = image.get("output", {}) if isinstance(image.get("output"), dict) else {}
    variants = output.get("variants", []) if isinstance(output.get("variants"), list) else []
    main = output.get("main", {}) if isinstance(output.get("main"), dict) else {}
    byte_count = main.get("bytes")
    main_width = main.get("width")

    if recipe_name in {"hero-banner", "blog-cover"} and len(variants) == 0 and isinstance(main_width, int) and main_width >= 768:
        warnings.append("no_responsive_variants")

    if isinstance(byte_count, int):
        threshold = max_hero_kb * 1024 if recipe_name in {"hero-banner", "blog-cover"} else max_standard_kb * 1024
        if byte_count > threshold:
            warnings.append("oversized_for_recipe")

    if strict:
        promoted = [code for code in warnings if code in STRICT_LINT_CODES]
        blocking.extend(promoted)
        warnings = [code for code in warnings if code not in STRICT_LINT_CODES]

    return sorted(set(blocking)), sorted(set(warnings))


def serialize_result(result: ProcessResult, recipe: RecipeConfig) -> dict[str, object]:
    entry: dict[str, object] = {
        "version": VERSION,
        "id": result.metadata.slug,
        "input": {
            "path": str(result.source_path),
            "format": result.input_format,
            "bytes": result.source_size,
        },
        "output": {
            "mode": result.mode,
            "fit_mode": result.fit_mode,
            "main": {
                "path": str(result.output_path),
                "src": result.snippets.src,
                "format": "webp",
                "width": result.width,
                "height": result.height,
                "bytes": result.output_size,
            },
            "variants": [
                serialize_asset(asset)
                for asset in sorted(result.responsive_assets, key=lambda asset: asset.width)
                if asset.path != result.output_path
            ],
            "focus": {
                "framing": result.framing,
                "preset": result.focus_label,
                "x": result.focus_x,
                "y": result.focus_y,
            },
        },
        "recipe": serialize_recipe(recipe),
        "metadata": {
            "inputs": {
                "subject": result.metadata_inputs.subject,
                "context": result.metadata_inputs.context,
                "purpose": result.metadata_inputs.purpose,
                "visible_text": result.metadata_inputs.visible_text,
                "framing": result.metadata_inputs.framing,
            },
            "accessibility_mode": result.metadata.accessibility_mode,
            "provenance": result.metadata.provenance,
            "generated": {
                "slug": result.metadata.slug,
                "alt": result.metadata.alt,
                "title": result.metadata.title,
                "caption": result.metadata.caption,
            },
            "usage_overrides": {
                key: {
                    "alt": override.alt,
                    "title": override.title,
                    "caption": override.caption,
                    "accessibility_mode": override.accessibility_mode,
                    "provenance": override.provenance,
                }
                for key, override in sorted(result.usage_overrides.items())
            },
        },
        "snippets": {
            "enabled": result.snippets.enabled,
            "src": result.snippets.src,
            "srcset": result.snippets.srcset,
            "sizes": result.snippets.sizes,
            "loading": result.snippets.loading,
            "fetch_priority": result.snippets.fetch_priority,
            "usage_key": result.active_usage_key,
            "targets": {
                name: {"markup": target.markup}
                for name, target in sorted(result.snippets.targets.items())
            },
        },
        "analysis": {
            "compression": {
                "source_bytes": result.source_size,
                "output_bytes": result.output_size,
                "reduction_percent": result.reduction,
            },
            "lints": {
                "blocking": [],
                "warnings": [],
            },
        },
    }
    blocking, warnings = lint_image_entry(entry, DEFAULT_HERO_KB, DEFAULT_STANDARD_KB)
    analysis = entry["analysis"]
    if isinstance(analysis, dict):
        analysis["status"] = "blocking" if blocking else ("warning" if warnings else "ok")
        lints = analysis.get("lints")
        if isinstance(lints, dict):
            lints["blocking"] = blocking
            lints["warnings"] = warnings
    return entry


def write_sidecar(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_sidecar(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SidecarError(f"Sidecar not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SidecarError(f"Sidecar is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise SidecarError("Sidecar root must be a JSON object.")
    validate_image_entry(payload, 1)
    return payload


def metadata_from_payload(payload: dict[str, Any]) -> SeoMetadata:
    generated = payload.get("generated")
    if not isinstance(generated, dict):
        raise SidecarError("Sidecar metadata.generated must be a JSON object.")
    return SeoMetadata(
        slug=str(generated.get("slug", "")),
        alt=str(generated.get("alt", "")),
        title=str(generated.get("title", "")),
        caption=str(generated.get("caption", "")),
        accessibility_mode=str(payload.get("accessibility_mode", "descriptive")),
        provenance=str(payload.get("provenance", "manual")),
    )


def merge_usage_override(base: SeoMetadata, payload: dict[str, Any]) -> SeoMetadata:
    return SeoMetadata(
        slug=base.slug,
        alt=str(payload.get("alt", base.alt)),
        title=str(payload.get("title", base.title)),
        caption=str(payload.get("caption", base.caption)),
        accessibility_mode=str(payload.get("accessibility_mode", base.accessibility_mode)),
        provenance=str(payload.get("provenance", base.provenance)),
    )


def responsive_assets_from_sidecar(sidecar: dict[str, Any]) -> tuple[ResponsiveAsset, list[ResponsiveAsset]]:
    output = sidecar.get("output")
    if not isinstance(output, dict):
        raise SidecarError("Sidecar output must be a JSON object.")
    main = output.get("main")
    if not isinstance(main, dict):
        raise SidecarError("Sidecar output.main must be a JSON object.")

    def build_asset(payload: dict[str, Any]) -> ResponsiveAsset:
        return ResponsiveAsset(
            path=Path(str(payload.get("path", ""))),
            src=str(payload.get("src", "")),
            width=int(payload.get("width", 0)),
            height=int(payload.get("height", 0)),
            bytes=payload.get("bytes") if isinstance(payload.get("bytes"), int) else None,
        )

    main_asset = build_asset(main)
    variant_payloads = output.get("variants", [])
    if not isinstance(variant_payloads, list):
        raise SidecarError("Sidecar output.variants must be a list.")
    variants = [
        build_asset(payload)
        for payload in variant_payloads
        if isinstance(payload, dict)
    ]
    return main_asset, [main_asset, *sorted(variants, key=lambda asset: asset.width)]


def select_snippet_targets(
    targets: dict[str, SnippetTarget],
    requested_target: str,
) -> dict[str, SnippetTarget]:
    if requested_target == "all":
        return dict(sorted(targets.items()))
    if requested_target not in targets:
        raise SidecarError(f"Snippet target not found in sidecar output: {requested_target}")
    return {requested_target: targets[requested_target]}


def build_snippets_from_sidecar(sidecar: dict[str, Any], usage_key: str | None) -> tuple[SnippetSet, SeoMetadata, str | None]:
    metadata_payload = sidecar.get("metadata")
    if not isinstance(metadata_payload, dict):
        raise SidecarError("Sidecar metadata must be a JSON object.")
    snippets_payload = sidecar.get("snippets")
    if not isinstance(snippets_payload, dict):
        raise SidecarError("Sidecar snippets must be a JSON object.")

    base_metadata = metadata_from_payload(metadata_payload)
    usage_overrides = metadata_payload.get("usage_overrides", {})
    if not isinstance(usage_overrides, dict):
        raise SidecarError("Sidecar metadata.usage_overrides must be a JSON object.")

    active_usage_key = usage_key if usage_key is not None else snippets_payload.get("usage_key")
    effective_metadata = base_metadata
    if active_usage_key:
        override_payload = usage_overrides.get(active_usage_key)
        if not isinstance(override_payload, dict):
            raise SidecarError(f"Usage override not found in sidecar: {active_usage_key}")
        effective_metadata = merge_usage_override(base_metadata, override_payload)

    main_asset, responsive_assets = responsive_assets_from_sidecar(sidecar)
    srcset = serialize_srcset(responsive_assets)
    sizes = snippets_payload.get("sizes")
    effective_sizes = str(sizes) if srcset and sizes else ("100vw" if srcset else None)
    loading = str(snippets_payload.get("loading", "lazy"))
    fetch_priority = snippets_payload.get("fetch_priority")
    if fetch_priority is not None:
        fetch_priority = str(fetch_priority)

    targets = build_snippet_targets(
        src=main_asset.src,
        metadata=effective_metadata,
        width=main_asset.width,
        height=main_asset.height,
        srcset=srcset,
        effective_sizes=effective_sizes,
        loading=loading,
        fetch_priority=fetch_priority,
    )
    return (
        SnippetSet(
            enabled=True,
            src=main_asset.src,
            srcset=srcset,
            sizes=effective_sizes,
            loading=loading,
            fetch_priority=fetch_priority,
            targets=targets,
        ),
        effective_metadata,
        str(active_usage_key) if active_usage_key else None,
    )


def load_proof_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        ["arialbd.ttf", "DejaVuSans-Bold.ttf"]
        if bold
        else ["arial.ttf", "DejaVuSans.ttf"]
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def has_transparency(image: Image.Image) -> bool:
    if "A" not in image.getbands():
        return False
    alpha = image.getchannel("A")
    minimum, maximum = alpha.getextrema()
    return minimum < 255 or maximum < 255


def parse_proof_surfaces(raw_value: str | None, *, transparent: bool) -> list[str]:
    if not raw_value:
        surfaces = ["dark", "light"]
        if transparent:
            surfaces.append("checker")
        return surfaces
    tokens = [token.strip().lower() for token in raw_value.split(",") if token.strip()]
    if not tokens:
        raise UsageError("--surfaces must include at least one of dark, light, or checker.")
    invalid = [token for token in tokens if token not in PROOF_SURFACE_COLORS]
    if invalid:
        raise UsageError(f"Unsupported proof surfaces: {', '.join(invalid)}")
    deduped: list[str] = []
    for token in tokens:
        if token not in deduped:
            deduped.append(token)
    return deduped


def proof_output_path(args: argparse.Namespace, asset_path: Path) -> Path:
    if args.output:
        output = args.output
    else:
        output = asset_path.with_name(f"{asset_path.stem}-proof.png")
    if output.exists() and not args.overwrite:
        raise UsageError(f"Proof output already exists: {output}. Use --overwrite to replace it.")
    return output


def resolve_proof_source(args: argparse.Namespace) -> tuple[Path, dict[str, Any] | None, SeoMetadata | None, str | None]:
    source = args.input
    if source.suffix.lower() == ".json":
        sidecar = load_sidecar(source)
        output = sidecar.get("output", {})
        main = output.get("main", {}) if isinstance(output, dict) else {}
        asset_path = Path(str(main.get("path", ""))).resolve()
        if not asset_path.exists():
            raise SidecarError(f"Proof asset not found from sidecar output.main.path: {asset_path}")
        _, effective_metadata, active_usage_key = build_snippets_from_sidecar(sidecar, args.usage_key)
        return asset_path, sidecar, effective_metadata, active_usage_key

    asset_path = source.resolve()
    sidecar_path = asset_path.with_suffix(".json")
    if sidecar_path.exists():
        sidecar = load_sidecar(sidecar_path)
        _, effective_metadata, active_usage_key = build_snippets_from_sidecar(sidecar, args.usage_key)
        return asset_path, sidecar, effective_metadata, active_usage_key

    if args.usage_key:
        raise UsageError("--usage-key for proof requires a sidecar or a sibling .json sidecar.")
    return asset_path, None, None, None


def build_checkerboard(size: tuple[int, int], square: int = 24) -> Image.Image:
    image = Image.new("RGB", size, (228, 228, 228))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], square):
        for x in range(0, size[0], square):
            if ((x // square) + (y // square)) % 2 == 0:
                draw.rectangle((x, y, x + square - 1, y + square - 1), fill=(196, 196, 196))
    return image


def fit_image(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    copy = image.copy()
    copy.thumbnail((max_width, max_height), RESAMPLE)
    return copy


def wrap_for_canvas(text: str, width: int) -> list[str]:
    if not text:
        return []
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def render_proof_sheet(
    asset_path: Path,
    image: Image.Image,
    metadata: SeoMetadata | None,
    *,
    recipe_name: str | None,
    accessibility_mode: str | None,
    usage_key: str | None,
    surfaces: list[str],
) -> Image.Image:
    canvas_width = 1680
    page_padding = 56
    panel_gap = 28
    panel_width = (canvas_width - (page_padding * 2) - (panel_gap * (len(surfaces) - 1))) // len(surfaces)
    panel_height = 470
    header_height = 172
    details_height = 340
    canvas_height = header_height + panel_height + details_height + 120

    sheet = Image.new("RGBA", (canvas_width, canvas_height), (4, 18, 31, 255))
    draw = ImageDraw.Draw(sheet)
    title_font = load_proof_font(42, bold=True)
    label_font = load_proof_font(22, bold=True)
    body_font = load_proof_font(20)
    small_font = load_proof_font(17)

    draw.text((page_padding, 34), "Webp Me Daddy Proof", fill=(245, 241, 232), font=title_font)
    draw.text(
        (page_padding, 88),
        f"Asset: {asset_path.name}",
        fill=(189, 168, 132),
        font=body_font,
    )
    subtitle_parts = []
    if recipe_name:
        subtitle_parts.append(f"Recipe: {recipe_name}")
    if accessibility_mode:
        subtitle_parts.append(f"Accessibility: {accessibility_mode}")
    if usage_key:
        subtitle_parts.append(f"Usage: {usage_key}")
    if subtitle_parts:
        draw.text((page_padding, 120), " | ".join(subtitle_parts), fill=(189, 168, 132), font=small_font)

    preview = image.convert("RGBA")
    preview_area_top = header_height
    for index, surface in enumerate(surfaces):
        x = page_padding + index * (panel_width + panel_gap)
        y = preview_area_top
        panel_box = (x, y, x + panel_width, y + panel_height)
        draw.rounded_rectangle(panel_box, radius=24, fill=(18, 42, 51), outline=(49, 80, 90), width=2)
        label = PROOF_SURFACE_COLORS[surface][1]
        draw.text((x + 20, y + 16), label, fill=(209, 167, 108), font=label_font)

        art_left = x + 24
        art_top = y + 64
        art_width = panel_width - 48
        art_height = panel_height - 92
        art_box = (art_left, art_top, art_left + art_width, art_top + art_height)

        if surface == "checker":
            background = build_checkerboard((art_width, art_height))
        else:
            background = Image.new("RGB", (art_width, art_height), PROOF_SURFACE_COLORS[surface][0])
        sheet.paste(background, (art_left, art_top))

        fitted = fit_image(preview, art_width - 24, art_height - 24)
        paste_x = art_left + (art_width - fitted.width) // 2
        paste_y = art_top + (art_height - fitted.height) // 2
        sheet.alpha_composite(fitted, dest=(paste_x, paste_y))

    details_top = preview_area_top + panel_height + 34
    detail_box = (page_padding, details_top, canvas_width - page_padding, canvas_height - 56)
    draw.rounded_rectangle(detail_box, radius=24, fill=(18, 42, 51), outline=(154, 122, 83), width=2)

    text_x = page_padding + 26
    text_y = details_top + 20
    metadata_lines = [
        ("Alt", metadata.alt if metadata else asset_path.stem.replace("-", " ")),
        ("Title", metadata.title if metadata else asset_path.stem.replace("-", " ").title()),
        ("Caption", metadata.caption if metadata else "No sidecar metadata loaded."),
    ]
    for label, value in metadata_lines:
        draw.text((text_x, text_y), label, fill=(209, 167, 108), font=label_font)
        text_y += 30
        for line in wrap_for_canvas(value or "-", 105):
            draw.text((text_x, text_y), line, fill=(245, 241, 232), font=body_font)
            text_y += 28
        text_y += 12

    return sheet.convert("RGB")


def render_batch_contact_sheet(
    results: list[ProcessResult],
    entries: list[dict[str, object]],
    recipe: RecipeConfig,
) -> Image.Image:
    card_width = 780
    card_height = 560
    columns = 2 if len(results) > 1 else 1
    gutter = 28
    padding = 44
    header_height = 120
    rows = max(1, math.ceil(len(results) / columns))
    canvas_width = padding * 2 + columns * card_width + (columns - 1) * gutter
    canvas_height = padding * 2 + header_height + rows * card_height + (rows - 1) * gutter

    sheet = Image.new("RGBA", (canvas_width, canvas_height), (4, 18, 31, 255))
    draw = ImageDraw.Draw(sheet)
    title_font = load_proof_font(38, bold=True)
    label_font = load_proof_font(20, bold=True)
    body_font = load_proof_font(18)
    small_font = load_proof_font(16)

    draw.text((padding, 28), "Webp Me Daddy Batch Proof", fill=(245, 241, 232), font=title_font)
    draw.text(
        (padding, 76),
        f"Recipe: {recipe.name}  |  Images: {len(results)}  |  Dry-run visual QA",
        fill=(189, 168, 132),
        font=label_font,
    )

    for index, (result, entry) in enumerate(zip(results, entries)):
        column = index % columns
        row = index // columns
        x = padding + column * (card_width + gutter)
        y = padding + header_height + row * (card_height + gutter)
        card_box = (x, y, x + card_width, y + card_height)
        draw.rounded_rectangle(card_box, radius=24, fill=(18, 42, 51), outline=(49, 80, 90), width=2)

        draw.text((x + 24, y + 18), result.output_path.name, fill=(245, 241, 232), font=label_font)
        status, issue_labels, issue_actions = extract_entry_issue_details(entry)
        badge_fill = {
            "ok": (30, 110, 94),
            "warning": (131, 90, 24),
            "blocking": (130, 46, 46),
        }.get(status, (49, 80, 90))
        badge_text = status.upper()
        badge_width = max(90, 24 + len(badge_text) * 11)
        badge_box = (x + card_width - badge_width - 24, y + 18, x + card_width - 24, y + 50)
        draw.rounded_rectangle(badge_box, radius=14, fill=badge_fill)
        draw.text((badge_box[0] + 12, badge_box[1] + 6), badge_text, fill=(245, 241, 232), font=small_font)
        draw.text(
            (x + 24, y + 48),
            f"{result.width}x{result.height}  |  {result.fit_mode}  |  {result.framing}",
            fill=(189, 168, 132),
            font=small_font,
        )

        surfaces = ["dark", "light"] + (["checker"] if result.has_transparency else [])
        surface_gap = 16
        panel_top = y + 84
        panel_height = 220
        panel_width = (card_width - 48 - surface_gap * (len(surfaces) - 1)) // len(surfaces)
        with Image.open(result.source_path) as opened:
            preview_source = ImageOps.exif_transpose(opened).convert("RGBA")
        preview = render_processed_preview(
            source=preview_source,
            width=result.width,
            height=result.height,
            fit_mode=result.fit_mode,
            allow_upscale=True,
            focus_x=result.focus_x,
            focus_y=result.focus_y,
        )

        for surface_index, surface in enumerate(surfaces):
            px = x + 24 + surface_index * (panel_width + surface_gap)
            panel_box = (px, panel_top, px + panel_width, panel_top + panel_height)
            draw.rounded_rectangle(panel_box, radius=18, fill=(10, 28, 40), outline=(49, 80, 90), width=2)
            draw.text((px + 14, panel_top + 12), PROOF_SURFACE_COLORS[surface][1], fill=(209, 167, 108), font=small_font)
            art_top = panel_top + 44
            art_height = panel_height - 58
            if surface == "checker":
                background = build_checkerboard((panel_width - 20, art_height), square=18)
            else:
                background = Image.new("RGB", (panel_width - 20, art_height), PROOF_SURFACE_COLORS[surface][0])
            sheet.paste(background, (px + 10, art_top))
            fitted = fit_image(preview, panel_width - 32, art_height - 16)
            paste_x = px + 10 + ((panel_width - 20) - fitted.width) // 2
            paste_y = art_top + (art_height - fitted.height) // 2
            sheet.alpha_composite(fitted, dest=(paste_x, paste_y))

        meta_top = panel_top + panel_height + 16
        alt_preview = effective_alt_for_result(result) or "-"
        caption_preview = result.metadata.caption or "-"
        usage_label = result.active_usage_key or "default metadata"
        detail_lines = [
            f"Usage: {usage_label}",
            f"Surfaces: {', '.join(surfaces)}",
            f"Variants: {len(result.responsive_assets)}",
        ]
        if issue_labels:
            detail_lines.append(f"Issues: {'; '.join(issue_labels)}")
        if issue_actions:
            detail_lines.append(f"Next: {', '.join(issue_actions)}")
        for detail in detail_lines:
            draw.text((x + 24, meta_top), detail, fill=(189, 168, 132), font=small_font)
            meta_top += 24
        draw.text((x + 24, meta_top + 6), "Alt", fill=(209, 167, 108), font=small_font)
        meta_top += 30
        for line in wrap_for_canvas(alt_preview, 74)[:3]:
            draw.text((x + 24, meta_top), line, fill=(245, 241, 232), font=body_font)
            meta_top += 24
        draw.text((x + 24, meta_top + 6), "Caption", fill=(209, 167, 108), font=small_font)
        meta_top += 30
        for line in wrap_for_canvas(caption_preview, 74)[:2]:
            draw.text((x + 24, meta_top), line, fill=(216, 225, 231), font=small_font)
            meta_top += 22

    return sheet.convert("RGB")


def run_proof(args: argparse.Namespace) -> int:
    asset_path, sidecar, effective_metadata, active_usage_key = resolve_proof_source(args)
    with Image.open(asset_path) as opened:
        image = opened.convert("RGBA")
    output_path = proof_output_path(args, asset_path)
    surfaces = parse_proof_surfaces(args.surfaces, transparent=has_transparency(image))

    recipe_name = None
    accessibility_mode = effective_metadata.accessibility_mode if effective_metadata else None
    if sidecar:
        recipe_payload = sidecar.get("recipe", {})
        if isinstance(recipe_payload, dict):
            recipe_name = str(recipe_payload.get("name") or "")
        metadata_payload = sidecar.get("metadata", {})
        if isinstance(metadata_payload, dict) and not accessibility_mode:
            accessibility_mode = str(metadata_payload.get("accessibility_mode") or "")

    proof_image = render_proof_sheet(
        asset_path,
        image,
        effective_metadata,
        recipe_name=recipe_name,
        accessibility_mode=accessibility_mode,
        usage_key=active_usage_key,
        surfaces=surfaces,
    )
    proof_image.save(output_path, format="PNG")
    print(f"Proof sheet: {output_path}")
    print(f"Surfaces: {', '.join(surfaces)}")
    if active_usage_key:
        print(f"Usage key: {active_usage_key}")
    return 0


def summarize_entries(entries: list[dict[str, object]]) -> dict[str, object]:
    generated_count = sum(
        1
        for entry in entries
        if isinstance(entry.get("output"), dict)
        and str(entry["output"].get("mode", "")).endswith("generated")
    )
    metadata_only_count = len(entries) - generated_count

    reductions = [
        compression.get("reduction_percent")
        for entry in entries
        if isinstance(entry.get("analysis"), dict)
        and isinstance(entry["analysis"].get("compression"), dict)
        and isinstance((compression := entry["analysis"]["compression"]).get("reduction_percent"), (int, float))
    ]
    output_sizes = [
        main.get("bytes")
        for entry in entries
        if isinstance(entry.get("output"), dict)
        and isinstance(entry["output"].get("main"), dict)
        and isinstance((main := entry["output"]["main"]).get("bytes"), int)
    ]
    blocking_count = 0
    warning_count = 0
    for entry in entries:
        analysis = entry.get("analysis")
        if not isinstance(analysis, dict):
            continue
        lints = analysis.get("lints")
        if not isinstance(lints, dict):
            continue
        blocking = lints.get("blocking", [])
        warnings = lints.get("warnings", [])
        if isinstance(blocking, list):
            blocking_count += len(blocking)
        if isinstance(warnings, list):
            warning_count += len(warnings)

    return {
        "image_count": len(entries),
        "generated_count": generated_count,
        "metadata_only_count": metadata_only_count,
        "blocking_issue_count": blocking_count,
        "warning_issue_count": warning_count,
        "average_reduction_percent": (
            round(sum(reductions) / len(reductions), 2) if reductions else None
        ),
        "largest_output_bytes": max(output_sizes) if output_sizes else None,
    }


def write_manifest(
    manifest_path: Path,
    command: str,
    input_path: Path,
    recipe: RecipeConfig,
    args: argparse.Namespace,
    entries: list[dict[str, object]],
) -> None:
    payload = {
        "version": VERSION,
        "run": {
            "command": command,
            "input": str(input_path.resolve()),
            "recipe": recipe.name,
            "dry_run": args.dry_run,
            "public_root": str(args.public_root.resolve()) if args.public_root else None,
            "overwrite": args.overwrite,
            "reencode_webp": args.reencode_webp,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "summary": summarize_entries(entries),
        "images": entries,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def iter_audit_source_files(src_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in src_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIT_EXTENSIONS
    )


def extract_literal_asset_references(text: str) -> list[str]:
    return [match.group(1) for match in PATH_REFERENCE_PATTERN.finditer(text)]


def inspect_public_asset(path: Path) -> dict[str, object]:
    extension = path.suffix.lower()
    dimensions: dict[str, int] | None = None
    frame_count = 1
    animated = False
    alpha_analysis: dict[str, object] | None = None
    if extension != ".svg":
        try:
            with Image.open(path) as image:
                dimensions = {"width": image.width, "height": image.height}
                frame_count = int(getattr(image, "n_frames", 1))
                animated = frame_count > 1
                alpha_analysis = inspect_alpha_bounds(image)
        except Exception:
            dimensions = None
    return {
        "name": path.name,
        "path": str(path),
        "extension": extension,
        "bytes": path.stat().st_size,
        "dimensions": dimensions,
        "frame_count": frame_count if extension != ".svg" else None,
        "animated": animated,
        "alpha_analysis": alpha_analysis,
    }


def inspect_alpha_bounds(image: Image.Image) -> dict[str, object] | None:
    if "A" not in image.getbands():
        return None

    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return {
            "has_alpha": True,
            "content_bbox": None,
            "padding_pixels": None,
            "padding_ratio": None,
            "significant_padding_edges": [],
        }

    left, top, right, bottom = bbox
    width, height = image.size
    padding_pixels = {
        "left": left,
        "top": top,
        "right": max(width - right, 0),
        "bottom": max(height - bottom, 0),
    }
    padding_ratio = {
        "left": round(padding_pixels["left"] / width, 4) if width else 0.0,
        "top": round(padding_pixels["top"] / height, 4) if height else 0.0,
        "right": round(padding_pixels["right"] / width, 4) if width else 0.0,
        "bottom": round(padding_pixels["bottom"] / height, 4) if height else 0.0,
    }
    significant_padding_edges = [edge for edge, ratio in padding_ratio.items() if ratio >= 0.08]
    return {
        "has_alpha": True,
        "content_bbox": {
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
            "width": max(right - left, 0),
            "height": max(bottom - top, 0),
        },
        "padding_pixels": padding_pixels,
        "padding_ratio": padding_ratio,
        "significant_padding_edges": significant_padding_edges,
    }


def extract_asset_name_from_src(src: str | None) -> str | None:
    if not src:
        return None
    cleaned = src.split("?", 1)[0].split("#", 1)[0].strip().strip("'\"")
    if cleaned.startswith("/"):
        return cleaned[1:]
    return None


def slugify_identifier(value: str) -> str:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value)
    normalized = normalized.replace("_", "-")
    return slugify(normalized)


def has_bare_attribute(tag_text: str, attribute_name: str) -> bool:
    pattern = re.compile(rf"(?<![A-Za-z0-9_:-]){re.escape(attribute_name)}(?!\s*=)")
    return bool(pattern.search(tag_text))


def guess_loading_suggestion(tag: ImgTagAudit, asset_name: str | None) -> tuple[str, str | None, str]:
    haystack = " ".join(part.lower() for part in [tag.file, asset_name or "", tag.alt or ""] if part)
    if any(keyword in haystack for keyword in ("hero", "banner", "masthead", "lcp")):
        return "eager", "high", "Review this suggestion if the image is not above the fold."
    return "lazy", None, "Lazy loading is usually safe for non-hero imagery."


def patch_img_tag(tag_text: str, attributes: list[str]) -> str:
    if not attributes:
        return tag_text
    closing_match = re.search(r"\s*/?>\s*$", tag_text)
    if not closing_match:
        return tag_text
    insert_at = closing_match.start()
    if "\n" not in tag_text:
        spacer = "" if tag_text[:insert_at].endswith((" ", "\n", "\t")) else " "
        return f"{tag_text[:insert_at]}{spacer}{' '.join(attributes)}{tag_text[insert_at:]}"

    indent_match = re.search(r"\n([ \t]+)[A-Za-z_:@]", tag_text)
    indent = indent_match.group(1) if indent_match else "  "
    addition = "".join(f"\n{indent}{attribute}" for attribute in attributes)
    return f"{tag_text[:insert_at]}{addition}{tag_text[insert_at:]}"


def build_img_autofix(tag: ImgTagAudit, public_assets: dict[str, dict[str, object]]) -> dict[str, object] | None:
    asset_name = extract_asset_name_from_src(tag.src)
    matched_asset = public_assets.get(asset_name) if asset_name else None
    suggested_attributes: dict[str, str | int] = {}
    jsx_attributes: list[str] = []
    html_attributes: list[str] = []
    notes: list[str] = []

    if matched_asset:
        dimensions = matched_asset.get("dimensions")
        if isinstance(dimensions, dict):
            width = dimensions.get("width")
            height = dimensions.get("height")
            if not tag.has_fill and not tag.has_width and isinstance(width, int):
                suggested_attributes["width"] = width
                jsx_attributes.append(f"width={{{width}}}")
                html_attributes.append(build_attr_string("width", str(width)))
            if not tag.has_fill and not tag.has_height and isinstance(height, int):
                suggested_attributes["height"] = height
                jsx_attributes.append(f"height={{{height}}}")
                html_attributes.append(build_attr_string("height", str(height)))

    if tag.loading is None:
        loading, fetch_priority, note = guess_loading_suggestion(tag, asset_name)
        suggested_attributes["loading"] = loading
        jsx_attributes.append(f"loading={jsx_literal(loading)}")
        if tag.component_kind == "html-img":
            html_attributes.append(build_attr_string("loading", loading))
        if fetch_priority:
            fetch_priority_key = "fetchPriority" if tag.component_kind == "next-image" else "fetchpriority"
            suggested_attributes[fetch_priority_key] = fetch_priority
            jsx_attributes.append(f"fetchPriority={jsx_literal(fetch_priority)}")
            if tag.component_kind == "html-img":
                html_attributes.append(build_attr_string("fetchpriority", fetch_priority))
        notes.append(note)

    if tag.component_kind == "html-img" and tag.decoding is None:
        suggested_attributes["decoding"] = "async"
        jsx_attributes.append(f"decoding={jsx_literal('async')}")
        html_attributes.append(build_attr_string("decoding", "async"))

    if not suggested_attributes:
        return None

    return {
        "file": tag.file,
        "line": tag.line,
        "component_kind": tag.component_kind,
        "tag_name": tag.tag_name,
        "src": tag.src,
        "asset_name": asset_name,
        "attributes": suggested_attributes,
        "jsx_attributes": jsx_attributes,
        "html_attributes": html_attributes,
        "original_tag": tag.tag_text,
        "jsx_patch": patch_img_tag(tag.tag_text, jsx_attributes),
        "html_patch": patch_img_tag(tag.tag_text, html_attributes),
        "content_update": {
            "old_str": tag.tag_text,
            "new_str": patch_img_tag(tag.tag_text, jsx_attributes),
        },
        "notes": notes,
    }


def parse_img_attributes(tag_text: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for match in ATTRIBUTE_PATTERN.finditer(tag_text):
        name = match.group(1)
        value = match.group(2) or match.group(3) or match.group(4) or ""
        attributes[name] = value.strip()
    return attributes


def find_next_image_aliases(text: str) -> set[str]:
    return {match.group(1) for match in NEXT_IMAGE_IMPORT_PATTERN.finditer(text)}


def audit_img_tags(source_file: Path) -> list[ImgTagAudit]:
    text = source_file.read_text(encoding="utf-8")
    audits: list[ImgTagAudit] = []
    for match in IMG_TAG_PATTERN.finditer(text):
        tag_text = match.group(0)
        attrs = parse_img_attributes(tag_text)
        src = attrs.get("src")
        alt = attrs.get("alt") if "alt" in attrs else None
        audits.append(
            ImgTagAudit(
                file=str(source_file),
                line=text.count("\n", 0, match.start()) + 1,
                component_kind="html-img",
                tag_name="img",
                src=src,
                alt=alt,
                tag_text=tag_text,
                has_fill=False,
                has_width="width" in attrs,
                has_height="height" in attrs,
                loading=attrs.get("loading"),
                decoding=attrs.get("decoding"),
                has_srcset="srcSet" in attrs or "srcset" in attrs,
                has_sizes="sizes" in attrs,
            )
        )

    for alias in sorted(find_next_image_aliases(text)):
        component_pattern = re.compile(rf"<{re.escape(alias)}\b[\s\S]*?/>")
        for match in component_pattern.finditer(text):
            tag_text = match.group(0)
            attrs = parse_img_attributes(tag_text)
            src = attrs.get("src")
            alt = attrs.get("alt") if "alt" in attrs else None
            audits.append(
                ImgTagAudit(
                    file=str(source_file),
                    line=text.count("\n", 0, match.start()) + 1,
                    component_kind="next-image",
                    tag_name=alias,
                    src=src,
                    alt=alt,
                    tag_text=tag_text,
                    has_fill=has_bare_attribute(tag_text, "fill"),
                    has_width="width" in attrs,
                    has_height="height" in attrs,
                    loading=attrs.get("loading"),
                    decoding=None,
                    has_srcset=False,
                    has_sizes="sizes" in attrs,
                )
            )
    return audits


def build_usage_override_suggestions(
    asset: dict[str, object],
    reference_files: list[str],
    public_dir: Path,
) -> list[dict[str, str]]:
    relative_path = str(asset.get("relative_path", asset.get("name", "")))
    asset_stem = slugify(Path(relative_path).stem)
    sidecar_path = public_dir / Path(relative_path).with_suffix(".json")
    suggestions: list[dict[str, str]] = []
    for reference_file in reference_files:
        file_stem = slugify_identifier(Path(reference_file).stem)
        usage_key = f"{file_stem}.{asset_stem}"
        suggestion: dict[str, str] = {
            "file": reference_file,
            "usage_key": usage_key,
        }
        if sidecar_path.exists():
            suggestion["snippet_command"] = (
                f"python {CLI_SCRIPT} snippets {sidecar_path} --usage-key {usage_key} --target react"
            )
        suggestions.append(suggestion)
    return suggestions


def infer_recipe_for_asset(asset: dict[str, object]) -> str:
    name = str(asset.get("name", "")).lower()
    relative_path = str(asset.get("relative_path", "")).lower()
    haystack = f"{name} {relative_path}"
    if any(keyword in haystack for keyword in ("logo", "lockup", "badge", "icon", "wordmark")):
        return "logo-lockup"
    dimensions = asset.get("dimensions")
    if isinstance(dimensions, dict):
        width = int(dimensions.get("width", 0) or 0)
        height = int(dimensions.get("height", 0) or 0)
        if width > 0 and height > 0:
            ratio = width / height
            if ratio >= 1.6:
                return "hero-banner"
            if ratio >= 1.2:
                return "blog-cover"
            if ratio >= 0.9:
                return "card-thumbnail"
            if ratio >= 0.65:
                return "poster"
    return "review-hero"


def build_logo_padding_candidate(asset: dict[str, object]) -> dict[str, object] | None:
    alpha_analysis = asset.get("alpha_analysis")
    if not isinstance(alpha_analysis, dict):
        return None

    padding_ratio = alpha_analysis.get("padding_ratio")
    if not isinstance(padding_ratio, dict):
        return None

    top_ratio = float(padding_ratio.get("top", 0.0) or 0.0)
    bottom_ratio = float(padding_ratio.get("bottom", 0.0) or 0.0)
    left_ratio = float(padding_ratio.get("left", 0.0) or 0.0)
    right_ratio = float(padding_ratio.get("right", 0.0) or 0.0)
    max_padding = max(top_ratio, bottom_ratio, left_ratio, right_ratio)
    vertical_imbalance = abs(top_ratio - bottom_ratio)
    horizontal_imbalance = abs(left_ratio - right_ratio)

    if max_padding < 0.12 and vertical_imbalance < 0.06 and horizontal_imbalance < 0.06:
        return None

    recommendation_parts: list[str] = []
    if max_padding >= 0.12:
        recommendation_parts.append("large transparent margins")
    if vertical_imbalance >= 0.06:
        recommendation_parts.append("vertical headroom imbalance")
    if horizontal_imbalance >= 0.06:
        recommendation_parts.append("horizontal side-padding imbalance")

    reason = ", ".join(recommendation_parts) or "significant transparent padding"
    return {
        "name": asset.get("name"),
        "relative_path": asset.get("relative_path"),
        "path": asset.get("path"),
        "padding_ratio": padding_ratio,
        "padding_pixels": alpha_analysis.get("padding_pixels"),
        "content_bbox": alpha_analysis.get("content_bbox"),
        "recommendation": (
            f"Proof this lockup before blaming layout: {reason}. "
            "Keep the source intact when the whitespace is intentional, but use a page-level stage alignment "
            "or generate a placement-specific lockup if the visible mark needs to sit flush in a fixed tile."
        ),
    }


def build_audit_fix_plan(args: argparse.Namespace, payload: dict[str, object]) -> list[dict[str, object]]:
    assets = payload.get("assets", {})
    markup = payload.get("markup", {})
    if not isinstance(assets, dict) or not isinstance(markup, dict):
        return []

    root = args.root.resolve()
    public_dir = args.public_dir.resolve()
    public_dir_rel = public_dir.relative_to(root).as_posix()
    fix_plan: list[dict[str, object]] = []

    live_pngs = assets.get("live_pngs", [])
    live_jpegs = assets.get("live_jpegs", [])
    for asset_group, reason in ((live_pngs, "replace live PNG with optimized WebP"), (live_jpegs, "replace live JPEG with optimized WebP")):
        if not isinstance(asset_group, list):
            continue
        for asset in asset_group:
            if not isinstance(asset, dict):
                continue
            path_value = asset.get("path")
            if not isinstance(path_value, str):
                continue
            source_path = Path(path_value)
            recipe_name = infer_recipe_for_asset(asset)
            relative_path = str(asset.get("relative_path", source_path.name))
            fix_plan.append(
                {
                    "kind": "prepare",
                    "asset": relative_path,
                    "reason": reason,
                    "recipe": recipe_name,
                    "command": (
                        f"python {CLI_SCRIPT} prepare {source_path} "
                        f"--recipe {recipe_name} --public-root {public_dir} --write-sidecar --overwrite"
                    ),
                }
            )

    live_animated = assets.get("live_animated", [])
    if isinstance(live_animated, list):
        for asset in live_animated:
            if not isinstance(asset, dict):
                continue
            path_value = asset.get("path")
            if not isinstance(path_value, str):
                continue
            source_path = Path(path_value)
            output_name = f"{source_path.stem}-optimized.webp"
            fix_plan.append(
                {
                    "kind": "animate",
                    "asset": str(asset.get("relative_path", source_path.name)),
                    "reason": "animated asset should go through the loop optimizer",
                    "command": f"python {CLI_SCRIPT} animate {source_path} {source_path.with_name(output_name)}",
                }
            )

    shared_candidates = assets.get("shared_usage_candidates", [])
    if isinstance(shared_candidates, list):
        for asset in shared_candidates:
            if not isinstance(asset, dict):
                continue
            suggestions = asset.get("usage_override_suggestions", [])
            if not isinstance(suggestions, list):
                continue
            for suggestion in suggestions[:2]:
                if not isinstance(suggestion, dict):
                    continue
                command = suggestion.get("snippet_command")
                if not isinstance(command, str):
                    continue
                fix_plan.append(
                    {
                        "kind": "usage-override",
                        "asset": str(asset.get("relative_path", asset.get("name", ""))),
                        "reason": "shared asset may need page-specific metadata",
                        "usage_key": suggestion.get("usage_key"),
                        "command": command,
                    }
                )

    transparent_logo_padding = assets.get("transparent_logo_padding_candidates", [])
    if isinstance(transparent_logo_padding, list):
        for asset in transparent_logo_padding[:3]:
            if not isinstance(asset, dict):
                continue
            path_value = asset.get("path")
            if not isinstance(path_value, str):
                continue
            source_path = Path(path_value)
            fix_plan.append(
                {
                    "kind": "proof",
                    "asset": str(asset.get("relative_path", source_path.name)),
                    "reason": "transparent logo may look misaligned because of baked-in alpha padding",
                    "command": f"python {CLI_SCRIPT} proof {source_path} --surfaces dark,light,checker",
                }
            )

    autofix_suggestions = markup.get("autofix_suggestions", [])
    if isinstance(autofix_suggestions, list) and autofix_suggestions:
        fix_plan.append(
            {
                "kind": "autofix",
                "asset": "markup",
                "reason": "low-risk image tag fixes are available",
                "command": f"python {CLI_SCRIPT} audit {root} --apply-autofix",
            }
        )

    unused_assets = assets.get("unused", [])
    if isinstance(unused_assets, list) and unused_assets:
        fix_plan.append(
            {
                "kind": "cleanup",
                "asset": public_dir_rel,
                "reason": "unused public assets can be reviewed for deletion",
                "command": f"python {CLI_SCRIPT} cleanup {root} --dry-run",
            }
        )

    return fix_plan


def load_seo_handoff(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HandoffError(f"SEO handoff not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HandoffError(f"SEO handoff is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise HandoffError("SEO handoff root must be a JSON object.")
    if payload.get("version") != SEO_HANDOFF_VERSION:
        raise HandoffError(
            f"SEO handoff version must be {SEO_HANDOFF_VERSION}. Found {payload.get('version')!r}."
        )
    items = payload.get("items")
    if not isinstance(items, list):
        raise HandoffError("SEO handoff must include an items list.")
    return payload


def build_prepare_args_from_handoff(
    handoff: dict[str, Any],
    item: dict[str, Any],
    args: argparse.Namespace,
) -> argparse.Namespace:
    defaults = handoff.get("defaults", {})
    source = item.get("source", {})
    metadata = item.get("metadata", {})
    markup = item.get("markup", {})

    if not isinstance(source, dict):
        raise HandoffError("SEO handoff item source must be a JSON object.")
    if not isinstance(metadata, dict):
        raise HandoffError("SEO handoff item metadata must be a JSON object.")
    if not isinstance(markup, dict):
        raise HandoffError("SEO handoff item markup must be a JSON object.")

    source_path = source.get("path")
    recipe = item.get("recipe")
    if not isinstance(source_path, str) or not source_path.strip():
        raise HandoffError("Ready SEO handoff items must include source.path.")
    if not isinstance(recipe, str) or recipe not in RECIPES:
        raise HandoffError(f"Unsupported or missing recipe in SEO handoff item: {recipe!r}")

    prepare_argv = ["prepare", source_path, "--recipe", recipe, "--write-sidecar"]
    if args.dry_run:
        prepare_argv.append("--dry-run")
    if args.overwrite:
        prepare_argv.append("--overwrite")

    public_root = defaults.get("public_root") if isinstance(defaults, dict) else None
    if isinstance(public_root, str) and public_root.strip():
        prepare_argv.extend(["--public-root", public_root])

    subject = metadata.get("subject")
    context = metadata.get("context")
    purpose = metadata.get("purpose")
    accessibility_mode = metadata.get("accessibility_mode")
    framing = metadata.get("framing")
    visible_text = metadata.get("visible_text")
    usage_key = metadata.get("usage_key")
    usage_alt = metadata.get("usage_alt")
    usage_title = metadata.get("usage_title")
    usage_caption = metadata.get("usage_caption")

    if isinstance(subject, str) and subject.strip():
        prepare_argv.extend(["--seo-subject", subject])
    if isinstance(context, str) and context.strip():
        prepare_argv.extend(["--seo-context", context])
    if isinstance(purpose, str) and purpose.strip():
        prepare_argv.extend(["--seo-purpose", purpose])
    if isinstance(accessibility_mode, str) and accessibility_mode in {"decorative", "logo", "descriptive", "text-bearing"}:
        prepare_argv.extend(["--accessibility-mode", accessibility_mode])
    if isinstance(framing, str) and framing in {"auto", "subject", "text", "balanced"}:
        prepare_argv.extend(["--framing", framing])
    if isinstance(visible_text, str) and visible_text.strip():
        prepare_argv.extend(["--visible-text", visible_text])
    if isinstance(usage_key, str) and usage_key.strip():
        prepare_argv.extend(["--usage-key", usage_key])
        if isinstance(usage_alt, str):
            prepare_argv.extend(["--usage-alt", usage_alt])
        if isinstance(usage_title, str) and usage_title.strip():
            prepare_argv.extend(["--usage-title", usage_title])
        if isinstance(usage_caption, str) and usage_caption.strip():
            prepare_argv.extend(["--usage-caption", usage_caption])

    loading = markup.get("loading")
    fetch_priority = markup.get("fetch_priority")
    sizes = markup.get("sizes")
    needs_responsive_variants = markup.get("needs_responsive_variants")
    if isinstance(loading, str) and loading in {"lazy", "eager"}:
        prepare_argv.extend(["--loading", loading])
    if isinstance(fetch_priority, str) and fetch_priority in {"high", "low"}:
        prepare_argv.extend(["--fetch-priority", fetch_priority])
    if needs_responsive_variants is True:
        prepare_argv.append("--responsive")
    if isinstance(sizes, str) and sizes.strip():
        prepare_argv.extend(["--sizes", sizes])

    return normalize_args(parse_args(prepare_argv))


def build_seo_handoff_report_item(
    *,
    item_id: str,
    priority: str | None,
    reasons: list[str],
    status: str,
    message: str,
    entry: dict[str, object] | None = None,
    source_path: Path | None = None,
    output_path: Path | None = None,
    sidecar_path: Path | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": item_id,
        "status": status,
        "priority": priority,
        "reasons": reasons,
        "message": message,
    }
    if source_path is not None:
        payload["source_path"] = str(source_path)
    if output_path is not None:
        payload["output_path"] = str(output_path)
    if sidecar_path is not None:
        payload["sidecar_path"] = str(sidecar_path)
    if entry is not None:
        payload["entry"] = entry
    return payload


def run_seo_handoff(args: argparse.Namespace) -> int:
    handoff = load_seo_handoff(args.handoff)
    items = handoff.get("items", [])
    report_items: list[dict[str, object]] = []
    applied_count = 0
    manual_count = 0
    failed_count = 0

    for index, raw_item in enumerate(items, start=1):
        if not isinstance(raw_item, dict):
            failed_count += 1
            report_items.append(
                build_seo_handoff_report_item(
                    item_id=f"item-{index}",
                    priority=None,
                    reasons=[],
                    status="failed",
                    message="SEO handoff item must be a JSON object.",
                )
            )
            continue

        item_id = str(raw_item.get("id") or f"item-{index}")
        priority = str(raw_item.get("priority")) if raw_item.get("priority") is not None else None
        reasons_value = raw_item.get("reasons", [])
        reasons = [str(reason) for reason in reasons_value] if isinstance(reasons_value, list) else []
        status_value = str(raw_item.get("status") or "manual")

        if status_value != "ready":
            manual_count += 1
            notes = raw_item.get("notes", [])
            note_text = "; ".join(str(note) for note in notes) if isinstance(notes, list) and notes else "Manual review required."
            report_items.append(
                build_seo_handoff_report_item(
                    item_id=item_id,
                    priority=priority,
                    reasons=reasons,
                    status="manual",
                    message=note_text,
                )
            )
            continue

        try:
            prepare_args = build_prepare_args_from_handoff(handoff, raw_item, args)
            recipe = RECIPES[prepare_args.recipe]
            result = process_one(prepare_args.input.resolve(), recipe, prepare_args)
            entry = serialize_result(result, recipe)
            sidecar_path = result.output_path.with_suffix(".json")
            if not prepare_args.dry_run:
                write_sidecar(sidecar_path, entry)
            report_items.append(
                build_seo_handoff_report_item(
                    item_id=item_id,
                    priority=priority,
                    reasons=reasons,
                    status="dry-run" if prepare_args.dry_run else "applied",
                    message="Prepared image remediation item.",
                    entry=entry,
                    source_path=result.source_path,
                    output_path=result.output_path,
                    sidecar_path=sidecar_path,
                )
            )
            applied_count += 1
        except WebpMeDaddyError as exc:
            failed_count += 1
            report_items.append(
                build_seo_handoff_report_item(
                    item_id=item_id,
                    priority=priority,
                    reasons=reasons,
                    status="failed",
                    message=str(exc),
                )
            )

    report = {
        "version": VERSION,
        "run": {
            "command": "seo-handoff",
            "handoff": str(args.handoff),
            "dry_run": args.dry_run,
            "overwrite": args.overwrite,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "page": handoff.get("page", {}),
        "summary": {
            "item_count": len(items),
            "applied_count": applied_count,
            "manual_count": manual_count,
            "failed_count": failed_count,
        },
        "items": report_items,
    }

    print("SEO handoff summary:")
    print(f"- {len(items)} items in handoff")
    print(f"- {applied_count} {'previewed' if args.dry_run else 'applied'} items")
    print(f"- {manual_count} manual items skipped")
    print(f"- {failed_count} failed items")

    previewed = [item for item in report_items if isinstance(item, dict) and item.get("status") in {"applied", "dry-run"}]
    if previewed:
        print("")
        print("Prepared items:")
        for item in previewed:
            print(f"- {item.get('id')}: {item.get('output_path')}")

    manual_items = [item for item in report_items if isinstance(item, dict) and item.get("status") == "manual"]
    if manual_items:
        print("")
        print("Manual review items:")
        for item in manual_items:
            print(f"- {item.get('id')}: {item.get('message')}")

    failed_items = [item for item in report_items if isinstance(item, dict) and item.get("status") == "failed"]
    if failed_items:
        print("")
        print("Failed items:")
        for item in failed_items:
            print(f"- {item.get('id')}: {item.get('message')}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("")
        print(f"JSON report: {args.json}")

    return 1 if failed_count else 0


def build_audit_payload(args: argparse.Namespace) -> dict[str, object]:
    source_files = iter_audit_source_files(args.src_dir)
    used_assets: dict[str, list[str]] = {}
    img_tags: list[ImgTagAudit] = []

    for source_file in source_files:
        text = source_file.read_text(encoding="utf-8")
        relative_file = source_file.relative_to(args.root).as_posix()
        for lineno, line in enumerate(text.splitlines(), 1):
            for asset_name in extract_literal_asset_references(line):
                used_assets.setdefault(asset_name, []).append(f"{relative_file}:{lineno}")
        img_tags.extend(audit_img_tags(source_file))

    public_assets = {
        path.relative_to(args.public_dir).as_posix(): {
            **inspect_public_asset(path),
            "relative_path": path.relative_to(args.public_dir).as_posix(),
        }
        for path in sorted(args.public_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in AUDIT_IMAGE_EXTENSIONS
    }

    used_asset_records = []
    live_pngs: list[dict[str, object]] = []
    live_jpegs: list[dict[str, object]] = []
    live_animated_assets: list[dict[str, object]] = []
    shared_assets: list[dict[str, object]] = []
    transparent_logo_padding_candidates: list[dict[str, object]] = []
    for asset_name, references in sorted(used_assets.items()):
        asset = dict(
            public_assets.get(
                asset_name,
                {
                    "name": Path(asset_name).name,
                    "relative_path": asset_name,
                    "path": None,
                    "extension": Path(asset_name).suffix.lower(),
                    "bytes": None,
                    "dimensions": None,
                    "frame_count": None,
                    "animated": False,
                },
            )
        )
        asset["references"] = references
        used_asset_records.append(asset)
        extension = str(asset.get("extension", "")).lower()
        if extension == ".png":
            live_pngs.append(asset)
        if extension in {".jpg", ".jpeg"}:
            live_jpegs.append(asset)
        if asset.get("animated") is True:
            live_animated_assets.append(asset)
        if infer_recipe_for_asset(asset) == "logo-lockup":
            padding_candidate = build_logo_padding_candidate(asset)
            if padding_candidate is not None:
                transparent_logo_padding_candidates.append(padding_candidate)
        unique_source_files = sorted({reference.rsplit(":", 1)[0] for reference in references})
        if len(unique_source_files) > 1:
            shared_assets.append(
                {
                    **asset,
                    "reference_files": unique_source_files,
                    "suggestion": "consider_usage_overrides",
                    "usage_override_suggestions": build_usage_override_suggestions(asset, unique_source_files, args.public_dir),
                }
            )

    unused_assets = [
        asset
        for name, asset in sorted(public_assets.items())
        if name not in used_assets
    ]

    missing_alt = [
        tag for tag in img_tags if tag.alt is None
    ]
    empty_alt = [
        tag for tag in img_tags if tag.alt is not None and tag.alt == ""
    ]
    missing_dimensions = [
        tag
        for tag in img_tags
        if not tag.has_fill and not (tag.has_width and tag.has_height)
    ]
    missing_loading = [
        tag for tag in img_tags if tag.loading is None
    ]
    missing_decoding = [
        tag for tag in img_tags if tag.component_kind == "html-img" and tag.decoding is None
    ]
    responsive_tags = [
        tag for tag in img_tags if tag.has_srcset
    ]
    autofix_suggestions = [
        suggestion
        for tag in img_tags
        if (suggestion := build_img_autofix(tag, public_assets)) is not None
    ]
    codemod_patches = [
        {
            "file": suggestion["file"],
            "line": suggestion["line"],
            "target": "jsx",
            "old_str": suggestion["content_update"]["old_str"],
            "new_str": suggestion["content_update"]["new_str"],
        }
        for suggestion in autofix_suggestions
        if isinstance(suggestion, dict)
        and isinstance(suggestion.get("content_update"), dict)
        and isinstance(suggestion["content_update"].get("old_str"), str)
        and isinstance(suggestion["content_update"].get("new_str"), str)
    ]

    def serialize_tag(tag: ImgTagAudit) -> dict[str, object]:
        return {
            "file": tag.file,
            "line": tag.line,
            "component_kind": tag.component_kind,
            "tag_name": tag.tag_name,
            "src": tag.src,
            "asset_name": extract_asset_name_from_src(tag.src),
            "alt": tag.alt,
            "has_fill": tag.has_fill,
            "has_width": tag.has_width,
            "has_height": tag.has_height,
            "loading": tag.loading,
            "decoding": tag.decoding,
            "has_srcset": tag.has_srcset,
            "has_sizes": tag.has_sizes,
        }

    payload = {
        "version": VERSION,
        "run": {
            "command": "audit",
            "root": str(args.root),
            "src_dir": str(args.src_dir),
            "public_dir": str(args.public_dir),
            "apply_autofix": bool(getattr(args, "apply_autofix", False)),
            "emit_fix_plan": bool(getattr(args, "emit_fix_plan", False)),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "summary": {
            "used_asset_count": len(used_asset_records),
            "unused_asset_count": len(unused_assets),
            "live_png_count": len(live_pngs),
            "live_jpeg_count": len(live_jpegs),
            "live_animated_count": len(live_animated_assets),
            "shared_asset_count": len(shared_assets),
            "transparent_logo_padding_count": len(transparent_logo_padding_candidates),
            "img_tag_count": len(img_tags),
            "next_image_tag_count": sum(1 for tag in img_tags if tag.component_kind == "next-image"),
            "missing_alt_count": len(missing_alt),
            "empty_alt_count": len(empty_alt),
            "missing_dimensions_count": len(missing_dimensions),
            "missing_loading_count": len(missing_loading),
            "missing_decoding_count": len(missing_decoding),
            "responsive_tag_count": len(responsive_tags),
            "autofixable_tag_count": len(autofix_suggestions),
            "codemod_patch_count": len(codemod_patches),
            "applied_patch_count": 0,
            "skipped_patch_count": 0,
            "fix_plan_count": 0,
        },
        "assets": {
            "used": used_asset_records,
            "unused": unused_assets,
            "live_pngs": live_pngs,
            "live_jpegs": live_jpegs,
            "live_animated": live_animated_assets,
            "shared_usage_candidates": shared_assets,
            "transparent_logo_padding_candidates": transparent_logo_padding_candidates,
        },
        "markup": {
            "img_tags": [serialize_tag(tag) for tag in img_tags],
            "missing_alt": [serialize_tag(tag) for tag in missing_alt],
            "empty_alt": [serialize_tag(tag) for tag in empty_alt],
            "missing_dimensions": [serialize_tag(tag) for tag in missing_dimensions],
            "missing_loading": [serialize_tag(tag) for tag in missing_loading],
            "missing_decoding": [serialize_tag(tag) for tag in missing_decoding],
            "autofix_suggestions": autofix_suggestions,
            "codemod_patches": codemod_patches,
        },
        "autofix": {
            "attempted": bool(getattr(args, "apply_autofix", False)),
            "applied": [],
            "skipped": [],
        },
    }
    if getattr(args, "emit_fix_plan", False):
        fix_plan = build_audit_fix_plan(args, payload)
        payload["fix_plan"] = fix_plan
        summary_payload = payload.get("summary")
        if isinstance(summary_payload, dict):
            summary_payload["fix_plan_count"] = len(fix_plan)
    return payload


def write_audit_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def apply_audit_autofix(payload: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    markup = payload.get("markup", {})
    patch_candidates = markup.get("codemod_patches", []) if isinstance(markup, dict) else []
    patches = [patch for patch in patch_candidates if isinstance(patch, dict)]

    file_contents: dict[Path, str] = {}
    dirty_files: set[Path] = set()
    applied: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []

    for patch in patches:
        file_value = patch.get("file")
        old_str = patch.get("old_str")
        new_str = patch.get("new_str")
        if not isinstance(file_value, str) or not isinstance(old_str, str) or not isinstance(new_str, str):
            skipped.append({**patch, "reason": "invalid_patch"})
            continue

        file_path = Path(file_value)
        if not file_path.exists():
            skipped.append({**patch, "reason": "file_not_found"})
            continue

        if file_path not in file_contents:
            file_contents[file_path] = file_path.read_text(encoding="utf-8")
        content = file_contents[file_path]
        occurrences = content.count(old_str)
        if occurrences == 0:
            skipped.append({**patch, "reason": "original_not_found"})
            continue
        if occurrences > 1:
            skipped.append({**patch, "reason": "multiple_matches"})
            continue

        file_contents[file_path] = content.replace(old_str, new_str, 1)
        dirty_files.add(file_path)
        applied.append({**patch, "reason": "applied"})

    for file_path in sorted(dirty_files):
        file_path.write_text(file_contents[file_path], encoding="utf-8")

    return {"applied": applied, "skipped": skipped}


def summarize_cleanup_assets(assets: list[dict[str, object]]) -> dict[str, int]:
    total_bytes = sum(
        int(asset.get("bytes", 0))
        for asset in assets
        if isinstance(asset, dict) and isinstance(asset.get("bytes"), int)
    )
    return {
        "asset_count": len(assets),
        "total_bytes": total_bytes,
    }


def build_cleanup_payload(
    args: argparse.Namespace,
    audit_payload: dict[str, object],
    deleted_assets: list[dict[str, object]],
) -> dict[str, object]:
    assets = audit_payload.get("assets", {})
    candidates = assets.get("unused", []) if isinstance(assets, dict) else []
    candidate_assets = [asset for asset in candidates if isinstance(asset, dict)]
    deleted = [asset for asset in deleted_assets if isinstance(asset, dict)]
    candidate_summary = summarize_cleanup_assets(candidate_assets)
    deleted_summary = summarize_cleanup_assets(deleted)
    return {
        "version": VERSION,
        "run": {
            "command": "cleanup",
            "root": str(args.root),
            "src_dir": str(args.src_dir),
            "public_dir": str(args.public_dir),
            "dry_run": args.dry_run,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "summary": {
            "candidate_count": candidate_summary["asset_count"],
            "candidate_bytes": candidate_summary["total_bytes"],
            "deleted_count": deleted_summary["asset_count"],
            "deleted_bytes": deleted_summary["total_bytes"],
        },
        "audit_summary": audit_payload.get("summary", {}),
        "cleanup": {
            "candidates": candidate_assets,
            "deleted": deleted,
        },
    }


def run_audit(args: argparse.Namespace) -> int:
    payload = build_audit_payload(args)
    if args.apply_autofix:
        autofix_results = apply_audit_autofix(payload)
        summary_payload = payload.get("summary")
        if isinstance(summary_payload, dict):
            summary_payload["applied_patch_count"] = len(autofix_results["applied"])
            summary_payload["skipped_patch_count"] = len(autofix_results["skipped"])
        autofix_payload = payload.get("autofix")
        if isinstance(autofix_payload, dict):
            autofix_payload["applied"] = autofix_results["applied"]
            autofix_payload["skipped"] = autofix_results["skipped"]
    summary = payload["summary"]
    assets = payload["assets"]
    markup = payload["markup"]

    print("Image audit summary:")
    print(f"- {summary['used_asset_count']} referenced public assets")
    print(f"- {summary['unused_asset_count']} unused public assets")
    print(f"- {summary['live_png_count']} live PNG assets")
    print(f"- {summary['live_jpeg_count']} live JPEG assets")
    print(f"- {summary['live_animated_count']} live animated assets")
    print(f"- {summary['shared_asset_count']} shared assets used across multiple source files")
    print(f"- {summary['transparent_logo_padding_count']} transparent logo assets with notable padding")
    print(f"- {summary['img_tag_count']} image tags scanned")
    print(f"- {summary['next_image_tag_count']} next/image tags scanned")
    print(f"- {summary['missing_alt_count']} image tags missing alt")
    print(f"- {summary['empty_alt_count']} image tags with empty alt")
    print(f"- {summary['missing_dimensions_count']} image tags missing width/height")
    print(f"- {summary['missing_loading_count']} image tags missing loading")
    print(f"- {summary['missing_decoding_count']} image tags missing decoding")
    print(f"- {summary['responsive_tag_count']} image tags with srcset")
    print(f"- {summary['autofixable_tag_count']} image tags with autofix suggestions")
    print(f"- {summary['codemod_patch_count']} file-specific codemod patches")
    if args.emit_fix_plan:
        print(f"- {summary['fix_plan_count']} suggested fix-plan commands")
    if args.apply_autofix:
        print(f"- {summary['applied_patch_count']} codemod patches applied")
        print(f"- {summary['skipped_patch_count']} codemod patches skipped")

    live_pngs = assets["live_pngs"] if isinstance(assets, dict) else []
    if isinstance(live_pngs, list) and live_pngs:
        print("")
        print("Live PNG assets:")
        for asset in live_pngs:
            if isinstance(asset, dict):
                print(f"- {asset.get('name')} ({asset.get('bytes')} bytes)")

    live_jpegs = assets["live_jpegs"] if isinstance(assets, dict) else []
    if isinstance(live_jpegs, list) and live_jpegs:
        print("")
        print("Live JPEG assets:")
        for asset in live_jpegs:
            if isinstance(asset, dict):
                print(f"- {asset.get('name')} ({asset.get('bytes')} bytes)")

    live_animated = assets["live_animated"] if isinstance(assets, dict) else []
    if isinstance(live_animated, list) and live_animated:
        print("")
        print("Live animated assets:")
        for asset in live_animated:
            if isinstance(asset, dict):
                print(
                    f"- {asset.get('name')} ({asset.get('bytes')} bytes, {asset.get('frame_count')} frames) -> use webp-me-daddy animate"
                )

    shared_candidates = assets["shared_usage_candidates"] if isinstance(assets, dict) else []
    if isinstance(shared_candidates, list) and shared_candidates:
        print("")
        print("Shared assets that may need usage-level metadata overrides:")
        for asset in shared_candidates:
            if isinstance(asset, dict):
                reference_files = asset.get("reference_files", [])
                files_text = ", ".join(reference_files) if isinstance(reference_files, list) else "multiple files"
                print(f"- {asset.get('relative_path', asset.get('name'))}: {files_text}")
                usage_suggestions = asset.get("usage_override_suggestions", [])
                if isinstance(usage_suggestions, list):
                    for suggestion in usage_suggestions:
                        if isinstance(suggestion, dict):
                            print(f"  usage_key: {suggestion.get('usage_key')}")

    transparent_logo_padding = assets["transparent_logo_padding_candidates"] if isinstance(assets, dict) else []
    if isinstance(transparent_logo_padding, list) and transparent_logo_padding:
        print("")
        print("Transparent logo assets with notable padding:")
        for asset in transparent_logo_padding:
            if isinstance(asset, dict):
                print(f"- {asset.get('relative_path', asset.get('name'))}")
                print(f"  {asset.get('recommendation')}")

    unused = assets["unused"] if isinstance(assets, dict) else []
    if isinstance(unused, list) and unused:
        print("")
        print("Unused public assets:")
        for asset in unused:
            if isinstance(asset, dict):
                print(f"- {asset.get('name')}")

    missing_dimensions = markup["missing_dimensions"] if isinstance(markup, dict) else []
    if isinstance(missing_dimensions, list) and missing_dimensions:
        print("")
        print("Markup missing width/height:")
        for tag in missing_dimensions:
            if isinstance(tag, dict):
                print(f"- {tag.get('file')}:{tag.get('line')}")

    missing_loading = markup["missing_loading"] if isinstance(markup, dict) else []
    if isinstance(missing_loading, list) and missing_loading:
        print("")
        print("Markup missing loading:")
        for tag in missing_loading:
            if isinstance(tag, dict):
                print(f"- {tag.get('file')}:{tag.get('line')}")

    missing_decoding = markup["missing_decoding"] if isinstance(markup, dict) else []
    if isinstance(missing_decoding, list) and missing_decoding:
        print("")
        print("Markup missing decoding:")
        for tag in missing_decoding:
            if isinstance(tag, dict):
                print(f"- {tag.get('file')}:{tag.get('line')}")

    autofix_suggestions = markup["autofix_suggestions"] if isinstance(markup, dict) else []
    if isinstance(autofix_suggestions, list) and autofix_suggestions:
        print("")
        print("Autofix suggestions:")
        for suggestion in autofix_suggestions:
            if isinstance(suggestion, dict):
                print(f"- {suggestion.get('file')}:{suggestion.get('line')}")
                jsx_patch = suggestion.get("jsx_patch")
                if isinstance(jsx_patch, str):
                    print("  JSX patch:")
                    print(f"  {jsx_patch}")

    codemod_patches = markup["codemod_patches"] if isinstance(markup, dict) else []
    if isinstance(codemod_patches, list) and codemod_patches:
        print("")
        print("Codemod patch candidates:")
        for patch in codemod_patches:
            if isinstance(patch, dict):
                print(f"- {patch.get('file')}:{patch.get('line')}")
                print("  Replace:")
                print(f"  {patch.get('old_str')}")
                print("  With:")
                print(f"  {patch.get('new_str')}")

    autofix_results = payload["autofix"] if isinstance(payload, dict) else {}
    if args.apply_autofix and isinstance(autofix_results, dict):
        applied = autofix_results.get("applied", [])
        skipped = autofix_results.get("skipped", [])
        print("")
        print("Autofix application:")
        if isinstance(applied, list) and applied:
            print("Applied patches:")
            for patch in applied:
                if isinstance(patch, dict):
                    print(f"- {patch.get('file')}:{patch.get('line')}")
        if isinstance(skipped, list) and skipped:
            print("Skipped patches:")
            for patch in skipped:
                if isinstance(patch, dict):
                    print(f"- {patch.get('file')}:{patch.get('line')} ({patch.get('reason')})")
        if (not isinstance(applied, list) or not applied) and (not isinstance(skipped, list) or not skipped):
            print("No codemod patches were available to apply.")

    if args.emit_fix_plan:
        fix_plan = payload.get("fix_plan", [])
        if isinstance(fix_plan, list) and fix_plan:
            print("")
            print("Suggested fix plan:")
            for step in fix_plan:
                if isinstance(step, dict):
                    reason = step.get("reason")
                    asset = step.get("asset")
                    command = step.get("command")
                    header = f"- [{step.get('kind')}] {asset}" if asset else f"- [{step.get('kind')}]"
                    print(header)
                    if reason:
                        print(f"  Why: {reason}")
                    if command:
                        print(f"  Run: {command}")

    if args.json:
        write_audit_report(args.json.resolve(), payload)
        print("")
        print(f"Audit report: {args.json.resolve()}")

    return 0


def run_cleanup(args: argparse.Namespace) -> int:
    audit_payload = build_audit_payload(args)
    assets = audit_payload.get("assets", {})
    candidates = assets.get("unused", []) if isinstance(assets, dict) else []
    candidate_assets = [asset for asset in candidates if isinstance(asset, dict)]
    cleanup_summary = summarize_cleanup_assets(candidate_assets)

    print("Image cleanup summary:")
    print(f"- {cleanup_summary['asset_count']} unused public assets found")
    print(f"- {cleanup_summary['total_bytes']} bytes reclaimable")

    if candidate_assets:
        print("")
        print("Cleanup candidates:")
        for asset in candidate_assets:
            print(f"- {asset.get('name')} ({asset.get('bytes')} bytes)")
    else:
        print("")
        print("No unused public assets found.")

    deleted_assets: list[dict[str, object]] = []
    if args.dry_run:
        if candidate_assets:
            print("")
            print("Dry run only. Re-run with --yes to delete these assets.")
    elif candidate_assets:
        for asset in candidate_assets:
            path_value = asset.get("path")
            if not isinstance(path_value, str):
                continue
            target_path = Path(path_value)
            if target_path.exists():
                try:
                    target_path.unlink()
                except OSError:
                    pass  # FUSE filesystem; overwrite in-place
                deleted_assets.append(asset)
        print("")
        print(
            "Deleted "
            f"{len(deleted_assets)} unused public assets "
            f"and reclaimed {summarize_cleanup_assets(deleted_assets)['total_bytes']} bytes."
        )

    if args.json:
        payload = build_cleanup_payload(args, audit_payload, deleted_assets)
        write_audit_report(args.json.resolve(), payload)
        print("")
        print(f"Cleanup report: {args.json.resolve()}")

    return 0


def run_snippets(args: argparse.Namespace) -> int:
    sidecar = load_sidecar(args.sidecar)
    snippet_set, effective_metadata, active_usage_key = build_snippets_from_sidecar(
        sidecar,
        args.usage_key,
    )
    selected_targets = select_snippet_targets(snippet_set.targets, args.target)
    selected_payload = {
        name: {"markup": target.markup}
        for name, target in sorted(selected_targets.items())
    }

    print("Snippet helper:")
    print(f"Sidecar: {args.sidecar}")
    print(f"Usage key: {active_usage_key or 'default'}")
    print(f"Alt: {effective_metadata.alt}")
    print(f"Loading: {snippet_set.loading}")
    if snippet_set.srcset:
        print(f"Srcset: {snippet_set.srcset}")
    if snippet_set.sizes:
        print(f"Sizes: {snippet_set.sizes}")

    for name, target in sorted(selected_targets.items()):
        print("")
        print(f"[{name}]")
        print(target.markup)

    if args.json:
        payload = {
            "version": VERSION,
            "run": {
                "command": "snippets",
                "sidecar": str(args.sidecar),
                "usage_key": active_usage_key,
                "target": args.target,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "metadata": {
                "alt": effective_metadata.alt,
                "title": effective_metadata.title,
                "caption": effective_metadata.caption,
                "accessibility_mode": effective_metadata.accessibility_mode,
                "provenance": effective_metadata.provenance,
            },
            "snippets": {
                "src": snippet_set.src,
                "srcset": snippet_set.srcset,
                "sizes": snippet_set.sizes,
                "loading": snippet_set.loading,
                "fetch_priority": snippet_set.fetch_priority,
                "targets": selected_payload,
            },
        }
        write_audit_report(args.json, payload)
        print("")
        print(f"Snippet export: {args.json}")

    return 0


def convert_animated_webp_to_gif(source_path: Path, temp_dir: Path) -> Path:
    target_path = temp_dir / f"{source_path.stem}.gif"
    with Image.open(source_path) as image:
        if getattr(image, "n_frames", 1) <= 1:
            raise UsageError("Animate expects a GIF or animated WebP input.")
        frames: list[Image.Image] = []
        durations: list[int] = []
        for frame in ImageSequence.Iterator(image):
            frames.append(frame.convert("RGBA"))
            durations.append(int(frame.info.get("duration", image.info.get("duration", 40))))
        frames[0].save(
            target_path,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=int(image.info.get("loop", 0)),
            format="GIF",
            disposal=2,
        )
    return target_path


def build_animate_command(args: argparse.Namespace, source_path: Path) -> list[str]:
    command = [
        sys.executable,
        str(TRANSPARENT_GIF_SCRIPT),
        args.mode,
        str(source_path),
        str(args.output),
        "--size",
        str(args.size),
        "--threshold",
        str(args.threshold),
    ]
    if args.loop_start is not None:
        command.extend(["--loop-start", str(args.loop_start)])
    if args.loop_end is not None:
        command.extend(["--loop-end", str(args.loop_end)])
    if args.mode == "animated":
        command.extend(
            [
                "--speed-scale",
                str(args.speed_scale),
                "--midpoint-frames",
                str(args.midpoint_frames),
                "--bridge-frames",
                str(args.bridge_frames),
                "--bridge-duration",
                str(args.bridge_duration),
                "--quality",
                str(args.quality),
                "--method",
                str(args.method),
            ]
        )
    else:
        command.extend(["--still-frame", str(args.still_frame)])
    return command


def run_animate(args: argparse.Namespace) -> int:
    suffix = args.input.suffix.lower()
    if suffix not in {".gif", ".webp"}:
        raise UsageError("Animate input must be a GIF or animated WebP file.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp_dir: tempfile.TemporaryDirectory | None = None
    handoff_source = args.input
    try:
        if suffix == ".webp":
            temp_dir = tempfile.TemporaryDirectory(prefix="webp-me-daddy-animate-")
            handoff_source = convert_animated_webp_to_gif(args.input, Path(temp_dir.name))

        command = build_animate_command(args, handoff_source)
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "Transparent loop workflow failed."
            raise WebpMeDaddyError(message)

        if suffix == ".webp":
            print(f"Animated WebP handoff source: {handoff_source}")
        if result.stdout.strip():
            print(result.stdout.strip())
        print(f"Animated output: {args.output}")
        return 0
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def format_output_size(size: int | None) -> str:
    return "dry-run" if size is None else f"{size} bytes"


def format_reduction(reduction: float | None) -> str:
    return "dry-run" if reduction is None else f"{reduction:.1f}%"


def clip_terminal_text(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def proof_surface_names_for_result(result: ProcessResult) -> str:
    surfaces = ["dark", "light"]
    if result.has_transparency:
        surfaces.append("checker")
    return ", ".join(surfaces)


def effective_alt_for_result(result: ProcessResult) -> str:
    if result.active_usage_key:
        override = result.usage_overrides.get(result.active_usage_key)
        if override:
            return override.alt
    return result.metadata.alt


def suggested_action_for_issue(code: str) -> str:
    actions = {
        "alt_too_long": "trim alt",
        "missing_alt": "add alt",
        "decorative_has_alt": "clear alt",
        "filename_like_alt": "rewrite alt",
        "keyword_stuffed_alt": "simplify alt",
        "no_responsive_variants": "enable responsive",
        "oversized_for_recipe": "lower quality",
        "redundant_alt_prefix": "drop image of",
        "text_bearing_missing_visible_text": "add visible_text",
    }
    if code.startswith("missing_structured_field:"):
        return "repair sidecar"
    return actions.get(code, "review metadata")


def extract_entry_issue_details(entry: dict[str, object]) -> tuple[str, list[str], list[str]]:
    analysis = entry.get("analysis", {})
    if not isinstance(analysis, dict):
        return "ok", [], []
    status = str(analysis.get("status", "ok") or "ok")
    lints = analysis.get("lints", {})
    if not isinstance(lints, dict):
        return status, [], []
    blocking = lints.get("blocking", [])
    warnings = lints.get("warnings", [])
    issue_codes: list[str] = []
    if isinstance(blocking, list):
        issue_codes.extend(str(code) for code in blocking)
    if isinstance(warnings, list):
        issue_codes.extend(str(code) for code in warnings)
    labels = [pretty_issue(code) for code in issue_codes[:2]]
    actions: list[str] = []
    for code in issue_codes:
        action = suggested_action_for_issue(code)
        if action not in actions:
            actions.append(action)
        if len(actions) >= 2:
            break
    return status, labels, actions


def print_batch_dry_run_summary(results: list[ProcessResult], entries: list[dict[str, object]]) -> None:
    print("Dry-run proof summary:")
    headers = ("Source", "Output", "Size", "Status", "Action", "Surfaces", "Alt preview")
    rows: list[tuple[str, str, str, str, str, str, str]] = []
    for result, entry in zip(results, entries):
        status, labels, actions = extract_entry_issue_details(entry)
        status_text = status if not labels else f"{status}: {'; '.join(labels)}"
        action_text = ", ".join(actions) if actions else "-"
        rows.append(
            (
                result.source_path.name,
                result.output_path.name,
                f"{result.width}x{result.height}",
                status_text,
                action_text,
                proof_surface_names_for_result(result),
                effective_alt_for_result(result),
            )
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            max_width = 60 if index == 3 else 24 if index == 4 else 42 if index == 6 else 28
            widths[index] = min(max(widths[index], len(value)), max_width)

    divider = " | ".join("-" * width for width in widths)
    header_row = " | ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    print(header_row)
    print(divider)
    for source, output, size, status_text, action_text, surfaces, alt_preview in rows:
        values = (
            clip_terminal_text(source, widths[0]),
            clip_terminal_text(output, widths[1]),
            clip_terminal_text(size, widths[2]),
            clip_terminal_text(status_text, widths[3]),
            clip_terminal_text(action_text, widths[4]),
            clip_terminal_text(surfaces, widths[5]),
            clip_terminal_text(alt_preview, widths[6]),
        )
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(values)))
    print("")


def print_result(result: ProcessResult, recipe: RecipeConfig, entry: dict[str, object]) -> None:
    print(f"Source: {result.source_path}")
    print(f"Mode: {result.mode}")
    print(f"Recipe: {recipe.name} ({result.width}x{result.height}, {recipe.aspect_ratio})")
    print(f"Output: {result.output_path}")
    print(f"Original size: {result.source_size} bytes")
    print(f"WebP size: {format_output_size(result.output_size)}")
    print(f"Reduction: {format_reduction(result.reduction)}")
    print(f"Accessibility mode: {result.metadata.accessibility_mode}")
    print(f"Fit mode: {result.fit_mode}")
    print(f"Framing: {result.framing}")
    print(f"Suggested alt: {result.metadata.alt}")
    print(f"Suggested title: {result.metadata.title}")
    print(f"Suggested caption: {result.metadata.caption}")
    if result.active_usage_key:
        print(f"Active usage override: {result.active_usage_key}")
        override = result.usage_overrides.get(result.active_usage_key)
        if override:
            print(f"Usage alt: {override.alt}")
    print(f"Suggested src: {result.snippets.src}")
    print(f"Crop focus: {result.focus_label} ({result.focus_x:.2f}, {result.focus_y:.2f})")
    if result.snippets.enabled:
        if result.snippets.srcset:
            print(f"Suggested srcset: {result.snippets.srcset}")
        if result.snippets.sizes:
            print(f"Suggested sizes: {result.snippets.sizes}")
        html_target = result.snippets.targets.get("html")
        react_target = result.snippets.targets.get("react")
        if html_target:
            print(f"HTML snippet: {html_target.markup}")
        if react_target:
            print(f"React snippet: {react_target.markup}")
    else:
        print("Snippets: disabled by recipe or flag")
    analysis = entry.get("analysis", {})
    if isinstance(analysis, dict):
        lints = analysis.get("lints", {})
        if isinstance(lints, dict):
            blocking = lints.get("blocking", [])
            warnings = lints.get("warnings", [])
            if blocking:
                print(f"Blocking issues: {', '.join(blocking)}")
            if warnings:
                print(f"Warnings: {', '.join(warnings)}")
    print("")


def run_processing_command(args: argparse.Namespace) -> int:
    recipe = RECIPES[args.recipe]

    if args.command == "prepare":
        input_path = args.input.resolve()
        if not input_path.is_file():
            raise UsageError("Prepare input must be a single image file.")
        if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise UsageError("Prepare input must be a PNG, JPG, JPEG, or WebP file.")
        source_paths = [input_path]
    else:
        source_paths = iter_source_paths(args.input, getattr(args, "recursive", False))
        source_paths = collapse_batch_paths(
            source_paths,
            overwrite=args.overwrite,
            reencode_webp=args.reencode_webp,
        )

    results = [process_one(source_path, recipe, args) for source_path in source_paths]
    entries = [serialize_result(result, recipe) for result in results]

    if args.command == "batch" and args.dry_run:
        print_batch_dry_run_summary(results, entries)
        if getattr(args, "proof_contact_sheet", None):
            proof_path = args.proof_contact_sheet
            if proof_path.exists() and not args.overwrite:
                raise UsageError(
                    f"Proof contact sheet already exists: {proof_path}. Use --overwrite to replace it."
                )
            proof_path.parent.mkdir(parents=True, exist_ok=True)
            contact_sheet = render_batch_contact_sheet(results, entries, recipe)
            contact_sheet.save(proof_path, format="PNG")
            print(f"Batch proof contact sheet: {proof_path}")
            print("")

    for result, entry in zip(results, entries):
        if not (args.command == "batch" and args.dry_run):
            print_result(result, recipe, entry)
        if args.write_sidecar:
            sidecar_path = result.output_path.with_suffix(".json")
            if args.dry_run:
                print(f"Sidecar (dry-run): {sidecar_path}")
            else:
                write_sidecar(sidecar_path, entry)
                print(f"Sidecar: {sidecar_path}")

    if args.manifest:
        manifest_path = args.manifest.resolve()
        if args.dry_run:
            print(f"Manifest (dry-run): {manifest_path}")
        else:
            write_manifest(manifest_path, args.command, args.input, recipe, args, entries)
            print(f"Manifest: {manifest_path}")

    if len(results) > 1:
        summary = summarize_entries(entries)
        print(
            "Processed "
            f"{summary['image_count']} images: "
            f"{summary['generated_count']} generated WebP files, "
            f"{summary['metadata_only_count']} metadata-only files, "
            f"{summary['warning_issue_count']} warnings."
        )

    return 0


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"Manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Manifest is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise ManifestError("Manifest root must be a JSON object.")
    if payload.get("version") != VERSION:
        raise ManifestError(
            f"Manifest version must be {VERSION}. Found {payload.get('version')!r}."
        )
    for key in ("run", "summary", "images"):
        if key not in payload:
            raise ManifestError(f"Manifest is missing required top-level key: {key}.")
    if not isinstance(payload.get("images"), list):
        raise ManifestError("Manifest images must be a list.")
    return payload


def validate_image_entry(image: dict[str, Any], index: int) -> None:
    required = ("version", "id", "input", "output", "recipe", "metadata", "snippets", "analysis")
    for key in required:
        if key not in image:
            raise ManifestError(f"Image entry {index} is missing required key: {key}.")
    if image.get("version") != VERSION:
        raise ManifestError(
            f"Image entry {index} must use version {VERSION}. Found {image.get('version')!r}."
        )


def pretty_issue(code: str) -> str:
    labels = {
        "alt_too_long": "alt text exceeds recommended length",
        "missing_alt": "missing alt text",
        "decorative_has_alt": "decorative image has non-empty alt",
        "filename_like_alt": "alt text mirrors the file name",
        "keyword_stuffed_alt": "alt text looks keyword stuffed",
        "no_responsive_variants": "missing responsive variants for hero-like recipe",
        "oversized_for_recipe": "output exceeds byte budget for recipe",
        "redundant_alt_prefix": "alt text starts with a redundant prefix",
        "text_bearing_missing_visible_text": "text-bearing image is missing visible text input",
    }
    if code.startswith("missing_structured_field:"):
        return f"missing structured field ({code.split(':', 1)[1]})"
    return labels.get(code, code.replace("_", " "))


def run_lint(args: argparse.Namespace) -> int:
    payload = load_manifest(args.manifest.resolve())
    images = payload["images"]
    if not images:
        print("Image lint summary:")
        print("- 0 images checked")
        print("Lint status: OK")
        return 0

    grouped_offenders: dict[str, list[str]] = {}
    blocking_counter: Counter[str] = Counter()
    warning_counter: Counter[str] = Counter()

    for index, image in enumerate(images, start=1):
        if not isinstance(image, dict):
            raise ManifestError(f"Image entry {index} must be a JSON object.")
        validate_image_entry(image, index)
        blocking, warnings = lint_image_entry(
            image,
            max_hero_kb=args.max_hero_kb,
            max_standard_kb=args.max_standard_kb,
            strict=args.strict,
        )
        image_id = str(image.get("id", f"image-{index}"))
        for code in blocking:
            blocking_counter[code] += 1
            grouped_offenders.setdefault(code, []).append(image_id)
        for code in warnings:
            warning_counter[code] += 1
            grouped_offenders.setdefault(code, []).append(image_id)

    print("Image lint summary:")
    print(f"- {len(images)} images checked")
    print(f"- {sum(blocking_counter.values())} blocking issues")
    print(f"- {sum(warning_counter.values())} warnings")

    for code, count in sorted(blocking_counter.items()):
        print(f"- {count} images with {pretty_issue(code)}")
    for code, count in sorted(warning_counter.items()):
        print(f"- {count} images with {pretty_issue(code)}")

    for code in sorted(grouped_offenders):
        print("")
        print(f"{pretty_issue(code).title()}:")
        for image_id in grouped_offenders[code]:
            print(f"- {image_id}")

    if blocking_counter:
        print("")
        print(f"Lint status: {'FAIL (strict)' if args.strict else 'FAIL'}")
        return 1

    print("")
    print("Lint status: OK")
    return 0


def wants_json_errors(argv: list[str]) -> bool:
    return "--json-errors" in argv


def emit_error(exc: Exception, json_errors: bool) -> int:
    exit_code = getattr(exc, "exit_code", 1)
    if json_errors:
        payload = {
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
                "exit_code": exit_code,
            }
        }
        print(json.dumps(payload, indent=2), file=sys.stderr)
    else:
        print(f"[webp-me-daddy] Error: {exc}", file=sys.stderr)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    argv_list = list(sys.argv[1:] if argv is None else argv)
    json_errors_requested = wants_json_errors(argv_list)
    try:
        args = normalize_args(parse_args(argv_list))
        json_errors_requested = getattr(args, "json_errors", False)
        if args.command == "lint":
            return run_lint(args)
        if args.command == "audit":
            return run_audit(args)
        if args.command == "seo-handoff":
            return run_seo_handoff(args)
        if args.command == "cleanup":
            return run_cleanup(args)
        if args.command == "snippets":
            return run_snippets(args)
        if args.command == "proof":
            return run_proof(args)
        if args.command == "animate":
            return run_animate(args)
        return run_processing_command(args)
    except WebpMeDaddyError as exc:
        return emit_error(exc, json_errors_requested)
    except Exception as exc:  # pragma: no cover - defensive fallback
        return emit_error(exc, json_errors_requested)


if __name__ == "__main__":
    raise SystemExit(main())
