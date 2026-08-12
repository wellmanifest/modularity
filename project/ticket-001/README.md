# Ticket 001: Define Modularity DSL core standard

- **ID**: ticket-001
- **Owner**: unresolved:human
- **Status**: DONE
- **Workflow state**: DONE
- **Created**: 2026-08-12

## Goal and scope

Define the language-neutral Modularity DSL v1 contract for composing modules
owned by independent repositories. The bounded slice covers canonical JSON
AST, immutable external-standard bindings, ownership, dependency direction,
authority references, lifecycle state, Twin observation and POA capability
semantics. It does not implement a runtime, fetch repositories, or execute a
declared composition.

## Acceptance criteria

- [x] AC-01: The standard defines module, contract and composition boundaries
  without coupling them to a programming language or transport.
- [x] AC-02: The closed JSON Schema rejects mutable revisions, authority on
  non-invocation links, shell-string conformance commands and unsupported
  composition modes.
- [x] AC-03: DSL, Lifecycle and Twin are bound to exact published repository
  revisions; unpublished POA is clearly informative and unpinned.
- [x] AC-04: Stable `MOD-*` diagnostics cover every semantic rule that the
  deterministic validator must enforce in the next slice.
- [x] AC-05: The Wellmanifest DSL manifest owns all five implementation
  artifacts, digest-binds the four non-self-referential artifacts, and passes
  the pinned DSL checker.
- [x] AC-06: Optional analysis scope separates owned, managed and generated
  paths and requires budgeted, provenance-bound LLM batches rather than an
  unbounded whole-repository graph.

## Risks

- A repository URI or capability URI could be mistaken for authority. The
  standard permits only opaque authority references and states that resolution
  remains an external runtime responsibility.
- Cross-module dependency cycles can be intentional at deployment time but
  make source and contract ownership ambiguous. V1 rejects cycles and expects
  orchestration to live above the module graph.
- POA currently has no immutable publication baseline. It therefore informs
  terminology but cannot be a normative dependency of this release.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
