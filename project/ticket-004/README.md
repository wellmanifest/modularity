# Ticket 004: Reconcile DSL and POA standard pins

- **ID**: ticket-004
- **Owner**: unresolved:human
- **Status**: DONE
- **Workflow state**: DONE
- **Created**: 2026-08-14

## Goal and scope

Refresh Modularity's immutable external-standard evidence so it no longer
disagrees with the DSL revision already pinned by Wellmanifest SSOT and no
longer claims that Wellmanifest POA lacks a repository or commit.

Use the verified remote-main identities:

- Wellmanifest DSL
  `b7d0595c95e5abbb48ebfdbdae0bc6d43c6f82f4`, with
  `schemas/dsl-manifest.schema.json` digest
  `sha256:34d356b76bbd483372df84bb986e15bb84e9c1f8b11b7dc9e3a6c7276c85ed13`;
- Wellmanifest POA
  `8424a7f5c977915ee08404b8b82d63e0f5e44ea2`, version `0.1.0`, with
  `docs/ARCHITECTURE.md` digest
  `sha256:57570c935134b322cd69cd39be2136c24a6ceeaab36afa2f68a5b4d398856f28`.

The DSL revision is normative for Modularity manifest conformance. POA remains
an informative compatible standard and receives no module, capability link,
authority reference or runtime role merely because an immutable revision now
exists.

## Acceptance criteria

- [x] AC-01: The human owner requested execution and correction of the
      cross-standard inconsistencies, recording `SESSION_EXECUTION_AUTHORIZATION`.
- [x] AC-02: Every Modularity DSL reference uses the same exact revision and
      schema digest as the inspected SSOT standards lock and DSL remote main.
- [x] AC-03: Every POA reference names its real repository, exact remote-main
      revision and published artifact while retaining `informative` relation.
- [x] AC-04: The ecosystem profile and guide contain no stale DSL digest and no
      statement that POA lacks a commit or repository.
- [x] AC-05: Modularity's own DSL manifest binds every changed governed
      artifact to its recomputed SHA-256 digest.
- [x] AC-06: Closed-schema/profile validation, unit tests, DSL manifest checks
      and repository governance pass.

## Participants

- Human participant: unresolved; no `user-*` file was created.
- Agent participant: [ai-codex.md](ai-codex.md)

## Authorization

The user explicitly approved continued implementation and asked to correct the
DSL-revision inconsistency and similar discovered issues on 2026-08-14. This is
bounded session execution authorization, not trusted merge approval.

## Verification evidence

- The current Wellmanifest DSL checker passes both manifest validation and the
  changed-artifact gate with zero errors.
- Modularity's dependency-free CLI reports `valid: true` with no findings for
  the reconciled ecosystem profile.
- All 19 Python unit tests pass with bytecode generation disabled for a clean
  governed diff.
- `./project/governance-check.sh`, exact stale-pin searches and
  `git diff --check` pass on 2026-08-14.
- Validator App approved exact implementation head
  `c676321fdf08ffef7296f87b3ee5abcd5f3cafb5`, binding repository, PR #7,
  ticket-004, correlation ID and actor. Its advisory LLM was unavailable, so
  the recorded approval rests explicitly on deterministic gates.
- PR #7 merged as `main@2edd13e8e74ca0b7d00aa57087b5567eebf05633`
  and GitHub automatically deleted `ticket-004-reconcile-standard-pins`.
- This governance-only follow-up closes the ticket from the integrated default
  branch; no implementation artifact changes in the closure.

## Non-goals

- No edit to Wellmanifest DSL, SSOT or POA source repositories.
- No change to Modularity schema semantics, validator, diagnostic catalog or
  version.
- No POA module, invoke link, authority reference, execution grant or receipt.
- No refresh of unrelated ecosystem modules or their historical evidence.
