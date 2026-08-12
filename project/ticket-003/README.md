# Ticket 003: Publish Subactor ecosystem modularity profile

- **ID**: ticket-003
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-08-12

## Goal and scope

Publish one validated Subactor ecosystem workspace that demonstrates how
independently owned DSL, lifecycle, Twin, model-routing, intent-analysis,
repository-audit and trusted-review contracts compose. Every source and
contract artifact is pinned to its current remote `main` commit and SHA-256.
The profile is a reference architecture, not a claim that every illustrative
link is an installed runtime dependency.

## Acceptance criteria

- [x] AC-01: Eight published repositories and ten contract artifacts are bound
  to full remote-main revisions and exact SHA-256 digests.
- [x] AC-02: The profile passes the dependency-free Modularity validator with
  document, graph and standards conformance and no network access.
- [x] AC-03: The companion guide distinguishes observed integration evidence
  from recommended composition and maps DSL, Lifecycle, Twin, POA, CQRS/Event
  Sourcing, protobuf, CLI, safe shell, REST and MCP boundaries.
- [x] AC-04: Unpublished POA and the absent local `patterns` repository are
  represented as explicit limitations, not fabricated immutable modules.
- [x] AC-05: The Wellmanifest DSL manifest owns and digest-binds both profile
  artifacts, and pinned DSL plus adopted governance checks pass.

## Risks

- A profile can accidentally turn an example link into a false dependency
  claim. Every link is classified in the guide with source evidence and
  architectural intent.
- Mutable branches would make the profile irreproducible. Branches are used
  only for discovery; the document records the resolved full commits.
- POA or `patterns` could be invented from local expectations. Neither is
  treated as a published module without an immutable repository artifact.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
