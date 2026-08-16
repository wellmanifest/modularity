# Modularity

Language-neutral standards and an executable DSL for composing independently
owned modules without duplicating their contracts, authority, or state.

The project will standardize how repositories reuse the Wellmanifest DSL and
Subactor Lifecycle/Twin standards. Process-Oriented Architecture (POA) is
tracked as an informative draft until it has an immutable published revision.

## Product commercial contracts

Sales list prices and entitlements are a **single-exporter** contract.
`contractOwnership=single-exporter`: one product pack owns the public catalog.

For Subactor:

| Contract | Exporter (HOME) | Consumers (ADOPT / facade) |
| --- | --- | --- |
| Public commercial sheet + site binding | [`subactor/offer`](https://github.com/subactor/offer) | portals (`plans.json`), checkout copy |
| Brand tokens + closed vocabulary | [`subactor/brand`](https://github.com/subactor/brand) | CSS/i18n, offer display names, social |
| Promo / qualification decisions | `wellmanifest/policy-dsl` sales profile | backend/frontend evaluators |

Runtime portals and PHP/TS modules **import** those exporters; they must not
re-export a second public price sheet or brand kit. Parallel modules may
project presentation fields, but a drift gate must fail before merge when
facade amounts, entitlements, tokens or forbidden terms diverge.

Standards pointers (no product content): [`wellmanifest/offer`](../offer),
[`wellmanifest/brand`](../brand).

## Offer catalogs

Public commercial sheets HOME in `subactor/offer` (ADOPT wellmanifest
standards; do **not** HOME offers under wellmanifest). Sites ADOPT a binding
pin (`offer://subactor/offer/<id>/v<N>`). Do not duplicate list prices inside
runtime portals, local `packages/*`, or policy packs.

## Brand kits

Brand tokens and vocabulary HOME in `subactor/brand`. Sites and offer packs
ADOPT the profile. Do not HOME product brand under wellmanifest.

