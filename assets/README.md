# Avatar images

The app's `Avatar` component auto-loads a photo from this folder when the
filename matches the person's name; otherwise it shows initials. No code or
database changes needed — just add image files here and redeploy.

## Naming rule

`assets/<group>/<slug>.<ext>`

- `<group>` is `family`, `people`, or `ventures`
- `<slug>` = the person's name, lowercased, spaces → hyphens, punctuation removed
  - "Frederick" → `frederick`
  - "Tim Ward" → `tim-ward`
  - "Lewis Robinson" → `lewis-robinson`
  - "WolfLock" → `wolflock`
- `<ext>` can be `png`, `jpg`, `jpeg`, `webp`, or `svg` (any one works)

## Known names the app currently looks for

- family/: erin, george, graham, frederick, blair
- people/: tim-ward, lewis-robinson (plus any stakeholder/contact name you add)
- ventures/: wolflock

Square-ish images crop best. After adding files, re-drop the `wolfmaster`
folder onto the same Netlify site to update.
