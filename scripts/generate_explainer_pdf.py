from __future__ import annotations

import html
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as PlatypusImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "assets" / "webp-me-daddy-explainer.pdf"
LABS_LOGO_PATH = ROOT / "assets" / "shadewater-labs-logo-lockup.png"

PAGE_BG = colors.HexColor("#04121F")
SURFACE = colors.HexColor("#122A33")
SURFACE_ALT = colors.HexColor("#253E44")
SURFACE_CARD = colors.HexColor("#16252D")
FOREGROUND = colors.HexColor("#F5F1E8")
FOREGROUND_MUTED = colors.HexColor("#BDA884")
SANDSTONE = colors.HexColor("#9A7A53")
TEAL = colors.HexColor("#176B66")
CORAL = colors.HexColor("#D1A76C")
LINE = colors.HexColor("#31505A")


def styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    sample.add(
        ParagraphStyle(
            name="HeroTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=30,
            textColor=FOREGROUND,
            alignment=TA_CENTER,
            spaceAfter=10,
        )
    )
    sample.add(
        ParagraphStyle(
            name="EyebrowCenter",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=CORAL,
            alignment=TA_CENTER,
            spaceAfter=7,
        )
    )
    sample.add(
        ParagraphStyle(
            name="DeckCenter",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=11.5,
            leading=17,
            textColor=FOREGROUND_MUTED,
            alignment=TA_CENTER,
            spaceAfter=14,
        )
    )
    sample.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=19,
            textColor=FOREGROUND,
            spaceBefore=4,
            spaceAfter=4,
        )
    )
    sample.add(
        ParagraphStyle(
            name="SectionIntro",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=FOREGROUND_MUTED,
            spaceAfter=10,
        )
    )
    sample.add(
        ParagraphStyle(
            name="Body",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=FOREGROUND,
            alignment=TA_LEFT,
        )
    )
    sample.add(
        ParagraphStyle(
            name="Tagline",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.white,
            alignment=TA_CENTER,
        )
    )
    sample.add(
        ParagraphStyle(
            name="Badge",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10,
            textColor=FOREGROUND,
            alignment=TA_CENTER,
        )
    )
    sample.add(
        ParagraphStyle(
            name="CardTitle",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=FOREGROUND,
            spaceAfter=5,
        )
    )
    sample.add(
        ParagraphStyle(
            name="CardBody",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.3,
            leading=12.5,
            textColor=FOREGROUND,
        )
    )
    sample.add(
        ParagraphStyle(
            name="StepNum",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=CORAL,
            spaceAfter=4,
        )
    )
    sample.add(
        ParagraphStyle(
            name="CodeLabel",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10.5,
            textColor=FOREGROUND,
            spaceAfter=0,
        )
    )
    sample.add(
        ParagraphStyle(
            name="CodeBlock",
            parent=sample["BodyText"],
            fontName="Courier",
            fontSize=8.1,
            leading=10.2,
            textColor=FOREGROUND,
        )
    )
    sample.add(
        ParagraphStyle(
            name="Small",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.8,
            leading=11.5,
            textColor=FOREGROUND_MUTED,
        )
    )
    return sample


def logo_lockup() -> PlatypusImage | None:
    if not LABS_LOGO_PATH.exists():
        return None
    logo = PlatypusImage(str(LABS_LOGO_PATH), width=2.9 * inch, height=2.2 * inch)
    logo.hAlign = "CENTER"
    return logo


def panel(
    content: list,
    width: float = 7.0 * inch,
    background= SURFACE,
    border_color= LINE,
    left_padding: int = 12,
    right_padding: int = 12,
    top_padding: int = 10,
    bottom_padding: int = 10,
) -> Table:
    box = Table([[content]], colWidths=[width])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.8, border_color),
                ("LEFTPADDING", (0, 0), (-1, -1), left_padding),
                ("RIGHTPADDING", (0, 0), (-1, -1), right_padding),
                ("TOPPADDING", (0, 0), (-1, -1), top_padding),
                ("BOTTOMPADDING", (0, 0), (-1, -1), bottom_padding),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return box


