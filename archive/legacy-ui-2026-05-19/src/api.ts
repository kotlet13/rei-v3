import type { CharacterDefinition, REICycleRequest, REICycleResponse, SimulateRequest, SimulateResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8010";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  return response.json() as Promise<T>;
}

export async function getCharacters(): Promise<CharacterDefinition[]> {
  const payload = await request<{ characters: CharacterDefinition[] }>("/api/v1/characters");
  return payload.characters;
}

export async function getProviders(): Promise<{
  default: Record<string, unknown>;
  ollama: { available: boolean; models: string[]; recommended: Record<string, string> };
  lmstudio: { available: boolean; models: string[]; recommended: Record<string, string> };
}> {
  return request("/api/v1/providers");
}

export async function simulate(payload: SimulateRequest): Promise<SimulateResponse> {
  return request<SimulateResponse>("/api/v1/simulate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function runReiCycle(payload: REICycleRequest): Promise<REICycleResponse> {
  return request<REICycleResponse>("/api/v1/rei-cycle", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export { API_BASE };
