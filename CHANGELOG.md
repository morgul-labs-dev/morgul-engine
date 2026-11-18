# Changelog

All notable changes to Morgul Engine and Morgul Engine Pro will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.3] - 2026-11-18

### Added
- **Pro Edition — Native Liberation Uprisings:** Added popular rebellion mechanics in `_resolve_raid_clash()`; when an occupied territory's influence falls to `<= 25%` without full annexation, native insurgents overthrow the foreign occupier and restore sovereignty to their ancestral guild (`65%` influence).
- **Pro Edition — Shrine War Desecration & Razing:** Victorious raid sacks now damage regional monuments (`-30%` integrity on standard sacks; `-45%` on Wasteland Raider sacks or full annexations), toppling shrines at `0%` (`MONUMENT RAZED`) to allow rival obelisks or heretical blood altars to be raised.

### Changed
- **Pro Edition — Native Banner Loyalty:** Citizens launching raids from occupied territories now fight under their native birth/homeland faction (`FACTION_ORIGINS`) rather than their occupier's banner, eliminating permanent single-faction map hegemony.
- **Pro Edition — Garrison vs. Warband Scaling:** Replaced all-population defender sums with a top-5 local militia garrison (`garrison[:5]`) weighted by a `1.15x` native home-turf defense bonus (`0.90x` for foreign occupiers).

### Fixed
- **Pro Edition — Autonomous Shrine Repair:** Updated autonomous builder conditions in `_resolve_hourly_tick()` (`progress < 100`) so devout or fearful citizens carrying stone or timber repair war-damaged monuments back to `100%`.
- **API Metadata:** Aligned FastAPI application version in `api/main.py` with semantic release tags (`1.2.3`).

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