def section_rule(width: float = 7.0 * inch) -> Table:
    rule = Table([["", ""]], colWidths=[1.15 * inch, width - (1.15 * inch)], rowHeights=[0.05 * inch])
    rule.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), CORAL),
                ("BACKGROUND", (1, 0), (1, 0), LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return rule


def badge_grid(labels: list[str], columns: int = 4) -> Table:
    padded = list(labels)
    while len(padded) % columns != 0:
        padded.append("")

    rows: list[list[Paragraph]] = []
    for start in range(0, len(padded), columns):
        row = []
        for label in padded[start : start + columns]:
            text = label if label else "&nbsp;"
            row.append(Paragraph(text, styles()["Badge"]))
        rows.append(row)

    table = Table(rows, colWidths=[7.0 * inch / columns] * columns)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.75, SANDSTONE),
                ("INNERGRID", (0, 0), (-1, -1), 0.75, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def bullet_list(items: list[str], style: ParagraphStyle) -> list[Table]:
    flows: list[Table] = []
    bullet_style = ParagraphStyle(name=f"Bullet{style.name}", parent=style, spaceAfter=0)
    for item in items:
        table = Table(
            [["-", Paragraph(item, bullet_style)]],
            colWidths=[0.18 * inch, 6.55 * inch],
        )
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TEXTCOLOR", (0, 0), (-1, -1), FOREGROUND),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        flows.append(table)
    return flows


def card_cell(title: str, body: str, width: float, title_style: ParagraphStyle, body_style: ParagraphStyle) -> Table:
    content = [
        Paragraph(title, title_style),
        Paragraph(body, body_style),
    ]
    return panel(content, width=width, background=SURFACE_CARD, top_padding=10, bottom_padding=10)


def card_grid(items: list[tuple[str, str]], columns: int = 2) -> Table:
    total_width = 7.0 * inch
    gap = 0.14 * inch
    col_width = (total_width - (gap * (columns - 1))) / columns
    row_cells: list[list] = []
    current_row: list = []
    s = styles()

    for title, body in items:
        current_row.append(card_cell(title, body, col_width, s["CardTitle"], s["CardBody"]))
        if len(current_row) == columns:
            row_cells.append(current_row)
            current_row = []

    if current_row:
        while len(current_row) < columns:
            current_row.append(Spacer(1, 0.1 * inch))
        row_cells.append(current_row)

    grid = Table(row_cells, colWidths=[col_width] * columns, hAlign="LEFT")
    grid.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), gap),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    for row_index in range(len(row_cells)):
        grid.setStyle(TableStyle([("RIGHTPADDING", (columns - 1, row_index), (columns - 1, row_index), 0)]))
    return grid


def step_grid(items: list[tuple[str, str]]) -> Table:
    total_width = 7.0 * inch
    columns = 2
    gap = 0.16 * inch
    col_width = (total_width - gap) / columns
    s = styles()
    rows: list[list] = []
    current_row: list = []

    for index, (title, body) in enumerate(items, start=1):
        content = [
            Paragraph(f"STEP {index}", s["StepNum"]),
            Paragraph(title, s["CardTitle"]),
            Paragraph(body, s["CardBody"]),
        ]
        current_row.append(panel(content, width=col_width, background=SURFACE, top_padding=10, bottom_padding=10))
        if len(current_row) == columns:
            rows.append(current_row)
            current_row = []

    if current_row:
        while len(current_row) < columns:
            current_row.append(Spacer(1, 0.1 * inch))
        rows.append(current_row)

    grid = Table(rows, colWidths=[col_width] * columns)
    grid.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), gap),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    for row_index in range(len(rows)):
        grid.setStyle(TableStyle([("RIGHTPADDING", (columns - 1, row_index), (columns - 1, row_index), 0)]))
    return grid


def code_panel(title: str, command_lines: list[str]) -> Table:
    s = styles()
    body = "<br/>".join(html.escape(line) for line in command_lines)
    header = Table([[Paragraph(title, s["CodeLabel"])]], colWidths=[6.72 * inch])
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), TEAL),
                ("LEFTPADDING", (0, 0), (-1, -1), 11),
                ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    body_table = Table(
        [["", Paragraph(body, s["CodeBlock"])]],
        colWidths=[0.14 * inch, 6.58 * inch],
    )
    body_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), CORAL),
                ("BACKGROUND", (1, 0), (1, 0), SURFACE_CARD),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (1, 0), (1, 0), 11),
                ("RIGHTPADDING", (1, 0), (1, 0), 11),
                ("TOPPADDING", (1, 0), (1, 0), 9),
                ("BOTTOMPADDING", (1, 0), (1, 0), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    outer = Table([[header], [body_table]], colWidths=[6.72 * inch])
    outer.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.85, SANDSTONE),
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE_CARD),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return outer


