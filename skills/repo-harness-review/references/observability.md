# Observability Principles

For the completeness score, consider logs, business metrics, performance metrics, and traces as four separate entries. Decide which signals are required from the repository's responsibilities and explicit requirements before checking the instrumentation.

For each signal found, cite where the code emits it. Record collection conditions and where users can read it. If the host owns export, distinguish evidence of emission from evidence of delivery. For a missing signal, name the entry points checked.

Score capability quality separately using the four dimensions below. For example, useful logs can support failure diagnosis even when required traces are missing. To lower a quality score, identify the specific diagnostic question the available signals cannot answer.

## Outcome Visibility

- Callers must be able to distinguish outcomes that require different actions. A timeout after submission can leave the outcome unknown.
- For asynchronous work, distinguish acceptance from completion. Identify where callers can read the final result after the initial response.
- Prefer receipts, status fields, or exit codes that callers can use without parsing diagnostic prose.

## Failure Diagnosis

- Maintainers should be able to follow one failed operation to the stage and component where it failed.
- Prefer a stable operation identifier across retries, queues, and process boundaries. Keep individual attempts distinguishable.
- Check where a diagnostic is recorded and who can retrieve it. Account for sampling, export settings, and retention when judging which failures remain visible.

## Operational Health

- Assess business outcomes where the repository owns them. For a job service, compare jobs accepted, completed, and failed to detect work that stops after acceptance.
- Assess performance where it affects users or operators. Prefer measures that expose delays under load, such as queue wait, completion latency, throughput, or saturation.
- Operators should be able to tell which operation or dependency has degraded. Existing queries, dashboards, and exported measurements can show what they can observe.
- Judge each measure against the repository's role. A library may expose measurements to its host. Explain when ongoing health monitoring falls outside the repository's responsibilities.

## Signal Quality

- Prefer one actionable diagnostic for a failure. Look for duplicate messages across layers, routine events logged as errors, or retries that bury the final cause.
- Metric names and units must match their recording points. For rates, check the numerator, denominator, and time window. For latency, check where timing starts and stops.
- Check how retries, cancellations, and unknown outcomes enter each metric. Counting attempts as completed jobs can hide a drop in business success.
- Prefer bounded metric labels. Keep per-request identifiers in logs or traces when correlation requires them.
- Credentials must stay out of telemetry. Inspect field selection and redaction before logs, metric labels, or trace attributes are stored or exported. Check access and retention for necessary sensitive fields. Cite field names or redacted examples in the report.
