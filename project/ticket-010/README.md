# Ticket 010: Wire standalone pytest pythonpath and align DSL manifest LLM boundary

- **ID**: ticket-010
- **Owner**: agent:antigravity under SESSION_EXECUTION_AUTHORIZATION
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-11

## Goal and scope

Configure `pythonpath = [".", "src"]` and `testpaths = ["tests"]` in `pyproject.toml` so standalone `pytest` discovers `modularity`, and publish `docs/schemas/modularity-validation-report.schema.v1.json` bound into `docs/dsl-manifest.json` (`llm.mode = "bidirectional"`, `llm.decisionProtocol = "dsl-input-output"`, `standardsLock` revision/digest, and `python3` conformance commands).

## Acceptance criteria

- [x] AC-01: Standalone `pytest -q` collects and passes all Modularity unit tests.
- [x] AC-02: `dsl_check.py validate docs/dsl-manifest.json` passes with 0 errors.
- [x] AC-03: `./project/governance-check.sh --base origin/main` and `wellman check` pass with 0 errors.

## Participants

- Human participant: session request to validate, fix, optimize, and harden `wellmanifest/*` standards; no `user-*` file was created or modified.
