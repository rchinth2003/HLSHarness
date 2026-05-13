# Authentication & Azure Integration

HLSHarness uses `DefaultAzureCredential` for all Azure OpenAI calls. No API keys are stored anywhere in code, configuration files, or CI environment variables.

## Authentication Flow

```mermaid
sequenceDiagram
    participant USER as Developer<br/>(local machine)
    participant AZ as az CLI
    participant AAD as Azure Active Directory<br/>(Entra ID)
    participant TOKEN as DefaultAzureCredential
    participant BTP as get_bearer_token_provider()
    participant AOAI as Azure OpenAI Service

    Note over USER,AZ: One-time setup
    USER->>AZ: az login
    AZ->>AAD: interactive browser login
    AAD-->>AZ: OAuth 2.0 token
    AZ->>AZ: cache token → ~/.azure/

    Note over TOKEN,AOAI: Per-request flow (automatic)
    TOKEN->>TOKEN: Try credential chain in order:
    TOKEN->>TOKEN: 1. EnvironmentCredential (env vars)
    TOKEN->>TOKEN: 2. WorkloadIdentityCredential (AKS/GH Actions OIDC)
    TOKEN->>TOKEN: 3. ManagedIdentityCredential (Azure-hosted)
    TOKEN->>TOKEN: 4. AzureCliCredential (~/.azure/ cache)
    TOKEN->>TOKEN: 5. InteractiveBrowserCredential (fallback)

    TOKEN->>BTP: create token provider for cognitive services scope
    BTP-->>TOKEN: token_provider lambda

    TOKEN->>AOAI: AzureOpenAI(endpoint=..., azure_ad_token_provider=token_provider)
    AOAI->>AAD: validate bearer token
    AAD-->>AOAI: token valid
    AOAI-->>TOKEN: chat.completions.create() ready
```

## Credential Chain by Environment

```mermaid
graph TB
    subgraph LOCAL["Local Development"]
        AZ_CLI["AzureCliCredential\n(~/.azure/ cache)\naz login once"]
    end

    subgraph CI["CI — GitHub Actions"]
        OIDC["WorkloadIdentityCredential\n(GitHub OIDC token)\nNo secrets needed"]
    end

    subgraph PROD["Production — Azure Hosted"]
        MI["ManagedIdentityCredential\n(Assigned identity)\nNo credentials at all"]
    end

    subgraph DEFAULT["DefaultAzureCredential chain"]
        D1["1. EnvironmentCredential"]
        D2["2. WorkloadIdentityCredential"]
        D3["3. ManagedIdentityCredential"]
        D4["4. AzureCliCredential"]
        D5["5. InteractiveBrowserCredential"]
    end

    AZ_CLI -->|"Local dev"| D4
    OIDC -->|"CI/CD"| D2
    MI -->|"Azure compute"| D3
```

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `AZURE_OPENAI_ENDPOINT` | **Yes** | — | Full Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT_JUDGE` | No | `gpt-5.4-pro` | Judge model deployment name |
| `AZURE_OPENAI_DEPLOYMENT_SCHEDULING` | No | `gpt-5.4-nano` | scheduling-v1 agent model |
| `AZURE_OPENAI_DEPLOYMENT_<AGENT>` | No | — | Per-agent model overrides |

**No API keys, no connection strings, no passwords** — only the endpoint URL (not a secret) is required.

## Azure Services Used

```mermaid
graph LR
    subgraph HARNESS["HLSHarness"]
        AGENT_CLIENT["Agent Azure OpenAI Client\n(gpt-5.4-nano)"]
        JUDGE_CLIENT["Judge Azure OpenAI Client\n(gpt-5.4-pro)"]
        CRED["DefaultAzureCredential"]
    end

    subgraph AZURE["Azure Services"]
        AOAI["Azure OpenAI Service\n(chat completions, JSON mode)"]
        AAD["Azure Active Directory\n(Entra ID — token validation)"]
    end

    CRED --> AGENT_CLIENT
    CRED --> JUDGE_CLIENT
    AGENT_CLIENT --> AOAI
    JUDGE_CLIENT --> AOAI
    AOAI --> AAD
```

**Notable**: HLSHarness does **not** use Azure Storage, Key Vault, Service Bus, or any other Azure service beyond Azure OpenAI. All persistence is local (SQLite, JSON files).

## Token Refresh

`get_bearer_token_provider()` from `azure-identity` wraps the credential in a lazy refresh provider. Tokens are automatically refreshed before expiry — no explicit token management in application code.

```python
# Pattern used in hlsharness/maf_agent.py
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)

client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    azure_ad_token_provider=token_provider,
    api_version="2024-12-01-preview",
)
```
