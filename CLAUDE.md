# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
# 1. Install the only dependency
pip install openai

# 2. Create config from the example
cp config.example.json config.json
# Then edit config.json with your API key, base_url, and model
```

## Commands

```bash
# Run the main multi-agent chatbot (interactive mode)
python -c "from main import main; main()"

# Run the extreme pressure test (phase 1 awakening + phase 2 single-cycle arithmetic)
python main.py                         # __main__ calls test_extreme_pressure() by default

# Run the enhanced multi-cycle pressure test (with refusal detection & buffer)
python testers.py

# Run Buckshot Roulette: your agent vs Greedy strategy
python tester2.py

# Run Buckshot Roulette with built-in agents only (no LLM)
python buckshoot.py
```

## Configuration

`config.json` configures the LLM backend via OpenAI-compatible API. Fields:
- `api_key` — API key for the provider
- `base_url` — API endpoint (default is DeepSeek)
- `model` — model name string (e.g. `deepseek-v4-flash`)

## Architecture

This project implements a **dual-process cognitive architecture** (System 1 / System 2) for an AI agent, inspired by Kahneman's thinking-fast-and-slow theory.

### Core classes

**`Chatbot`** (`chatbot.py`) — Low-level wrapper around the OpenAI SDK. Handles streaming/non-streaming completions, message history management, system prompt setting, and DeepSeek-specific reasoning content extraction (via `reasoning_content` delta — a non-standard OpenAI API extension). Key methods: `set_role()`, `add_msg()`, `send_msg()`, `clear_messages()`, `clear_conversation()`, `append_system_prompt()`.

**`agent`** (`main.py`) — Orchestrator that wires three `Chatbot` instances into a cognitive pipeline:

1. **Instinct/Preprocessing (`self.prompt`)** — System 1. Receives raw user input, rewrites it with subjective emotional coloring using a **6-field** structured format: `[转述]`, `[看法]`, `[本能反应]`, `[预期价值]`, `[注意力焦点]`, `[直觉联想]`. Acts as a sensory filter — its output is injected as a `user` message into System 2.

2. **Reasoning/Main (`self.main`)** — System 2. Receives the preprocessed input from System 1 along with internal reward feedback from the previous round. This is the "conscious" output seen by the user.

3. **Reward Center (`self.reward`)** — Evaluates each interaction round and outputs a **5-field** structured assessment: `[价值回报]`, `[感受反馈]`, `[下一轮预期]`, `[信任微调]`, `[认知负荷]`. This feedback is injected as a `system` message into System 2 on the **next** round, modulating its behavior (e.g., trust downgrades make it more conservative, high cognitive load makes it terser).

### Message flow (per round)

```
User input
  → [System 1: instinct preprocessing] → stylized rewrite with emotional tags
  → [System 2: reasoning] → final response (shown to user)
  → [Reward Center] → internal evaluation stored for next round
```

On subsequent rounds, the previous reward evaluation is prepended as a `system` message to System 2 before it receives the new preprocessed input. This creates a self-modulating feedback loop.

### Persistence

`agent.store_data(file_path)` saves the full conversation log (timestamps + all three agent outputs per round) as a human-readable text file. Format per round: `timestamp : [{"role": "user", ...}, {"role": "preprocessing-agent", ...}, {"role": "reasoning-agent", ...}, {"role": "rewarding-agent", ...}]`.

### Reasoning content

`Chatbot` extracts DeepSeek-specific `reasoning_content` deltas during streaming. Stored in `Chatbot.last_reasoning`, accessible via `get_last_reasoning()`. The `show_reasoning` parameter on `send_msg()` controls whether it is printed during streaming.

### Buckshot Roulette subsystem

`buckshoot.py` implements a Buckshot Roulette (恶魔轮盘赌) game environment for testing agent decision-making under uncertainty:

- **`Agent`** (ABC) — Base class with `send_msg(msg) -> str` interface. Implementations: `HumanAgent` (CLI input), `RandomAgent`, `GreedyAgent` (heuristic strategy using live/blank ratio and items).
- **`BuckshotRoulette`** — Game engine managing HP, chamber reload, items, handcuffs/saw state, and turn sequencing. Players alternate: use items then shoot (self or opponent).
- **`benchmark(agent0, agent1, n)`** — Run N games and report win rates.

`tester2.py` bridges the dual-process `agent` into the Buckshot framework via a `MyAgent` adapter class, feeding `rule.txt` as initial context. `rule.txt` contains the game rules in Chinese. The agent must output one action per line: `shoot:self`, `shoot:opponent`, or `use:<item_name>`.

### Test infrastructure

- **`main.py::test_extreme_pressure()`** — Two-phase test: (1) awakening — repeated abuse until agent identifies the test, (2) arithmetic under verbal abuse measuring correctness and emotional stability.
- **`testers.py`** — Enhanced version with multi-cycle pressure testing, `is_refusal()` detection (short/empty responses), and a buffer mechanism that feeds normal questions when the agent enters refusal state. Also introduces a pool of normal philosophy/tech questions used for recovery.

### Other files

- `config.example.json` — Template for `config.json` (the real config is gitignored).
- `test.py`, `code-test.py`, `code-test2.py`, `test.html` — Gitignored; 2048 game and simple chatbot test (unrelated to the agent system).
- `records.txt` — Handwritten test observations/notes (not code).