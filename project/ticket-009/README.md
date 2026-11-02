# Ticket 009: Eliminate duplicated AST helpers and raw print output per SSOT and nohardcode standards

- **ID**: ticket-009
- **Owner**: agent:antigravity under SESSION_EXECUTION_AUTHORIZATION
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-02

## Goal and scope

Deduplicate AST helper functions (`_is_digest`, `_is_relative_path`, `_glob_covers`) across `modularity.py` and `modularity_semantics.py` to satisfy `wellmanifest/ssot` (SSOT-COUPLE-001) and replace raw `print()` calls in CLI execution with stream-directed outputs to satisfy `wellmanifest/nohardcode` (NOHARDCODE-007).

## Acceptance criteria

- [x] AC-01: `PYTHONPATH=src pytest -q` passes without errors.
- [x] AC-02: `ssot audit src` reports 0 findings on `src/`.
- [x] AC-03: `nohardcode_check.py --target .` reports 0 errors.
- [x] AC-04: `./project/governance-check.sh --actor agent` passes with GOV-PASS.

## Participants

- Human participant: session request to eliminate code duplication and raw prints per wellmanifest standards; no `user-*` file was created or modified.
