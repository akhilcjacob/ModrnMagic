# Open choices for Akhil

Choices the site waits on. Each one is a draft until Akhil decides; nothing here is published (`_docs/` is not served). Remove a line once it is decided and the data matches.

| Product or page | Open choice | Now | Where it lands |
|---|---|---|---|
| Ramble | Brand hue for the card glow. The mark is monochrome, and the earlier `#915a19` read as a tan smear in light and rust in dark (re-review item 8). | No `tint`, so the neutral path: no glow on its cards, dark bento cell without stars. | `apps/ramble/app.json` `tint`, then `render.py` and `og.py`. |
| Legal URLs | Confirm no store listing points at the template legal URLs removed in PR #1 (re-review item 16). | Removed. | Store listings; restore the paths if any listing still uses them. |
| Every draft | Confirm or rewrite each draft product, outcome line, and lesson. `check.py --release` lists them. | Drafts block a release (see the launch checklist in `APPS.md`). | `apps/<id>/app.json` |

Decided and kept: SkyWise tint `#23c8f9` (sky cyan) and Astro Defender tint `#2a85c7` (night blue), with stars on Astro Defender only.
