# otfinst install pipeline

## What gets produced and where

For every input `.otf`, otfinst.py produces this set of files:

| Output | Path under install root | Producer |
|---|---|---|
| `.tfm` (font metrics) | `fonts/tfm/<vendor>/<typeface>/` | `otftotfm` |
| `.vf` (virtual font) | `fonts/vf/<vendor>/<typeface>/` | `otftotfm` |
| `.pfb` (Type 1 outline) | `fonts/type1/<vendor>/<typeface>/` | `otftotfm` |
| `.enc` (encoding) | `fonts/enc/dvips/<vendor>/` | `otftotfm` |
| `<vendor>.map` (psfonts entry) | `fonts/map/dvips/<vendor>/` | `otftotfm` (per-call fragments) → otfinst.py merge |
| `<typeface>.sty` | `tex/latex/localfonts/` | otfinst.py |
| `<typeface>.fd` | `tex/latex/localfonts/` | otfinst.py |

## Where the install root should be: TEXMFHOME

`otftotfm -a` (automatic mode) picks a TDS root for its outputs. Recent
versions default to **TEXMFVAR** (`~/.texlive*/texmf-var`); older versions
defaulted to **TEXMFHOME** (`~/Library/texmf`). Both work — kpathsea
searches both — but they have very different lifetime semantics:

- **TEXMFVAR is regenerable cache.** TeX Live treats it as content that
  can be wiped and rebuilt at any time. It gets cleaned during TL
  upgrades, during `fmtutil`/cache utilities, and by people who run
  `rm -rf ~/.texlive*` to fix unrelated problems. Licensed fonts you
  depend on should not live in cache.
- **TEXMFHOME is durable user content.** TeX Live never touches it.
  Fonts here survive TL upgrades and cleanup runs unscathed.

**otfinst.py forces all output to TEXMFHOME** by setting
`TEXMFVAR=$TEXMFHOME` in the environment of the `otftotfm`
subprocess. That single env override is what `-a` consults to pick the
TDS root, so it's enough to redirect every output (TFM/VF/`.pfb`/`.enc`/
fragment `.map`) into `~/Library/texmf/...`. The merged canonical
`<vendor>.map` is then written to TEXMFHOME by otfinst.py directly.

The `.sty` and `.fd` files are written by otfinst.py itself directly to
TEXMFHOME, regardless of `otftotfm` settings — so they're already in the
right place.

## The updmap step

After all `otftotfm` calls finish and per-vendor maps are merged in
TEXMFHOME, otfinst.py needs to make pdfTeX *see* the new fonts. That's
the job of `updmap`, which combines all enabled per-vendor maps into a
master `pdftex.map`.

Three things to know about `updmap-user`:

1. **It does not auto-discover map files.** It only regenerates
   `pdftex.map` from maps already enabled in
   `~/.texlive*/texmf-config/web2c/updmap.cfg`. Old TeX Live versions
   had a `--syncwithtrees` flag that scanned TEXMF trees and enabled
   what it found; modern TeX Live has removed that flag. We have to
   call `updmap-user --enable Map=<name>` explicitly for each new
   vendor map.
2. **`--enable` is idempotent.** Re-enabling a map that's already
   enabled is a no-op, so this step is safe to run unconditionally.
3. **`--nomkmap`** skips the (slow) `pdftex.map` regeneration after
   each `--enable`. We use it on every per-map call and run a single
   bare `updmap-user` at the end to do the rebuild once.

## Post-otftotfm post-pass, in order

1. **Discover roots.** `kpsewhich -var-value=TEXMFHOME` and
   `-var-value=TEXMFVAR`. Most installs only have things in TEXMFHOME
   after the change above, but TEXMFVAR may still hold legacy installs
   from older otftotfm versions, so we still scan both.
2. **Merge map fragments.** Each `otftotfm` call wrote its map line
   to a private tempfile (see `otfinst-parallel.md` for why). Read all
   fragments for a given vendor, dedupe by display-name, append to the
   canonical `<TEXMFHOME>/fonts/map/dvips/<vendor>/<vendor>.map`,
   preserving any pre-existing entries.
3. **`texhash` both roots.** Rebuilds `ls-R` so kpathsea can find the
   new TFMs/VFs/.fd/.map files.
4. **`updmap-user --nomkmap --enable Map=<vendor>.map`** for every
   per-vendor map found in `fonts/map/dvips/*/*.map` under either root
   (skipping the `updmap/` subdir, which holds updmap's own outputs,
   not source maps).
5. **`updmap-user`** (no flags) — single regeneration of `pdftex.map`,
   `psfonts.map`, etc.

After step 5, pdfTeX/dvips/dvipdfmx all know about the new fonts.

## Why this design (vs. just letting otftotfm handle updmap)

`otftotfm` *can* run `updmap` itself when invoked without `--no-updmap`.
We pass `--no-updmap` and batch the work because:

- With many fonts, per-call updmap regeneration of `pdftex.map` (a
  multi-megabyte file) was a major contributor to the "many hours"
  install times.
- Letting `otftotfm` run `updmap` per call also serializes our parallel
  runner on `updmap.cfg`, undoing the parallelism win.
- Per-call updmap can leave `updmap.cfg` in a weird intermediate state
  if a run is killed midway; one batched `updmap-user` at the end is
  cleaner.

## Tree at rest

After a full install, with everything routed to TEXMFHOME:

```
~/Library/texmf/
├── fonts/
│   ├── enc/dvips/<vendor>/a_<hash>.enc
│   ├── map/dvips/<vendor>/<vendor>.map
│   ├── tfm/<vendor>/<typeface>/...tfm
│   ├── type1/<vendor>/<typeface>/...pfb
│   └── vf/<vendor>/<typeface>/...vf
└── tex/latex/localfonts/
    ├── <typeface>.sty
    └── ly1<family-id>.fd  (etc.)

~/.texlive*/texmf-config/web2c/updmap.cfg
    Map adobe.map
    Map linotype.map
    Map <vendor>.map ...      # one line per per-vendor map enabled

~/.texlive*/texmf-var/fonts/map/pdftex/updmap/pdftex.map
    # the regenerated combined map; this IS regenerable cache,
    # legitimately living in TEXMFVAR.
```

The only things otfinst leaves in TEXMFVAR are the legitimately-cached
`updmap` outputs (`pdftex.map`, `psfonts.map`, etc.). Those are exactly
the kinds of files TEXMFVAR is for.
