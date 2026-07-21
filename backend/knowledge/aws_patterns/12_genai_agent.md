# AWS Reference: GenAI Agent / RAG Architecture

## Pattern: Production GenAI Agent with RAG on AWS
**Use when**: chatbot, AI assistant, knowledge base Q&A, AI agent, LLM-powered workflow

### Core GenAI Stack on AWS
```
Amazon Bedrock — managed LLM API (Claude 3.5 Sonnet, Llama 3.1, Titan)
  - No infrastructure to manage, no GPU provisioning
  - Pay per token (input + output), not per hour
  - Available models: claude-3-5-sonnet, claude-3-haiku, llama-3-70b, titan-embed-v2

OpenSearch Serverless (vector search) — RAG knowledge base
  - k-NN index with cosine similarity (1536-dim vectors for Claude embeddings)
  - Serverless: no capacity planning, auto-scales to zero
  - Alternative: Aurora PostgreSQL + pgvector (if already using Aurora)

DynamoDB — conversation history + agent session state
  - Table: {session_id, timestamp, role, content, tool_calls}
  - TTL: 24h for chat sessions (automatic cleanup)
  - On-demand pricing: pay per request, no idle cost

S3 — knowledge base document store
  - Raw documents (PDF, DOCX, MD) uploaded here
  - Bedrock Knowledge Base sync job ingests → chunks → embeds → stores in OpenSearch
  - Versioned bucket (enables re-ingestion without data loss)
```

### Architecture: RAG Chatbot API
```
Users → API Gateway (WebSocket for streaming) → Lambda (agent orchestrator)
                                                → Bedrock (Claude invoke with streaming)
                                                → OpenSearch (vector search, top-5 chunks)
                                                → DynamoDB (get/put conversation history)
                                                → S3 (retrieve document metadata)
                                         Bedrock Knowledge Base Sync:
                                                → S3 (document source)
                                                → Bedrock Embeddings (titan-embed-v2)
                                                → OpenSearch (k-NN index)

Supporting services (aws_managed zone):
  CloudWatch: token usage metrics, latency alarms, error rate
  X-Ray: trace each LLM call, retrieval step, tool call
  Secrets Manager: Bedrock API config, any 3rd party API keys
  KMS: encrypt S3 documents, DynamoDB at rest, OpenSearch index
```

### Multi-Step AI Agent Architecture (ECS-based)
```
Users → ALB → ECS Fargate (agent runtime: LangChain / LlamaIndex)
                         → Bedrock (Claude — reasoning + tool selection)
                         → Tools:
                             - OpenSearch (search_knowledge_base)
                             - Lambda (execute_code, call_external_api)
                             - DynamoDB (get_user_context, store_result)
                             - SQS (queue_async_task → Lambda worker)
                         → DynamoDB (agent memory, scratchpad)
                         → S3 (agent artifacts, generated files)
                         Monitoring:
                         → CloudWatch (agent step count, tool call latency)
                         → X-Ray (end-to-end trace per user request)
```

### Bedrock Best Practices
- Model selection: Claude 3.5 Sonnet for reasoning-heavy tasks, Haiku for classification/simple tasks
- Context window: Claude 200k tokens — enough for 150-page documents in a single call
- Streaming: use InvokeModelWithResponseStream for chat UX (shows tokens as they arrive)
- Prompt caching: cache system prompt (saves 90% cost on repeated calls with same system prompt)
- Guardrails: Bedrock Guardrails to filter PII, toxicity, topic restrictions
- Cross-region inference: use inference profiles for failover (us-east-1 + us-west-2)

### RAG Pipeline Design
```
Ingestion (offline):
  S3 document → Bedrock Knowledge Base → Titan Embed v2 → OpenSearch index
  Chunk size: 512 tokens, 64-token overlap
  Schedule: EventBridge → Lambda → Bedrock StartIngestionJob API

Retrieval (online, per user query):
  User query → Titan Embed (query vector) → OpenSearch k-NN (top-5 chunks)
  → Claude prompt: [CONTEXT: {chunks}]\n[QUESTION: {user_query}]
  → Streaming response to user
```

### OpenSearch Serverless vs Aurora pgvector
| Factor | OpenSearch Serverless | Aurora pgvector |
|--------|----------------------|-----------------|
| Setup | Zero config, instant | Add extension, create index |
| Scale | Auto, 0→ unlimited | Limited by instance size |
| Query | Approximate k-NN (fast) | Exact or approximate |
| Cost | $0.24/OCU-hr (min 2 OCU) = $350/mo | $0 extra if Aurora already provisioned |
| Best for | Dedicated RAG, large corpus | Already have Aurora, small corpus |

### Well-Architected Scores (typical GenAI agent)
- Performance: 88/100 — Bedrock scales transparently; streaming reduces perceived latency
- Cost: 75/100 — Token costs add up; use caching + Haiku for cheap operations
- Security: 85/100 — Bedrock is VPC-endpoint capable; add guardrails for PII
- Reliability: 82/100 — Bedrock SLA 99.9%; add retry with exponential backoff
- Operations: 80/100 — Instrument every LLM call with X-Ray; alarm on token usage spikes

### Cost Estimate (medium RAG chatbot, 10k queries/day)
- Bedrock Claude 3.5 Sonnet (1M tokens/day): ~$15/day = $450/mo
- Bedrock Titan Embeddings (100k embeds/day): $0.10/day
- OpenSearch Serverless (2 OCU min): ~$350/mo
- DynamoDB on-demand (10k writes/day): ~$10/mo
- S3 (10GB docs): ~$0.25/mo
- Lambda (10k invocations): ~$2/mo
- Total: $800–1,200/mo at medium scale
- Cost cut: use Claude 3 Haiku for simple queries → $60/mo LLM cost instead

### Terraform Modules Deploy Order
1. networking/vpc (private subnets for Lambda/ECS)
2. networking/waf (rate limiting on API Gateway)
3. networking/apigw (HTTP or WebSocket API)
4. security/kms (encrypt S3, DynamoDB, OpenSearch)
5. security/iam (Lambda/ECS role: bedrock:InvokeModel, aoss:APIAccessAll, s3:GetObject)
6. security/secrets-manager (API keys, DB creds)
7. data/s3 (knowledge base documents, KMS encrypted, versioned)
8. data/dynamodb (conversation history table, TTL enabled)
9. ai/opensearch (vector collection, k-NN index policy)
10. ai/bedrock (knowledge base, data source pointing to S3, sync schedule)
11. compute/lambda (agent orchestrator or ECS for multi-step agent)
12. monitoring/cloudwatch (token usage, latency, error rate alarms)
13. monitoring/xray (trace sampling 10%)
