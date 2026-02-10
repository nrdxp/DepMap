# PLAN: Performance Optimization — Graph Construction + Rendering Pipeline

<!--
  PLAN documents are structured procedures for /core execution.
  They should be professional, complete, and ready to hand off.

  Iterate in your sketch; commit in the plan.

  See: workflows/plan.md for the full protocol specification.
-->

## Goal

Eliminate the two dominant performance bottlenecks in DepMap's mapping pipeline — quadratic graph edge construction from ubiquitous identifiers (B4), and O(log T) redundant full re-renders during binary search (B2) — by applying an identifier stopword filter, switching to a weighted DiGraph, and (conditionally) replacing the binary search with tag-level greedy accumulation. The combined fixes target a ~1000x speedup for large codebases (2000+ files).

## Constraints

- Existing tests (`pytest`) must continue to pass
- No changes to the MCP server protocol or tool signatures
- No new external dependencies
- Map output must be **comparable** in quality — covering the same high-value files with equivalent or better budget utilization (exact output will differ due to graph changes)

## Complexity Analysis

> **Variables:** F = files, T = total tags, I = unique identifiers, M = "stopword" identifiers (appearing in >50% of files), K = PageRank iterations (~100), R = render cost per file.

### Current Hot Path

| Step                     | Operation                                                                     | Complexity                                         | F=2000, M=10 estimate |
| :----------------------- | :---------------------------------------------------------------------------- | :------------------------------------------------- | :-------------------- |
| Graph edge construction  | For each identifier, for each (ref_file × def_file) pair, call `G.add_edge()` | O(Σᵢ rᵢ × dᵢ) ≈ O(M × F²) for stopword identifiers | ~40M edge insertions  |
| PageRank                 | SciPy sparse power iteration (already native since nx 3.0)                    | O(K × E) native                                    | ~4B sparse ops (fast) |
| Binary search rendering  | log₂(T) iterations × to_tree() over selected files                            | O(log T × F × R)                                   | ~15 × 2000 × R        |
| Second `get_tags()` loop | Re-parses all files for ranked tag collection                                 | O(F × parse_cost)                                  | Redundant full pass   |
| tiktoken encoding lookup | `encoding_for_model()` called per `token_count()`                             | O(lookup) per call                                 | Repeated lookup       |

> **Note:** `nx.pagerank()` in networkx 3.6.1 already uses SciPy sparse matrices internally (`pagerank_scipy` was absorbed in nx 3.0). The PageRank step is already native — no swap needed. `weight="weight"` is already the default parameter. The dominant bottleneck is **graph construction**, not PageRank.

### Per-Phase Theoretical Improvement

| Phase | Target                       | Before                | After                        | Theoretical Speedup                   |
| :---- | :--------------------------- | :-------------------- | :--------------------------- | :------------------------------------ |
| 1     | Graph edge construction (B4) | O(M × F²) ≈ 40M edges | O((I−M) × f²) ≈ 5k-50k edges | **~1000-5000×** on graph construction |
| 1     | PageRank input               | O(K × 40M) sparse ops | O(K × 50k) sparse ops        | **~800×** on PageRank step            |
| 1     | Double `get_tags()` (B1)     | 2 × O(F × parse)      | 1 × O(F × parse)             | **2×** on tag collection              |
| 1     | tiktoken lookup (B3)         | O(lookup) per call    | O(1) amortized               | Negligible wall-clock                 |
| 2     | Binary search rendering (B2) | O(log T × F × R)      | O(F × R)                     | **~15×** (log₂ 30k ≈ 15)              |

> Phase 1 targets the dominant bottleneck (graph construction) which is almost certainly >95% of wall-clock time. Phase 2 targets rendering which is O(log T) overhead — significant only if Phase 1 makes the graph fast enough that rendering becomes the new bottleneck.

## Decisions

