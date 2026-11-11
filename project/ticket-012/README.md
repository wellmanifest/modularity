# Ticket 012: Harden SCC cycle detection, unhashable field guards, and bounded JSON I/O

- **ID**: ticket-012
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-11

## Goal and scope

Eliminate missed secondary cycle branches, false bridge-edge cycle findings, and `RecursionError` in `src/modularity_semantics.py` by replacing recursive DFS cycle walks with iterative Tarjan strongly connected components; guard semantic lookups and `_json_identity` against unhashable/heterogeneous malformed inputs so `validate_document` never raises `TypeError`; and harden `load_json_bytes`, `validate_path`, and `check_local_digest` with `O_NOFOLLOW | O_NONBLOCK` 4 MiB regular-file reads, `NaN`/`Infinity` rejection, and iterative `MAX_JSON_DEPTH = 64` bounds while keeping all modules well below 500 lines.

## Acceptance criteria

- [x] AC-01: Iterative Tarjan SCC detects all edges in multi-branch cycles without `RecursionError` on 1,500+ module chains and without flagging one-way bridges between disjoint cycles.
- [x] AC-02: Unhashable non-scalar link/contract/layer/state fields, non-finite JSON constants, deep JSON nesting, symlinks, FIFOs, and oversized files fail deterministically with schema/JSON/path findings rather than `MOD-INTERNAL-001` crashes.
- [x] AC-03: All `src/` and `tests/` Python files remain strictly under 500 lines, and `PYTHONPATH=src pytest -q`, `ruff check src tests`, `./project/governance-check.sh --base origin/main`, and `wellman check` pass with 0 errors.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
