# PLAN: Performance Optimization — Graph Construction + Rendering Pipeline

<!--
  PLAN documents are structured procedures for /core execution.
  They should be professional, complete, and ready to hand off.

  Iterate in your sketch; commit in the plan.

  See: workflows/plan.md for the full protocol specification.
-->

```yaml
PLAN: "performance-optimization"
STATUS: CHALLENGE
CONFIDENCE: 0.70 # Reduced from 0.85 — challenge revealed real issues

CTX:
  GOAL: >
    Eliminate the two dominant performance bottlenecks in DepMap's repo/dep mapping
    pipeline: (1) quadratic graph edge construction from common identifiers, and
    (2) redundant full re-renders during binary search for token budget fitting.
    The combined fixes should reduce wall-clock time by ~1000x for large codebases.
  CONSTRAINTS:
    - Must preserve correctness of generated API maps
    - Must remain compatible with the MCP server interface (no protocol changes)
    - No new external dependencies
    - Existing tests must continue to pass
  NON_GOALS:
    - Changing tree-sitter parsing grammars or SCM files
    - Modifying the MCP protocol interface
    - Rewriting PageRank itself
    - Parallelizing file parsing (orthogonal optimization)
  SKETCH: ".sketches/performance-bottleneck.md"

CHALLENGE:
  RISKS:
    - RISK: "Tag-level vs file-level selection is a semantic change, not just an optimization"
      SEVERITY: HIGH
      MITIGATION: >
        The current binary search selects ranked_tags[:num_tags] — individual tags, not
        files. A file with 50 tags where only the top 3 are highly ranked currently
        gets 3 lines-of-interest rendered. The proposed greedy file accumulation would
        include ALL 50 tags or NONE — wasting budget on low-ranked tags from important
        files, or excluding important files entirely because their full cost exceeds
        remaining budget.

        MITIGATION: Keep tag-level granularity within the greedy approach. Instead of
        accumulating files, accumulate tags in rank order (as the binary search does),
        but group them by file for rendering. Pre-render each file with its FULL tag
        set for estimation, but track which tags are selected. When assembling the
        final output, render only selected tags per file. This preserves tag-level
        semantics while eliminating the binary search.

    - RISK: "DiGraph PageRank weight parameter must be explicitly passed"
      SEVERITY: MEDIUM
      MITIGATION: >
        The current code calls nx.pagerank(G, alpha=0.85) on a MultiDiGraph with NO
        weight parameter. On a MultiDiGraph, networkx implicitly counts multiple
        parallel edges as higher connectivity. Switching to a DiGraph with explicit
        weight attributes requires passing weight='weight' to nx.pagerank() — otherwise
        the weights are ignored and every edge is treated as weight=1, which changes
        the PageRank distribution. This is subtle and easy to miss.

        MITIGATION: Explicitly pass weight='weight' in the nx.pagerank() call. Add a
        regression test comparing PageRank output on a known fixture before and after
        the graph type change.

    - RISK: "30% stopword threshold is arbitrary and language-dependent"
      SEVERITY: MEDIUM
      MITIGATION: >
        In Rust, structurally important trait names (Display, Debug, Clone, From, Into)
        may appear in >30% of files. In Python, __init__ and __str__ would be filtered.
        These identifiers DO carry real structural signal — a file implementing Display
        for a type has a genuine dependency relationship with Display's definition.
        Filtering them loses real edges.

        MITIGATION: Use a two-tier approach. Hard stopwords (language keywords: self,
        this, new, None, null, true, false) are always filtered. Frequency-based
        filtering uses a higher threshold (50%) and is configurable via constructor
        parameter. Log filtered identifiers at debug level so users can tune.

    - RISK: "Constraint 'preserve output quality' contradicts changed selection semantics"
      SEVERITY: MEDIUM
      MITIGATION: >
        The plan's Constraints section says "Map output quality must be preserved
        (same files selected, same ranking)." But both the graph changes (stopword
        filter, DiGraph) and the rendering changes (greedy vs binary search) WILL
        produce different output. The ranking order changes, the selection changes,
        and the rendered content changes. This constraint as stated is impossible
        to satisfy.

        MITIGATION: Weaken the constraint to: "Map output must be COMPARABLE in
        quality — covering the same high-value files with equivalent or better
        budget utilization." Accept that output will differ and verify quality
        empirically by comparing maps of known projects.

  ASSUMPTIONS:
    - ASSUMPTION: "TreeContext.format() output for a file is independent of other selected files"
      VALIDATED: YES
      EVIDENCE: >
        Code review confirms: render_tree() calls tree_context.format(lois) with only
        the lines-of-interest for that specific file. TreeContext is per-file (keyed by
        rel_fname in tree_context_cache). No cross-file state leaks between renders.
        Per-file token estimation is valid.

    - ASSUMPTION: "Stopword filter removes 90%+ of edges"
      VALIDATED: PARTIAL
      EVIDENCE: >
        Plausible for Python/Rust/TypeScript where self/this/new are ubiquitous, but
        the 90% figure is an estimate, not measured. For Go (which uses short names like
        err, ctx, ok frequently), the filter may be less effective. Need empirical
        measurement on a real codebase.

    - ASSUMPTION: "Phase 1 alone might be sufficient to solve the problem"
      VALIDATED: NO
      EVIDENCE: >
        This is the steel-man for Approach A. If B4 is 99% of the wall-clock time
        (as suspected), then fixing B4 alone might make the binary search tolerable.
        We should measure after Phase 1 before committing to Phase 2. Phase 2 adds
        complexity for potentially marginal gain.

  ALTERNATIVES_REJECTED:
    - APPROACH: "Phase 1 only (Approach A) — fix the graph, keep binary search"
      REASON: >
        NOT FULLY REJECTED. This is the honest steel-man. Phase 1 fixes the O(N²)
        graph construction, which is almost certainly the dominant bottleneck. After
        Phase 1, the binary search operates over a much smaller, faster graph and may
        be "fast enough." The strongest case FOR this: it has zero risk of changing
        output semantics, which Phase 2 inherently does.

        DISPOSITION: Phase 1 is unconditionally good. Phase 2 should be conditional —
        measure performance after Phase 1, and only proceed to Phase 2 if the binary
        search is still measurably slow. This changes the plan structure.

    - APPROACH: "Use IDF weighting instead of hard stopword cutoff"
      REASON: >
        Instead of a binary filter (include/exclude), weight each identifier by its
        inverse document frequency (IDF = log(N/df)). Common identifiers get low
        weight, rare ones get high weight. This avoids the arbitrary threshold problem.
        REJECTED because: it changes the edge weight semantics (currently weight =
        count of distinct identifiers; IDF would make it a TF-IDF-like signal). More
        complex, and the hard stopword approach is simpler to reason about and debug.
        But worth noting as a future refinement.

DESIGN:
  ARCHITECTURE: >
    Phase 1: Replace quadratic MultiDiGraph edge construction with a stopword-filtered
    weighted DiGraph. Phase 2 (conditional): If binary search is still a measurable
    bottleneck after Phase 1, replace it with tag-level greedy accumulation that renders
    each file exactly once.
  KEY_DECISIONS:
    - DECISION: "Two-tier stopword filter instead of fixed 30% threshold"
      RATIONALE: >
        Hard stopwords (language keywords) are always filtered. Frequency-based
        filtering uses a configurable threshold (default 50%, not 30%) to avoid
        removing structurally significant identifiers.
      REVERSIBLE: YES
    - DECISION: "Switch MultiDiGraph to weighted DiGraph with explicit weight='weight'"
      RATIONALE: >
        Collapses parallel edges. Must explicitly pass weight='weight' to nx.pagerank()
        to preserve the PageRank signal from the original MultiDiGraph.
      REVERSIBLE: YES
    - DECISION: "Phase 2 is conditional on Phase 1 measurement"
      RATIONALE: >
        Phase 1 may be sufficient. Measuring before committing to Phase 2 avoids
        unnecessary complexity. If the binary search takes <1s after Phase 1, Phase 2
        is not worth the semantic risk.
      REVERSIBLE: YES
    - DECISION: "Tag-level greedy accumulation (not file-level) in Phase 2"
      RATIONALE: >
        Preserves the current algorithm's semantics of selecting individual tags by
        rank, not entire files. Each file renders all its LOIs for estimation, but
        only selected tags contribute to the final output.
      REVERSIBLE: YES
  PHASES:
    - ID: 1
      NAME: "Graph Construction Fix"
      OBJECTIVE: "Eliminate quadratic edge explosion and reduce PageRank input by ~5000x"
      DELIVERABLES:
        - Two-tier stopword filter (hard keywords + configurable frequency threshold)
        - MultiDiGraph → DiGraph with weighted edges + explicit weight='weight' in PageRank
        - In-memory tags cache to eliminate double get_tags() calls
        - tiktoken encoding cache (instance-level)
        - Performance measurement baseline (before/after timing)
      DEPENDENCIES: []
      ESTIMATED_SCOPE: MEDIUM
    - ID: 2
      NAME: "Rendering Pipeline Optimization (Conditional)"
      OBJECTIVE: "Replace binary search with tag-level greedy accumulation — only if Phase 1 is insufficient"
      DELIVERABLES:
        - Tag-level greedy accumulation in get_ranked_tags_map_uncached()
        - Per-file render + token estimation
        - Render cache keyed by (rel_fname, frozenset(lois))
        - Budget overflow trim pass (safety net)
      DEPENDENCIES: [1]
      ESTIMATED_SCOPE: MEDIUM
```

