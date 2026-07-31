# Webp Me Daddy 🖼️

A recipe-driven WebP pipeline for website images. You tell it what the image is *for*, not what to do to it, and it handles the rest: optimized variants, responsive sets, structured metadata, accessibility-safe alt text, framework snippets, and a manifest you can actually lint.

Regrettable name. Genuinely useful tool.

## 🎯 The Idea

Most image tooling makes you specify dimensions, quality, and crop by hand for every asset, which means every site ends up with images that were each optimized slightly differently by a slightly different mood.

This pipeline replaces that with **recipes**. A `hero-banner` and a `review-hero` and an `avatar` have different correct answers for size, crop bias, and compression, and those answers should live in the tool rather than in your head. Pick the recipe that matches the slot and the output is consistent across the whole site.

## 📦 Install

**As an agent skill** (Claude Code, Codex) — clone it into your skills directory so the
agent picks up `SKILL.md`:

```shell
git clone https://github.com/BrinShadewater/Webp-Me-Daddy-Skill ~/.claude/skills/webp-me-daddy
```

Codex users: swap `~/.claude/skills` for `~/.codex/skills`. Then ask your agent to prepare,
batch, audit, or lint images and it will use the recipes below.

**Standalone** — it is a plain Python CLI, no agent required:

```shell
git clone https://github.com/BrinShadewater/Webp-Me-Daddy-Skill
cd Webp-Me-Daddy-Skill
python -m pip install Pillow
python scripts/webp_me_daddy.py --help
```

The `animate` command additionally needs its companion tool, cloned as a sibling:

```shell
git clone https://github.com/BrinShadewater/Transparent-Gif-Loop-Skill
```

## ⚙️ Requirements

- Python 3
- Pillow

`scripts/webp_me_daddy.py` is the entrypoint. (`scripts/prepare_image.py` is a legacy shim kept for older call sites — new work should not use it.)

## 🚀 Quick Start

Prepare a single image against a recipe:

```shell
python scripts/webp_me_daddy.py prepare public/source-image.jpg --recipe review-hero --seo-subject "Bugonia movie review art" --seo-context "Brin Shadewater notes page" --framing subject --usage-key "notes.bugonia.hero" --public-root public --write-sidecar
```

Batch a whole folder — **always dry-run first**:

```shell
python scripts/webp_me_daddy.py batch public --recipe blog-cover --dry-run --manifest image-manifest.json --proof-contact-sheet batch-proof.png
```

Lint the manifest before shipping:

```shell
python scripts/webp_me_daddy.py lint image-manifest.json --strict
```

## 🧪 Commands

| Command | What it does |
|---|---|
| `prepare` | Process one image against a recipe |
| `batch` | Process a folder; supports contact-sheet proofs |
| `lint` | Validate a manifest against the output contract |
| `audit` | Inspect an existing project's image set, with optional autofix |
| `snippets` | Emit framework markup (e.g. React) for a usage key |
| `proof` | Render a proof for a specific usage key |
| `seo-handoff` | Apply an SEO tool's image recommendations |
| `animate` | Route to the transparent-gif-loop cleanup path |
| `cleanup` | Find and report orphaned/superseded assets |

## 🧭 Recipes

Recipes encode intent per slot: `hero-banner`, `review-hero`, `blog-cover`, `avatar`, `card`, `poster`, `story-cover`, `logo-lockup`, `logo-grid`, and friends.

Use `--framing subject|text|balanced` when the crop needs intent rather than just a hotspot. Poster-to-landscape crops bias toward `subject` automatically, because cropping a poster to a banner without that bias reliably decapitates someone.

## 🛑 Rules That Exist For A Reason

- **Dry-run before `batch` and `cleanup`.** Both touch a lot of files. Confirm before the real run.
- **No upscaling by default.** Small sources stay small unless you explicitly pass `--allow-upscale` and accept the tradeoff.
- **Animated assets do not belong here.** Route them to `transparent-gif-loop` instead of forcing them through the still-image path — that's what `animate` is for.
- **Check transparent logos before blaming the layout.** Wordmarks often ship with baked-in headroom or off-centre padding. The audit reports when a logo's visible alpha box is much smaller or off-centre inside its canvas, which is usually the actual bug.

## 🗺️ Project Map

```text
SKILL.md                     Skill definition and the full workflow
scripts/webp_me_daddy.py     v2 entrypoint (CLI)
scripts/webp_me_daddy_core.py  Recipes, processing, manifest and contract logic
scripts/prepare_image.py     Legacy shim — do not build on this
scripts/generate_explainer_pdf.py  Explainer PDF generation
scripts/test_prepare_image.py      Tests
references/                  Messaging, roadmap, and SEO guidelines
assets/                      Sample and reference art
agents/                      Agent-facing config
```

## ♿ Accessibility

Alt text is part of the output contract, not a nice-to-have. `--usage-alt` sets it explicitly; the pipeline will not pretend a missing alt string is fine, and `lint --strict` will say so.

## 🔗 Related

- **[transparent-gif-loop](https://github.com/BrinShadewater/Transparent-Gif-Loop-Skill)** — the animated-asset counterpart. This pipeline calls it under the hood for `animate`.
