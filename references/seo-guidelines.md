# SEO Naming And Alt Text

## File naming

- Use lowercase words separated by hyphens.
- Prefer specific nouns over generic names like `image-1` or `hero-final-final`.
- Put the subject first, then the page or campaign context if it improves clarity.
- Keep names short enough to scan quickly in `public/`.

## Good patterns

- `brin-shadewater-creator-portrait.webp`
- `ai-tools-launch-hero-banner.webp`
- `bugonia-review-hero.webp`
- `summer-sale-card-thumbnail.webp`
- `fantasy-stream-story-cover.webp`

## Accessibility modes

- Use `descriptive` for normal informative images.
- Use `decorative` for separators, flourishes, textures, or ambient artwork that adds no meaning.
- Use `logo` for brand marks so the alt text stays crisp instead of drifting into page-copy language.
- Use `text-bearing` when visible text matters for understanding the image.
- When using `text-bearing`, pass `--visible-text` if the exact on-image copy should be preserved in the generated metadata.
- Prefer `logo-lockup` or `--fit-mode contain` for transparent brand art so the optimizer preserves the full composition instead of clipping the edges away.
- Use `logo-grid` for partner badges, sponsor grids, or creator-program tiles where the logo should sit inside a fixed card without cropping.

## Alt text

- Describe the image itself, not the surrounding page.
- Keep it natural and concise; one sentence or phrase is usually enough.
- Aim to stay under about 125 characters when possible.
- Skip keyword stuffing.
- Avoid redundant prefixes like `image of`, `photo of`, or `picture of`.
- If the image is decorative and adds no meaning, use empty alt text in code instead of forcing SEO words into it.
- If the image contains important readable text, include that text only when it matters for understanding.
- Review generated metadata during bulk runs and tighten anything that feels generic before publishing.
- If you paste the generated snippet into markup, keep the alt text aligned with the final page meaning instead of treating the generated string as untouchable.
- If the same asset appears in multiple contexts, keep a clean default alt in the file metadata and store page-specific copy as a usage override instead of overloading one alt string to do every job.
- Use the `snippets` helper when you need to rebuild markup for one `usage_key` without regenerating the image itself.

## Recipe heuristics

- Use `hero-banner` for large landing-page heroes and other primary banners.
- Use `review-hero` for notes, review cards, and article headers where the final slot is landscape even if the source art started as a poster.
- Use `blog-cover` for editorial or article imagery.
- Use `profile-avatar` for avatars, author photos, and square thumbnails.
- Use `card-thumbnail` for 4:5 cards, campaign tiles, and feed promos.
- Use `poster` for vertical promo art, posters, and book-cover-like assets.
- Use `story-cover` for 9:16 stories, reels, and short-form vertical placements.
- Use `logo-lockup` for logos, wordmarks, badges, and partner-program lockups that should not be center-cropped.
- Use `logo-grid` for smaller logo tiles inside sponsor grids, partner walls, or badge collections.
- Use `--framing subject` when a landscape crop should center a face or main subject instead of preserving lower poster text.
- Use `--framing text` when the visible title or wordmark is the important thing to protect inside the crop.
- Use `--framing balanced` when both subject and title matter and neither should dominate.
- Poster-to-landscape `cover` crops default toward `subject`, so only override that when the title text needs to stay visible.
- Use `--focus-preset top` or a custom `--focus-y` value when vertical crops need more explicit control than the framing intent provides.
- Use `--focus-preset left` or `right`, or a custom `--focus-x`, when the subject is intentionally off-center and a default center crop would miss it.
- Use `--fit-mode contain` when the layout needs fixed output dimensions but the artwork should preserve all edges and transparent padding.
- Prefer the default no-upscale behavior for small source files so the optimized asset does not get larger or softer just to match a recipe target.
- Only use `--allow-upscale` when a downstream layout absolutely requires a larger canvas and the user accepts the quality tradeoff.
- Prefer responsive variants for `hero-banner`, `blog-cover`, and large `card-thumbnail` imagery where the site serves multiple viewport sizes.
- Use `--dry-run` before a large batch pass if you need to sanity-check naming, accessibility mode, or snippet output.
- In `batch --dry-run`, use the proof-style summary table to catch odd slugs, mismatched dimensions, weak alt previews, or any `warning` / `blocking` statuses before you write files. The action column should tell you what to do next for the most important issue.
- Use `--proof-contact-sheet` on larger batch dry-runs when you want one visual PNG proof board for approval, especially for logo passes, mixed poster-derived review art, or anything with transparent edges. The contact sheet now carries lint-style status badges and short next-step hints so the visual board and the metadata review tell the same story.
- Run `audit` against the project root after a larger image pass so you can catch live PNG/JPEG references, animated assets, shared assets that may need usage overrides, unused assets, and `<img>` tags still missing width, loading, or decoding attributes.
- Use the audit's ready-to-paste JSX patch output for simple `<img>` attribute cleanup before you reach for manual rewrites.
- If you want to wire those fixes into tooling later, use the audit's file-specific codemod entries as the stable `old_str` / `new_str` replacement contract.
- Use `audit --apply-autofix` for low-risk width, height, loading, and decoding additions when the exact match is unique, and review anything more complex by hand.
- Use `audit --emit-fix-plan` when you want the tool to translate findings into runnable next-step commands like `prepare`, `animate`, `snippets`, or `cleanup`.
- If the project uses `next/image`, prefer the audit's component-aware prop suggestions over copying raw `<img>` attributes by hand.
- For shared assets, start with the audit's suggested `usage_key` names so the snippet helper and sidecar overrides stay consistent across pages.
- Use `proof` before shipping transparent logos, lockups, or edge-sensitive crops so you can review the asset on dark and light surfaces instead of trusting one background.
- Follow `audit` with `cleanup --dry-run` when you want to prune superseded originals or stale generated assets, then confirm the deletion pass with `--yes`.
- If the asset is animated, route it through `animate` instead of trying to make the still-image pipeline guess how to optimize a loop.
- Use `lint --strict` when you want these metadata checks to fail fast instead of landing as soft warnings.
