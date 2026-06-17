# Vision-Agents

Multi-modal AI agents that watch, listen, and understand video in real-time. Built for low-latency video experiences using Stream's edge network, but compatible with any video edge network.

## Project Overview

Vision-Agents is a Python monorepo framework for building intelligent video AI. It provides building blocks to combine real-time video processing (YOLO, Roboflow) with state-of-the-art LLMs (Gemini Live, OpenAI Realtime, etc.).

- **Core Package:** `agents-core` (contains the `vision_agents` package).
- **Plugins:** Over 37 provider integrations in `plugins/`.
- **Primary Language:** Python 3.12 (managed with `uv`).
- **Network:** WebRTC-based real-time communication.

## Architecture & Key Concepts

### Core Components
- **Agent:** The central orchestrator (`vision_agents.core.agents.Agent`). Manages the lifecycle of a call session, coordinates LLMs, STT, TTS, and processors.
- **LLM / Realtime:** Abstractions for Large Language Models. `Realtime` LLMs handle Speech-to-Speech (STS) flows directly.
- **STT & TTS:** Speech-to-Text and Text-to-Speech plugin interfaces.
- **Processors:** Pluggable video/audio processing pipeline (e.g., `YOLOPoseProcessor`).
- **Edge:** Abstraction for the video network (default is `getstream`).
- **Events:** Asynchronous event system (`EventManager`) for cross-component communication.

### Data Handling
- **Audio (PCM):** Audio MUST be passed around using the `PcmData` container (`getstream.video.rtc.PcmData`). Avoid raw bytes for audio.
- **Video Frames:** Handled via `aiortc.VideoStreamTrack`. Use `frame.to_ndarray(format="rgb24")` for processing.
- **Warmup:** Heavy resources (ML models) should implement the `Warmable` trait for efficient loading and caching.

### Framework Flows
- **Transcribing Flow:** Audio -> STT -> LLM -> TTS -> Audio.
- **Real-time Flow (STS):** Audio/Video -> Realtime LLM -> Audio/Events.

## Building and Running

Managed via `uv`. Always use `uv run` to ensure correct environment.

### Setup
```bash
uv venv --python 3.12.11
uv sync --all-extras --dev
cp env.example .env
pre-commit install
```

### Key Commands
- **Full Check:** `uv run python dev.py check` (Lints, validates deps, type checks, and runs unit tests).
- **Run Example:** `uv run examples/01_simple_agent_example/simple_agent_example.py run`
- **Format & Lint:** `uv run ruff format .` and `uv run ruff check --fix .`
- **Type Check:** `uv run mypy`

## Testing Strategy

Uses `pytest` with `asyncio_mode = auto`.

- **Unit Tests:** `uv run pytest -m "not integration"`
- **Integration Tests:** `uv run pytest -m "integration"` (Requires `.env` secrets).
- **Behavior-Driven:** Assert on outputs and state, avoid mocking internals or checking calling paths.
- **Structure:** Keep unit tests for a class inside the same test class (e.g., `TestAgent`).
- **Fixtures:** Use `pytest.fixture` for setup, not helper methods.

## Development Conventions

### Python Style
- **Python 3.12+:** Use modern syntax (e.g., `X | Y` for unions, `dict[str, T]` for generics).
- **No Annotations Import:** Do NOT use `from __future__ import annotations`.
- **Typing:** Use type hints everywhere. Avoid `Any` and `# type: ignore`.
- **Naming:** `snake_case` for functions/vars, `PascalCase` for classes, `_leading_underscore` for private members.
- **Logging:** Module-level `logger = logging.getLogger(__name__)`. Use `logger.exception()` for tracebacks. Guard hot-path debug logs with `if logger.isEnabledFor(logging.DEBUG):`.

### Plugin Rules
- **Light Wrapping:** Plugins should wrap underlying SDKs minimally.
- **Packaging:** In `pyproject.toml`, ensure `packages = ["vision_agents"]` for the wheel target.
- **Documentation:** Every plugin MUST have a `README.md`.

### Async & Lifecycle
- **Async-First:** Use `start`/`stop` lifecycle methods.
- **Resource Management:** Use `__aenter__`/`__aexit__` and `finally` blocks for cleanup.
- **Concurrency:** Use `asyncio.Lock`, `asyncio.Task`, and `asyncio.gather`.

## Key Files & Directories

- `agents-core/`: Core framework source code.
- `plugins/`: Integration packages (Anthropic, Gemini, OpenAI, etc.).
- `examples/`: Standalone application examples.
- `tests/`: Global test suite and shared assets.
- `dev.py`: Primary development CLI tool.
- `AGENTS.md`: Repository guidelines and module organization.
- `CLAUDE.md`: Detailed coding rules, testing philosophy, and style guide.
- `DEVELOPMENT.md`: Onboarding and contributor instructions.
