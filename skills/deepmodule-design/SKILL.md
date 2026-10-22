---
name: deepmodule-design
description: Design deep modules with language-independent interfaces and TypeSpec contracts. Use for module design, interface simplification, and testability.
---

# Deep Module Design

## Goal

Design deep modules that hide complexity behind small interfaces.
Keep the design independent of implementation and programming language.
Deliver a design, not implementation code.

## Glossary

Use the vocabulary from `codebase-design` consistently.

| Term | Meaning |
| --- | --- |
| Module | Anything with an interface and an implementation, regardless of scale. |
| Interface | Everything callers must know: types, invariants, ordering, errors, configuration, and performance constraints. |
| Implementation | The code inside a module. |
| Depth | The behavior available through an interface relative to what callers must learn. |
| Seam | A location where behavior can change without edits at that location. |
| Adapter | A concrete implementation that satisfies an interface at a seam. |
| Leverage | The capability callers gain from learning an interface. |
| Locality | The concentration of changes, knowledge, and verification within a module. |

## Principles

- Design around caller goals and observable behavior, not existing classes, tables, frameworks, or programming languages.
- Preserve required behavior and data constraints. Separate these constraints from implementation choices.
- Hide complexity inside the module. Do not make callers coordinate internal steps or decode a generic command interface.
- Use seams where behavior must vary. Do not invent adapters to justify a seam.
- Describe external operations and data structures in TypeSpec (`.tsp`). Add transport bindings only when requirements need them.
- Define inputs, results, failures, and field semantics. Document behavioral constraints that TypeSpec cannot express.
- Define ordering, state changes, side effects, retries, and lifecycle rules where applicable.
- Make the interface the test surface. Assert results and observable effects, not private state or internal calls.
- Make nondeterministic behavior controllable through necessary seams. Do not add business operations solely for tests.
- Define contract test scenarios with initial state, input, and expected results. Cover normal behavior, limits, and defined failures.
- Require all adapters to satisfy the same contract tests when multiple adapters exist.
- Store all design artifacts under `harness/modules/<module-name>/`: design notes, TypeSpec files, and contract test scenarios.
- Keep established decisions, assumptions, and unresolved questions distinct. Mark designs with unresolved contract decisions as drafts.

## Good and Bad Designs

| Concern | Bad design | Good design |
| --- | --- | --- |
| Depth | Callers reserve stock, charge payment, and repair partial failures. | Callers place an order. The module coordinates these actions under an explicit failure contract. |
| Independence | The interface accepts database rows or framework objects. | The interface accepts domain data with explicit constraints. |
| Small interface | `execute(command: string, payload: unknown)` hides undocumented commands and results. | Named operations define valid inputs, results, and failures. |
| Side effects | `charge()` returns nothing. Callers cannot determine whether a retry causes another charge. | `charge()` returns an outcome. The contract defines duplicate requests and uncertain outcomes. |
| Testability | Tests inspect private state or assert internal call sequences. | Tests assert results and observable effects through the caller interface. |
| Determinism | Tests wait for real time or depend on a live payment provider. | Necessary seams control time and provider outcomes. Separate tests check real provider behavior. |

## Workflow

1. Identify the module, its callers, and the capability it owns.
2. Use `grill-with-docs` to clarify requirements and scope. Follow its process until the discussion concludes.
3. Write the design using [the module design template](templates/design.md) after discussion.
   Store the design, TypeSpec contract, and contract test scenarios under `harness/modules/<module-name>/`.
4. Compile TypeSpec with the project compiler when available. Otherwise, report compilation as unverified.
5. After completing the artifacts, start an independent review agent with a fresh context.
   Provide the requirements and design artifacts. Request findings on design quality and contract consistency.
6. If writing or review reveals unresolved decisions, return to discussion. Update the artifacts and repeat the review.
7. Report review findings and passed, failed, or unverified checks. TypeSpec compilation does not prove behavioral correctness.
