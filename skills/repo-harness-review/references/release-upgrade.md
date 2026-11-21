# Release and Upgrade Principles

## Interface Compatibility

- Identify the public contracts consumers depend on and the versions the project supports. Include APIs, protocols, CLI output, configuration, and stored data where applicable.
- Preserve supported behavior, including defaults, error semantics, and side effects. A signature check alone covers only the shape of an interface.
- Prefer compatibility checks against a released baseline. Use old clients or data fixtures to establish which combinations work, including mixed versions during rollout.

## Feature Flags and Rollout Control

- Prefer an explicit opt-in or feature flag when a risky change needs a gradual rollout. For libraries, an optional API or a consumer-controlled version pin may provide sufficient control.
- A flag must control the actual behavior. Trace its default, scope, and effect on both new and in-flight operations.
- Disabling a flag can stop new writes. Treat it as a rollback mechanism only if the old path can still read the state already written.

## Breaking Change Management

- Make breaking changes identifiable before consumers upgrade. State who is affected, which replacement to use, and when support for the old behavior ends.
- Prefer a transition that supports old and new consumers while they migrate. For a field rename, define when readers accept both names and when writers can stop emitting the old one.
- Specify upgrade order and how to resume an interrupted migration. Before an irreversible write, document a usable backup or forward-recovery path.
- Use old-version fixtures or upgrade records to show that migrated data remains usable. State which versions and paths the evidence covers.

## Release Gates and Provenance

- A mandatory check must prevent the relevant merge or release when it fails, is skipped, or has no result. Verify the effective rule and any authorized exception paths.
- Required checks must apply to the revision or artifact that advances. Prefer promoting the checked artifact by digest.
- A published version must be traceable to its source and build inputs. Use package metadata, release manifests, or attestations to link the shipped artifact to its checks.
