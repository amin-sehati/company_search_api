import os
import secrets
from datetime import datetime
from typing import List, Optional, TypedDict

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from tavily import TavilyClient
from pydantic import BaseModel, Field

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
API_KEY = os.getenv("API_KEY")


# Create FastAPI app
# Set root_path to "/api" so routes match when deployed behind Vercel's /api prefix
app = FastAPI(title="Company_Search_API", root_path="/api")

tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# Pydantic models for database schema


## Required by the API
class Company(BaseModel):
    id: str
    createdAt: datetime
    updatedAt: datetime
    name: str
    tags: List[str]
    personalNote: Optional[str]
    companyMasterId: str
    companyMaster: List["CompanyMaster"]


## Returned from the API
class CompanyMaster(BaseModel):
    id: str
    createdAt: datetime
    updatedAt: datetime
    creatorId: str
    name: str
    websiteUrl: Optional[str] = None
    wikipediaUrl: Optional[str] = None
    linkedinUrl: Optional[str] = None
    logoUrl: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    tagsMaster: List[str] = Field(default_factory=list)
    naicsCode: Optional[str] = None
    companies: List[Company] = Field(default_factory=list)
    stillInBusiness: Optional[bool] = None


class LLMCompany(BaseModel):
    name: str
    websiteUrl: Optional[str] = None
    wikipediaUrl: Optional[str] = None
    linkedinUrl: Optional[str] = None
    logoUrl: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    stillInBusiness: Optional[bool] = None


class CompaniesResponse(BaseModel):
    companies: List[LLMCompany] = Field(default_factory=list)


class Concept(BaseModel):
    id: str
    createdAt: datetime
    updatedAt: datetime
    idea: str
    productName: str
    websiteUrl: Optional[str] = None
    overview: Optional[str] = None
    targetIndustries: List[str] = Field(default_factory=list)
    targetEndUsers: List[str] = Field(default_factory=list)
    businessNatures: List["BusinessNature"] = Field(default_factory=list)
    companies: List["Company"] = Field(default_factory=list)


class BusinessNature(BaseModel):
    id: str
    createdAt: datetime
    updatedAt: datetime
    name: str
    description: Optional[str] = None


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """Validate the x-api-key header if API_KEY is configured.

    If API_KEY is not set in the environment, the check is skipped (useful for local dev).
    """
    if not API_KEY:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


@app.get("/")
async def api_info():
    return {
        "service": "Company Search API",
        "version": "0.1.0",
        "endpoints": ["/health", "/search", "/chat"],
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "groq_key_present": bool(os.getenv("GROQ_API_KEY")),
        "tavily_key_present": bool(os.getenv("TAVILY_API_KEY")),
    }


@app.post("/search", dependencies=[Depends(require_api_key)])
async def search(company: Company, concept: Concept):
    return run_graph(company, concept)["companies"]


class GraphState(TypedDict, total=False):
    company: Company
    concept: Concept
    search_results: List[dict]
    companies: List[LLMCompany]


def raw_search_companies(state: "GraphState") -> dict:
    company = state["company"]
    concept = state["concept"]

    # Step 1: Initial broad search to identify similar companies
    search_query = (
        f"companies similar to {company.name} with {company.personalNote} and "
        f"related to {company.tags} that are in the {concept.targetIndustries} industry"
    )
    print(f"Initial search query: {search_query}")

    initial_response = tavily_client.search(
        search_query, max_results=8, search_depth="advanced"
    )

    search_results = [
        {
            "title": result.get("title", ""),
            "content": result.get("content", ""),
            "url": result.get("url", ""),
            "published_date": result.get("published_date", ""),
        }
        for result in initial_response.get("results", [])
    ]

    return {"search_results": search_results}


def process_search_results(state: "GraphState") -> dict:
    company = state["company"]
    concept = state["concept"]
    search_results = state.get("search_results", [])

    model = init_chat_model(
        model=GROQ_MODEL,
        model_provider="groq",
        api_key=GROQ_API_KEY,
        temperature=0,
    ).with_structured_output(CompaniesResponse)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "Based on the search result provided as a whole, list 5 "
                    "companies similar to {company_name} with {company_personal_note} "
                    "and related to {company_tags} that are in the "
                    "{concept_target_industries} industry"
                ),
            ),
            ("user", "{search_results}"),
        ]
    )
    response = (prompt | model).invoke(
        {
            "company_name": company.name,
            "company_personal_note": company.personalNote,
            "company_tags": company.tags,
            "concept_target_industries": concept.targetIndustries,
            "search_results": search_results,
        }
    )
    return {"companies": response.companies}


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("search", raw_search_companies)
    graph.add_node("process", process_search_results)
    graph.add_edge(START, "search")
    graph.add_edge("search", "process")
    graph.add_edge("process", END)
    return graph.compile()


def run_graph(company: Company, concept: Concept) -> dict:
    compiled_graph = build_graph()
    result = compiled_graph.invoke({"company": company, "concept": concept})
    print(result)
    return result


if __name__ == "__main__":
    pass