## Goal

Eliminate the two dominant performance bottlenecks in DepMap's mapping pipeline — quadratic graph edge construction from ubiquitous identifiers (B4), and O(log T) redundant full re-renders during binary search (B2) — by applying an identifier stopword filter, switching to a weighted DiGraph, and (conditionally) replacing the binary search with tag-level greedy accumulation. The combined fixes target a ~1000x speedup for large codebases (2000+ files).

## Constraints

- Existing tests (`pytest`) must continue to pass
- No changes to the MCP server protocol or tool signatures
- No new external dependencies
- Map output must be **comparable** in quality — covering the same high-value files with equivalent or better budget utilization (exact output will differ due to graph changes)

## Decisions

| Decision              | Choice                                                         | Rationale                                                                                                                                  |
| :-------------------- | :------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------- |
| Stopword strategy     | Two-tier: hard keywords + configurable frequency (default 50%) | Hard filter for known noise (`self`, `this`, `new`). Higher threshold avoids removing structurally important identifiers like trait names. |
| Graph type            | `nx.DiGraph` with `weight='weight'` passed to PageRank         | Must explicitly pass weight param — without it, edge weights are ignored and ranking changes silently.                                     |
| Phase 2               | Conditional on Phase 1 measurement                             | Phase 1 may be sufficient. Measure before adding complexity.                                                                               |
| Selection granularity | Tag-level (not file-level) if Phase 2 proceeds                 | Preserves current algorithm's semantics. File-level would waste budget on low-ranked tags.                                                 |
| Budget precision      | ~5% tolerance with trim safety net                             | Only relevant if Phase 2 proceeds.                                                                                                         |
| tiktoken caching      | Instance-level `self._encoding`                                | Trivial.                                                                                                                                   |

