# Changelog

All notable changes to Morgul Engine and Morgul Engine Pro will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-10

### Added
- Headless deterministic circadian tick engine (foraging, rest cycles, spoilage).
- SQLite WAL mode for high-concurrency read/write separation via FastAPI.
- Open-core AGPL-3.0 engine with decoupled local LLM daily chronicle generation.
- Pro Edition: React Atlas dashboard, divine intervention endpoints, and containerized Docker orchestration.
- Pro Edition: Regional Orphan Emancipation (age >= 7.0 early coming-of-age in leaderless provinces).
- Pro Edition: Communal foster care allowing self-sustaining apprentices to nourish dependent infants.

### Fixed
- Toddler role boundary: enforced `age < 7.0` strictly as Child to prevent premature apprentice starvation.
- Safe dictionary lookups on raid resolutions preventing KeyError server crashes.
- Bounded memory log cap (2,000 entries) preventing unbounded RAM growth.
- Hardened CORS origins with explicit whitelist enforcement.

## [1.1.0] - 2026-11-11
### Added
- **Wasteland Raider Combat Asymmetry:** Scaled marauder combat power by 0.70x to simulate malnutrition and lack of martial militia discipline.
- **Pyrrhic Attrition Mechanics:** Enforced 15 HP combat fatigue on successful sacks and increased repelled assault damage from 30 HP to 45 HP.
- **Sterility Mating Block:** Enforced bidirectional sterility checks in `_resolve_mating` preventing sterile agents from initiating or receiving mating proposals.

### Fixed
- **Database Loader Persistence:** Explicitly reconstructed `agent.is_sterile` from SQLite rows in `database.py`.
- **API Serializer Fix:** Fixed variable generator binding for `is_sterile` attribute in `/api/sim/state`.
