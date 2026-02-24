# Briefsmith

**Briefsmith** is a multi-agent workflow automator. It uses [LangGraph](https://github.com/langchain-ai/langgraph) for orchestration, exposes a [Typer](https://typer.tiangolo.com/) CLI, and provides a minimal [FastAPI](https://fastapi.tiangolo.com/) web API.

## Requirements

- Python 3.11+

## Setup

1. **Clone and enter the repo** (if not already):

   ```bash
   cd briefsmith-ai
   ```

2. **Create a virtual environment** (recommended):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\Scripts\activate
   ```

3. **Install the package** (editable, with dev dependencies for tests and linting):

   ```bash
   pip install -e ".[dev]"
   ```

   Or with **uv**:

   ```bash
   uv pip install -e ".[dev]"
   ```

4. **Copy environment template** (never commit real secrets):

   ```bash
   cp .env.example .env
   # Edit .env and add any required keys or settings.
   ```

## CLI usage

The CLI is available as the `briefsmith` command after install.

**Hello world:**

```bash
briefsmith hello
```

Output:

```
Hello world!
```

**Help:**

```bash
briefsmith --help
briefsmith hello --help
```

## Running the API

Start the FastAPI server with Uvicorn:

```bash
uvicorn briefsmith.api:app --reload
```

- API base: **http://127.0.0.1:8000**
- Health check: **GET http://127.0.0.1:8000/health** → `{"status":"ok"}`
- Interactive docs: **http://127.0.0.1:8000/docs**

## Development

- **Run tests:** `pytest`
- **Lint:** `ruff check src tests`
- **Format:** `black src tests`

## License

MIT. See [LICENSE](LICENSE).
