# MODULARITY

Canonical contract: `subactor.modularity/workspace/v1`

This standard describes how independently owned modules are composed without
copying their semantics, authority, or state. It is language-neutral and
transport-neutral. A conforming document is descriptive input to validation,
generation, observation, or a separately authorized runtime; it is never an
execution grant.

## Purpose

Define one language-neutral, authority-safe contract for composing modules
owned by independent repositories.

## Syntax

Use canonical UTF-8 JSON conforming to
`docs/schemas/modularity-workspace.schema.v1.json`.

## Inputs

Provide immutable module sources, exported contracts, composition links,
ownership, lifecycle, state roles, policies, and argv-based conformance checks.

## Outputs

Conformance produces deterministic typed findings only. Generators and
runtimes are separate consumers of a valid document.

## Errors

Stable diagnostics are defined in `docs/errors/catalog.json`; invalid input
exits 1 and unexpected validator failure exits 2.

## Examples

Reference workspace profiles will be published in a separately governed slice
after the core validator exists.

## 1. Scope

The standard governs:

- module identity, repository ownership, and immutable source revisions;
- exported and imported contracts identified by stable URIs and digests;
- dependency direction and allowed composition modes;
- single-writer state ownership and read-only projections;
- bindings to DSL, Lifecycle, Twin, and Process-Oriented Architecture (POA);
- deterministic conformance commands and stable diagnostics.

It does not define a package manager, deployer, source-code generator, secret
store, capability broker, or workflow executor.

## 2. Canonical form and versioning

The sole canonical representation is UTF-8 JSON conforming to
[`modularity-workspace.schema.v1.json`](schemas/modularity-workspace.schema.v1.json).
YAML, a textual DSL, CLI flags, protobuf messages, REST resources, shell
wrappers, and MCP tools MAY be projections, but MUST round-trip through the
canonical JSON AST without changing semantics.

The top-level `schema` MUST equal `subactor.modularity/workspace/v1`.
`version` follows Semantic Versioning. Unknown fields are rejected. Consumers
MUST NOT infer behavior from an unknown enum value.

## 3. Module identity and source

Each module MUST have a unique `id`, at least one owner, one architectural
`layer`, one lifecycle state, a repository URI, and an exact lowercase
40-character Git commit in `revision`.

Moving branches and tags are discovery aids only and MUST NOT appear where an
immutable revision is required. A module MAY select a repository-relative
`path`; absolute paths and `..` segments are forbidden. `manifest` identifies
the module's owning contract when one exists.

The five ordered layers are:

1. `foundation`
2. `domain`
3. `application`
4. `interface`
5. `deployment`

A module MAY depend on the same or a lower layer. A lower layer MUST NOT depend
on a higher layer. Modules within one layer remain subject to the acyclic graph
rule.

Lifecycle is one of `experimental`, `stable`, `deprecated`, or `retired`.
These values describe compatibility state; transition rules SHOULD be supplied
by a pinned Subactor Lifecycle profile. The Modularity document itself neither
performs nor authorizes lifecycle transitions.

## 4. Contracts

A contract belongs to exactly one exporting module and has:

- a module-local `id`;
- a globally stable `uri`;
- a `kind`;
- a Semantic Version;
- a SHA-256 digest of its canonical bytes;
- an optional repository-relative path.

Supported kinds are `dsl`, `json-schema`, `protobuf`, `lifecycle`,
`poa-capability`, `twin-trait`, and `other`. A contract declaration is an
export. Imports are expressed only by composition links, so a contract has one
semantic owner and any number of consumers.

Changing canonical bytes without changing `digest` is invalid. A breaking
semantic change requires a new major version or URI according to the owning
standard. Transport bindings MUST NOT redefine the contract.

## 5. Composition graph

`links` form a directed graph from consumer (`from`) to provider (`to`). Every
endpoint and contract URI MUST resolve uniquely. Self-links and graph cycles are
invalid.

V1 permits four composition modes:

| Mode | Meaning |
| --- | --- |
| `link` | Consume the provider contract directly by URI and digest. |
| `generate` | Derive a projection while retaining source provenance. |
| `observe` | Read evidence or a projection without becoming its authority. |
| `invoke` | Request a provider capability through a separate authority boundary. |

Copying or embedding another module's canonical source is not a composition
mode. Generated output MUST record its source contract URI, version, digest,
and generator identity. Generated output never becomes the semantic owner of
the source contract.

An `invoke` link MUST contain an opaque `authorityRef`. The reference locates a
separately resolvable grant or policy; it MUST NOT contain a token, secret,
credential, approval, or proof of execution. Other modes MUST NOT contain an
authority reference.

## 6. Ownership and state

The nested `state.role` is one of:

- `none`: the module owns no durable state for this composition;
- `owner`: the sole writer and semantic owner of its state;
- `projection`: a rebuildable read model derived from an owner.

Every named `state.domain` MUST have exactly one module with `state.role:
owner`; that module is implicitly its own owner. A projection MUST name that
module using `state.owner`. Modules with `state.role: none` MUST omit both
fields.

Composition does not transfer state ownership. Synchronized copies, caches,
indexes, event projections, and Digital Twins remain projections unless the
state owner publishes an explicit versioned migration contract.

## 7. DSL binding

Modularity is a Wellmanifest DSL profile:

