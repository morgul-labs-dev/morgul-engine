# Contributing to Morgul Engine

We welcome contributions from the community!

### Contributor License Agreement (CLA)
Before your pull request can be merged, you must agree to our [Contributor License Agreement](CLA.md).

To sign off, include the following statement in your pull request description:
> "I have read and agree to the Contributor License Agreement (CLA.md)."

Pull requests without this sign-off statement will not be merged.

### Technical Standards
1. Determinism: All state transitions and random generation must be deterministic, seeded by `(seed, day, hour)`.
2. Benchmark Validation: Any change impacting population dynamics or agent logic must pass the 30-year demographic benchmark (`python tests_30yr.py`).
3. License: All contributions are licensed under AGPL-3.0 and the terms of the CLA.
