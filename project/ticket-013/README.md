# Ticket 013: Harden modularity unhashable enum guards, finite float parsing, and intra-root symlink digest rejection

- **ID**: ticket-013
- **Owner**: unresolved:human
- **Status**: DONE
- **Workflow state**: MERGED
- **Created**: 2026-11-11

## Goal and scope

Eliminate `TypeError` crashes on unhashable `owners[*].kind`, `contracts[*].kind`, `standards[*].relation`, and `standards[*].status` fields; reject `1e999` / `-1e999` float overflow in `load_json_bytes` and `_enforce_json_depth` and enforce `allow_nan=False` in `render_json`; reject intra-root leaf and directory symlinks in `check_local_digest` before `.resolve()` dereferences them; and reconcile merged `ticket-010`, `ticket-011`, and `ticket-012` statuses to `DONE`.

## Acceptance criteria

- [x] AC-01: Malformed unhashable `owner.kind`, `contract.kind`, `standard.relation`, and `standard.status` emit deterministic `MOD-SCHEMA-001` findings without `TypeError` / `MOD-INTERNAL-001`.
- [x] AC-02: `load_json_bytes` rejects `1e999` / `-1e999` float overflow, and `check_local_digest` emits `MOD-PATH-001` on both leaf symlinks and symlinked ancestor directories inside `--root`.
- [x] AC-03: All Python modules remain strictly below 500 lines, and `ruff check src tests`, `PYTHONPATH=src pytest -q`, `./project/governance-check.sh --base origin/main`, and `wellman check` pass with 0 errors.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
