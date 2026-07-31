# Webp Me Daddy Landing Page Messaging

## Positioning

**Category**

CLI-first, layout-aware image pipeline for production web teams.

**One-line value prop**

Webp Me Daddy turns messy website images into production-ready web assets with semantic recipes, strict metadata, visual proofing, and audit-driven cleanup.

**Expanded value prop**

Webp Me Daddy is a CLI-first image pipeline for front-end teams, agencies, and technical creators who want more than compression. It prepares website images for real layouts, generates responsive assets and framework snippets, enforces SEO and accessibility rules, and gives teams a repeatable audit-to-proof workflow instead of ad hoc manual fixes.

## Hero

**Eyebrow**

Layout-aware image pipeline

**Headline options**

1. Turn messy website images into production-ready assets
2. The image pipeline for teams who ship real websites
3. Stop hand-tuning website images one page at a time

**Recommended headline**

Turn messy website images into production-ready assets

**Subheadline**

Prepare layout-aware WebP assets with semantic recipes, strict SEO and accessibility metadata, proof sheets, snippets, audits, and cleanup reports in one repeatable workflow.

**Primary CTA**

See The Workflow

**Secondary CTA**

Read The Explainer

**Support line**

Built for front-end teams, agencies, and technical creators who care about performance, accessibility, and maintainable codebases.

## Hero Callouts

- Semantic recipes for heroes, review art, blog covers, logos, cards, posters, and more
- Strict metadata and lint rules for alt text, accessibility, and responsive delivery
- Visual proof sheets and audit-driven fix plans before anything ships

## Problem Section

**Section title**

The usual image workflow falls apart fast

**Intro**

Most teams do not have an image pipeline. They have a pile of one-off fixes:

- drag a file through TinyPNG
- crop it by hand
- guess the alt text
- forget width and height
- paste an inconsistent snippet
- leave old PNGs and unused assets in the repo

That works until the site grows. Then image quality, accessibility, and performance start drifting across the codebase.

## Solution Section

**Section title**

Webp Me Daddy gives image work a real production loop

**Loop**

1. Audit the project
2. Dry-run the image prep
3. Proof the visuals on real surfaces
4. Generate a fix plan
5. Apply safe fixes and regenerate assets

**Support copy**

Instead of treating image work as a last-minute asset chore, Webp Me Daddy treats it like production infrastructure.

## Feature Pillars

### Semantic recipes, not random aspect ratios

Use recipes like `hero-banner`, `review-hero`, `blog-cover`, `profile-avatar`, `poster`, `logo-lockup`, and `logo-grid` so image prep matches layout intent instead of raw dimensions.

### Framing that respects the placement

Bias crops toward the subject, text, or a balanced composition. Posters can become review heroes. Logo lockups can stay contained. Small source files can stay at native size.

### SEO and accessibility built into the pipeline

Generate structured metadata, enforce accessibility modes, lint risky alt text, and keep metadata tied to the asset and the usage context.

### Snippets that fit the stack

Generate ready-to-paste markup for HTML, React, Next.js, and Astro, with usage-level overrides when one asset appears in multiple placements.

### Audit, proof, and cleanup in one loop

Scan codebases for legacy formats, markup gaps, animated assets, and stale files. Generate proof sheets and contact boards. Turn findings into autofixes and fix plans.

## Differentiation Section

**Section title**

Not another compression tool

**Comparison framing**

Most image tools optimize files.

Webp Me Daddy optimizes the workflow around the files.

**Comparison bullets**

- TinyPNG-style tools shrink bytes, but do not understand your layout roles
- CDN platforms transform images, but do not enforce a local production workflow
- AI alt-text tools generate copy, but do not connect metadata to snippets, proofs, and codebase audits
- Webp Me Daddy ties recipes, metadata, snippets, proofs, audits, and cleanup together in one CLI-first loop

## Who It’s For

**Section title**

Built for technical operators

**Primary audience**

Front-end teams and agencies shipping production sites.

**Secondary audience**

Technical creators who treat their site like a product, not just a page builder project.

**Not the core audience**

Casual users looking for a drag-and-drop compressor with no workflow.

## Example Workflow Section

**Section title**

What a real pass looks like

```powershell
python ~/.codex/skills/webp-me-daddy/scripts/webp_me_daddy.py `
  audit C:/path/to/project `
  --emit-fix-plan `
  --json image-audit.json
```

```powershell
python ~/.codex/skills/webp-me-daddy/scripts/webp_me_daddy.py `
  batch public `
  --recipe review-hero `
  --dry-run `
  --proof-contact-sheet review-proof.png
```

```powershell
python ~/.codex/skills/webp-me-daddy/scripts/webp_me_daddy.py `
  prepare public/bugonia.jpg `
  --recipe review-hero `
  --framing subject `
  --public-root public `
  --write-sidecar `
  --overwrite
```

## Closing Section

**Headline**

Give website images the same rigor as the rest of the codebase

**Copy**

If your team already cares about performance, accessibility, and maintainable front-end systems, your image workflow should not still be held together by guesswork.

Webp Me Daddy gives you a repeatable way to prep assets, verify quality, and clean up the mess before it ships.

**CTA options**

- Read The Explainer
- See The Workflow
- Review The Commands

## Tone Notes

- Keep the tone sharp, confident, and practical.
- Avoid sounding like a generic SEO tool or design app.
- Emphasize workflow discipline over novelty.
- Keep “Shave bytes. Keep vibes.” as a supporting line, not the only message.
