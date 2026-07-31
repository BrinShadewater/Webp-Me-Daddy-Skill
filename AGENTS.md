# Webp Me Daddy — Agent Guide

Agent-neutral. Claude and Codex both read this file; `CLAUDE.md` points here.

A recipe-driven **WebP pipeline for website images**: optimised variants, responsive sets,
structured metadata, alt text, and lintable output contracts. Python 3 + Pillow.
Repo: `github.com/BrinShadewater/Webp-Me-Daddy-Skill`.

The design idea: you declare what an image is *for* rather than what to do to it. A
`hero-banner`, a `review-hero`, and an `avatar` have different correct answers for size, crop
bias, and compression, and those answers live in the tool instead of in someone's head. That is
what keeps images consistent across a whole site. Preserve that framing when extending it.

The name is deliberately silly; the tool is not.

## Entry point, and the shim not to build on

- **`scripts/webp_me_daddy.py` is the v2 entrypoint.** Use it.
- **`scripts/prepare_image.py` is a legacy shim. Do not build on it.**
- Commands: `prepare`, `batch`, `lint`, `audit`, `snippets`, `proof`, `seo-handoff`, `animate`,
  `cleanup`

## Operating rules

- **Dry-run before `batch` and `cleanup`.** Both touch many files at once, and `cleanup`
  deletes. Ask for explicit confirmation before running `batch` without `--dry-run`.
- **No upscaling by default.** `--allow-upscale` is an explicit, deliberate tradeoff, not a
  convenience flag to reach for when an image is too small.
- **Animated assets do not belong in the still pipeline.** The `animate` command routes them to
  the `transparent-gif-loop` tool, which this one calls under the hood. For site assets, start
  here — go to that repo directly only for one-off standalone GIF cleanup.
- Alt text is part of the output contract, and `lint --strict` enforces it. Do not satisfy the
  linter with filler text; missing alt text is a real accessibility gap, not a lint nag.

## This repo is the source for an installed skill

The `webp-me-daddy` skill is derived from this project. If you change behaviour here, the
copy installed into your agent's skills directory can go stale — reinstall it after a change
rather than editing the installed copy, which is a read-only cache.

## Rails

Standard: task branch, no direct commits to `main`, no push without approval, no secrets.
