# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the main multi-agent chatbot
python main.py

# Run the simple single-agent chatbot
python test.py

# Run the 2048 CLI game (WASD controls, Q to quit)
python code-test.py          # version with real-time key input (macOS only)
python code-test2.py         # version with Enter-key input

# Run the extreme pressure test (automated abuse + arithmetic test)
python -c "from main import test_extreme_pressure; test_extreme_pressure()"
```

## Configuration

`config.json` configures the LLM backend via OpenAI-compatible API. Fields:
- `api_key` — API key for the provider
- `base_url` — API endpoint (default is DeepSeek)
- `model` — model name string (e.g. `deepseek-v4-flash`)

## Architecture

This project implements a **dual-process cognitive architecture** (System 1 / System 2) for an AI agent, inspired by Kahneman's thinking-fast-and-slow theory.

### Core classes

**`Chatbot`** (`chatbot.py`) — Low-level wrapper around the OpenAI SDK. Handles streaming/non-streaming completions, message history management, system prompt setting, and reasoning content extraction (via `reasoning_content` delta attribute for DeepSeek thinking models).

**`agent`** (`main.py`) — Orchestrator that wires three `Chatbot` instances into a cognitive pipeline:

1. **Instinct/Preprocessing (`self.prompt`)** — System 1. Receives raw user input, rewrites it with subjective emotional coloring using a 5-line structured format: `[转述]`, `[本能反应]`, `[预期价值]`, `[注意力焦点]`, `[直觉联想]`.

2. **Reasoning/Main (`self.main`)** — System 2. Receives the preprocessed input from System 1 along with internal reward feedback from the previous round. This is the "conscious" output seen by the user.

3. **Reward Center (`self.reward`)** — Evaluates each interaction round and outputs a 4-line structured assessment: `[价值回报]`, `[感受反馈]`, `[信任微调]`, `[认知负荷]`. This feedback is injected as a `system` message into System 2 on the **next** round, modulating its behavior (e.g., trust downgrades make it more conservative, high cognitive load makes it terser).

### Message flow (per round)

```
User input
  → [System 1: instinct preprocessing] → stylized rewrite with emotional tags
  → [System 2: reasoning] → final response (shown to user)
  → [Reward Center] → internal evaluation stored for next round
```

On subsequent rounds, the previous reward evaluation is prepended as a `system` message to System 2 before it receives the new preprocessed input. This creates a self-modulating feedback loop.

### Other files

- `test.py` — Minimal single-agent chatbot test (no cognitive pipeline).
- `code-test.py` / `code-test2.py` — Two independent 2048 CLI game implementations (unrelated to the agent system).
- `test.html` — 2048 game in HTML/JS (also unrelated).
