# Parallelization in otfinst.py

## The problem

Running `otftotfm` once per `.otf` × encoding × feature combination on a
large font collection (hundreds of Adobe `.otf`s) is wall-time-bound at
the level of *hours*. The work is mostly CPU spent reading OTF tables
and writing TFM/VF metric data — embarrassingly parallel in principle.

A naive `concurrent.futures` over `installcommands` does not work,
though. Several `otftotfm` invocations running concurrently can corrupt
each other's output files.

## What `otftotfm` writes per call

Per the dry-run trace (`otftotfm --no-create -a -e ... --typeface ...
--vendor ... <src>.otf <fontname>`):

| File | Path | Contention |
|---|---|---|
| `.tfm` (display) | `tfm/<vendor>/<typeface>/<fontname>.tfm` | Unique per call (last argv is the fontname suffix) |
| `.tfm` (base) | `tfm/<vendor>/<typeface>/<fontname>--base.tfm` | Unique |
| `.vf` | `vf/<vendor>/<typeface>/<fontname>.vf` | Unique |
| `.enc` | `enc/dvips/<vendor>/a_<hash>.enc` | Hashed; collides only between calls with identical encoding+features. Content is byte-identical → benign. |
| `.pfb` | `type1/<vendor>/<typeface>/<src>.pfb` | **Shared** — every call referencing the same source `.otf` writes the same `.pfb` file. |
| `<vendor>.map` | `map/dvips/<vendor>/<vendor>.map` | **Shared** — read-modify-write per call against a per-vendor map. |
| `ls-R` | TEXMFHOME root | Shared, but we regenerate it from scratch with `texhash` after the run, so in-flight corruption is irrelevant. |

The two real correctness hazards are:

- **`<vendor>.map` race**: read-modify-write means two concurrent
  same-vendor calls can lose each other's entries silently. Failure
  mode: pdfTeX later complains that a font isn't scalable, because
  the map line is missing (the symptom that started this whole
  refactor in the first place — see the original `lzfw` debugging
  session).
- **`<src>.pfb` race**: same source `.otf` referenced by multiple
  commands (e.g., the same font installed under multiple encodings)
  → both invocations want to write the same `.pfb` bytes. Identical
  content but POSIX makes no atomicity guarantee for concurrent
  overlapping writes.

## Why per-vendor parallelism isn't enough

The first instinct is to group commands by vendor and serialize within
a group. That fixes the map race (vendor-scoped) and the `.pfb` race
(same `.otf` is always same vendor). But for users whose fonts are
mostly from a single vendor (e.g., all Adobe), this collapses back to
serial execution.

## The actual strategy

Three pieces:

### 1. Per-call private map fragment

Pass `--map-file=<unique tempfile>` to every `otftotfm` invocation.
This redirects the per-call map output away from
`<vendor>.map` and into a private file that only that one process
writes. Confirmed via dry-run that `--map-file` overrides the
automatic per-vendor destination cleanly:

```
otftotfm: would update /tmp/otfinst-xxx/frag-NNNNN.map for LY1-Foo--base
otftotfm: would update /tmp/otfinst-xxx/frag-NNNNN.map for LY1-Foo
```

(Compare to the default, where both lines target
`<TEXMFHOME>/fonts/map/dvips/<vendor>/<vendor>.map`.)

The map race is now structurally impossible: no two calls write to
the same map file.

### 2. Group-by-source serialization

`installcommands` is grouped by source `.otf` path. Within a group
(same `.otf`, possibly multiple encodings), commands run sequentially.
Across groups, they run concurrently. Different sources → different
`.pfb` paths → no `.pfb` race.

### 3. ThreadPoolExecutor across groups

```python
with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as pool:
    futures = [pool.submit(run_group, g) for g in groups.values()]
    for fut in concurrent.futures.as_completed(futures):
        print(fut.result())
```

Threads, not processes, because:

- Each task spends almost all its time waiting on the `otftotfm`
  subprocess. The Python GIL is released during that wait, so
  threads parallelize fine.
- Threads are lighter to spawn than processes and avoid
  pickling-related issues with the closure over `otftotfm_env`.

## Output capture

Each task does `subprocess.run(record["argv"], capture_output=True,
text=True)` and accumulates a transcript string for its whole group.
The transcript is `print()`-ed atomically when the future completes.
Without capture, dozens of concurrent processes interleave their
warning messages on stderr unreadably.

One side-effect to be aware of: if you pipe `otfinst.py` to a file or
to `tee`, Python's `print()` is block-buffered while subprocess output
inherits stdout directly. So in a piped run, the post-pass `updmap`
output (which uses inherited stdout) appears in the log file *before*
Python flushes the captured `otftotfm` transcripts at exit. To a TTY
the order is correct; if you need correct order in a pipe, run
`PYTHONUNBUFFERED=1 otfinst.py ...`.

## Post-pass merge

After all parallel groups finish, a single serial pass:

1. Bucket fragment paths by vendor.
2. For each vendor, read the existing canonical
   `<TEXMFHOME>/fonts/map/dvips/<vendor>/<vendor>.map` (if any) into
   an `OrderedDict` keyed by display-name (the line's first
   whitespace-separated token). This is the dedup key.
3. Read each fragment, overlay its entries onto the dict
   (last-write-wins, but no duplicate keys).
4. Rewrite the canonical map with otftotfm's standard header comment
   followed by the deduped entries.

This is correct because each fragment contains at most one line per
display-name, and display-name is unique to the
(encoding × source × feature-set) tuple — so two different commands
never produce conflicting entries with the same key.

## Speedup

The parallelism is bounded by `min(N_unique_otf_sources,
cpu_count)`. For a load of ~400 unique `.otf` sources on a 10-core
machine, that's roughly 10× wall-clock improvement on the
`otftotfm` phase. The post-pass (merge + texhash + updmap) is serial
but small relative to the otftotfm work.

## Tempfile cleanup

The fragment files are created under
`tempfile.mkdtemp(prefix="otfinst-")`. Best-effort cleanup happens at
the end of `executeCommands()`: each fragment is `os.unlink`-ed and
the tempdir is `os.rmdir`-ed. Failures are silently swallowed (the OS
will clean `/tmp` eventually anyway).

## Things this design does NOT need

- **No file locking.** The two real races are both eliminated
  structurally — `--map-file` for vendor maps, group-by-source for
  `.pfb`s. Locking would just paper over a less-clear design.
- **No multiprocessing.** Threads are sufficient since the work is
  subprocess-bound.
- **No retry logic.** `otftotfm` is deterministic; if it fails, the
  user's input is broken (missing source font, malformed OTF, etc.)
  and retry doesn't help. We surface the exit code in the captured
  transcript and let the user decide.
