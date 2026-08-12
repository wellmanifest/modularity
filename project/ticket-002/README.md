# Ticket 002: Implement deterministic Modularity validator

- **ID**: ticket-002
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-08-12

## Goal and scope

Implement a dependency-free Python validator for the canonical Modularity v1
workspace. The validator parses strict UTF-8 JSON, evaluates the closed
document contract and semantic composition rules, and emits deterministically
sorted findings from the published `MOD-*` catalog. It observes local files
only and never fetches repositories, resolves authority, or executes declared
conformance commands.

## Acceptance criteria

- [ ] AC-01: Strict parsing rejects invalid UTF-8, malformed JSON and duplicate
  object keys with stable diagnostics.
- [ ] AC-02: Closed-document validation rejects unknown/missing fields,
  malformed identifiers, revisions, digests, paths, policies and mode-specific
  fields without a third-party schema runtime.
- [ ] AC-03: Semantic validation covers unique identifiers and exports,
  endpoint/contract resolution, local digests, layer direction, DAG topology,
  state ownership, lifecycle, Twin, POA and bounded analysis scope.
- [ ] AC-04: Text and JSON reports sort findings by path, code and message;
  valid input exits 0, invalid input exits 1 and internal failure exits 2.
- [ ] AC-05: Positive and focused negative tests pass without network access,
  and the adopted governance gate reports zero errors and warnings.

## Risks

- A partial schema reimplementation could silently accept unknown structure.
  Field sets and type rules are centralized and exercised with mutation-based
  negative cases.
- Digest validation could escape the selected root. Repository-relative paths
  are checked before any local read, and missing artifacts fail closed.
- A descriptive invocation could be mistaken for authority. Validation only
  checks opaque references and never resolves or exercises them.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
