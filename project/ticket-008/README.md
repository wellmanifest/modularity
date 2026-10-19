# Ticket 008: Split modularity validator into shape and graph semantics modules under 500 lines

- **ID**: ticket-008
- **Owner**: agent:antigravity under SESSION_EXECUTION_AUTHORIZATION
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-19

## Goal and scope

Split `src/modularity.py` (`871` lines) into `src/modularity.py` (`<= 500` lines) and `src/modularity_semantics.py` (`<= 500` lines) per `REUSE-011` and `REUSE-015`, eliminating the monolith hotspot while preserving 100% behavioral parity.

## Acceptance criteria

- [x] AC-01: `src/modularity.py` and `src/modularity_semantics.py` are both `<= 500` lines and `pytest -q` passes.
- [x] AC-02: `./project/governance-check.sh --actor agent` reports `GOV-PASS`.

## Participants

- Human participant: session request to reduce horizontal complexity and modularize under 500 lines; no `user-*` file was created or modified.
- Agent participant: [ai-antigravity.md](ai-antigravity.md)
