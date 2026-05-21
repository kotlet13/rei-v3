from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from rei.engine import ReiEngine
from rei.knowledge import KnowledgeIndex
from rei.models import ProviderSelection, REICycleRequest, REICycleResponse, SimulateRequest, SimulateResponse
from rei.playground import (
    PLAYGROUND_PROFILES,
    PlaygroundRequest,
    PlaygroundRunResponse,
    SAFETY_FRAMING,
    build_playground_response,
    load_observation,
    list_observations,
    stream_playground_response,
)
from rei.providers import LMStudioProvider, OllamaProvider
from rei.version_manifest import PROJECT_VERSION, runtime_manifest


ROOT_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_PATH = ROOT_DIR / "knowledge" / "rei_knowledge_index.json"

knowledge = KnowledgeIndex(KNOWLEDGE_PATH)
ollama = OllamaProvider()
lmstudio = LMStudioProvider()
engine = ReiEngine(knowledge=knowledge, ollama=ollama, lmstudio=lmstudio)

app = FastAPI(title="REI PoC API", version=PROJECT_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health() -> dict[str, object]:
    manifest = runtime_manifest()
    project = manifest["project"]
    return {
        "status": "ok",
        "knowledge": KNOWLEDGE_PATH.exists(),
        "active_stack_id": project["active_stack_id"],
        "project_version": project["version"],
    }


@app.get("/api/v1/version")
def version() -> dict[str, object]:
    return runtime_manifest()


@app.get("/api/v1/minds", deprecated=True)
def minds() -> dict[str, object]:
    return {"minds": [mind.model_dump(mode="json") for mind in knowledge.minds]}


@app.get("/api/v1/characters", deprecated=True)
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


@app.post("/api/v1/simulate", response_model=SimulateResponse, deprecated=True)
def simulate(request: SimulateRequest) -> SimulateResponse:
    trace, diagnostics = engine.simulate(
        scenario=request.scenario,
        psyche_state=request.psyche_state,
        provider=request.provider,
    )
    return SimulateResponse(trace=trace, diagnostics=diagnostics)


@app.post("/api/v1/rei-cycle", response_model=REICycleResponse, deprecated=True)
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


@app.get("/api/v1/playground/profiles")
def playground_profiles() -> dict[str, object]:
    return {"profiles": PLAYGROUND_PROFILES, "safety_framing": SAFETY_FRAMING}


@app.post("/api/v1/playground/run", response_model=PlaygroundRunResponse)
def playground_run(request: PlaygroundRequest) -> PlaygroundRunResponse:
    return build_playground_response(engine=engine, request=request, root_dir=ROOT_DIR)


@app.post("/api/v1/playground/run-stream")
def playground_run_stream(request: PlaygroundRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_playground_response(knowledge=knowledge, request=request, root_dir=ROOT_DIR),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/v1/playground/observations")
def playground_observations() -> dict[str, object]:
    return {"observations": list_observations(ROOT_DIR), "safety_framing": SAFETY_FRAMING}


@app.get("/api/v1/playground/observations/{observation_id}")
def playground_observation(observation_id: str) -> dict[str, object]:
    try:
        return load_observation(ROOT_DIR, observation_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Observation not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid observation id") from exc
