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

## [1.1.1] - 2026-11-12

### Fixed
- Resolved `UnboundLocalError` in `_resolve_raid_clash()` caused by referencing `conquering_guild` prior to dictionary lookup, which silently aborted raid resolution on impact.
- Prevented occupied native citizens from being conscripted into defending `Wasteland Raiders` garrisons or recruited into marauder warbands.

## [1.1.0] - 2026-11-11
### Added
- **Wasteland Raider Combat Asymmetry:** Scaled combat power by 0.70x to reflect malnutrition and lack of militia discipline.
- **Pyrrhic Attrition Mechanics:** Added 15 HP combat wear on successful sacks and increased repelled assault damage from 30 to 45 HP.
- **Sterility Mating Block:** Enforced bidirectional reproduction guards in `_resolve_mating` preventing sterile agents from initiating or receiving mating proposals.

### Changed
- **Database Loader Persistence:** Explicitly reconstructed `agent.is_sterile` from SQLite rows in `database.py`.
- **API Serializer Fix:** Fixed variable generator binding for `is_sterile` attribute in `/api/sim/state`.
