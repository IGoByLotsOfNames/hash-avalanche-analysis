# Figure sources and reproduction

These documentation figures read the committed reports. Generating them does **not** rerun the experiment, change its outputs or modify the package.

```bash
python -m pip install matplotlib==3.10.8
python docs/visuals/generate.py
```

Matplotlib is only needed to recreate the figures; the experiment itself uses Python's standard library. Each figure has an SVG version for sharp rendering and a PNG version for convenient viewing. Both use an opaque light background so labels stay readable in light and dark GitHub themes.

| Figure | Evidence and method |
|---|---|
| `experiment-flow` | The byte sampler, exact bit mutation, digest comparison and accumulator in [`experiment.py`](../../src/hash_avalanche/experiment.py). This diagram describes implemented behaviour. |
| `normalized-distributions` | The [MD5](../../results/replayable/md5-100k-seed20261002.json) and [SHA-256](../../results/replayable/sha256-100k-seed20261002.json) 100,000-trial histograms. Density is `count / trials / (1 / digest_bits)`, allowing equal-area comparison across different digest widths. The dashed reference is the exact `Binomial(B, 0.5)` probability mass divided by the same bin width; it is a theoretical comparison, not another measured run. The plotted range contains every nonzero observed bin. |
| `streaming-memory` | All 12 records in the [recorded benchmark](../../benchmarks/windows-python-2026-10-02.json): two algorithms, three trial counts and two aggregation methods. Both axes use logarithmic scales, points are actual measurements and connecting lines only guide the eye. KiB means 1,024 bytes. Memory is a separate tracemalloc pass, not total process memory. See the [benchmark method](../../benchmarks/README.md). |

Before drawing, the generator checks histogram counts, raw moments, run settings and normalized means. It also checks that every streaming/retained benchmark pair has the same result fingerprint. Rendering was produced with Python 3.12 and Matplotlib 3.10.8; minor font or rendering differences can occur with a different platform or Matplotlib dependency version. SVG timestamps are omitted and the SVG hash salt is fixed.

The figures make no security ranking, speed guarantee or claim to reproduce the historical ten-million-trial investigation. No performance result has been extrapolated beyond the recorded trial counts.
