# Battery Troubleshooting Knowledge Graph

This project turns one Dell support article into an interactive troubleshooting graph. The source page is saved locally, cleaned into sections, sent to an OpenAI model through LangChain, validated against the graph ontology, and displayed in Streamlit. The graph is stored in `data/graph.json`; no database is used.

## Requirements

- Python 3.11 or newer
- An OpenAI API key
- An OpenAI API model ID available to your account

## Project files

- `config.py` — source article URL and article number.
- `clean_article.py` — reads the manually saved HTML and writes `data/sections.json`.
- `build_graph.py` — asks the LLM for a generic troubleshooting flow, copies it for each affected device, validates it, and writes `data/graph.json`.
- `app.py` — reads `data/graph.json` and displays the selected device's graph.
- `.env` — local API settings; keep this file private and do not commit it.
- `.env.example` — safe template with empty settings.
- `data/article.html` — HTML page saved from a browser.
- `data/sections.json` — cleaned article content produced by `clean_article.py`.
- `data/graph.json` — generated nodes and edges produced by `build_graph.py`.

The three files under `data/` are local inputs or generated outputs and are excluded from Git. Each person using the shared repository must save the article locally and generate their own sections and graph JSON.

## 1. Set up the Python environment

From the project folder, create and activate a virtual environment. Create it only once:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If `.venv` already exists, just activate it and install any updated requirements:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure the article and OpenAI

Edit `config.py` to set `ARTICLE_URL` and `ARTICLE_NUMBER`. If you switch to another article, change both values. The cleaner currently expects a Dell KB page with an article body and an Affected Products list.

Create `.env` from the template if you do not already have one:

```bash
test -f .env || cp .env.example .env
```

Edit `.env` and set:

```dotenv
LLM_API_KEY=your_openai_api_key
LLM_BASE_URL=
LLM_MODEL=your_available_openai_model_id
```

Leave `LLM_BASE_URL` blank to use OpenAI's default API endpoint. Use a model ID that is enabled for your OpenAI API account. Do not put real credentials in `.env.example` or share them in chat. If an API key was exposed, revoke it and create a replacement.

## 3. Save the article HTML

The project does not download the article automatically. Open the URL in `config.py` in a browser and save the full webpage as HTML at this exact path:

```text
data/article.html
```

If the `data` folder does not exist yet, create it first:

```bash
mkdir -p data
```

Save the page as an HTML webpage, not as a PDF or text-only copy. Dell may block automated requests, so using the browser is the expected way to provide the source file.

## 4. Clean the article

With the virtual environment active, run:

```bash
python clean_article.py
```

The cleaner removes page navigation and scripts, extracts the title, article sections, ordered and unordered lists, tables, links, videos, article metadata, and affected products, then saves them to `data/sections.json`.

Check the command output for warnings. In particular, the graph builder needs a non-empty Affected Products list.

## 5. Build the graph

Run:

```bash
python build_graph.py
```

LangChain sends the cleaned article to the configured OpenAI model and asks for JSON containing troubleshooting Questions, Answers, Resolutions, and their relationships. Python validates the response, adds the Intent, Vendor, KBArticle, and Device nodes, applies the Chromebook-specific exclusions, copies the generic flow for each affected device, and saves the result to `data/graph.json`.

The model's default temperature is used because some OpenAI models reject a custom temperature value. The graph builder stops with an error if the model response does not match the expected JSON or ontology.

## 6. View the graph

Run:

```bash
streamlit run app.py
```

Open the local address printed by Streamlit (normally `http://localhost:8501`). Choose a Dell device in the sidebar. The graph is arranged top-down; answer labels appear on answer edges, and dashed amber edges mean “If not fixed.” Hover over a node for its properties. Use the node inspector below the graph for instructions, commands, notes, and resource links. Enable “Show vendor and article nodes” in the sidebar to include those context nodes.

## Re-run after changing the source

1. Update `ARTICLE_URL` and `ARTICLE_NUMBER` in `config.py`.
2. Save the new page as `data/article.html`.
3. Run `python clean_article.py`.
4. Run `python build_graph.py`.
5. Restart or refresh the Streamlit app.

## Common issues

- **Missing `data/article.html`:** save the browser page at that exact path.
- **Affected Products warning:** ensure the saved HTML is the full Dell article page, then rerun `python clean_article.py`.
- **401 / invalid API key:** check `LLM_API_KEY` in `.env`; verify it is an active OpenAI API key. Never paste it into this project README or `.env.example`.
- **Model not found or unsupported request parameter:** check that `LLM_MODEL` is an API model ID available to your account. A model name shown in another product or interface may not be an API model ID.
- **Stale shell variables:** if variables exported in the current terminal are overriding `.env`, clear them with `unset LLM_API_KEY LLM_BASE_URL LLM_MODEL`, then rerun `python build_graph.py`.

The project writes JSON only. It does not use a database, caching, or Neo4j.
