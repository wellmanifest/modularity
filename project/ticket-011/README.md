# Ticket 011: Harden URI/path parsing, generator provenance resolution, and SSOT helpers

- **ID**: ticket-011
- **Owner**: agent:antigravity under SESSION_EXECUTION_AUTHORIZATION
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-11

## Goal and scope

Eliminate `ValueError` / `RuntimeError` validator crashes on malformed bracketed URIs, embedded NUL/control path characters, and symlink loops; enforce `generation.generator` module existence and `outputContract` exporter ownership for `generate` links (`MOD-COMPOSE-001`); and complete SSOT helper deduplication between `src/modularity.py` and `src/modularity_semantics.py`.

## Acceptance criteria

- [x] AC-01: Malformed URIs (`http://[invalid`, `https://`, whitespace/control URIs) and unsafe relative paths (NUL/control chars, `.`, empty segments, symlink loops) emit deterministic `MOD-SCHEMA-001` / `MOD-PATH-001` findings instead of `MOD-INTERNAL-001`.
- [x] AC-02: `mode: "generate"` links validate that `generation.generator` resolves to a declared module that exports `generation.outputContract` distinct from the source `link.contract` (`MOD-COMPOSE-001`).
- [x] AC-03: `src/modularity_semantics.py` imports `LAYER_ORDER`, `_is_identifier`, and `_is_uri` from `src/modularity.py` without duplicating definitions; `ruff check src tests` and `pytest -q` pass with 0 errors.
- [x] AC-04: `./project/governance-check.sh --base origin/main` and `wellman check` pass with 0 errors.

## Participants

- Human participant: session request to validate, fix, optimize, and harden `wellmanifest/*` standards; no `user-*` file was created or modified.
