# Ticket 016: Modularize modularity_io and harden symlink traversal, JSON digit bounds, and control-character checks

- **ID**: ticket-016
- **Owner**: tom
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-11

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: On 2026-11-11 user authorized auditing, fixing bugs, optimizing, and modularizing `< 500` lines across `wellmanifest/*` standard repositories.

Extract bounded regular-file I/O, symlink-ancestor checks, and strict JSON parsing into `src/modularity_io.py` so `src/modularity.py`, `src/modularity_semantics.py`, and all test files stay well below 500 lines; harden `_has_ancestor_symlink` against relative (`sym_dir/..`, `../sym_dir`) and un-normalized absolute symlink-parent traversal; bound JSON integer digits (`<= 400`) before `int()` conversion; enforce UTF-8 surrogate and ASCII C0/DEL control-character rejection across `owners[*].id`, `description`, `standards[*].note`, and `conformance.commands`; and reconcile merged `project/ticket-015/README.md` to `DONE`.

## Acceptance criteria

- [x] AC-01: `src/modularity_io.py` encapsulates bounded regular-file I/O and strict JSON parsing (re-exported via `__all__` in `src/modularity.py`), keeping every `src/*.py` and `tests/*.py` module strictly `< 500` lines.
- [x] AC-02: `_has_ancestor_symlink` rejects relative and un-normalized absolute symlink-parent traversal, `_parse_bounded_int` bounds raw JSON integer digits (`<= 400`) before `int()` conversion, and `Validator` / `modularity_semantics` reject lone UTF-16 surrogates and forbidden ASCII control characters in `owners[*].id`, `description`, `standards[*].note`, and `conformance.commands`.
- [x] AC-03: Regression tests in `tests/test_modularity_hardening.py` pass alongside `ruff check --no-cache src tests`, `./project/governance-check.sh --base origin/main`, and `wellman check`, and merged `project/ticket-015/README.md` is marked `DONE`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
