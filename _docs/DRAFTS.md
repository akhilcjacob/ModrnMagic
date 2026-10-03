# Open choices for Akhil

Choices the site waits on. Each one is a draft until Akhil decides. Draft content is held in `_drafts/` and is not published (`_docs/` and `_drafts/` are not served). Remove a line once it is decided and the data matches. How to preview and promote: Held drafts in `APPS.md`.

| Product or page | Open choice | Now | Where it lands |
|---|---|---|---|
| Ramble | Brand hue for the card glow. The mark is monochrome, and the earlier `#915a19` read as a tan smear in light and rust in dark (re-review item 8). | No `tint`, so the neutral path: no glow on its cards, dark bento cell without stars. | `_drafts/apps/ramble/app.json` `tint` (or `apps/ramble/` once promoted), then `render.py` and `og.py`. |
| Legal URLs | Confirm no store listing points at the template legal URLs removed in PR #1 (re-review item 16). | Removed. | Store listings; restore the paths if any listing still uses them. |
| Every draft | Confirm or rewrite each held draft. `python3 _scripts/drafts.py` lists them. | Held in `_drafts/`, so the site ships without them. 10 held: Ramble and HypeBridge (products), and the outcome line and lesson of Nookly OS, Triply, QuietDesk, and Quorum. | On a yes: `python3 _scripts/drafts.py promote <id>`, then `render.py`. A rewrite: edit `_drafts/apps/<id>/app.json` or `_drafts/drafts.json` first. |
| Flagship | Which product, if any, gets the full-width panel on home. | None (HQ: no flagship for four weeks from 2026-10-03). | `flagship: true` in one `apps/<id>/app.json`. |

Decided and kept: SkyWise tint `#23c8f9` (sky cyan) and Astro Defender tint `#2a85c7` (night blue), with stars on Astro Defender only.
