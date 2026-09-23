# Template Studio Next — isolated comparison

Open the running application with `?view=template-studio-next`. The existing
`?view=template-studio` remains the functional Studio. Its comparison link uses
same-page navigation, keeping report/Studio drafts and the launcher session alive.

This is a **visual comparison**, not a second operational template pipeline.
The iframe contains only synthetic content from the user-supplied Stitch HTML.
Buttons are disabled; native details can be expanded. No save/import/publish API
is called by this view. Existing API and customer DOCX templates are unchanged.

Isolation: lazy-loaded module, CSS Module for the outer comparison bar, sandboxed
iframe without script or same-origin permission, strict embedded CSP. Never pass
customer HTML into the srcDoc. No CDN, remote images, remote fonts or analytics.
SVG icons replace the icon font. Typography falls back to Segoe UI if the named
fonts are not installed. Continuous glow/ping/shimmer was removed.

The checked-in stylesheet was generated with Tailwind 3.4.17; application builds
do not require Tailwind or network access. To deliberately regenerate from the
reviewed reference, from apps/frontend:

```powershell
npm exec --yes --package=tailwindcss@3.4.17 -- tailwindcss -c src/features/template-studio-next/tailwind.config.cjs -i src/features/template-studio-next/tailwind.input.css -o src/features/template-studio-next/stitch-reference.generated.css --minify
npx --no-install prettier --write src/features/template-studio-next/stitch-reference.generated.css
```

First command downloads and executes the specified build tool when not cached;
it is not part of normal installation or runtime.

Next gate: user visual approval, then implement real controls using the existing
Studio contract under a separately reviewed scope. Do not interpret a static
"saved" badge in this synthetic document as evidence of a real backend write.
