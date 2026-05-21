import type {
  ObservationSummary,
  PlaygroundRequest,
  PlaygroundRunResponse,
  ProfileId,
  ProviderPayload,
  RuntimeManifest,
  StreamEvent,
} from "./types";

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

export async function getProviders(): Promise<ProviderPayload> {
  return request<ProviderPayload>("/api/v1/providers");
}

export async function getRuntimeManifest(): Promise<RuntimeManifest> {
  return request<RuntimeManifest>("/api/v1/version");
}

export async function getProfiles(): Promise<{ profiles: ProfileId[]; safety_framing: string }> {
  return request<{ profiles: ProfileId[]; safety_framing: string }>("/api/v1/playground/profiles");
}

export async function getObservations(): Promise<{ observations: ObservationSummary[]; safety_framing: string }> {
  return request<{ observations: ObservationSummary[]; safety_framing: string }>("/api/v1/playground/observations");
}

export async function getObservation(id: string): Promise<PlaygroundRunResponse> {
  return request<PlaygroundRunResponse>(`/api/v1/playground/observations/${encodeURIComponent(id)}`);
}

export async function runPlayground(payload: PlaygroundRequest): Promise<PlaygroundRunResponse> {
  return request<PlaygroundRunResponse>("/api/v1/playground/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function streamPlayground(
  payload: PlaygroundRequest,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/playground/run-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  if (!response.body) {
    throw new Error("Streaming response has no readable body.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split(/\n\n/);
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const parsed = parseSseBlock(block);
      if (parsed) onEvent(parsed);
    }
  }

  buffer += decoder.decode();
  const parsed = parseSseBlock(buffer);
  if (parsed) onEvent(parsed);
}

function parseSseBlock(block: string): StreamEvent | null {
  if (!block.trim()) return null;
  let event = "message";
  const data: string[] = [];
  for (const line of block.split(/\n/)) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      data.push(line.slice("data:".length).trimStart());
    }
  }
  if (!data.length) return null;
  try {
    return { event, data: JSON.parse(data.join("\n")) } as StreamEvent;
  } catch {
    return null;
  }
}

export { API_BASE };
