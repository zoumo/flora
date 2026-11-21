# Repository Documentation Principles

## Coverage

- The project introduction must explain what the project does, who it serves, and where to start.
- Development guides should identify the dependencies, settings, and commands needed to contribute.
- Describe module responsibilities and boundaries. Record the reasons and constraints behind key design decisions.
- Cover the needs of the project. One document can answer several questions.

## Freshness

- Commands, paths, defaults, and public contracts must match the version they describe.
- When a design precedes implementation, state the target version or implementation status.
- Mark superseded decisions and link to the current decision when one exists.
- Prefer links to authoritative scripts, configuration, and interface definitions.

## Information Value

- Explain design choices, operational constraints, and relationships that are hard to infer from code.
- Link to definitions for implementation details. A directory guide should tell readers where to start and why.
- Avoid copying directory trees, paraphrasing source code, or adding generic advice.
- Remove a passage if readers can still find the information, make the decision, and complete the task as easily without it.

## Audience and Navigation

- Readers should be able to find setup instructions, design documents, and development guides from the project entry point.
- Agents should be able to find applicable rules, change boundaries, and verification instructions from their entry point.
- Link to details where a task requires them. Say when to follow the link and what it contains.
- Prefer one authoritative source for rules that people and agents share.

## Readability

- State prerequisites and conditions before the steps they govern.
- Identify who acts, what to do, and how to recognize completion.
- Use one term for each concept. Use the actual names of commands, flags, and fields.
- Express one idea per sentence. Avoid ambiguous references and instructions with multiple plausible readings.
