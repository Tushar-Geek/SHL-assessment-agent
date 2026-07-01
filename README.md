# SHL Assessment Recommendation Agent

Production-ready FastAPI service for recommending SHL Individual Test Solutions from a structured catalog. The service is stateless: every /chat request must include the conversation history needed to answer the current turn.

## Architecture Checklist

- FastAPI app with strict Pydantic request and response schemas.
- Catalog repository loads structured JSON records and validates fields.
- Scraper extracts SHL Individual Test Solutions with BeautifulSoup and optional Playwright for JavaScript-rendered pages.
- Embedding layer supports OpenAI-compatible /v1/embeddings; deterministic local embeddings keep tests and local development runnable without secrets.
- Vector search uses FAISS when available and a NumPy cosine fallback for portability.
- Ranking combines semantic similarity, metadata matching, skills overlap, seniority, technical skills, and job-description overlap.
- Agent supports clarification, recommendations, refinement, comparisons, off-topic refusal, prompt-injection refusal, and stateless history.
- Evaluation script reports Recall@10, precision, latency, response quality notes, conversation turns, and hallucination rate.

## Folder Structure

- app/: FastAPI app, schemas, agent, retrieval, ranking, safety.
- scripts/: Catalog scraping, index building, evaluation.
- data/catalog.json: Structured catalog seed; refresh from SHL before production submission.
- tests/: Pytest suite.
- .github/workflows/: CI pipeline.

## Data Flow

1. scripts/scrape_catalog.py fetches SHL product catalog pages.
2. The scraper ignores Job Solutions and normalizes Individual Test Solution records into data/catalog.json.
3. CatalogRepository validates records with Pydantic.
4. VectorStore embeds each assessment search document and builds a FAISS index.
5. /chat parses the current stateless message history, applies safety checks, retrieves candidates, ranks them, and returns the exact assignment response schema.

## Retrieval Flow

The retriever embeds the user request plus relevant history. It retrieves more candidates than needed, applies metadata filters such as remote testing and job level, and passes candidates to the ranker. FAISS is used in production when faiss-cpu is installed.

## Prompting Flow

The system prompt in app/llm.py constrains the optional OpenAI-compatible chat model to the loaded SHL catalog, forbids hallucinated URLs, asks clarifying questions only when necessary, supports comparison and refinement, and refuses unrelated or adversarial requests. The deterministic agent path is the default so the API works without an LLM key.

## Ranking Pipeline

Ranking score is a weighted blend of semantic similarity, metadata match, skills overlap, job description and assessment family overlap, and technical or personality terms found in the user request. The API returns between 1 and 10 recommendations.

## API

GET /health returns HTTP 200 with {"status":"ok"}.

POST /chat request: {"messages":[{"role":"user","content":"Need a Python developer assessment under 45 minutes"}]}

POST /chat response: {"reply":"...","recommendations":[{"name":"...","url":"...","test_type":"..."}],"end_of_conversation":false}

## Run Locally

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

Open http://localhost:8000/docs.

## Refresh The SHL Catalog

python scripts/scrape_catalog.py --output data/catalog.json --browser
python scripts/build_index.py

The included data/catalog.json is a small seed so tests and the app run immediately. Refresh it from SHL with the scraper before final production deployment or assignment submission where a complete catalog is required.

## Tests

pytest -q

## Evaluation

python scripts/evaluate.py

The script writes evaluation_report.json and prints aggregate metrics.

## Docker

docker build -t shl-assessment-agent .
docker run --env-file .env -p 8000:8000 shl-assessment-agent
docker compose up --build

## Render Deployment

1. Create a new Web Service from the GitHub repository.
2. Use Docker runtime.
3. Set environment variables from .env.example.
4. Set health check path to /health.
5. Deploy and test /docs and /chat.

## Railway Deployment

1. Create a Railway project from the GitHub repository.
2. Select Dockerfile deployment.
3. Add environment variables from .env.example.
4. Expose port 8000.
5. Deploy and verify /health.

## Design Decisions

- The API is stateless by design to match the assignment. No server memory is used for conversation state.
- The local deterministic embedding fallback prevents test flakiness and secret leakage.
- Catalog grounding is enforced by returning only records loaded from JSON.
- The LLM is optional and OpenAI-compatible, so deployments can use OpenAI or a compatible provider.

## Future Improvements

- Add assignment-provided gold evaluation queries when available.
- Expand scraper selectors when SHL changes page markup.
- Persist FAISS index artifacts instead of building lazily for very large catalogs.
- Add observability dashboards for latency, refusal rate, and recommendation quality.
