# Webp Me Daddy Product Brief And Roadmap

## Product Summary

Webp Me Daddy is a CLI-first, layout-aware image pipeline for production websites. It prepares images for real placements, generates structured metadata and snippets, audits codebases for image problems, creates proof artifacts for review, and helps teams clean up stale or low-quality asset workflows.

The product is strongest as a developer and agency workflow tool, not a mass-market drag-and-drop compressor.

## Positioning

**Category**

CLI-first, layout-aware image pipeline for production web teams.

**Current one-line positioning**

Webp Me Daddy turns messy website images into production-ready web assets with semantic recipes, strict metadata, visual proofing, and audit-driven cleanup.

## Target Users

### Primary

- Front-end teams shipping production websites
- Agencies handling multiple marketing and content-heavy sites

### Secondary

- Technical creators who maintain portfolio, content, or product sites with code-level control

### Not the primary focus

- Casual users who only want a quick drag-and-drop compressor
- Teams looking for a full hosting/CDN image platform

## Core Product Loop

This should be treated as the center of the product:

1. `audit`
   Scan the codebase for live image issues, legacy formats, animated assets, markup gaps, and shared-usage problems.
2. `dry-run`
   Preview image prep without writing files so teams can see recipes, dimensions, alt behavior, and likely risks.
3. `proof`
   Generate visual QA artifacts that catch matte halos, clipping, bad framing, and transparency problems.
4. `fix-plan`
   Turn findings into concrete next steps with suggested commands, codemods, and cleanup passes.
5. `apply`
   Run approved `prepare`, `snippets`, `cleanup`, and safe autofix steps, then re-audit.

This is the workflow to optimize around in docs, UX, and future UI work.

## Strategic Strengths

### 1. Semantic recipes

Recipes like `hero-banner`, `review-hero`, `blog-cover`, `profile-avatar`, `card-thumbnail`, `poster`, `story-cover`, `logo-lockup`, and `logo-grid` let teams think in terms of placement instead of only aspect ratio.

### 2. Framing intent

Subject-first versus text-first composition is first-class via `--framing auto|subject|text|balanced` and focal-point controls.

### 3. Deterministic metadata

Metadata generation is structured and enforceable, with accessibility modes, strict linting, and usage-level overrides.

### 4. Snippet generation

Assets produce code, not just files. HTML, React, Next.js, and Astro outputs make the pipeline more directly useful to front-end teams.

### 5. Manifest as API

The versioned manifest/sidecar contract already powers snippets, proofing, linting, and audits, and can become the backbone for editor tools or a future web app.

### 6. Audit plus action

The product does not stop at issue detection. Autofixes, codemod patches, action hints, and fix plans move teams toward resolution.

### 7. Visual proofing

Proof sheets and contact boards catch problems file-size and metadata checks cannot detect.

## Real Competitive Position

The everyday competitor is not just another SaaS.

It is the messy manual workflow:

- ad hoc compression
- inconsistent naming
- weak cropping decisions
- no responsive variants
- poor alt text
- missing width and height
- no QA artifact
- stale sources left in the repo

### Market context competitors

- TinyPNG / Tinify
- ShortPixel / Imagify / similar CMS optimizers
- Cloudinary / ImageKit / image CDNs
- AltText.ai and AI alt-text tools

These validate the problem space, but they do not directly replace the current CLI-first workflow and codebase-audit model.

## Current Product Status

The product is in strong shape for the CLI-first vision. It is no longer missing core fundamentals.

Best estimate:

- Core CLI product maturity: `85-90%`
- Productization and positioning maturity: still actively being refined
- Web app readiness: schema and workflow are promising, but not yet the focus

## Main Risks

### 1. Loss of focus

The biggest risk is adding more clever capabilities without locking the story and the core loop.

### 2. Onboarding friction

The tool is strong, but the command surface is deep. A newcomer must still understand the shortest path quickly.

### 3. Overselling future capability

AVIF, AI assistance, orchestration, and a web app are all plausible next steps, but they should not be sold as present-day product promises until they are real.

### 4. Scope drift

Trying to become a CDN, WYSIWYG editor, or generic AI copy system would dilute the product.

## Roadmap

## Phase 1: Story And Core Workflow

**Goal**

Make the product easy to explain and easy to trust.

**Deliverables**

- Finalize official positioning language
- Center docs around `audit -> dry-run -> proof -> fix-plan -> apply`
- Tighten CLI help output and examples around the core flow
- Build a small command cookbook for the most common tasks

**Estimated effort**

- `1-2 days`

## Phase 2: Multi-Format Readiness

**Goal**

Future-proof the contract before adding more delivery formats.

**Deliverables**

- Design AVIF-ready manifest and snippet structure
- Decide output policy:
  - WebP default
  - AVIF opt-in
  - possible photo-only AVIF path
- Document the format strategy clearly

**Estimated effort**

- Schema/design: `3-5 hours`
- Initial implementation path: `6-10 hours`

## Phase 3: Operator Experience

**Goal**

Make audits and fix plans feel like production checklists, not logs.

**Deliverables**

- Improve `audit --emit-fix-plan` grouping and prioritization
- Explore a safe `apply-fix-plan` orchestration model
- Strengthen proof/report exports for approvals and handoffs

**Estimated effort**

- `1-2 days`

## Phase 4: Real-World Validation

**Goal**

Refine recipes, lint severity, and proofing from real projects instead of theory.

**Deliverables**

- Build a named test corpus:
  - heroes
  - posters
  - logos
  - screenshots with text
  - decorative art
  - reused shared assets
- Run the loop on more real codebases
- Tune recipes and lint based on repeated edge cases

**Estimated effort**

- `1-2 days` for corpus setup
- ongoing dogfooding after that

## Phase 5: Web App Exploration

**Goal**

Extend access without forking product behavior.

**Deliverables**

- Thin UI prototype built around the CLI/manifest model
- Basic flow:
  - upload
  - choose recipe
  - proof
  - export assets/snippets/manifest
- Keep the CLI as the source of truth

**Estimated effort**

- prototype: `1-3 days`
- polished product: larger separate project

## Explicit Non-Goals For Now

- Building a full hosting or CDN platform
- Becoming a general-purpose image editor
- Adding unconstrained AI rewriting throughout the workflow
- Supporting too many frameworks before the main ones are excellent

## Recommended Immediate Priorities

1. Lock the public positioning and homepage messaging
2. Make the core operator loop the center of docs and onboarding
3. Plan AVIF support at the schema level
4. Keep dogfooding on real projects
5. Delay web app work until the CLI loop feels effortless

## Open Questions

- What is the safest possible design for `apply-fix-plan`?
- How should multi-format manifest entries represent WebP and AVIF cleanly?
- Where should automation stop and explicit human approval begin for metadata and review artifacts?
- What is the smallest useful web UI that adds value without splitting the product?
