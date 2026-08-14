# Roadmap

## Active

- [x] [`ticket-004`](project/ticket-004/README.md): reconcile Modularity's DSL
  revision and schema digest with the immutable pin used by SSOT, and replace
  the stale POA no-repository placeholder with its published revision while
  retaining an informative, no-authority relation. Current state:
  `DONE / DONE`; exact-head Validator approval, protected merge and automatic
  implementation-branch deletion are verified.
- [x] Adopt immutable `new-project` governance at published revision
  `6800f0138bc9063eb2dacb0a8b797dedcafb7952`; repository bootstrap evidence:
  commit `653e677e508132be30b97bcbba48599c902437ed`.
- [x] [`ticket-001`](project/ticket-001/README.md): define Modularity DSL v1,
  its closed schema, stable errors and immutable standard bindings.
  - [x] Pass deterministic schema, DSL-manifest and governance validation.
  - [x] Complete the LLM-assisted todo2code/SubLLM semantic audit.
  - [x] Obtain trusted exact-head review, merge, and verify branch deletion.
- [x] [`ticket-002`](project/ticket-002/README.md): implement dependency-free,
  deterministic document and semantic validation with stable `MOD-*` errors.
  - [x] Preserve plan-first history and the two-file implementation budget.
  - [x] Pass unit, static, schema-equivalence and governance validation.
  - [x] Complete LLM-assisted todo2code/SubLLM intent review.
  - [x] Obtain trusted exact-head review, merge and verify branch deletion.
- [x] [`ticket-003`](project/ticket-003/README.md): publish a validated,
  digest-bound Subactor ecosystem modularity profile and evidence guide.

## Later

- [ ] Validate intent and refactoring opportunities with todo2code using LLM
  analysis through SubLLM when it provides a stronger result.
