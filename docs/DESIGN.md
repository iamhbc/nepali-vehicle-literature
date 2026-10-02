# Design system

## Visual research → principles

South Asian vehicle decoration (Nepali public buses and goods trucks, Indian lorries, Pakistani truck art) shares a grammar. We borrowed the **grammar**, not any artist's work:

| Observed in vehicle art | Principle | How the interface uses it |
|---|---|---|
| Painted panels framed by double borders and corner flowers | Content lives in *framed panels* | `PaintedFrame`: ink border, inner coloured rule, corner rosettes |
| Bead-and-pennant fringe (झालर) hanging from visors and bumpers | Edges are celebrated, not hidden | `Jhalar` strip under the header |
| Hand-lettered slogans with hard drop shadows | Type is the hero; shadows are solid, offset, never blurred | Yatra One / Rozha One headings with offset shadow; buttons with a hard 3px shadow that "press in" |
| Saturated enamel on metal: vermilion, marigold, turmeric, peacock, royal blue, pink | A bold but disciplined palette | Tokens below; colours encode *dimensions*, not decoration |
| Black number plates with white Devanagari (public vehicles) | Identity as a plate | `NumberPlate` for corpus ids (NVL ०२१) |
| Diagonal hazard chevrons on tailboards | Rhythm and boundaries | `ChevronBand` above the footer |
| Road centre-lines | Movement, sections | `RoadDivider` |
| "फेरि भेटौंला" painted on vehicle backs | The farewell | Footer sign-off |

What we avoided: religious motifs used as decoration, eyes/nazar imagery, and dense ornament behind text. Ornament frames content and never sits under it. **Clarity beats decoration.**

## Tokens (`frontend/src/styles/tokens.css`)

- **Surfaces**: enamel cream `--paper #f4ecdb`, card `#fbf6ea`, ink `#1c1633`. Dark mode is "night road": indigo-black `#15112a` with brightened paints.
- **Paint**: vermilion `#b3301c`, marigold, turmeric, peacock `#0d6767`, indigo `#24378a`, rose, plum, leaf.
- **Text-bearing colours meet WCAG AA (≥ 4.5:1)** on their backgrounds. Turmeric, marigold and chrome are decorative only, or carry dark text.
- **Dimension colours** (`--dim-emotion`, `--dim-love`, …) are shared by the map, reading cards, finding stripes and theme dots.
- **Type**: `Yatra One` (brush-painted Devanagari display), `Rozha One` (sign-painter Latin/Devanagari headings), `Mukta` (body, both scripts), `Noto Serif` italic (transliteration with full diacritics). The original Nepali phrase is always the largest text on the page.
- **Space**: 4px grid. **Touch**: 48px minimum targets. **Motion**: 120/240/480ms with a single ease curve.

## Components

`PaintedFrame` · `Jhalar` · `Rosette` · `NumberPlate` · `RoadDivider` · `ChevronBand` · `Wordmark` · `TruckAnimation` · `NepaliPhrase` (evidence highlighting) · `PhraseCard` · `ThemeBadge` · `KindBadge` · `ConfidenceIndicator` · `FindingItem` · `ReferenceCard` · `RelatedList` · `MindMap` (radial map + accessible "Branches" outline + detail panel) · `PhraseInput` (with on-screen Devanagari letters) · `AnalysisProgress` · `SearchBar` · `VehicleSelector` · `LocationSelector` · `BarList` · `CooccurrenceNetwork`

## Signature interactions

- **Truck**: drives in once, then idles with turning wheels, scrolling road paint and dust. Real corpus inscriptions are brush-wiped onto its side panel. It pauses offscreen and when the tab is hidden, and is static under `prefers-reduced-motion`.
- **Evidence highlighting**: hovering or focusing any finding, or selecting a map node, underlines its quoted words inside the big phrase.
- **Camera**: shutter flash, optional Web Audio click (off by default, remembered per browser), and a scan-line sweep with staged status text.

## Accessibility

- Semantic landmarks, skip link, focus moved to `<main>` on navigation, visible focus rings.
- `lang="ne"` on all Nepali text so screen readers switch voice.
- Confidence is always a word as well as bars; hypotheses are dashed *and* labelled.
- Every visualisation has a text alternative: the map has a keyboard-operable Branches outline (the default on phones), and the network has a table.
- Charts are horizontal bars with printed values (no rotated labels).
- Reduced motion is respected globally; the bottom navigation suits one-handed use.

## Responsive

Mobile-first. The bottom tab bar has a raised camera button (< 900px); a top nav replaces it on desktop. The map shows as a radial view at ≥ 680px and as branches below that. There is no horizontal page scroll at 375px (verified).
