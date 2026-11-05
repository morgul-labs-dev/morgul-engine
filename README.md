# Morgul Engine

A self-hosted, tick-based multi-agent simulation framework written in Python with persistent SQLite Write-Ahead Logging (WAL) and automated LLM chronicle distillation.

[![PyPI version](https://img.shields.io/pypi/v/morgul-engine.svg)](https://pypi.org/project/morgul-engine/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL_3.0-blue.svg)](LICENSE)

- **Live Observer Demo (Morgul Engine Pro):** https://pangaea.morgul-labs.com (runs our extended engine with interactive Atlas, factions, and divine interventions; the open-core engine in this repository is the headless simulation foundation)
- **Studio & Commercial Licenses:** https://morgul-labs.com

---

## Architectural Overview

- **Deterministic Tick Orchestration:** Agents advance through structured hourly state transitions covering circadian sleep/energy restoration, metabolic foraging, and natural demographic cycles.
- **SQLite in WAL Mode:** Concurrent, non-blocking snapshot reads across observation workers while the primary simulation engine executes atomic state updates.
- **Narrative Chronicle Pipeline:** Automated daily chronicle chapters generated using local LLMs (Ollama/vLLM) or remote OpenAI-compatible endpoints, backed by an offline procedural synthesis engine when no model is attached.
- **Decoupled REST API:** Lightweight FastAPI service delivering real-time world state snapshots and historical annals.

## Quickstart

```bash
git clone https://github.com/morgul-labs-dev/morgul-engine.git
cd morgul-engine
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 init_sim.py
python3 run_sim.py
```

## Editions & Licensing

- **Open Source Core (AGPL-3.0):** The simulation engine, SQLite WAL persistence layer, and REST API are open-source under the GNU Affero General Public License v3.0. Any network-hosted derivatives or modifications must be released under AGPL-3.0.
- **Commercial Pro Edition:** Includes the complete React Pangaea Atlas visual dashboard, turnkey multi-container Docker compose orchestration, and a proprietary commercial license grant waiving copyleft disclosure for games, SaaS, and private client deployments. Available at https://morgul-labs.com.
