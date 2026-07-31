# Claude Context: Webp Me Daddy

`AGENTS.md` in this folder is the full guide and is agent-neutral. Read it first.

The three that bite:

- **`scripts/webp_me_daddy.py` is the v2 entrypoint.** `scripts/prepare_image.py` is a legacy
  shim — do not build on it.
- **Dry-run before `batch` and `cleanup`.** Both touch many files; `cleanup` deletes.
- **Animated assets belong in the `animate` command**, which routes to `transparent-gif-loop`,
  not in the still pipeline.

This repo is the source for the installed `webp-me-daddy` skill. Edit the source here and
reinstall; never edit the installed copy, which is a read-only cache.
