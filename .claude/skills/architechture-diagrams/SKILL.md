---
name: architechture-diagrams
description: Describe what this skill does and when to use it. Include keywords that help agents identify relevant tasks.
---

---
name: architecture-diagrams
description: >
  Analyze a project repo and generate Mermaid-based architecture diagrams
  and sequence diagrams for all major user-facing functionality.
  Supports Azure, AWS, GCP, open-source, SaaS, on-prem, and hybrid stacks.
---

# Universal Architecture & Sequence Diagram Generator

## When to Use
Use this skill when the user asks to:
- Generate architecture diagrams from a codebase
- Create sequence diagrams for user flows or API interactions
- Visualize cloud/hybrid infrastructure and service dependencies
- Document system architecture with diagrams

---

## Step 1: Codebase Discovery

Scan the entire repository to build a complete technology inventory.

### 1A. Infrastructure-as-Code (IaC) — Primary Source of Truth

| Provider | Files to Scan |
|---|---|
| **Azure** | `*.bicep`, ARM templates (`azuredeploy.json`), `azure-pipelines.yml` |
| **AWS** | `template.yaml/json` (SAM/CFN), `cdk.json`, `*.template`, `serverless.yml` |
| **GCP** | `app.yaml`, `*.jinja`, `cloudbuild.yaml`, `firebase.json` |
| **Terraform** | `*.tf`, `*.tfvars`, `terraform.lock.hcl` (check `provider` blocks for cloud) |
| **Pulumi** | `Pulumi.yaml`, `Pulumi.*.yaml`, `__main__.py`, `index.ts` |
| **Kubernetes** | `*.yaml` with `apiVersion:`, `kustomization.yaml`, Helm `Chart.yaml` |
| **Docker** | `Dockerfile*`, `docker-compose*.yml`, `.dockerignore` |
| **Ansible/Chef/Puppet** | `playbook.yml`, `roles/`, `cookbooks/`, `manifests/` |

### 1B. SDK & Dependency References

Scan dependency manifests for cloud SDKs and service clients:

| Ecosystem | File | What to Look For |
|---|---|---|
| **.NET** | `*.csproj`, `packages.config` | `Azure.*`, `AWSSDK.*`, `Google.Cloud.*` |
| **Node.js** | `package.json` | `@azure/*`, `@aws-sdk/*`, `@google-cloud/*`, `firebase`, `stripe`, `twilio` |
| **Python** | `requirements.txt`, `pyproject.toml`, `Pipfile` | `azure-*`, `boto3`, `google-cloud-*`, `celery`, `kafka-python`, `redis` |
| **Java** | `pom.xml`, `build.gradle` | `com.azure:`, `software.amazon.awssdk:`, `com.google.cloud:` |
| **Go** | `go.mod` | `github.com/Azure/`, `github.com/aws/`, `cloud.google.com/go/` |
| **Ruby** | `Gemfile` | `aws-sdk-*`, `google-cloud-*`, `azure_mgmt_*` |

### 1C. Configuration & Connection Strings

| File Patterns | Signals |
|---|---|
| `appsettings*.json`, `.env*`, `config.*` | Connection strings, endpoints, API keys |
| `local.settings.json`, `host.json` | Azure Functions configuration |
| `application.yml`, `application.properties` | Spring Boot / Java configs |
| `.aws/`, `~/.kube/config` | AWS CLI / Kubernetes context |
| `firebase.json`, `.firebaserc` | Firebase/GCP config |

### 1D. Application Entry Points & User Flows

Look for:
- **API layers**: Controllers, route handlers, GraphQL resolvers, gRPC service definitions
- **Frontend**: Pages, components, API client calls, state management
- **Workers**: Background jobs, message consumers, cron handlers, queue processors
- **Auth**: OAuth/OIDC middleware, JWT validation, API key checks, SAML config
- **Webhooks**: Incoming webhook handlers and outbound webhook dispatchers

### 1E. Data Flow & Integrations

| Category | What to Find |
|---|---|
| **Databases** | SQL Server, PostgreSQL, MySQL, MongoDB, Cosmos DB, DynamoDB, Firestore, Supabase, CockroachDB, Cassandra |
| **Caches** | Redis, Memcached, Hazelcast |
| **Message Brokers** | Service Bus, SQS/SNS, Pub/Sub, Kafka, RabbitMQ, NATS, ZeroMQ |
| **Event Systems** | Event Grid, EventBridge, Cloud Events, Webhooks |
| **Object Storage** | Blob Storage, S3, GCS, MinIO |
| **Search** | Elasticsearch, OpenSearch, Azure AI Search, Algolia, Typesense |
| **Auth Providers** | Entra ID, Cognito, Firebase Auth, Auth0, Okta, Keycloak, Clerk |
| **Payment/SaaS** | Stripe, PayPal, Twilio, SendGrid, Mailgun, LaunchDarkly, Segment |
| **AI/ML** | OpenAI, Azure OpenAI, Bedrock, Vertex AI, Hugging Face, LangChain |
| **CDN/Edge** | CloudFront, Azure CDN, Cloudflare, Fastly, Vercel Edge |
| **DNS/Networking** | Route 53, Azure DNS, Cloudflare DNS, VPN, Private Link |
| **Monitoring** | App Insights, CloudWatch, Cloud Monitoring, Datadog, Prometheus, Grafana, Sentry, New Relic |
| **CI/CD** | GitHub Actions, Azure DevOps, GitLab CI, Jenkins, CircleCI, ArgoCD |

