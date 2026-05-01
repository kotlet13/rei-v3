from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rei.engine import ReiEngine
from rei.knowledge import KnowledgeIndex
from rei.models import ProviderSelection, REICycleRequest, REICycleResponse, SimulateRequest, SimulateResponse
from rei.providers import LMStudioProvider, OllamaProvider


ROOT_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_PATH = ROOT_DIR / "knowledge" / "rei_knowledge_index.json"

knowledge = KnowledgeIndex(KNOWLEDGE_PATH)
ollama = OllamaProvider()
lmstudio = LMStudioProvider()
engine = ReiEngine(knowledge=knowledge, ollama=ollama, lmstudio=lmstudio)

app = FastAPI(title="REI PoC API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health() -> dict[str, object]:
    return {"status": "ok", "knowledge": KNOWLEDGE_PATH.exists()}


@app.get("/api/v1/minds")
def minds() -> dict[str, object]:
    return {"minds": [mind.model_dump(mode="json") for mind in knowledge.minds]}


@app.get("/api/v1/characters")
def characters() -> dict[str, object]:
    return {"characters": [character.model_dump(mode="json") for character in knowledge.characters]}


@app.get("/api/v1/providers")
def providers() -> dict[str, object]:
    ollama_models = ollama.list_models()
    lmstudio_models = lmstudio.list_models()
    return {
        "default": ProviderSelection().model_dump(mode="json"),
        "ollama": {
            "available": bool(ollama_models),
            "models": ollama_models,
            "recommended": {
                "R": "qwen3.5:9b",
                "E": "qwen3.5:9b",
                "I": "qwen3.5:9b",
                "S": "qwen3.5:9b",
            },
        },
        "lmstudio": {
            "available": bool(lmstudio_models),
            "models": lmstudio_models,
            "recommended": {
                "R": "qwen/qwen3.5-9b",
                "E": "qwen/qwen3.5-9b",
                "I": "qwen/qwen3.5-9b",
                "S": "qwen/qwen3.5-9b",
            },
        },
    }


@app.post("/api/v1/simulate", response_model=SimulateResponse)
def simulate(request: SimulateRequest) -> SimulateResponse:
    trace, diagnostics = engine.simulate(
        scenario=request.scenario,
        psyche_state=request.psyche_state,
        provider=request.provider,
    )
    return SimulateResponse(trace=trace, diagnostics=diagnostics)


@app.post("/api/v1/rei-cycle", response_model=REICycleResponse)
def rei_cycle(request: REICycleRequest) -> REICycleResponse:
    response, _diagnostics = engine.run_rei_cycle(
        user_prompt=request.scenario.prompt,
        character_profile=request.character_profile,
        acceptance_mode=request.acceptance_mode,
        rounds=request.rounds,
        stream=request.stream,
        use_memory=request.use_memory,
        provider=request.provider,
    )
    return response
