# Open choices for Akhil

Choices the site waits on. Each one is a draft until Akhil decides. Draft content is held in `.drafts/`, a local gitignored folder, so it is neither served nor in the public repository. This page names open choices only; it never carries the draft text itself. Remove a line once it is decided and the data matches. How to preview and promote: Held drafts in `APPS.md`.

| Product or page | Open choice | Now | Where it lands |
|---|---|---|---|
| Ramble | Brand hue for the card glow. The mark is monochrome, and the earlier `#915a19` read as a tan smear in light and rust in dark (re-review item 8). | No `tint`, so the neutral path: no glow on its cards, dark bento cell without stars. | `.drafts/apps/ramble/app.json` `tint` (or `apps/ramble/` once promoted), then `render.py` and `og.py`. |
| Legal URLs | Confirm no store listing points at the template legal URLs removed in PR #1 (re-review item 16). | Removed. | Store listings; restore the paths if any listing still uses them. |
| Every draft | Confirm or rewrite each held draft. `python3 _scripts/drafts.py` lists them. | Held in a local `.drafts/` (durable copy: HQ `_attic/site-drafts-backup-2026-10-03/`; copy it to the checkout's `.drafts/` to preview), so the site and the repo ship without them. 10 held: two products and the outcome line and lesson of four others. | On a yes: `python3 _scripts/drafts.py promote <id>`, then `render.py`. A rewrite: edit `.drafts/apps/<id>/app.json` or `.drafts/drafts.json` first. |
| InboxHiive legal | Its privacy policy and terms live on inboxhiive.com (HQ ruling 2026-10-03). | `legal` in `apps/inboxhiiv/app.json` holds those URLs; `/apps/inboxhiiv/privacy/` and `/tos/` point there. | Nothing to decide unless the URLs change. |
| Nookly legal | Empty placeholders until Nookly has real policies. | Pages say the policy is not published and give the support address. | `apps/nookly/privacy/privacy-policy.md` and `tos/terms_of_service.md`. |
| Flagship | Which product, if any, gets the full-width panel on home. | None (HQ: no flagship for four weeks from 2026-10-03). | `flagship: true` in one `apps/<id>/app.json`. |

Decided and kept: SkyWise tint `#23c8f9` (sky cyan) and Astro Defender tint `#2a85c7` (night blue), with stars on Astro Defender only.