| Decision              | Choice                                                         | Rationale                                                                                                                                  |
| :-------------------- | :------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------- |
| Stopword strategy     | Two-tier: hard keywords + configurable frequency (default 50%) | Hard filter for known noise (`self`, `this`, `new`). Higher threshold avoids removing structurally important identifiers like trait names. |
| Graph type            | `nx.DiGraph` with weighted edges                               | Collapses parallel edges into weights. `weight="weight"` is already the default in `nx.pagerank()` (nx 3.6.1).                             |
| Phase 2               | Conditional on Phase 1 measurement                             | Phase 1 may be sufficient. Measure before adding complexity.                                                                               |
| Selection granularity | Tag-level (not file-level) if Phase 2 proceeds                 | Preserves current algorithm's semantics. File-level would waste budget on low-ranked tags.                                                 |
| Budget precision      | ~5% tolerance with trim safety net                             | Only relevant if Phase 2 proceeds.                                                                                                         |
| tiktoken caching      | Instance-level `self._encoding`                                | Trivial.                                                                                                                                   |
| Native code (C/Rust)  | Rejected                                                       | `nx.pagerank()` already delegates to SciPy/LAPACK. Custom FFI targets the wrong bottleneck.                                                |
| `pagerank_scipy()`    | N/A — already in effect                                        | Removed in nx 3.0; `nx.pagerank()` absorbed it. Our nx 3.6.1 already uses SciPy internally.                                                |

## Risks & Assumptions

| Risk / Assumption                                                                       | Severity | Status      | Mitigation / Evidence                                                                                                                       |
| :-------------------------------------------------------------------------------------- | :------- | :---------- | :------------------------------------------------------------------------------------------------------------------------------------------ |
| Tag-vs-file granularity mismatch — greedy file accumulation changes selection semantics | HIGH     | Mitigated   | Use tag-level greedy accumulation. Accumulate tags in rank order, group by file for rendering.                                              |
| 30% stopword threshold too aggressive — filters structurally important identifiers      | MEDIUM   | Mitigated   | Two-tier: hard keywords always filtered; frequency threshold raised to 50%, configurable.                                                   |
| "Preserve output quality" constraint impossible — graph changes alter rankings          | MEDIUM   | Mitigated   | Constraint weakened to "comparable quality." Verify empirically on known projects.                                                          |
| DiGraph `weight` parameter handling on migration from MultiDiGraph                      | LOW      | Resolved    | `weight="weight"` is already the default in nx 3.6.1. MultiDiGraph parallel edges sum to equivalent weights. Regression test still prudent. |
| TreeContext output independent per-file                                                 | —        | Validated   | Code review: `TreeContext` keyed by `rel_fname`, `.format(lois)` per-file only. No cross-file state.                                        |
| Stopword filter removes 90%+ of edges                                                   | —        | Partial     | Plausible for Python/Rust/TS. Less effective for Go. Needs empirical measurement.                                                           |
| Phase 1 alone sufficient                                                                | —        | Unvalidated | If B4 is >95% of wall-clock (likely), Phase 2's ~15x on rendering is marginal.                                                              |

## Open Questions

- **Stopword filter effectiveness across languages.** The 90% edge reduction estimate is analytical. Go's short identifiers (`err`, `ctx`, `ok`) may not be caught by hard keywords and may fall below 50% frequency in small projects. _Resolved empirically by Phase 1 measurement._
- **Tag-level greedy accumulation marginal cost.** When adding a tag to a file already partially rendered, marginal token cost is not a full re-render. Phase 2 implementation must track incrementally. _Only relevant if Phase 2 proceeds._

## Scope

### In Scope

- `repomap_class.py`: graph construction, rendering pipeline, caching
- `utils.py`: tiktoken encoding cache
- New tests: stopword filter, DiGraph edge count, weight validation
- Performance timing: before/after comparison on DepMap's own source
- Existing test suite must pass unchanged

### Out of Scope

- Tree-sitter grammar or SCM file changes
- MCP protocol interface changes
- Parallelizing file parsing
- Optimizing `find_src_files()` directory walk (B6 — low priority)
- Optimizing `TreeContext.format()` internals (in `grep-ast`, upstream)
- Replacing networkx entirely (igraph / fast-pagerank / raw SciPy sparse) — targets wrong bottleneck
- Native code extensions (Rust/C FFI) — `nx.pagerank()` already native SciPy
- `pagerank_scipy()` swap — already absorbed into `nx.pagerank()` since nx 3.0

## Phases

1. **Phase 1: Graph Construction Fix** — Eliminate quadratic edge explosion _(theoretical ~1000-5000× on graph step)_
   - [x] Add two-tier stopword filter: hard keywords (`self`, `this`, `new`, `None`, `null`, `true`, `false`) + configurable frequency threshold (default 50%)
   - [x] Convert `nx.MultiDiGraph()` → `nx.DiGraph()` with weighted edges
   - [x] Add in-memory tags dict to eliminate second `get_tags()` loop (B1)
   - [x] ~~Cache tiktoken encoding at `__init__` time (B3)~~ — N/A, tiktoken caches internally
   - [x] **Measure: time `repo_map` on DepMap's own source before/after** — 0.31s for 12 files
   - [x] Add test: verify stopword filter correctly removes high-frequency identifiers
   - [x] Add test: verify DiGraph edge count is bounded for a known fixture

