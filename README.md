## Company Search API

FastAPI service that finds companies similar to a given company in the context of a product concept. It uses Tavily for web search and Groq-hosted LLM (via LangChain) to synthesize results.

### Requirements
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for environment and package management
- API keys (see below)

### Environment variables (required)
Create a `.env` file in the repo root with the following variables:

```
GROQ_API_KEY=your_groq_api_key
TAVILY_API_KEY=your_tavily_api_key

# Optional (defaults to "llama-3.3-70b-versatile")
GROQ_MODEL=llama-3.3-70b-versatile
```

- **GROQ_API_KEY**: Get from Groq. See their docs at [Groq](https://groq.com/).
- **TAVILY_API_KEY**: Get from Tavily. See their docs at [Tavily](https://tavily.com/).
- **GROQ_MODEL**: Any Groq-supported chat model. Defaults to `llama-3.3-70b-versatile`.

### Install dependencies
Using `uv`:

```bash
uv pip install -r requirements.txt
```

### Run the API
```bash
uv run uvicorn api.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`. Interactive docs: `http://127.0.0.1:8000/docs`.

### Endpoints

- **GET /**: Basic service info
- **GET /health**: Health check and presence of API keys
- **POST /search**: Main endpoint that returns companies similar to the input
- **/docs**: Swagger UI

### GET /health
```bash
curl -s http://127.0.0.1:8000/health | jq
```
Response example:
```json
{
  "status": "healthy",
  "groq_key_present": true,
  "tavily_key_present": true
}
```

### POST /search
Accepts a JSON body with two top-level objects: `company` and `concept`.

Only a subset of fields is used by the current logic:
- From `company`: `name`, `personalNote`, `tags`
- From `concept`: `targetIndustries`

However, validation requires certain fields to be present. Below is a minimal valid payload that satisfies the Pydantic models while keeping unused fields stubbed.

Request:
```bash
curl -s -X POST \
  http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{
    "company": {
      "id": "cmp_123",
      "createdAt": "2024-01-01T00:00:00Z",
      "updatedAt": "2024-01-01T00:00:00Z",
      "name": "Acme Inc",
      "tags": ["SaaS", "Analytics"],
      "personalNote": "B2B focus, strong data platform",
      "companyMasterId": "cm_001",
      "companyMaster": [
        {
          "id": "cm_001",
          "createdAt": "2024-01-01T00:00:00Z",
          "updatedAt": "2024-01-01T00:00:00Z",
          "creatorId": "usr_1",
          "name": "Acme Group",
          "tagsMaster": [],
          "companies": []
        }
      ]
    },
    "concept": {
      "id": "cnc_123",
      "createdAt": "2024-01-01T00:00:00Z",
      "updatedAt": "2024-01-01T00:00:00Z",
      "idea": "AI assistant for finance teams",
      "productName": "FinAI",
      "targetIndustries": ["Financial Services"],
      "targetEndUsers": []
    }
  }' | jq
```

Response (example):
```json
[
  {
    "name": "ExampleCo",
    "websiteUrl": "https://example.com",
    "wikipediaUrl": null,
    "linkedinUrl": null,
    "logoUrl": null,
    "description": "Enterprise analytics platform",
    "industry": "Analytics",
    "tags": ["SaaS", "Data"],
    "stillInBusiness": true
  }
]
```

### Notes
- CORS is wide open (`*`) for development convenience.
- The service uses Tavily for retrieval and Groq LLM (via LangChain) to extract a structured list of companies.
- For request/response schemas, consult the docs at `/docs`.
