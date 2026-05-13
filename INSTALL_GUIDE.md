# Install Guide — HLS Harness

Everything runs inside a devcontainer. No Python, no uv, no package manager needed on your laptop.

---

## What you need on your laptop

| Tool | Install |
|------|---------|
| [Git](https://git-scm.com/) | `winget install Git.Git` (Windows) · `brew install git` (Mac) |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Enable WSL2 backend on Windows |
| [VS Code](https://code.visualstudio.com/) | + install the **Dev Containers** extension (`ms-vscode-remote.remote-containers`) |
| [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) | `winget install Microsoft.AzureCLI` (Windows) · `brew install azure-cli` (Mac) |

---

## Azure OpenAI — what to deploy first

You need **two model deployments** in your Azure OpenAI resource before starting. Create them in the [Azure AI Foundry portal](https://ai.azure.com/) under your resource → **Deployments → Deploy model**.

| Env var | Deployment name | Model | Used for |
|---------|-----------------|-------|----------|
| `AZURE_OPENAI_DEPLOYMENT_AGENT` | `gpt-5.4-nano` | GPT-4o-mini (or equivalent) | Scheduling + eligibility agents (structured tool-calling) |
| `AZURE_OPENAI_DEPLOYMENT_JUDGE` | `gpt-5.4-pro` | GPT-4o (or equivalent) | Orchestrator, triage (routing + safety), eval rubric scorer |

> **Deployment names matter.** The orchestrator and triage agents declare `model: gpt-5.4-pro` in their `agent.yaml` — this must match the name you give the deployment in the portal exactly. If you use a different name, update the `model:` field in `cases/orchestrator-v1/agent.yaml` and `cases/triage-v1/agent.yaml` to match.

---

## One-time setup (15 minutes)

### Step 1 — Log in to Azure

```bash
az login
```

This stores your credentials in `~/.azure`. The container inherits them automatically — you won't need to log in again inside the container.

### Step 2 — Set your environment variables

Add these to your shell profile (`~/.bashrc`, `~/.zshrc`, or PowerShell `$PROFILE`) so the container picks them up:

```bash
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
export AZURE_OPENAI_DEPLOYMENT_AGENT=gpt-5.4-nano   # scheduling + eligibility agents
export AZURE_OPENAI_DEPLOYMENT_JUDGE=gpt-5.4-pro    # orchestrator, triage + eval scorer
```

Restart your terminal after saving.

### Step 3 — Clone the repo

```bash
git clone https://github.com/rchinth2003/HLSHarness.git
cd HLSHarness
```

### Step 4 — Open in VS Code

```bash
code .
```

When VS Code opens, it will detect the devcontainer and show a prompt:

> **"Reopen in Container"** — click it.

First launch takes ~3 minutes to pull the Python 3.12 image and install dependencies. Subsequent launches are instant.

### Step 5 — Copy the env file

Inside the container terminal (VS Code → Terminal):

```bash
cp .env.example .env
```

Open `.env` and fill in your actual endpoint and deployment names. The file is gitignored — your values stay local.

---

## Launch the demo

```bash
uv run streamlit run demo/app.py
```

The app opens automatically at `http://localhost:8501` (port is forwarded from the container).

**Demo instructions:** `demo/README.md` — scenario table, turn-by-turn scripts, and presenter tips for all 6 scenarios.

---

## Run the eval harness

```bash
# Full test suite — no Azure calls, runs in ~35 seconds
uv run pytest tests/ -q

# Live eval against your Azure OpenAI deployment
uv run hls-eval
```

`uv run hls-eval` runs the scheduling-v1 agent through the full eval suite and prints a scored summary. Results are also written to `results.json`.

To explore results interactively:

```bash
uv run streamlit run dashboard/app.py -- results.json
```

---

## Verify everything is working

| Command | Expected output |
|---------|-----------------|
| `uv run pytest tests/ -q` | `1053 passed` in ~35 sec |
| `uv run hls-eval` | `Overall: PASSED` + `results.json` written |
| `uv run streamlit run demo/app.py` | Browser opens at `http://localhost:8501` |

If anything fails, check that your `.env` values are correct and that `az login` was run on the **host** (not inside the container) before opening VS Code.
