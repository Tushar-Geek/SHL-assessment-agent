# Approach Document

## Architecture

I built the solution as a stateless FastAPI service with two endpoints: /health for availability checks and /chat for recommendations. The chat endpoint accepts the full message history on every request, so the service does not depend on server-side session memory. The main pipeline is: validate request, detect unsafe or out-of-scope input, decide whether clarification is needed, retrieve candidate SHL assessments, rerank them, and return the response in the required schema.

The project is split into small modules: catalog loading and validation, embeddings, vector search, ranking, conversation logic, safety checks, API schemas, scraping, tests, and evaluation. Catalog records are represented with Pydantic models so malformed data is caught early.

## Retrieval Setup

I store SHL assessments as structured JSON with fields such as name, description, skills measured, duration, remote testing, languages, test type, job level, assessment family, and catalog URL. Each record is converted into a searchable text document using its description, skills, metadata, and assessment family.

For retrieval, the app supports OpenAI-compatible embeddings and FAISS. I also added a deterministic local embedding fallback so the service can run in development and CI without API keys. The retrieval step first performs semantic search, then applies metadata constraints such as remote testing, duration, and job level where possible.

## Ranking

The ranking layer combines semantic similarity with practical matching signals. I score candidates using skills overlap, job-description overlap, test type relevance, seniority match, duration fit, and remote-testing compatibility. This helps avoid returning a semantically similar assessment that fails an explicit constraint. The API returns between one and ten recommendations, depending on the available matches.

## Prompt And Conversation Design

The assistant is constrained to the loaded SHL catalog. It should not invent assessment names, metadata, or URLs. If the request is too vague, it asks for role, skills, seniority, or time constraints before recommending. It also supports follow-up refinement because the full conversation history is included in each request.

For comparisons, the agent compares only catalog-backed fields such as skills measured, duration, test type, family, and job level. For safety, I added explicit refusal handling for prompt injection, system prompt extraction, legal advice, salary advice, general hiring advice, and non-SHL recommendations.

## Evaluation

I added automated tests for /health, /chat schema compliance, clarification, recommendations, comparison, refinement, off-topic refusal, prompt-injection refusal, stateless history, and ranking behavior. I also included an evaluation script that measures Recall@10, precision, average latency, hallucination rate, and conversation capabilities.

The main quality measure is whether returned recommendations are relevant and grounded in catalog records. Hallucination rate is checked by verifying that returned URLs come from the loaded catalog. Retrieval quality can be improved by expanding the gold evaluation set with more role-specific test cases.

## What Did Not Work

The main issue was reliable access to the full public SHL catalog during development. Direct fetching can be blocked depending on the environment, so I implemented both a standard BeautifulSoup scraper and a Playwright-based browser mode for JavaScript-rendered or protected pages. I also kept the app runnable with a small seed catalog so the API, tests, and deployment flow can be validated before refreshing the complete catalog.

## AI Tools Used

I used AI assistance for scaffolding, code review, and documentation drafting, then reviewed and organized the implementation around the assignment requirements. The recommendation logic itself is grounded in the local SHL catalog data and does not rely on the model inventing assessments or URLs.