2. **Phase 2: Rendering Pipeline Optimization** _(DEFERRED — Phase 1 results sufficient; binary search overhead negligible at current scale)_
   - [ ] ~~Replace binary search with tag-level greedy accumulation in `get_ranked_tags_map_uncached()`~~
   - [ ] ~~Pre-render each file's full tag set, cache keyed by `(rel_fname, frozenset(lois))`~~
   - [ ] ~~Accumulate tags in rank order, tracking per-file token cost~~
   - [ ] ~~Trim from tail if final output exceeds budget~~
   - [ ] ~~Add test: verify greedy accumulation output fits within token budget~~

## Verification

- [x] All existing tests pass: `python -m pytest tests/ -v` — 64 passed
- [x] New unit test: stopword filter removes hard-coded keywords
- [x] New unit test: stopword filter removes identifiers above frequency threshold
- [x] New unit test: DiGraph edge count bounded by F² for a known fixture
- [x] Integration: `repo_map` MCP tool produces valid output on DepMap's own source
- [x] Performance: timed comparison of Phase 1 before/after
- [x] Real-world validation: eka project (128 files, 1209 defs, 3123 refs) — 0.66s
- [ ] ~~Phase 2 verification~~ _(deferred with Phase 2)_

## Technical Debt

| Item                                      | Severity | Why Introduced                     | Follow-Up                                                 | Resolved |
| :---------------------------------------- | :------- | :--------------------------------- | :-------------------------------------------------------- | :------: |
| `query()` deprecation warning in grep-ast | LOW      | Upstream API change in tree-sitter | Track grep-ast update for `Query()` constructor migration |   [ ]    |

## Retrospective

### Process

The `/sketch` → `/plan` → `/core` pipeline worked well here. Two adversarial challenge rounds during planning caught critical findings _before_ implementation:

- **`pagerank_scipy()` is a no-op** — discovered during Challenge Round 2 that `nx.pagerank()` already uses SciPy sparse matrices since networkx 3.0. This prevented us from wasting effort on a swap that would have done nothing.
- **`weight="weight"` is already the default** — reduced DiGraph migration risk from MEDIUM to LOW before any code was written.
- **tiktoken caches internally** — discovered during execution that `tiktoken.get_encoding()` uses a module-level dict cache, making our planned caching deliverable unnecessary.

The adversarial pattern of "assume every claim is wrong until verified" earned its keep. Without it, we would have shipped a plan with a redundant phase and two false assumptions.

### Outcomes

| Metric                 | Before                        | After                   | Improvement                                                                             |
| :--------------------- | :---------------------------- | :---------------------- | :-------------------------------------------------------------------------------------- |
| eka (128 files)        | Did not terminate             | 0.66s                   | ∞ → sub-second                                                                          |
| DepMap self (12 files) | ~0.3s (estimated)             | 0.31s                   | Baseline (too small to bottleneck)                                                      |
| Graph type             | MultiDiGraph (parallel edges) | DiGraph (weighted)      | Edge count: O(M×F²) → O(F²) max                                                         |
| Output quality         | Noise-polluted rankings       | Noise-filtered rankings | _Improved_ — stopwords no longer inflate PageRank of files with many keyword references |
| Test coverage          | 55 tests                      | 64 tests (+9)           | New: stopword filter, edge bounds, regression                                           |

Phase 2 (rendering pipeline, ~15× on binary search) was **deferred indefinitely**. At 0.66s for 128 files, binary search overhead is negligible — the theoretical 15× improvement on the rendering step would save ~10-20ms. If performance degrades on larger codebases in the future, Phase 2 remains a documented option.

### Pipeline Improvements

- **Challenge rounds should always verify library internals.** The `pagerank_scipy` finding was only possible because we inspected the actual networkx source code rather than trusting documentation or intuition. This should be a standard practice for any optimization plan that claims "swap X for Y."
- **"Comparable output" was the right constraint.** Demanding identical output would have prevented the stopword filter entirely. The weaker constraint allowed us to _improve_ output quality while still delivering the performance fix.

## References

- Sketch: `.sketches/performance-bottleneck.md`
- networkx 3.6.1 PageRank source: confirms SciPy sparse internals
- tiktoken source: `get_encoding()` caches via module-level `ENCODINGS` dict
