# Morgul Engine

A self-hosted, tick-based multi-agent simulation framework written in Python with persistent SQLite Write-Ahead Logging (WAL) and automated LLM chronicle distillation.

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
cp .env.example .env

# To use Ollama or a local endpoint, edit .env:
OPENAI_API_KEY=ollama   # any value except mock_key
OPENAI_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3        # or your preferred local model

# Set ENV=development in .env to enable POST /api/tick for local testing.
python3 init_sim.py
python3 run_sim.py
```

## Editions & Licensing

- **Open Source Core (AGPL-3.0):** The simulation engine, SQLite WAL persistence layer, and REST API are open-source under the GNU Affero General Public License v3.0. Any network-hosted derivatives or modifications must be released under AGPL-3.0.
- **Commercial Pro Edition:** Includes the extended simulation engine (factions, caravans, raids, divine interventions), the complete React Pangaea Atlas visual dashboard, turnkey Docker compose orchestration, and proprietary licensing options. Available at https://morgul-labs.com.

## Editions & Licensing Matrix

| Feature | Open Engine (AGPL-3.0) | Developer ($79) | Studio ($299) |
| :--- | :---: | :---: | :---: |
| Headless Deterministic Tick Simulation | Yes | Yes | Yes |
| Circadian Biology & Demographic Equilibrium | Yes | Yes | Yes |
| SQLite WAL Concurrency & Daily Chronicles | Yes | Yes | Yes |
| Extended Simulation Engine (Factions, Caravans, Raids) | - | Yes | Yes |
| React Pangaea Atlas Visual Dashboard | - | Yes | Yes |
| Real-Time Divine Intervention & Dialogue API | - | Yes | Yes |
| Turnkey Production Docker & Deployment Suite | - | Yes | Yes |
| Permitted Usage Scope | Any use under AGPL-3.0 terms | Internal / Non-Commercial | Commercial (Up to 5 Devs) |
| Proprietary Closed-Source Exemption | - | - | Included |

Learn more about licensing at [morgul-labs.com](https://morgul-labs.com).

## Contributing & License

Morgul Engine is licensed under [AGPL-3.0](LICENSE). Please review [CONTRIBUTING.md](CONTRIBUTING.md) and sign the [CLA](CLA.md) before submitting pull requests.
