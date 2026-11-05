# Contributing to Morgul Engine

We welcome contributions from the community!

### Contributor License Agreement (CLA)
Before your pull request can be merged, you must agree to our [Contributor License Agreement](CLA.md). When you open a pull request, the CLA Assistant bot will prompt you to review and digitally sign the agreement if you have not already done so.

### Guidelines
1. Ensure the 30-year demographic benchmark (`python tests_30yr.py`) and CI tests pass.
2. Keep agent transitions deterministic: all hourly RNG logic must be seeded via `(seed, day, hour)`.
3. Adhere to AGPL-3.0 licensing standards.
