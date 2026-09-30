# ai-cli

A polished command-line AI chatbot in Python, powered by the [OpenRouter](https://openrouter.ai/) API through the OpenAI Python SDK.

Chat with hundreds of models from your terminal — with streaming Markdown responses, Tab-completed model switching, a live model catalog, and conversation export.

```text
╭─────────────────────────────── Welcome ───────────────────────────────╮
│ ai-cli v0.2.0 — OpenRouter chat                                       │
│ Model: nvidia/nemotron-3-super-120b-a12b:free                         │
│ 464 models (20 free) loaded. Press Tab after /model for suggestions.  │
│ Enter sends · Alt+Enter newline · Ctrl+D exits · /help for commands   │
╰───────────────────────────────────────────────────────────────────────╯
```

## ✨ Features

| Area | What you get |
|------|--------------|
| 💬 Chat | Continuous conversation with streaming responses, rendered as Markdown |
| 🤖 Models | Live OpenRouter catalog (400+ models) with free/paid labels |
| ⌨️ Input | Tab autocomplete, persistent history, multiline (Enter sends, Alt+Enter newline) |
| 🎨 Interface | Welcome banner, status bar, spinners, styled tables and error panels |
| 💾 Export | `/save` exports the session to a Markdown file |
| ⚙️ Config | API key, default model, and persona via `.env`; `--model` / `--no-markdown` flags |

### Slash commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/model` | Show the current model |
| `/model <name>` | Switch models — Tab completes, fuzzy search, or pick by number |
| `/models [query] [--free]` | Browse/search the live OpenRouter catalog |
| `/models --refresh` | Re-fetch the catalog |
| `/md` | Toggle Markdown rendering on/off |
| `/clear` | Reset conversation history (keeps system prompt) |
| `/save [file]` | Export conversation to Markdown (system prompt excluded) |
| `/exit` | Quit |

## 📋 Requirements

* Python 3.9 or newer
* An [OpenRouter API key](https://openrouter.ai/keys)
* Internet connection

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/slawti/ai-cli.git
cd ai-cli
```

### 2. Create a virtual environment (recommended)

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the app

```bash
pip install -e .
```

This installs all dependencies and the `ai-cli` command.

## 🔧 Configuration

Create a `.env` file in the project root:

```env
OPENROUTER_API_KEY=your_api_key_here
MODEL=nvidia/nemotron-3-super-120b-a12b:free
SYSTEM_PROMPT=You are a helpful assistant.
```

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | ✅ | Your OpenRouter API key |
| `MODEL` | ❌ | Default model (any slug from [OpenRouter Models](https://openrouter.ai/models)) |
| `SYSTEM_PROMPT` | ❌ | Persona/instructions sent as a `system` message; preserved across `/clear` |

> **🔒 Security:** never commit `.env` — it's already in `.gitignore`. If a key leaks, revoke it immediately at [openrouter.ai/keys](https://openrouter.ai/keys).

## 🖥️ Usage

```bash
ai-cli
```

With options:

```bash
ai-cli --model openai/gpt-4o-mini   # start with a specific model
ai-cli --no-markdown                # plain-text streaming instead of Markdown
ai-cli --help                       # show all options
```

> Alternatives: `python -m ai_cli`, or the legacy `python main.py`.

### Example session

```text
You: What is Linux?

AI: **Linux** is an open-source operating system kernel...
    (streams live, rendered as Markdown with highlighted code blocks)

You: /model gpt<Tab>
  → openai/gpt-4o-mini [free] ...

You: /models llama --free
  → table of matching free models; pick with /model 2

You: /save mychat
Conversation saved to mychat.md

You: /exit
Goodbye!
```

### ⌨️ Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Alt` + `Enter` | New line (multiline input) |
| `Tab` | Autocomplete commands and model names |
| `↑` / `↓` | Recall input history (persists in `~/.ai_cli_history`) |
| `Ctrl` + `C` | Interrupt current generation |
| `Ctrl` + `D` | Exit |

## 🏗️ Project structure

```text
ai-cli/
├── ai_cli/               # application package
│   ├── cli.py            # entry point, main loop, command dispatch
│   ├── config.py         # .env loading, settings, --model/--no-markdown flags
│   ├── models.py         # OpenRouter catalog fetch, free-filter, search
│   ├── chat.py           # API client, Markdown streaming, conversation export
│   ├── ui.py             # banner, status bar, tables, spinners, error panels
│   └── complete.py       # Tab completion for commands and model ids
├── main.py               # backwards-compatible shim (use `ai-cli` instead)
├── pyproject.toml        # packaging, dependencies, ai-cli console script
├── requirements.txt      # pinned dev/venv install (alternative to pip install -e .)
├── README.md
├── LICENSE
└── .env                  # local only — never committed
```

## ⚙️ How it works

**Client** — the [OpenAI Python SDK](https://github.com/openai/openai-python) pointed at OpenRouter's OpenAI-compatible endpoint:

```python
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)
```

**Catalog** — `GET https://openrouter.ai/api/v1/models` (public, no auth) fetched fresh each session; a model counts as free when prompt + completion pricing are `0` or the id ends with `:free`.

**Streaming** — responses use `stream=True`; chunks render live into Markdown (with a `thinking…` spinner until the first token), then the full turn is appended to history so context carries forward. `--no-markdown` or `/md` switches to plain-text streaming.

## 📦 Dependencies

* [OpenAI Python SDK](https://github.com/openai/openai-python) — API client
* [python-dotenv](https://github.com/theskumar/python-dotenv) — `.env` loading
* [Rich](https://github.com/Textualize/rich) — colors, tables, panels, Markdown, spinners
* [prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) — Tab completion, history, multiline input

## 🧭 Limitations & roadmap

Current limitations:

* Single active conversation, kept in memory (export with `/save`)
* No graphical interface
* Long conversations are sent in full (no automatic summarization/truncation yet)

Ideas for the future:

* [ ] Load conversations back from Markdown
* [ ] Multiple named sessions
* [ ] Token/cost tracking per session
* [ ] Per-model parameters (temperature, max tokens)
* [ ] Shell completion scripts for `ai-cli`

PRs and issues welcome at [github.com/slawti/ai-cli](https://github.com/slawti/ai-cli).

## 📄 License

MIT — see [LICENSE](LICENSE).

## ⚠️ Disclaimer

Independent client for the OpenRouter API. Not affiliated with OpenRouter or any model provider.
