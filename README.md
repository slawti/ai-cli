# AI CLI

A simple command-line AI chatbot written in Python using the [OpenRouter](https://openrouter.ai/) API and the OpenAI Python SDK.

The program allows you to have a continuous conversation with an AI directly from your terminal, with responses streamed progressively as they are generated.

## Features

* Command-line chat interface
* Streaming AI responses
* Conversation history during the current session
* OpenRouter API support
* Configurable API key through environment variables
* `/clear` command to reset the conversation
* `/model` command with Tab autocomplete to view or switch models mid-session
* `/models` browser with free-filter and live OpenRouter catalog
* `/md` toggle and Markdown-rendered streaming responses
* Welcome banner, status bar, and spinners
* Persistent input history and multiline input (Enter sends, Alt+Enter newline)
* `/save` command to export the conversation to Markdown
* `SYSTEM_PROMPT` support for a default persona via `.env`
* `/exit` command to close the application

## Requirements

* Python 3.9 or newer
* An OpenRouter API key
* Internet connection

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/slawti/ai-cli.git
cd ai-cli
```

### 2. Create a virtual environment

Creating a virtual environment is recommended to keep the project's dependencies separate from your other Python projects.

#### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

#### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the app

```bash
pip install -e .
```

This installs dependencies and the `ai-cli` command.

## Configuration

The application uses a `.env` file to store your OpenRouter API key and model configuration.

Create a file named:

```text
.env
```

Add:

```env
OPENROUTER_API_KEY=your_api_key_here
MODEL=nvidia/nemotron-3-super-120b-a12b:free
SYSTEM_PROMPT=You are a helpful assistant.
```

Replace `your_api_key_here` with your actual OpenRouter API key.
The `MODEL` can be any model available on OpenRouter (see [OpenRouter Models](https://openrouter.ai/models)).
The optional `SYSTEM_PROMPT` sets a persona or default instructions. It is sent as a `system` message with every request and is preserved across `/clear`. Omit it or leave it empty for no system prompt.

### Security

**Never commit your `.env` file to GitHub.**

The repository's `.gitignore` should contain:

```gitignore
.env
__pycache__/
*.py[cod]
.venv/
venv/
```

Your API key should remain local to your machine.

If an API key is accidentally pushed to GitHub, revoke it immediately and generate a new one.

## Usage

Start the application with:

```bash
ai-cli
```

Options:

```bash
ai-cli --help
ai-cli --model openai/gpt-4o-mini
ai-cli --no-markdown
```

(`python -m ai_cli` and the legacy `python main.py` still work.)

You should see:

```text
You:
```

Enter a message and the AI will respond.

Example:

```text
You: What is Linux?

AI: Linux is an open-source operating system kernel...
```

Responses are streamed progressively rather than waiting for the entire response to be generated.

## Commands

### `/clear`

Clears the current conversation history.

```text
You: /clear
Conversation cleared.
```

The next message starts a new conversation.

### `/help`

Shows the help message with all available commands.

```text
You: /help
```

### `/model`

Shows the current model, or switches to a different model mid-session. Conversation history is kept.

```text
You: /model
Current model: nvidia/nemotron-3-super-120b-a12b:free

You: /model openai/gpt-4o-mini
Switched model to openai/gpt-4o-mini
```

### `/save`

Exports the current conversation to a Markdown file. The system prompt is excluded.

```text
You: /save
Conversation saved to chat_20260101_120000.md

You: /save mychat
Conversation saved to mychat.md
```

### `/exit`

Closes the application.

```text
You: /exit
Goodbye!
```

## How It Works

The application uses the OpenAI Python SDK with OpenRouter's OpenAI-compatible API.

The client is configured with:

```python
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)
```

The model is currently configured via the `.env` file:

```python
MODEL = os.getenv("MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
```

The conversation is stored in a Python list:

```python
messages = []
```

Each user and assistant message is added to this list and sent to the API with every request.

### Streaming

The application uses:

```python
stream=True
```

Instead of receiving the complete response at once, the API sends the response in chunks.

The program processes these chunks as they arrive:

```python
for chunk in response:
    text = chunk.choices[0].delta.content

    if text:
        print(text, end="", flush=True)
```

This creates a real-time typing effect in the terminal.

The chunks are also combined into a complete response so it can be added to the conversation history.

## Project Structure

```text
ai-cli/
├── main.py
├── requirements.txt
├── README.md
├── .gitignore
└── .env
```

The `.env` file is local and should **not** be committed to the repository.

## Dependencies

The project currently uses:

* [OpenAI Python SDK](https://github.com/openai/openai-python) — API client
* [python-dotenv](https://github.com/theskumar/python-dotenv) — loads environment variables from `.env`
* [Rich](https://github.com/Textualize/rich) — colored terminal output and markdown rendering

Install them with:

```bash
pip install -r requirements.txt
```

## Current Limitations

This is an early version of the project.

Currently:

* Conversations are not saved after the program closes.
* There is only one active conversation.
* There is no graphical interface.
* API errors are not extensively handled.
* The model is configured directly in the Python source.
* There are only a small number of CLI commands.

## Possible Future Improvements

Planned or potential improvements include:

* [ ] Better API error handling
* [ ] System prompt
* [ ] `/help` command
* [ ] `/model` command
* [ ] Configurable model through `.env`
* [ ] Save and load conversations
* [ ] Multiple conversations
* [ ] Improved terminal interface
* [ ] Markdown rendering
* [ ] Better handling of long conversations
* [ ] Conversation export
* [ ] Configuration file
* [ ] More OpenRouter options

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for the full license text.

## Disclaimer

This project is an independent client for the OpenRouter API and is not affiliated with OpenRouter or the model provider used by the application.