---

## Step 2: Generate the Architecture Diagram

Produce a **Mermaid flowchart** (`graph TB`) that shows ALL discovered services.

### Grouping Rules

Group nodes into subgraphs by **logical tier**, not by cloud provider.
Add a **cloud badge** to each node label when multi-cloud:

- `[Azure]`, `[AWS]`, `[GCP]`, `[Self-hosted]`, `[SaaS]`

#### Tier Definitions

| Subgraph | Contents |
|---|---|
| `Clients` | Browsers, mobile apps, CLI tools, IoT devices |
| `Edge / CDN` | CDN, WAF, load balancers, API gateways, reverse proxies |
| `Frontend` | Static sites, SSR apps, SPAs |
| `API Gateway` | API Management, API Gateway, Kong, Traefik |
| `Application` | App services, containers, functions, serverless, K8s pods |
| `Background Processing` | Workers, queue consumers, scheduled jobs, stream processors |
| `Messaging & Events` | Queues, topics, event buses, streams |
| `Data` | Databases (SQL & NoSQL), caches, search engines |
| `Storage` | Object/blob storage, file shares, data lakes |
| `AI / ML` | LLM APIs, ML endpoints, vector DBs, embeddings |
| `Identity & Security` | Auth providers, secrets management, certificate stores |
| `DevOps & CI/CD` | Pipelines, registries, GitOps controllers |
| `Monitoring` | APM, logging, alerting, tracing |
| `External / SaaS` | Third-party APIs (payment, email, SMS, analytics) |

### Architecture Diagram Template

~~~mermaid
graph TB
    subgraph Clients["👤 Clients"]
        Browser[Web Browser]
        Mobile[Mobile App]
    end

    subgraph Edge["🌐 Edge / CDN"]
        CDN[CDN\nCloudflare]
        WAF[WAF]
    end

    subgraph Frontend["🖥️ Frontend"]
        SPA[React SPA\nVercel]
    end

    subgraph Gateway["🔀 API Gateway"]
        GW[API Gateway\nKong / APIM / AWS GW]
    end

    subgraph Application["⚙️ Application Tier"]
        API[REST API\nNode.js on ECS]
        GQL[GraphQL\nApp Service]
    end

    subgraph Workers["🔄 Background Processing"]
        Worker[Queue Consumer\nLambda / Functions]
        Cron[Scheduled Job\nK8s CronJob]
    end

    subgraph Messaging["📨 Messaging & Events"]
        Queue[SQS / Service Bus]
        Stream[Kafka / Event Hubs]
        EventBus[EventBridge / Event Grid]
    end

    subgraph Data["💾 Data Tier"]
        SQL[(PostgreSQL\nRDS / Azure SQL)]
        NoSQL[(MongoDB\nCosmos DB / Atlas)]
        Cache[(Redis)]
        Search[(Elasticsearch)]
    end

    subgraph Storage["📦 Storage"]
        Blob[(S3 / Blob Storage)]
    end

    subgraph AI["🤖 AI / ML"]
        LLM[OpenAI / Azure OpenAI]
        VectorDB[(Pinecone / pgvector)]
    end

    subgraph Security["🔐 Identity & Security"]
        Auth[Auth0 / Entra ID / Cognito]
        Secrets[Key Vault / Secrets Manager]
    end

    subgraph Monitoring["📊 Monitoring"]
        APM[Datadog / App Insights]
        Logs[CloudWatch / Log Analytics]
    end

    subgraph External["🔗 External SaaS"]
        Payment[Stripe]
        Email[SendGrid / SES]
        SMS[Twilio]
    end

    Browser --> CDN --> SPA
    Mobile --> GW
    SPA -->|API Calls| GW
    GW -->|Auth| Auth
    GW --> API
    GW --> GQL
    API --> SQL
    API --> Cache
    API --> NoSQL
    API -->|Enqueue| Queue
    API -->|Prompt| LLM
    LLM -->|Embed| VectorDB
    Queue -->|Trigger| Worker
    Worker --> Blob
    Worker -->|Publish| EventBus
    EventBus -->|Fan-out| Stream
    Cron --> SQL
    API -->|Secrets| Secrets
    API -->|Charge| Payment
    Worker -->|Notify| Email
    Worker -->|SMS| SMS
    API -.->|Telemetry| APM
    Worker -.->|Logs| Logs
~~~

> **Adapt this template**: remove tiers with no matching services,
> collapse sparse tiers, and rename labels to match actual service
> names found in the codebase.

---

## Step 3: Generate Sequence Diagrams for Major User Flows

For **each major user-facing feature**, produce a **Mermaid sequence diagram**.

### Identification Rules

