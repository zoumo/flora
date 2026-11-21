# Test Layering Principles

For the completeness score, assess each of these test types. Decide which are required from the repository's responsibilities and explicit requirements before checking the suite.

- **Unit tests** exercise a rule or component in isolation.
- **Integration tests** exercise a component boundary and assert an outcome across it.
- **End-to-end (E2E) tests** exercise a public product entry point and check a user-visible result.
- **Smoke tests** quickly check that a build or deployment is usable, for example by starting the packaged service and checking readiness.

Classify tests by their entry points, dependencies, and assertions. Identify real services, test doubles, and recorded inputs. Smoke describes a test's purpose. A fast E2E test may satisfy both entries when it provides evidence for each.

Cite a representative test for each type found. For a missing type, name the entry points checked. Score capability quality separately using the five dimensions below.

## Essential Coverage

- Identify necessary tests from public promises, business rules, data integrity requirements, and failures with costly consequences.
- Trace each critical behavior to a test that would detect its loss. Include failure and recovery paths where the product promises them.
- Use test counts and coverage percentages to guide inspection. A score must cite specific behaviors protected or exposed.

## Layer Fit

- Prefer the least expensive layer that can reliably detect the fault.
- Test local decisions in isolation. Exercise real component boundaries when wiring, serialization, or transactions determine the result.
- Use E2E tests for outcomes that depend on the complete product path. State which external dependencies the test actually uses.
- Keep overlapping tests when each layer detects a distinct fault. Identify what the broader test adds before calling coverage redundant.

## Assertion Quality

- Assert the outcome the caller relies on, including persistent side effects when they are part of the contract.
- Identify an incorrect result that the assertion would catch. For example, a duplicate-charge test must detect a second debit even if both requests return success.
- Prefer observable results over incidental call order. Assert interactions when the interaction itself is a requirement.

## Feedback Efficiency

- Prefer a focused local command for a small change and broader checks for changes to shared contracts.
- Trace CI triggers and filters to the tests they select. A narrow filter must still include affected consumers.
- Use existing timings to assess feedback cost. A fast full suite can be a reasonable default. Identify the wait a contributor incurs before judging the strategy.

## Isolation and Reliability

- Tests should run independently with controlled inputs and explicit ownership of mutable state.
- Prefer readiness signals over fixed delays. Check that failure and cancellation paths release files, processes, and ports.
- Distinguish a possible source of instability from a recorded intermittent failure. Cite the shared resource or timing dependency for a risk, and prior runs for an observed failure.
