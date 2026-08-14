# Subactor ecosystem reference profile

Canonical workspace:
[`subactor-ecosystem.workspace.v1.json`](subactor-ecosystem.workspace.v1.json)

This profile demonstrates reproducible modular composition. It does not install,
fetch, invoke, or grant authority to any module. An edge says which versioned
contract an architecture consumes; it does not transfer semantic ownership or
prove that a package is installed in a particular deployment.

## Selection and evidence

The selected repositories expose complementary boundaries needed by the user’s
standardization goal. The original profile revisions were resolved from remote
`main` on 2026-08-12; DSL and POA were refreshed from remote `main` on
2026-08-14. Every digest covers the exact Git blob at its declared revision.

| Module | Revision | Contract artifact | SHA-256 |
| --- | --- | --- | --- |
| `wellmanifest/dsl` | `b7d0595c95e5abbb48ebfdbdae0bc6d43c6f82f4` | `schemas/dsl-manifest.schema.json` | `34d356b76bbd483372df84bb986e15bb84e9c1f8b11b7dc9e3a6c7276c85ed13` |
| `wellmanifest/poa` | `8424a7f5c977915ee08404b8b82d63e0f5e44ea2` | `docs/ARCHITECTURE.md` | `57570c935134b322cd69cd39be2136c24a6ceeaab36afa2f68a5b4d398856f28` |
| `subactor/lifecycle` | `f3b8e13eb17128fd0f3ff05ac45fc99c99c470c4` | `spec/LIFECYCLE_DSL.md` | `358c6718838a9f8e74cf95db83ffdda5b63b5df6d4369c36682b7583272dc465` |
| `subactor/twin` | `edfb690d4523643d6d2ea410a943b0a4a3ddd078` | `profiles/generic-twin.json` | `851a0d3923621899bb2348815141c4a6fb3df9108b692877df916d1545b98c7f` |
| `subactor/twin` | `edfb690d4523643d6d2ea410a943b0a4a3ddd078` | `proto/twin/v1/twin.proto` | `6ea85a3914189ab79e41abea2fe3d0318da2944b8613cc6f835737ba8f6460dc` |
| `subactor/modularity` | `3a414903181c5a06d03db7f3586da90941cf15f1` | `docs/schemas/modularity-workspace.schema.v1.json` | `98db51af5b17e9a480f587f462da52aafd70d8b40ae87d873d7a42fdd4fd5a68` |
| `subactor/subllm` | `b472efca0be3e9d55c8e83fe01a5e2e32654d953` | `docs/architecture.md` | `6561d80065abb0c9590ae4d11fa2a19235c7ecc3f01ebd17e76e3e603e9ad39e` |
| `semcod/todo2code` | `0dfb82c3c6b2d6af795c5a3263ca9e24a5652560` | `schemas/intent-graph.schema.json` | `bd5ce8511d5bb9a96ff346c49c7845601fffa8f7fb382ec1568bf440851778fd` |
| `subactor/diagit` | `f4fdfd958b21904c0e26ec6ffa98841644ee9117` | `src/diagit/grammars/diagit-request.v1.gbnf` | `633755cb2649c31cf97b306e9c9012fbd28889fff9e78e119dbea02f5c8ca0de` |
| `subactor/diagit` | `f4fdfd958b21904c0e26ec6ffa98841644ee9117` | `proto/diagit/v1/audit.proto` | `225623ab492af57de027dce73faea0ca72c0ba33e6104efa80987d77a9979d15` |
| `subactor/validator-agent` | `9cfe43cf3edf38421088eeb8e13df4883db98369` | `contracts/README.md` | `e42df9a613e7d40956c39c42bd49a3d6cfeca6d2ff97226d44b2ff944339dc5c` |

Branch names are discovery inputs only. A profile refresh resolves each branch
again, reviews the changed contract, updates its full commit and digest in one
ticket, and reruns deterministic validation.

## Composition evidence

Edges are grounded as follows:

