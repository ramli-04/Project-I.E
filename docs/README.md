# Project documentation

Use the repository root for the commands in these documents.

| Document | Purpose |
| --- | --- |
| [French user guide](GUIDE_UTILISATEUR.md) | Short instructions for each role |
| [Demo guide](../DEMO_GUIDE.md) | Setup, credentials and complete presenter walkthrough |
| [Installation and transfer](INSTALLATION.md) | Native environment, PostgreSQL/private-file transfer and deployment boundaries |
| [Production planning](PLANNING.md) | Scheduling, technician/machine phases, commands and database constraints |
| [Generated workflow diagrams](WORKFLOW.md) | Current physical/digital route families and explicit exception commands |
| [BPMN coverage matrix](BPMN_COVERAGE.md) | Every process element and gateway outcome, code/test evidence, manual-demo limits and unresolved differences |
| [Inventory workflow](INVENTORY_WORKFLOW.md) | Immutable stock movements, measured rework and loss analytics |
| [Billing analytics](BILLING_ANALYTICS.md) | Financial catalogs and refresh pipeline |
| [v1.0 product decisions](DECISIONS_V1.md) | Approved D1-D8, delivery steps and deferred v2 scope |
| [Light simulator design](SIMULATION_DESIGN.md) | Architecture, isolation, measured scope and deferred Phase 9 |
| [Clock audit](SIMULATION_CLOCK_AUDIT.md) | Time sources, virtual-clock handling and limitations |
| [Test results](TEST_RESULTS.md) | Canonical verification evidence, dates and limits |
| [Roadmap](ROADMAP.md) | Completed capabilities and remaining engineering work |
| [Graphify](GRAPHIFY.md) | Isolated graph setup and code exploration |

The root [README](../README.md) describes the application and development entrypoints. An optional ignored `memory.md` records a machine-local checkpoint and is not included in the demo handoff. Superseded handoff snapshots and duplicate test reports have been removed.

## Contributor review

1. Inspect `git status --short` and `git diff --check`. Include new source modules, migrations, tests, demo assets and documentation in the reviewed change.
2. Follow the verification commands in the demo guide. Use the separate verification Compose project for real browser tests when the main demo has occupied resources.
3. Compare results with the dated test report; older backend results are not a claim that a new full suite was run.
4. Keep `.env`, local database settings, `.runtime`, databases, private uploads, installed dependencies and generated builds excluded. Source checkout alone does not transfer existing accounts or clinical records.
5. Review migration0025 and runtime configuration before applying this source to an existing native installation. The synthetic environment and native PostgreSQL are separate.

The supported entrypoints are Docker Compose for the full synthetic demo and `manage.py` plus Vite for native development. The obsolete portable Windows EXE packaging path has been removed.
