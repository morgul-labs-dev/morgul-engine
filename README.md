# Morgul Engine

A self-hosted, tick-based multi-agent living world simulation framework written in Python with persistent SQLite Write-Ahead Logging (WAL) and zero mandatory token costs.

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL_3.0-blue.svg)](LICENSE)

- **Live Observer Demo (Pangaea):** https://pangaea.morgul-labs.com (runs continuous multi-agent simulation with interactive React Atlas, factions, and divine interventions)
- **Commercial Packages & Licensing:** https://morgul-labs.com

---

## Architectural Overview

- **Stochastic State Machine Simulation:** Agents autonomously advance through structured hourly state transitions covering biological foraging, resting, labor, kinship, migration, caravan trade routes, and territorial raids. Operates entirely without LMMs at $0 token cost.
- **SQLite in WAL Mode:** Concurrent, non-blocking snapshot reads across observation workers while the primary simulation engine executes atomic state transactions.
- **Narrative Chronicle & Dialogue Pipeline:** Automated daily chronicle chapters generated using local Ollama (`llama3.2:3b`) or any standard OpenAI-compatible `/v1` endpoint. Ambient dialogue and whispers activate only when interacted with; if the model is offline, the simulation continues ticking uninterrupted.
- **Decoupled REST API:** Lightweight FastAPI service delivering real-time world state snapshots, historical annals, and agent inspections.

## Quickstart

gfit clone https://github.com/morgul-labs-dev/morgul-engine.git
cd morgul-engine
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Optional: To connect local Ollama or an OpenAI-compatible endpoint:
OPENAI_API_KEY=ollama          # any value except mock_key
OPENAI_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.2:3b          # or your preferred local model

# initialize database and execute simulation
python3 init_sim.py
python3 run_sim.py

## Editions & Licensing Matrix

Morgul Engine follows an open-core commercial model. The headless Python core is open-source under AGPLL-3.0. For commercial games, SaaS products, client deliverables, or teams needing the real-time visual observer dashboard, commercial editions are available:

| Capability / Rights | Open Core (AGPL-3.0) | Developer Edition ($79) | Studio Commercial ($299) |
| :--- | :---: |:---: |
| **Licensing** | AGPL-3.0 (Copyleft) | Proprietary EULA | **Commercial AGPL Waiver** |
|**Permitted Use** | Open Source / Evaluation | Internal Eval & Prototyping | **Commercial Games, SaaS, Clients** |
| **Developer Seats** | Community | 1 Developer | **Up to 5 Developers** |
| **Headless Python Core** | Included | Included | Included |
| **Hourly Simulation Loop** | Included | Included | Included |
| **Atlas React Dashboard** | — | **Included** | **Included** |
| **Divine Intervention Console** | — | **Included** | **Included** |
| **Docker Compose Stack** | — | **Included** | **Included** |
| **Procedural Annals Engine** | Included | Included | Included |
| **Source-Disclosure Exemption** | — | — | **Included (Proprietary Safe)** |
| **Updates & Support** | Public GitHub Issues | 12 Months Updates | 12 Months Priority Support |

Learn more and obtain commercial licenses at [morgul-labs.com](https://morgul-labs.com).

## Contributing & License

The core simulation engine in this repository is licensed under the [GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE).p Clease review [CONTRIBUTING.md](CONTRIBUTING.md) and sign the [CLA](CLA.md) before submitting pull requests. For commercial closed-source licensing options, visit [morgul-labs.com](https://morgul-labs.com).
