# AI_ML

A collection of small, hands-on projects for learning agentic AI. Each project is built around one or more of the core concepts listed below, lives in its own folder, and can be run independently.

## Agentic AI 

An AI agent is a system that uses a model to decide what to do next, takes actions through tools, observes the results, and repeats until the goal is met. The small projects in this repo are based on the concepts below; the last column shows where each one is practised.

### Foundations

| Concept | What it means | Practised in |
| --- | --- | --- |
| Agent loop | Perceive → reason → act → observe, repeated until the task is done | SupportDesk |
| LLM as reasoning engine | The model chooses the next step instead of following hard-coded logic | SupportDesk |
| System prompt and role | Instructions that set the agent's job, policy and limits | SupportDesk |
| Tool use (function calling) | The model calls external functions or APIs to get data and take actions | SupportDesk, Carfinder |
| Tool schemas | Typed descriptions of each tool so the model knows when and how to call it | SupportDesk |
| Structured outputs | Machine-readable results (JSON) passed between tools, model and code | SupportDesk, Carfinder |
| Autonomy levels | How much the agent may do alone versus what needs approval | SupportDesk |

### Reasoning and planning

| Concept | What it means | Practised in |
| --- | --- | --- |
| ReAct | Interleaving reasoning with actions and observations | SupportDesk |
| Planning and task decomposition | Breaking a goal into ordered sub-tasks before acting | Planned |
| Reflection (self-critique) | The agent reviews its own output and improves it | Planned |
| Chain-of-thought | Step-by-step reasoning before giving an answer | Planned |

### Workflow patterns

| Concept | What it means | Practised in |
| --- | --- | --- |
| Prompt chaining | A fixed sequence of steps, each feeding the next | Carfinder (fetch → normalise → filter → export) |
| Routing | Classifying a request and sending it down the right path | SupportDesk (restart vs. escalate vs. no action) |
| Parallelisation | Running independent sub-tasks at the same time and merging results | Planned |
| Orchestrator-workers | A lead agent delegates sub-tasks to worker agents | Planned |
| Evaluator-optimiser | One model generates, another critiques, looping until good enough | Planned |

### Memory and knowledge

| Concept | What it means | Practised in |
| --- | --- | --- |
| Short-term memory | Conversation and tool results kept in the context window | SupportDesk |
| Long-term memory | Facts stored outside the model and recalled across sessions | Planned |
| Retrieval-augmented generation (RAG) | Grounding answers in retrieved documents | SupportDeskRAG (planned) |
| Embeddings and vector search | Finding relevant text by semantic similarity | SupportDeskRAG (planned) |
| Agentic RAG | The agent decides when, what and how often to retrieve | SupportDeskRAG (planned) |
| Context engineering | Choosing what goes into the context window and what stays out | Planned |

### Multi-agent systems

| Concept | What it means | Practised in |
| --- | --- | --- |
| Specialised agents | Several agents, each with its own role and tools | Planned |
| Handoffs | One agent passes control and context to another | Planned |
| Supervisor / hierarchical teams | A manager agent coordinates the others | Planned |
| Model Context Protocol (MCP) | A standard way to connect agents to tools and data sources | Planned |

### Safety, reliability and operations

| Concept | What it means | Practised in |
| --- | --- | --- |
| Human-in-the-loop | A person approves or takes over at key points | SupportDesk (escalation), Carfinder (confirm before a paid run) |
| Guardrails | Checks that block unsafe or unwanted actions | Carfinder (local-only server, request checks) |
| Error handling and fallbacks | Continuing sensibly when a tool or source fails | Carfinder (keeps going if one source fails) |
| Cost and latency control | Limiting calls, tokens and spend per run | Carfinder (`--max-per-source`) |
| Evaluation | Testing agent behaviour against known scenarios | SupportDesk (five test scenarios) |
| Observability and tracing | Logging each step so runs can be inspected and debugged | SupportDesk (tool-call prints) |
| Simulated environments | Mock tools and data for safe testing | SupportDesk |

Concepts marked "Planned" don't have a project yet; new small projects will be added to cover them.

## Carfinder

A dealer car-listing agent. It pulls new and certified pre-owned listings from AutoTrader and CarGurus through Apify actors, filters them by budget, model year and distance, merges duplicates by VIN, and writes the results to a CSV file and a filterable HTML page.

```bash
cd Carfinder
export APIFY_TOKEN=apify_api_xxx

python3 car_finder.py                                        # defaults: $40,000, ZIP 95113, 100 mi, 2023-2027
python3 car_finder.py --budget 25000 --zip 94538 --radius 50
python3 car_finder.py --serve                                # local page with a "Run" button to refresh data
```

- No third-party packages: Python 3 standard library only.
- Outputs `cars.csv` and `cars.html`; a sample of each is checked in.
- Each run uses Apify credit, which scales with `--max-per-source`.

See the [Carfinder README](Carfinder/README.md) for the full feature list and options.

## SupportDesk

A notebook ([`Assignment_solution.ipynb`](SupportDesk/Assignment_solution.ipynb)) that builds an AI agent acting as the first responder for server incidents. Given a user's report, the agent decides which tools to call and in what order:

| Tool | Purpose |
| --- | --- |
| `get_server_health` | Check CPU and memory usage for a server |
| `fetch_recent_logs` | Read the latest log lines to diagnose the issue |
| `restart_service` | Restart a service when CPU or memory is critical (>90%) |
| `escalate_to_engineer` | Hand off to a human when a restart won't fix it (e.g. a dependency failure) |

The notebook is organised in four parts: tool implementations, the function-calling schema, the agent execution loop, and test scenarios covering a high-CPU restart, a memory-leak restart, a dependency-failure escalation, and healthy servers that need no action. The server metrics and logs are simulated, so no real infrastructure is touched.

**To run it:**

1. Open the notebook in Google Colab.
2. Add an OpenRouter API key as a Colab secret named `OPENROUTER_APIKEY` and enable notebook access.
3. Run all cells. The notebook uses the `openai` SDK pointed at OpenRouter's `base_url`.

## SupportDeskRAG

Placeholder for a retrieval-augmented version of the support desk agent. Nothing has been added yet.

## Repository layout

```
AI_ML/
├── Carfinder/
│   ├── car_finder.py              # the agent and local web server
│   ├── cars.csv                   # sample output
│   ├── cars.html                  # sample output
│   └── README.md
├── SupportDesk/
│   └── Assignment_solution.ipynb  # IT support agent notebook
├── SupportDeskRAG/                # planned
└── README.md
```

## Requirements

- Python 3
- **Carfinder:** an [Apify](https://apify.com/) API token
- **SupportDesk:** an [OpenRouter](https://openrouter.ai/) API key and the `openai` Python package

Keep API keys in environment variables or Colab secrets; never commit them.

## Author

Juthika Dash — [@juthikaDash](https://github.com/juthikaDash) 
