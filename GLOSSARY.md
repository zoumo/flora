# Flora: Deep Module Design

This glossary defines the vocabulary used by Flora's module design skills.
The definitions align with `codebase-design`.

## Language

**Module**:
Anything with an interface and an implementation, regardless of scale.
_Avoid_: Unit, component, service.

**Interface**:
Everything callers must know to use a module correctly, including types, invariants, ordering, errors, configuration, and performance constraints.
_Avoid_: API, signature, public methods as substitutes for the complete interface.

**Implementation**:
The code inside a module.
An implementation describes substance, while an adapter describes a role at a seam.

**Depth**:
The behavior available through an interface relative to what callers must learn.
A deep module hides complexity behind a small interface.
_Avoid_: Ratios of implementation lines to interface lines.

**Seam**:
A location where behavior can change without edits at that location.
A module's external seam is the location of its interface.
_Avoid_: Boundary.

**Adapter**:
A concrete implementation that satisfies an interface at a seam.
The term identifies a role, not the size or complexity of the implementation.

**Leverage**:
The capability callers gain from learning an interface.

**Locality**:
The concentration of changes, knowledge, and verification within a module.