def build_story() -> list:
    s = styles()
    story: list = []

    logo = logo_lockup()
    if logo is not None:
        story.append(logo)
        story.append(Spacer(1, 0.08 * inch))

    story.append(Paragraph("Skill Explainer", s["EyebrowCenter"]))
    story.append(Paragraph("Webp Me Daddy", s["HeroTitle"]))
    story.append(
        Paragraph(
            "A reusable Codex skill for turning website images into recipe-driven, lintable WebP assets with structured metadata, accessibility-safe alt text, framing-aware crops, and paste-ready snippets.",
            s["DeckCenter"],
        )
    )

    story.append(
        panel(
            [Paragraph("Shave bytes. Keep vibes. Retire hero-final-final.jpg with dignity.", s["Tagline"])],
            background=TEAL,
            border_color=TEAL,
            top_padding=9,
            bottom_padding=9,
        )
    )
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        badge_grid(
            [
                "Semantic recipes",
                "Review heroes",
                "Framing intent",
                "Contain logos",
                "Usage overrides",
                "Audit reports",
                "Cleanup mode",
                "Animated handoff",
            ]
        )
    )
    story.append(Spacer(1, 0.18 * inch))

    story.append(Paragraph("What The Skill Does", s["SectionTitle"]))
    story.append(section_rule())
    story.append(Spacer(1, 0.09 * inch))
    story.append(
        Paragraph(
            "The skill is built for the moment where a raw source image needs to become a real production asset: cropped for the slot it will live in, named cleanly, described accessibly, and returned with snippets that are ready to paste.",
            s["SectionIntro"],
        )
    )
    story.extend(
        bullet_list(
            [
                "Convert <b>.jpg</b> and <b>.png</b> files into optimized <b>.webp</b> assets.",
                "Use semantic recipes such as <b>hero-banner</b>, <b>review-hero</b>, <b>blog-cover</b>, <b>profile-avatar</b>, <b>poster</b>, <b>story-cover</b>, <b>logo-lockup</b>, and <b>logo-grid</b>.",
                "Guide cover crops with framing intent like <b>subject</b>, <b>text</b>, or <b>balanced</b> before dropping to exact focus coordinates.",
                "Preserve transparent logos and lockups with contain-mode outputs instead of forcing a crop.",
                "Generate SEO-friendly slugs, suggested <b>alt</b>, <b>title</b>, and <b>caption</b> metadata, plus usage-specific overrides for shared assets.",
                "Emit paste-ready <b>HTML</b>, <b>React</b>, <b>Next.js</b>, and <b>Astro</b> snippets inside a stable sidecar and manifest contract.",
                "Audit a real codebase for live legacy formats, animated assets, stale public files, and markup gaps, then suggest or apply low-risk fixes.",
                "Hand animated GIF and WebP inputs to the transparent loop optimizer from the same top-level CLI.",
            ],
            s["Body"],
        )
    )

    story.append(PageBreak())

    story.append(Paragraph("How The Workflow Thinks", s["SectionTitle"]))
    story.append(section_rule())
    story.append(Spacer(1, 0.09 * inch))
    story.append(
        Paragraph(
            "The strongest part of Webp Me Daddy is that it starts from placement intent instead of raw image math. That keeps the workflow useful for solo creators, developers, and future app interfaces without constantly asking the user to think in crop ratios first.",
            s["SectionIntro"],
        )
    )
    story.append(
        card_grid(
            [
                (
                    "Recipes describe the job",
                    "Pick a layout role like hero-banner, review-hero, or logo-lockup so widths, crop shape, and loading defaults match the real placement.",
                ),
                (
                    "Framing describes the priority",
                    "Use subject, text, or balanced framing when a crop needs to preserve a face, a title, or a compromise between the two.",
                ),
                (
                    "Accessibility and usage stay explicit",
                    "Decorative, logo, descriptive, and text-bearing modes keep alt behavior deliberate, while usage overrides let one asset stay honest across homepage, deck, and article placements.",
                ),
                (
                    "Audit closes the loop",
                    "The same skill can review a codebase, surface stale assets, suggest safe fixes, clean out leftovers, and hand animated files to the loop workflow instead of forcing them through still-image prep.",
                ),
            ]
        )
    )

    story.append(Paragraph("Typical Flow", s["SectionTitle"]))
    story.append(section_rule())
    story.append(Spacer(1, 0.09 * inch))
    story.append(
        Paragraph(
            "In practice the workflow compresses into four repeatable moves: choose the role, frame it intentionally, generate the reusable output, and review the result before it ships.",
            s["SectionIntro"],
        )
    )
    story.append(
        step_grid(
            [
                (
                    "Choose the role",
                    "Pick the recipe and accessibility mode based on where the image will live and whether it is informative, decorative, logo-like, or text-bearing.",
                ),
                (
                    "Frame it on purpose",
                    "Use framing intent first, then refine with focus presets or exact coordinates only if the default crop still misses the mark.",
                ),
                (
                    "Generate the reusable output",
                    "Prepare the WebP, optional responsive variants, and the structured sidecar or manifest entry that keeps the result explainable.",
                ),
                (
                    "Review before shipping",
                    "Generate the right snippet, run lint or audit when needed, clean stale sources, and hand animated files off to the loop workflow instead of forcing them through still-image prep.",
                ),
            ]
        )
    )

    story.append(PageBreak())

    story.append(Paragraph("Where It Helps Most", s["SectionTitle"]))
    story.append(section_rule())
    story.append(Spacer(1, 0.09 * inch))
    story.append(
        Paragraph(
            "The skill is most useful when you want opinionated defaults that still leave room for editorial judgment. It does best in projects where image quality, readability, and code integration all matter at once.",
            s["SectionIntro"],
        )
    )
    story.extend(
        bullet_list(
            [
                "Turn a homepage image into a proper <b>hero-banner</b> with responsive variants and eager-loading defaults.",
                "Transform movie posters or game key art into <b>review-hero</b> crops that match notes cards and full review headers cleanly.",
                "Prepare creator portraits as <b>profile-avatar</b> assets with cleaner naming and safer sizes.",
                "Preserve sponsor badges, lockups, and partner logos with <b>logo-lockup</b> or <b>logo-grid</b> recipes instead of cropping them into awkward shapes.",
                "Run a batch preview before touching a large public folder, then lint or audit the results before a deployment.",
                "Use usage overrides when the same image appears in a homepage hero, a sponsor deck, and a post header with different alt needs.",
                "Audit a mature codebase to find lingering PNG and JPEG usage, shared-context assets, animated files, unused originals, or missing width and loading hints.",
                "Regenerate page-specific snippets from the sidecar after a copy edit without reprocessing the source image.",
            ],
            s["Body"],
        )
    )

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("What You Get Back", s["SectionTitle"]))
    story.append(section_rule())
    story.append(Spacer(1, 0.09 * inch))
    story.append(
        card_grid(
            [
                (
                    "Optimized assets",
                    "A main WebP plus optional responsive variants like <b>image-480w.webp</b> or <b>image-960w.webp</b>.",
                ),
                (
                    "Structured metadata",
                    "Per-image sidecars and run-level manifests that store recipe, framing, dimensions, bytes, usage overrides, and analysis fields.",
                ),
                (
                    "Paste-ready snippets",
                    "HTML, React, Next.js, and Astro markup with escaped attributes and the right public paths for the site build.",
                ),
                (
                    "Project-level reports",
                    "Audit and cleanup JSON output for codebase reviews, autofix suggestions, codemod patches, apply-mode results, and reclaimed bytes.",
                ),
            ]
        )
    )

    story.append(Paragraph("Guardrails That Matter", s["SectionTitle"]))
    story.append(section_rule())
    story.append(Spacer(1, 0.09 * inch))
    story.extend(
        bullet_list(
            [
                "Small source images stay at native size by default so recipe targets do not accidentally upscale them.",
                "Poster-to-landscape review crops bias toward the main subject unless the user explicitly says title text must stay visible.",
                "Contain-mode outputs protect transparent edges and lockups that should never be trimmed just to satisfy a crop target.",
                "Audit apply mode stays conservative and only writes exact, single-match replacements for low-risk image-tag fixes.",
                "Framework-aware audit suggestions preserve <b>next/image</b> semantics instead of flattening everything into raw HTML assumptions.",
            ],
            s["Body"],
        )
    )

    story.append(Paragraph("Command Patterns", s["SectionTitle"]))
    story.append(section_rule())
    story.append(Spacer(1, 0.09 * inch))
    story.append(
        Paragraph(
            "These are the commands that matter most in day-to-day use. They are short enough to copy, but opinionated enough to show the intended shape of the workflow.",
            s["SectionIntro"],
        )
    )
    story.append(
        code_panel(
            "Prepare one review hero",
            [
                "python ~/.codex/skills/webp-me-daddy/scripts/webp_me_daddy.py prepare public/poster.jpg",
                "  --recipe review-hero --framing subject --public-root public --write-sidecar",
            ],
        )
    )
    story.append(Spacer(1, 0.1 * inch))
    story.append(
        code_panel(
            "Prepare a transparent logo lockup",
            [
                "python ~/.codex/skills/webp-me-daddy/scripts/webp_me_daddy.py prepare public/logo.png",
                "  --recipe logo-lockup --accessibility-mode logo --public-root public --write-sidecar",
            ],
        )
    )
    story.append(Spacer(1, 0.1 * inch))
    story.append(
        code_panel(
            "Preview a batch run",
            [
                "python ~/.codex/skills/webp-me-daddy/scripts/webp_me_daddy.py batch public",
                "  --recipe blog-cover --dry-run --manifest image-manifest.json",
            ],
        )
    )
    story.append(Spacer(1, 0.1 * inch))
    story.append(
        code_panel(
            "Audit and apply safe fixes",
            [
                "python ~/.codex/skills/webp-me-daddy/scripts/webp_me_daddy.py audit C:/path/to/project",
                "  --apply-autofix --json image-audit.json",
            ],
        )
    )
    story.append(Spacer(1, 0.1 * inch))
    story.append(
        code_panel(
            "Rebuild page-specific markup",
            [
                "python ~/.codex/skills/webp-me-daddy/scripts/webp_me_daddy.py snippets public/hero-source.json",
                "  --usage-key home.hero --target react",
            ],
        )
    )
    story.append(Spacer(1, 0.1 * inch))
    story.append(
        code_panel(
            "Hand off an animated asset",
            [
                "python ~/.codex/skills/webp-me-daddy/scripts/webp_me_daddy.py animate public/spin.webp public/spin-clean.webp",
                "  --size 220 --bridge-frames 8",
            ],
        )
    )

    story.append(Spacer(1, 0.14 * inch))
    story.append(Paragraph("Validation", s["SectionTitle"]))
    story.append(section_rule())
    story.append(Spacer(1, 0.09 * inch))
    story.extend(
        bullet_list(
            [
                "Run <b>test_prepare_image.py</b> after meaningful script changes.",
                "Regenerate the explainer PDF and visually review the latest pages instead of trusting the source alone.",
                "Smoke-test <b>audit</b>, <b>cleanup --dry-run</b>, <b>snippets</b>, and <b>animate</b> against a real project so the helper flows stay honest.",
                "Run the skill validator before shipping documentation updates or command changes.",
            ],
            s["Body"],
        )
    )

    story.append(Spacer(1, 0.2 * inch))
    story.append(
        panel(
            [
                Paragraph(
                    "The future web app should inherit this same structure: recipe-first inputs, framing-aware crops, structured sidecars, and audit-style reporting, rather than becoming a generic upload-and-download converter.",
                    s["CardBody"],
                )
            ],
            background=SURFACE,
            border_color=SANDSTONE,
            top_padding=12,
            bottom_padding=12,
        )
    )

    return story


def draw_page_background(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(PAGE_BG)
    canvas.rect(0, 0, LETTER[0], LETTER[1], fill=1, stroke=0)
    canvas.setFillColor(TEAL)
    canvas.rect(0.45 * inch, LETTER[1] - 0.45 * inch, LETTER[0] - 0.9 * inch, 0.07 * inch, fill=1, stroke=0)
    canvas.restoreState()


def draw_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(FOREGROUND_MUTED)
    canvas.drawString(doc.leftMargin, 0.42 * inch, "Webp Me Daddy")
    canvas.setFillColor(CORAL)
    canvas.drawRightString(7.9 * inch, 0.42 * inch, f"Page {doc.page}")
    canvas.restoreState()


def draw_page(canvas, doc) -> None:
    draw_page_background(canvas, doc)
    draw_footer(canvas, doc)


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=LETTER,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title="Webp Me Daddy Explainer",
        author="Codex",
    )
    doc.build(build_story(), onFirstPage=draw_page, onLaterPages=draw_page)
    print(OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
