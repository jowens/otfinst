# otfinst-inventory.py

Read-only diagnostic that walks your TEXMFHOME and TEXMFVAR trees,
maps every installed `.pfb` back to its source `.otf`/`.ttf`, and
prints two derivative shell commands:

1. A **re-install** command — the exact `otfinst.py ...` invocation
   that rebuilds every font currently in TEXMFVAR.
2. A **cleanup** command — `rm -rf` over the per-vendor TEXMFVAR
   subtrees, plus a `texhash` and `updmap-user` to refresh kpathsea
   and `pdftex.map`.

The script never modifies anything itself. It exists to support two
workflows.

## When to run it

### Workflow 1: before wiping `~/.texlive*/`

If you're going to `rm -rf ~/.texlive2026` to clear out a corrupted
TeX Live state, you'll lose every TEXMFVAR-resident font. Run the
inventory first, save the re-install command, do the wipe, then
re-run the saved command.

### Workflow 2: consolidating fonts to TEXMFHOME

Modern `otftotfm` installs to TEXMFVAR by default; older versions
installed to TEXMFHOME. If you've been running otfinst across that
transition, your fonts are split across both roots. The current
otfinst.py forces all new installs into TEXMFHOME (see `summary.md`),
but pre-existing TEXMFVAR fonts stay where they are. The inventory
script's re-install + cleanup pair migrates them: the re-install
rebuilds them in TEXMFHOME, the cleanup removes the now-redundant
TEXMFVAR copies.

## Usage

```bash
~/Documents/src/otfinst/otfinst-inventory.py             # human-readable
~/Documents/src/otfinst/otfinst-inventory.py > /tmp/o.sh # capture for later
```

## Output structure

The output has four sections, all comment-prefixed (`#`) so the file
can be saved and consumed by sh:

1. **`# === TEXMFVAR (lost if you delete ~/.texlive*/) ===`** — every
   `.pfb` under `<TEXMFVAR>/fonts/type1/`, with the resolved source
   `.otf`/`.ttf` in `SOURCE_DIRS` (or `???` if none found).
2. **`# === TEXMFHOME (survives deletion of ~/.texlive*/) ===`** —
   same, for `<TEXMFHOME>/fonts/type1/`. Informational; these
   fonts don't need re-installation in either workflow because their
   files live in durable storage.
3. **`# === Re-install command (TEXMFVAR fonts only) ===`** — a
   single executable shell line:
   ```
   ~/Documents/src/otfinst/otfinst.py /path/to/A.otf /path/to/B.otf ...
   ```
   It includes only sources that resolved successfully. If any
   TEXMFVAR `.pfb` had no resolvable source, a warning lists them
   above the command.
4. **`# === Cleanup command (consolidate to TEXMFHOME) ===`** —
   a multi-line block:
   ```
   rm -rf <TEXMFVAR>/fonts/{tfm,vf,type1}/<vendor>... <TEXMFVAR>/fonts/{enc,map}/dvips/<vendor>...
   texhash <TEXMFVAR>
   updmap-user
   ```
   Vendors are discovered from `<TEXMFVAR>/fonts/type1/*`. If any
   vendor has `.pfb`s with no resolvable source, a per-vendor warning
   is printed above the command — those fonts would be lost by the
   cleanup, so either skip them or fix `SOURCE_DIRS` first.

## Recommended sequence (do not pipe-to-bash)

The script-output's two commands intentionally aren't a single safe
script. Run them with a verification step in between:

```bash
~/Documents/src/otfinst/otfinst-inventory.py > /tmp/otfinst.sh

# Phase 1: reinstall
grep -m1 'otfinst.py ' /tmp/otfinst.sh | bash

# Phase 2: verify -- re-compile a real document that uses one of the
# fonts being moved.
cd <some_doc_dir>
latexmk -pdf <doc>.tex

# Phase 3: cleanup -- only run if Phase 2 succeeded.
grep -E '^(rm -rf|texhash|updmap-user)' /tmp/otfinst.sh | bash
```

Running `bash /tmp/otfinst.sh` end-to-end *technically* works (the
inventory comments are just `#` lines), but it skips the verification
gap and runs the destructive `rm -rf` immediately after the
re-install reports exit 0. If the re-install completed but produced
subtly broken output, the cleanup compounds the problem.

## Configuration

Both at the top of the script:

### `SOURCE_DIRS`

List of directories to search for source `.otf`/`.ttf` files. Defaults:

```python
SOURCE_DIRS = [
    Path.home() / "Library" / "Fonts",
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
]
```

If you keep fonts elsewhere (network share, Adobe download cache,
etc.), append its `Path(...)`.

### `OTFTOTFM_DERIVED_SUFFIXES`

`otftotfm` sometimes emits a re-encoded Type 1 with a synthetic suffix
in addition to the plain font (e.g., `ACaslonPro-Bold.pfb` *and*
`ACaslonPro-BoldLCDFJ.pfb`, both produced from a single
`ACaslonPro-Bold.otf`). The suffixed variant has no source on disk —
its source is the parent. The script tries an exact source match
first; on failure, it tries stripping each suffix in
`OTFTOTFM_DERIVED_SUFFIXES`.

Default:
```python
OTFTOTFM_DERIVED_SUFFIXES = ("LCDFJ",)
```

If you discover another suffix in your tree (search "missing source"
warnings in the output for patterns), append it.

## What it does NOT do

- It does not regenerate `.sty` or `.fd` files. Those live in
  `<TEXMFHOME>/tex/latex/localfonts/` and are written by
  `otfinst.py` itself, not by `otftotfm`. They survive a TEXMFVAR
  wipe, and they're rewritten on every otfinst run.
- It does not handle TrueType-only installs. `otftotfm` writes
  `.pfb` for Type 1 outlines and `.ttf` for TrueType; the inventory
  walks `fonts/type1/*.pfb`. If you've installed any pure-TrueType
  fonts via `otfinst.py`, they won't appear in this inventory. (None
  of the fonts in the user's collection are TrueType-only, so this
  hasn't been an issue in practice.)
- It does not detect orphan files. If a font was partially installed
  (e.g., `.tfm` present but no `.pfb`), the inventory misses it.
  The `.pfb` is the canonical "this font is installed" indicator.
