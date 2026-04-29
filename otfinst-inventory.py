#!/usr/bin/env python3
"""Inventory fonts currently installed via otfinst.

Walks TEXMFVAR and TEXMFHOME for .pfb files (which otftotfm produces from
each .otf source), maps them back to source .otf/.ttf files, and prints
two commands: a reproducible re-install (so you can rebuild after wiping
~/.texlive*/) and a cleanup that consolidates everything into TEXMFHOME
by removing the per-vendor TEXMFVAR copies. Read-only; modifies nothing.
"""

import os
import shlex
import subprocess
from pathlib import Path


# Where to look for the original .otf/.ttf source files. Add more
# directories here if you keep fonts elsewhere.
SOURCE_DIRS = [
    Path.home() / "Library" / "Fonts",
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
]
SOURCE_EXTENSIONS = (".otf", ".OTF", ".ttf", ".TTF")

# otftotfm sometimes emits a re-encoded Type 1 with a synthetic suffix
# in addition to the plain font (e.g., ACaslonPro-Bold.pfb AND
# ACaslonPro-BoldLCDFJ.pfb from a single ACaslonPro-Bold.otf source).
# The suffixed .pfb has no corresponding source on disk; strip the
# suffix to find the parent.
OTFTOTFM_DERIVED_SUFFIXES = ("LCDFJ",)


def kpse(var):
    try:
        return (
            subprocess.check_output(["kpsewhich", "-var-value=" + var])
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def pfb_basenames(root):
    """Return sorted set of basename-without-extension for every .pfb
    under <root>/fonts/type1/. Empty set if root doesn't exist."""
    type1 = Path(root) / "fonts" / "type1"
    if not type1.is_dir():
        return []
    return sorted({p.stem for p in type1.rglob("*.pfb")})


def _lookup(name):
    for d in SOURCE_DIRS:
        for ext in SOURCE_EXTENSIONS:
            candidate = d / (name + ext)
            if candidate.exists():
                return candidate
    return None


def find_source(name):
    """Locate <name>.{otf,ttf} in SOURCE_DIRS, falling back to a
    suffix-stripped form for otftotfm-derived .pfb names. Returns
    a Path or None."""
    src = _lookup(name)
    if src is not None:
        return src
    for suffix in OTFTOTFM_DERIVED_SUFFIXES:
        if name.endswith(suffix):
            src = _lookup(name[: -len(suffix)])
            if src is not None:
                return src
    return None


def report(label, root, pfbs):
    print(f"# {label}")
    print(f"#   root: {root or '(unset)'}")
    if not pfbs:
        print("#   (none)")
        return [], []
    found, missing = [], []
    for name in pfbs:
        src = find_source(name)
        if src:
            found.append(src)
            print(f"#   {name}  ->  {src}")
        else:
            missing.append(name)
            print(f"#   {name}  ->  ??? (source .otf/.ttf not found)")
    return found, missing


def main():
    texmfvar = kpse("TEXMFVAR")
    texmfhome = kpse("TEXMFHOME")

    print("# === TEXMFVAR (lost if you delete ~/.texlive*/) ===")
    var_found, var_missing = report(
        "Fonts currently installed in TEXMFVAR:", texmfvar, pfb_basenames(texmfvar)
    )
    print()
    print("# === TEXMFHOME (survives deletion of ~/.texlive*/) ===")
    home_found, home_missing = report(
        "Fonts currently installed in TEXMFHOME:", texmfhome, pfb_basenames(texmfhome)
    )

    print()
    print("# === Re-install command (TEXMFVAR fonts only) ===")
    if var_missing:
        print(
            "# WARNING: the following TEXMFVAR fonts have no matching source"
        )
        print("# .otf/.ttf in any SOURCE_DIRS — they cannot be re-installed:")
        for n in var_missing:
            print(f"#   - {n}")
        print(
            "# Add the directory holding them to SOURCE_DIRS in this script,"
        )
        print("# or omit them from the re-install.")
    if var_found:
        # Dedupe in case the same source produced multiple .pfbs (unusual
        # but possible if otftotfm was invoked under multiple encodings).
        unique = sorted({str(p) for p in var_found})
        cmd = "~/Documents/src/otfinst/otfinst.py " + " ".join(
            shlex.quote(p) for p in unique
        )
        print(cmd)
    else:
        print("# (Nothing in TEXMFVAR — no re-install needed.)")

    if home_missing:
        print()
        print(
            "# Note: TEXMFHOME also has .pfbs whose source .otf/.ttf isn't"
        )
        print("# in SOURCE_DIRS. These survive deletion, so this is informational:")
        for n in home_missing:
            print(f"#   - {n}")

    print()
    print("# === Cleanup command (consolidate to TEXMFHOME) ===")
    print(
        "# After re-installing your fonts (which now go to TEXMFHOME under"
    )
    print(
        "# the modern otfinst), the old per-vendor copies under TEXMFVAR are"
    )
    print(
        "# duplicates. This command removes them, leaving updmap's regenerated"
    )
    print(
        "# outputs (psfonts.map, pdftex.map, ...) intact."
    )
    print(
        "# WARNING: only run this AFTER the re-install above completes and"
    )
    print(
        "# your documents still compile. Anything in TEXMFVAR that was NOT"
    )
    print(
        "# rebuilt in TEXMFHOME will be permanently gone."
    )

    if not texmfvar:
        print("# (TEXMFVAR not set — nothing to clean.)")
    else:
        type1_root = Path(texmfvar) / "fonts" / "type1"
        vendors = (
            sorted(d.name for d in type1_root.iterdir() if d.is_dir())
            if type1_root.is_dir()
            else []
        )
        if not vendors:
            print(
                "# (No vendor dirs under TEXMFVAR/fonts/type1 — nothing to clean.)"
            )
        else:
            # Flag any TEXMFVAR vendor that has at least one .pfb whose
            # source isn't on disk: cleanup would lose those.
            unrecoverable_by_vendor = {}
            for vendor in vendors:
                vendor_pfbs = sorted(
                    {
                        p.stem
                        for p in (type1_root / vendor).rglob("*.pfb")
                    }
                )
                losses = [n for n in vendor_pfbs if find_source(n) is None]
                if losses:
                    unrecoverable_by_vendor[vendor] = losses
            if unrecoverable_by_vendor:
                print(
                    "# WARNING: the following vendors have .pfbs with no source"
                )
                print(
                    "# .otf/.ttf in SOURCE_DIRS. Cleanup would lose them:"
                )
                for v, names in unrecoverable_by_vendor.items():
                    print(f"#   - {v}: {', '.join(names)}")
                print(
                    "# Either skip those vendors below, or locate the sources"
                )
                print("# and add their dir to SOURCE_DIRS first.")
            targets = []
            for vendor in vendors:
                for sub in ("fonts/tfm", "fonts/vf", "fonts/type1"):
                    targets.append(os.path.join(texmfvar, sub, vendor))
                for sub in ("fonts/enc/dvips", "fonts/map/dvips"):
                    targets.append(os.path.join(texmfvar, sub, vendor))
            cmd = "rm -rf " + " ".join(shlex.quote(t) for t in targets)
            print(cmd)
            print("texhash " + shlex.quote(texmfvar))
            print("updmap-user")


if __name__ == "__main__":
    main()
