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

* Python 3.10 or newer (`python --version`)
* An [OpenRouter API key](https://openrouter.ai/keys) — you'll paste it on first run
* Internet connection

## 🚀 Installation

No virtual environment, no config files — install once, run from anywhere.

### Option 1: pipx (recommended — isolated, `ai-cli` always on PATH)

```powershell
pip install pipx
pipx ensurepath
# restart your terminal, then:
pipx install git+https://github.com/slawti/ai-cli.git
```

### Option 2: plain pip (no new tools)

```powershell
pip install --user git+https://github.com/slawti/ai-cli.git
```

> If `ai-cli` isn't recognized afterwards, add Python's `Scripts` folder to PATH (the python.org installer offers this checkbox; with `pipx`, `ensurepath` handles it).

Then:

```powershell
ai-cli
```

On first run you'll be asked for your OpenRouter API key **once** — it's saved to `~/.ai-cli/.env` and never asked again.

Update later with `pipx upgrade ai-cli` (or `pip install --user --upgrade git+https://github.com/slawti/ai-cli.git`).

### From source (contributors only)

```powershell
git clone https://github.com/slawti/ai-cli.git
cd ai-cli
pip install -e .
```

## 🔧 Configuration

No manual setup needed: the first-run prompt stores your key in `~/.ai-cli/.env` (outside the repo, so it works from any folder and is never committed).

| Source | Precedence | Description |
|--------|------------|-------------|
| `--api-key KEY` | 🥇 | Key for this run only (scripts, CI) |
| `OPENROUTER_API_KEY` env var | 🥈 | Shell export / system environment |
| project `.env` | 🥉 | `OPENROUTER_API_KEY=…` in the current folder (dev override) |
| `~/.ai-cli/.env` | 4th | Written by the first-run prompt; may also hold `MODEL` / `SYSTEM_PROMPT` defaults |

To change the saved key later: delete `~/.ai-cli/.env` and re-run `ai-cli`, or set the env var.

> **🔒 Security:** never commit any file holding your key — project `.env` files are already in `.gitignore`, and `~/.ai-cli/` lives outside the repo. If a key leaks, revoke it immediately at [openrouter.ai/keys](https://openrouter.ai/keys).

## 🖥️ Usage

```bash
ai-cli
```

With options:

```bash
ai-cli --model openai/gpt-4o-mini   # start with a specific model
ai-cli --api-key sk-or-...           # one-off key (not saved)
ai-cli --no-markdown                # plain-text streaming instead of Markdown
ai-cli --no-tui                     # legacy inline prompt instead of fullscreen TUI
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
│   ├── tui.py            # fullscreen Textual TUI (default UI)
│   ├── config.py         # settings, first-run key prompt, --model/--api-key/--no-tui flags
│   ├── models.py         # OpenRouter catalog fetch, free-filter, search
│   ├── chat.py           # API client, Markdown streaming, conversation export
│   ├── ui.py             # legacy Rich output + toolbar (--no-tui)
│   └── complete.py       # Tab completion for commands and model ids
├── main.py               # backwards-compatible shim (use `ai-cli` instead)
├── pyproject.toml        # packaging, dependencies, ai-cli console script
├── README.md
├── LICENSE
└── .env                  # local dev override only — never committed
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