| Link | Classification | Evidence and intent |
| --- | --- | --- |
| `modularity -> dsl` | normative | Modularity declares itself a Wellmanifest DSL profile and its manifest maps to the pinned DSL repository. |
| `modularity -> lifecycle` | normative compatibility | Modularity’s standard and manifest bind Lifecycle for compatibility state and evidence-gated transitions. |
| `modularity -> twin` | observational compatibility | Modularity consumes Twin traits only as observations; a Twin is never authority. |
| `diagit -> dsl` | observed conformance | Diagit publishes `dsl-manifest.json` and binds its grammar, parser, protobuf log and documentation through Wellmanifest validation. |
| `todo2code -> subllm` | observed runtime integration | todo2code resolves its `semantic` model route through SubLLM and records the resolved provider/model in audit metadata. |
| `validator-agent -> subllm` | observed runtime integration | Validator workflows resolve `patch-review` and `direct-pr-review` through a pinned SubLLM policy. |
| `validator-agent -> todo2code` | observed validation integration | Validator checks out and runs the current todo2code process for semantic review while retaining deterministic approval authority. |
| `validator-agent -> diagit` | observed read-side integration | Validator’s central workflow materializes Diagit audit evidence; the link is `observe`, not mutation authority. |

No link is inferred merely from a shared organization, neighboring checkout,
similar filename, or a future TODO.

## DSL, Lifecycle, Twin and POA roles

- DSL owns reusable language manifests, artifacts, digests and conformance.
- Lifecycle owns state-transition definitions and evidence requirements; it does
  not authorize a transition.
- Twin owns language-neutral commands, events, queries, projections,
  observations, evidence and receipts. Modularity consumes its traits through
  `observe`.
- POA remains an informative sequence:
  `DSL -> AST -> capability -> read-only Twin -> dry plan/hash -> grant ->
  bounded executor -> read-back -> receipt`. POA now has a published immutable
  v1 contract, but this workspace imports no named POA capability. It therefore
  deliberately contains no POA module, capability link or authority reference;
  the exact POA revision is retained only as an informative standard binding.

An executable POA capability would require a separately resolvable
`authorityRef` on an `invoke` link. A URI, LLM verdict, Twin observation,
historic receipt or valid profile is not such authority.

## CLI, shell, REST, MCP and protobuf

The repositories show how interface diversity remains outside domain semantics:

- Twin’s protobuf is the language-neutral command/event/query/projection model;
  CLI, safe shell, REST and MCP are adapters over that model.
- Diagit’s fenced GBNF requests dispatch the same CQRS application messages
  from CLI, interactive shell, process URI and loopback REST. Commands append
  events; queries read rebuildable projections. Its protobuf event log is the
  append-only source, while SQLite is disposable.
- todo2code uses one application service boundary for CLI, MCP, A2A and SDKs;
  deterministic facts and LLM inference retain different epistemic classes.
- Validator Agent consumes typed evidence and hosted checks, while any LLM
  review stays advisory to the deterministic decision record.

Safe shell means argv transport, never string evaluation. REST and MCP do not
gain permissions absent from the underlying command. Generated bindings retain
contract URI, version, digest and source revision.

## State and dependency direction

The profile assigns `intent-evidence` to todo2code and `repository-audit` to
Diagit as separate single-writer domains. It does not relabel Validator Agent,
Twin or Modularity as owners of derived evidence. The graph flows from interface
to application to domain/foundation and is acyclic.

## Missing `patterns` repository

No repository named `patterns` exists in the configured workspace inventory.
The demonstrated patterns are therefore cited from the pinned Twin, Diagit,
todo2code and SubLLM artifacts rather than attributed to a fabricated module. A
future `patterns` module requires its own repository URI, full commit, owned
contract, semantic version and digest before it can enter this graph.

## Validation

Run from the Modularity repository:

```text
PYTHONPATH=src python -m modularity docs/profiles/subactor-ecosystem.workspace.v1.json --format json
python3 ../../wellmanifest/dsl/src/dsl_check.py validate --root . docs/dsl-manifest.json
```

The first command validates the closed document and semantic graph without
fetching sources. Reproducibility additionally compares each declared artifact
digest with `git show <revision>:<path>` in its owning repository.