## Scope

### In Scope

- `repomap_class.py`: graph construction, rendering pipeline, caching
- `utils.py`: tiktoken encoding cache
- New tests: stopword filter, DiGraph edge count, weight parameter validation
- Performance timing: before/after comparison on DepMap's own source
- Existing test suite must pass unchanged

### Out of Scope

- Tree-sitter grammar or SCM file changes
- MCP protocol interface changes
- Parallelizing file parsing
- Optimizing `find_src_files()` directory walk (B6 — low priority)
- Optimizing `TreeContext.format()` internals (in `grep-ast`, upstream)

## Phases

1. **Phase 1: Graph Construction Fix** — Eliminate quadratic edge explosion
   - Add two-tier stopword filter: hard keywords (`self`, `this`, `new`, `None`, `null`, `true`, `false`) + configurable frequency threshold (default 50%)
   - Convert `nx.MultiDiGraph()` → `nx.DiGraph()` with weighted edges
   - Pass `weight='weight'` to `nx.pagerank()` calls
   - Add in-memory tags dict to eliminate second `get_tags()` loop (B1)
   - Cache tiktoken encoding at `__init__` time (B3)
   - **Measure: time `repo_map` on DepMap's own source before/after**
   - Add test: verify stopword filter correctly removes high-frequency identifiers
   - Add test: verify DiGraph edge count is bounded for a known fixture

2. **Phase 2: Rendering Pipeline Optimization** _(conditional — only if binary search is still slow after Phase 1)_
   - Replace binary search with tag-level greedy accumulation in `get_ranked_tags_map_uncached()`
   - Pre-render each file's full tag set, cache keyed by `(rel_fname, frozenset(lois))`
   - Accumulate tags in rank order, tracking per-file token cost
   - Trim from tail if final output exceeds budget
   - Add test: verify greedy accumulation output fits within token budget

## Verification

- [ ] All existing tests pass: `python -m pytest tests/ -v`
- [ ] New unit test: stopword filter removes hard-coded keywords
- [ ] New unit test: stopword filter removes identifiers above frequency threshold
- [ ] New unit test: DiGraph edge count bounded by F² for a known fixture
- [ ] New unit test: `weight='weight'` is passed to `nx.pagerank()`
- [ ] Integration: `repo_map` MCP tool produces valid output on DepMap's own source
- [ ] Performance: timed comparison of Phase 1 before/after
- [ ] Phase 2 verification (if triggered):
  - [ ] Greedy accumulation output ≤ token budget
  - [ ] Trim pass activates when estimate overshoots

## References

- Sketch: `.sketches/performance-bottleneck.md`
- ADR: `docs/adr/0001-performance-optimization.md` _(to be created at COMMIT)_
