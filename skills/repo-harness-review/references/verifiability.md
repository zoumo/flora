# Verifiability Principles

## Acceptance Criteria

- State the promise in terms of an observable outcome. Specify the starting conditions, allowed variation, and what counts as failure.
- Define success at the boundary named in the promise. A recovery claim about an interrupted job requires evidence about that job after restart.
- Record exceptions and skipped checks explicitly. A required check that did not run must remain unverified.

## Repeatability

- Another contributor should be able to find the supported verification procedure and start from a known state.
- Identify the required tools, versions, inputs, permissions, and setup steps. Prefer a repository entry point that supplies shared defaults.
- State what can vary between runs and which result must remain reproducible. A documented manual procedure can support a repeatable check.

## Controllability and Observability

- The verifier must be able to establish the condition the claim depends on. To check interruption during processing, establish that work has started before interrupting it.
- Prefer explicit controls for inputs, dependencies, timing, and faults where the outcome depends on them.
- Read the promised result through a public interface, terminal event, or durable state. For asynchronous work, follow the same operation from acceptance to completion.

## Evidence Traceability

- A reviewer should be able to identify the revision or artifact, procedure, inputs, conditions, and outcome behind an acceptance claim.
- Prefer a concise record that links the claim to the actual observation. A manual acceptance record can provide sufficient evidence.
- Preserve failures, skipped checks, and limits on what the evidence proves. Distinguish recorded observations from expected results.