A "major user flow" includes any of:
- Authentication / login / signup / SSO
- Core CRUD operations on primary entities
- File or media upload / download
- Search / filtering / autocomplete
- Checkout / payment / subscription
- Notification delivery (email, SMS, push)
- Real-time features (WebSocket, SSE, polling)
- AI/ML-powered features (chat, recommendations, search)
- Background processing triggered by user action
- Webhook / event-driven flows visible to the user
- Admin or management console operations

### Sequence Diagram Guidelines

- **Participants**: Use actual component & service names from discovery
- **Arrows**: Label with HTTP methods, event names, message types
  (`->>` sync, `-->>` async response, `--)` fire-and-forget)
- **Alt/Opt/Par blocks**: Show conditional logic, error handling,
  parallel processing, retries
- **Notes**: Call out important details (token types, async handoff,
  idempotency, rate limits)
- **Activation bars**: Show when a service is actively processing
- **Color-code by provider** (use `Note` annotations when helpful)

### Sequence Diagram Template (Multi-Cloud Example)

~~~mermaid
sequenceDiagram
    actor User
    participant SPA as React SPA<br/>(Vercel)
    participant GW as API Gateway<br/>(Kong)
    participant Auth as Auth0
    participant API as REST API<br/>(ECS)
    participant Cache as Redis<br/>(ElastiCache)
    participant DB as PostgreSQL<br/>(RDS)
    participant Queue as SQS
    participant Worker as Lambda
    participant LLM as OpenAI API
    participant Blob as S3
    participant Email as SendGrid

    Note over User,Email: 🔹 Flow: [Feature Name]

    User->>SPA: Initiate action
    SPA->>GW: POST /api/resource (Bearer token)
    GW->>Auth: Validate JWT

    alt Token Valid
        Auth-->>GW: 200 OK (claims)
        GW->>API: Forward + inject claims

        API->>Cache: Check cache (key: resource:id)
        alt Cache Hit
            Cache-->>API: Cached result
        else Cache Miss
            API->>DB: SELECT query
            DB-->>API: Result set
            API->>Cache: SET with TTL
        end

        opt AI-Powered Feature
            API->>LLM: Chat completion request
            LLM-->>API: Generated response
        end

        API-->>GW: 200 JSON response
        GW-->>SPA: Response
        SPA-->>User: Render result

        API-)Queue: Enqueue async job
        Queue->>Worker: Trigger
        Worker->>Blob: Store artifact
        Worker->>Email: Send notification
        Email-->>User: Email delivered

    else Token Invalid / Expired
        Auth-->>GW: 401 Unauthorized
        GW-->>SPA: 401
        SPA->>Auth: Redirect to /authorize
        Auth-->>User: Login prompt
    end
~~~

---

## Step 4: Output Format

Present all diagrams in this order:

### 1. System Overview
A brief paragraph (3-5 sentences) summarizing:
- What the application does
- Which cloud providers / platforms are involved
- High-level architecture style (monolith, microservices, serverless, hybrid)

### 2. Technology Inventory Table

| Category | Technology | Provider | Detected In | Confidence |
|---|---|---|---|---|
| Compute | Azure App Service | Azure | `app.bicep` | ✅ High |
| Database | PostgreSQL | AWS RDS | `docker-compose.yml`, `database.tf` | ✅ High |
| Auth | Auth0 | SaaS | `package.json`, `auth.config.ts` | ✅ High |
| Cache | Redis | Self-hosted | `docker-compose.yml` | ⚠️ Medium |
| AI | OpenAI | SaaS | `requirements.txt`, `chat.py` | ✅ High |

Confidence levels:
- ✅ **High** — found in IaC or explicit configuration
- ⚠️ **Medium** — inferred from SDK/dependency usage
- ❓ **Low** — guessed from code patterns or naming conventions

### 3. Architecture Diagram
The full Mermaid flowchart.

### 4. Sequence Diagrams
One per major flow, each with:
- **H3 heading** with flow name
- **Description** (1-2 sentences: what the user does, why it matters)
- **Participants list** (quick reference of services involved)
- **The Mermaid sequence diagram**

### 5. Cross-Cutting Concerns (if detected)

Summarize any of these if found in the codebase:
- **Authentication & Authorization** flow
- **Error handling & retry** strategy
- **Logging & observability** pipeline
- **CI/CD** pipeline stages
- **Multi-region / DR** setup

---

## Rules

- Only include technologies actually found in the codebase — never invent
- IaC files are the primary source of truth; fall back to SDK/config inference
- Flag uncertain detections with ⚠️ or ❓ markers
- Use official service names (e.g., "Amazon SQS" not "SQS", "Azure Cosmos DB" not "CosmosDB")
- For self-hosted/open-source, use the project name (e.g., "PostgreSQL", "Redis", "Kafka")
- Keep diagrams readable:
  - Architecture: max ~20 nodes; split into domain-specific views if larger
  - Sequence: max ~12 participants; split complex flows into sub-diagrams
- All diagram code must be **valid Mermaid syntax**
- When a repo is multi-cloud or hybrid, make that prominent in the overview
  and ensure the architecture diagram clearly shows cross-cloud data flows
- If the repo has a `/docs` or `/architecture` folder, check it for
  existing diagrams or ADRs and reconcile your output with them