- the canonical source is the closed JSON Schema;
- ownership and artifacts are declared in `docs/dsl-manifest.json`;
- every normative artifact is digest-bound;
- deterministic validation is authoritative for conformance;
- LLM analysis MAY propose findings or refactors but MUST be typed,
  provenance-bound, and advisory.

An LLM MUST NOT create authority, mark an unevaluated module healthy, relax an
unknown-field rejection, or expand accepted intent. When todo2code is used,
LLM analysis SHOULD be enabled through SubLLM whenever it can improve semantic
or refactoring findings; deterministic validation still decides conformance.

## 8. Lifecycle binding

A module MAY export a `lifecycle` contract. The contract URI and digest bind a
Subactor Lifecycle definition. Lifecycle evidence identifiers describe
required proof; the runtime authenticates the evidence. Modularity validation
checks references and topology only, never the truth of evidence or permission
to transition.

Retired modules MUST NOT be the provider of any link. Deprecated modules MAY
be consumed only when the workspace explicitly allows deprecation in
`policies`.

## 9. Twin binding

A `twin-trait` contract describes a read-side trait or observation boundary.
Links to a Twin MUST use `observe`, unless a separate command capability is
exported and invoked with an authority reference.

A Twin is observational and MUST NOT be treated as system authority. Missing,
stale, contradictory, or unauthenticated evidence is `UNEVALUABLE`, not
healthy. Canonical resource and process URIs identify subjects and operations;
they do not grant permission.

For CQRS + Event Sourcing implementations, commands, immutable events,
projections, optimistic concurrency, idempotency, and the transactional outbox
remain responsibilities of the owning Twin contract. Modularity links those
contracts but does not reproduce them.

## 10. POA binding

POA means Process-Oriented Architecture. A `poa-capability` contract may name a
closed process capability that follows the conceptual path:

```text
DSL -> typed AST -> capability resolution -> read-only Twin -> dry plan/hash
    -> separate grant/intent -> bounded executor -> read-back -> receipt
```

The capability URI and dry plan are not authority. Execution requires a
separate exact grant or intent bound to the request, subject, revision, plan,
and applicable policy. Historic receipts are evidence, not reusable authority.

At publication of this version, the local Wellmanifest POA project has no Git
commit or published repository. It is therefore an informative design input,
not a normative pinned dependency. A future release MAY make it normative only
after an immutable revision and conformance contract exist.

## 11. Interfaces and transports

CLI, safe shell, REST, and MCP/protobuf interfaces SHOULD bind to the same
semantic command/query boundary. They MUST NOT implement divergent module
semantics.

- CLI arguments are tokenized values, not an implicit shell program.
- Shell bindings MUST pass argv arrays and MUST NOT use string evaluation.
- REST resources bind canonical identifiers and use explicit idempotency and
  concurrency semantics where commands are exposed.
- MCP tools SHOULD be generated from or mapped to protobuf command/query
  contracts and MUST preserve typed errors.

The workspace `conformance.commands` field contains argv arrays. Shell strings,
pipelines, interpolation, and command substitution are forbidden.

## 12. Policies

Every workspace declares the following fail-closed policies:

- `unknownFields: reject`
- `cycles: reject`
- `layerDirection: higher-to-same-or-lower`
- `contractOwnership: single-exporter`
- `stateOwnership: single-writer`
- `authority: external-reference-only`
- `twinAuthority: observational-only`
- `llmAuthority: propose-only`

`allowDeprecated` defaults to false by being required explicitly. Policy values
are constants in V1; weakening one requires a future major standard version,
not a workspace-local override.

## 13. Deterministic validation

A conforming validator performs, in order:

1. UTF-8 JSON parsing and closed-schema validation;
2. uniqueness checks for module IDs and contract URIs;
3. immutable revision, path, digest, and ownership checks;
4. link endpoint and contract resolution;
5. composition-mode and authority-reference checks;
6. single-writer state validation;
7. lifecycle and Twin restrictions;
8. layer-direction and directed-cycle checks;
9. deterministic diagnostic sorting.

Diagnostics use [`errors/catalog.json`](errors/catalog.json). Each finding has
`code`, `severity`, `path`, and `message`. Findings sort by path, code, then
message. Valid input exits 0, invalid input exits 1, and an unexpected internal
failure exits 2. Network access is not required for validation.

LLM review is an additional advisory producer. It MUST identify the repository
and exact revision it analyzed, bind its input digest, and distinguish evidence
from inference. It cannot replace any step above.

## 14. Conformance levels

| Level | Requirement |
| --- | --- |
| `document` | Canonical JSON passes syntax and closed-schema rules. |
| `graph` | IDs, contracts, ownership, layers, state, and DAG rules pass. |
| `standards` | Every normative external standard is bound to an exact revision. |
| `interfaces` | Generated CLI/shell/REST/MCP bindings preserve one semantic boundary. |
| `advisory` | Optional LLM findings are typed and provenance-bound. |

A tool MUST report only the levels it actually evaluated. Absence of evidence
is not success.

## 15. Evolution

Additive optional behavior requires a minor release. Tightening or changing an
existing semantic rule requires a major release unless it only corrects a
documented implementation defect without changing valid documents. Diagnostic
codes are stable within a major version; removed codes remain reserved.

Language-, framework-, and ecosystem-specific profiles extend the kernel by
contract reference. They MUST NOT fork, copy, or silently weaken this standard.
