export type Session = {
  authenticated: boolean;
  username: string;
  expires_at: string;
};

export type Person = {
  person_id: string;
  full_name: string;
  target_roles: string[];
  location: string;
  years_experience: number;
  skills: string[];
  culture_preferences: string[];
  cultural_fit_preferences: Record<string, CulturalFieldPreference>;
  culture_preferences_notes: string;
  created_at: string;
  updated_at: string;
};

export type CulturalFieldPreference = {
  enabled: boolean;
  selected_values: string[];
  criticality: "normal" | "high_penalty" | "non_negotiable";
};

export type ConversationMessage = {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type Conversation = {
  conversation_id: string;
  person_id: string;
  status: string;
  last_message_at: string;
  messages: ConversationMessage[];
};

export type SearchResult = {
  search_result_id: string;
  source_provider: string;
  source_url: string;
  title: string;
  company: string;
  location: string;
  snippet: string;
  captured_at: string;
  normalized_payload: Record<string, unknown>;
};

export type SearchProviderStatus = {
  provider_key: "adzuna" | "remotive" | "tavily";
  enabled: boolean;
  attempted: boolean;
  status: "ok" | "error" | "skipped";
  reason: string;
  results_count: number;
  query_truncated?: boolean;
};

export type Opportunity = {
  opportunity_id: string;
  person_id: string;
  source_type: string;
  source_provider: string;
  source_url: string;
  title: string;
  company: string;
  location: string;
  status: string;
  notes: string;
  snapshot_raw_text: string;
  snapshot_payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ApplicationArtifact = {
  artifact_id: string;
  person_id: string;
  opportunity_id: string;
  artifact_type: "cover_letter" | "experience_summary";
  content: string;
  is_current: boolean;
  created_at: string;
  updated_at: string;
};

export type AIRun = {
  run_id: string;
  person_id: string;
  opportunity_id: string;
  action_key: string;
  result_payload: Record<string, unknown>;
  is_current: boolean;
  created_at: string;
  updated_at: string;
};

export type CulturalSignal = {
  source_provider: string;
  source_url: string;
  title: string;
  snippet: string;
  captured_at: string;
};

export type SemanticEvidence = {
  source: string;
  query: string;
  top_k: number;
  snippets: string[];
};

export type AnalyzeOpportunityPayload = {
  opportunity: Opportunity;
  analysis_text: string;
  cultural_confidence: string;
  cultural_warnings: string[];
  cultural_signals: CulturalSignal[];
  semantic_evidence: SemanticEvidence;
};

export type AnalyzeProfileMatchPayload = {
  opportunity: Opportunity;
  analysis_text: string;
  semantic_evidence: SemanticEvidence;
  served_from_cache: boolean;
};

export type AnalyzeCulturalFitPayload = {
  opportunity: Opportunity;
  analysis_text: string;
  cultural_confidence: string;
  cultural_warnings: string[];
  cultural_signals: CulturalSignal[];
  served_from_cache: boolean;
};

export type PrepareOpportunityPayload = {
  opportunity: Opportunity;
  guidance_text: string;
  artifacts: ApplicationArtifact[];
  semantic_evidence: SemanticEvidence;
  served_from_cache: boolean;
};

export type ActiveCV = {
  cv_id: string;
  person_id: string;
  source_filename: string;
  mime_type: string;
  extraction_status: string;
  vector_index_status: string;
  vector_chunks_indexed: number;
  vector_last_indexed_at: string;
  text_length: number;
  text_truncated: boolean;
  extracted_text_preview: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type PromptConfig = {
  config_id: string;
  scope: string;
  flow_key: string;
  template_text: string;
  target_sources: string[];
  is_active: boolean;
  updated_by: string;
  created_at: string;
  updated_at: string;
};

export type PromptConfigVersion = {
  version_id: string;
  flow_key: string;
  template_text: string;
  target_sources: string[];
  is_active: boolean;
  source_updated_by: string;
  source_updated_at: string;
  reason: string;
  created_by: string;
  created_at: string;
};

export type RequestTrace = {
  trace_id: string;
  person_id: string;
  opportunity_id: string;
  run_id: string;
  destination: string;
  flow_key: string;
  request_payload: Record<string, unknown>;
  created_at: string;
};

export type SearchProviderConfig = {
  provider_key: "adzuna" | "remotive" | "tavily";
  is_enabled: boolean;
  updated_by: string;
  created_at: string;
  updated_at: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // Ignore parsing errors and keep default message.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function getSession(): Promise<Session> {
  const response = await fetch(`${API_BASE}/auth/session`, {
    method: "GET",
    credentials: "include"
  });
  return parseResponse<Session>(response);
}

export async function login(username: string, password: string): Promise<Session> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  });
  return parseResponse<Session>(response);
}

export async function logout(): Promise<void> {
  const response = await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    credentials: "include"
  });
  if (!response.ok) {
    throw new Error(`Logout failed: ${response.status}`);
  }
}

export async function listPersons(): Promise<Person[]> {
  const response = await fetch(`${API_BASE}/persons`, {
    method: "GET",
    credentials: "include"
  });
  const payload = await parseResponse<{ items: Person[] }>(response);
  return payload.items;
}

export async function listRequestTraces(
  personId: string,
  params?: { opportunityId?: string; destination?: string; runId?: string; limit?: number }
): Promise<RequestTrace[]> {
  const query = new URLSearchParams();
  if (params?.opportunityId?.trim()) {
    query.set("opportunity_id", params.opportunityId.trim());
  }
  if (params?.destination?.trim()) {
    query.set("destination", params.destination.trim().toLowerCase());
  }
  if (params?.runId?.trim()) {
    query.set("run_id", params.runId.trim());
  }
  if (typeof params?.limit === "number" && Number.isFinite(params.limit)) {
    query.set("limit", String(Math.max(1, Math.min(200, Math.trunc(params.limit)))));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  const response = await fetch(`${API_BASE}/persons/${personId}/request-traces${suffix}`, {
    method: "GET",
    credentials: "include"
  });
  const payload = await parseResponse<{ items: RequestTrace[] }>(response);
  return payload.items;
}

export async function listSearchProviderConfigs(): Promise<SearchProviderConfig[]> {
  const response = await fetch(`${API_BASE}/admin/search-providers`, {
    method: "GET",
    credentials: "include"
  });
  const payload = await parseResponse<{ items: SearchProviderConfig[] }>(response);
  return payload.items;
}

export async function updateSearchProviderConfig(
  providerKey: "adzuna" | "remotive" | "tavily",
  isEnabled: boolean
): Promise<SearchProviderConfig> {
  const response = await fetch(`${API_BASE}/admin/search-providers/${providerKey}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_enabled: isEnabled })
  });
  return parseResponse<SearchProviderConfig>(response);
}

export async function createPerson(payload: {
  full_name: string;
  target_roles: string[];
  location: string;
  years_experience: number;
  skills: string[];
}): Promise<Person> {
  const response = await fetch(`${API_BASE}/persons`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseResponse<Person>(response);
}

export async function updatePerson(
  personId: string,
  payload: {
    full_name?: string;
    target_roles?: string[];
    location?: string;
    years_experience?: number;
    skills?: string[];
    culture_preferences?: string[];
    cultural_fit_preferences?: Record<string, CulturalFieldPreference>;
    culture_preferences_notes?: string;
  }
): Promise<Person> {
  const response = await fetch(`${API_BASE}/persons/${personId}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseResponse<Person>(response);
}

export async function listPromptConfigs(): Promise<PromptConfig[]> {
  const response = await fetch(`${API_BASE}/admin/prompt-configs`, {
    method: "GET",
    credentials: "include"
  });
  const payload = await parseResponse<{ items: PromptConfig[] }>(response);
  return payload.items;
}

export async function updatePromptConfig(
  flowKey: string,
  payload: {
    template_text?: string;
    target_sources?: string[];
    is_active?: boolean;
  }
): Promise<PromptConfig> {
  const response = await fetch(`${API_BASE}/admin/prompt-configs/${flowKey}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseResponse<PromptConfig>(response);
}

export async function listPromptConfigVersions(
  flowKey: string,
  limit = 20
): Promise<PromptConfigVersion[]> {
  const params = new URLSearchParams();
  params.set("limit", String(Math.max(1, Math.min(100, Math.trunc(limit)))));
  const response = await fetch(
    `${API_BASE}/admin/prompt-configs/${flowKey}/versions?${params.toString()}`,
    {
      method: "GET",
      credentials: "include"
    }
  );
  const payload = await parseResponse<{ items: PromptConfigVersion[] }>(response);
  return payload.items;
}

export async function rollbackPromptConfig(
  flowKey: string,
  versionId: string
): Promise<PromptConfig> {
  const response = await fetch(`${API_BASE}/admin/prompt-configs/${flowKey}/rollback`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ version_id: versionId })
  });
  return parseResponse<PromptConfig>(response);
}

export async function getActiveCV(personId: string): Promise<ActiveCV | null> {
  const response = await fetch(`${API_BASE}/persons/${personId}/cv/active`, {
    method: "GET",
    credentials: "include"
  });
  if (response.status === 404) {
    return null;
  }
  return parseResponse<ActiveCV>(response);
}

export async function uploadCV(personId: string, file: File): Promise<ActiveCV> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/persons/${personId}/cv`, {
    method: "POST",
    credentials: "include",
    body: form
  });
  return parseResponse<ActiveCV>(response);
}

export async function getConversation(personId: string): Promise<Conversation> {
  const response = await fetch(`${API_BASE}/persons/${personId}/chat/conversation`, {
    method: "GET",
    credentials: "include"
  });
  return parseResponse<Conversation>(response);
}

export async function sendMessage(
  personId: string,
  message: string
): Promise<Conversation> {
  const response = await fetch(`${API_BASE}/persons/${personId}/chat`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message })
  });
  const payload = await parseResponse<{ conversation: Conversation }>(response);
  return payload.conversation;
}

type StreamEventHandler = (eventName: string, payload: Record<string, unknown>) => void;

function consumeSseBuffer(
  chunk: string,
  onEvent: StreamEventHandler
): { remainder: string } {
  let buffer = chunk;
  let separatorIndex = buffer.indexOf("\n\n");
  while (separatorIndex >= 0) {
    const rawEvent = buffer.slice(0, separatorIndex);
    buffer = buffer.slice(separatorIndex + 2);

    const lines = rawEvent.split("\n");
    let eventName = "";
    let dataText = "";
    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.slice("event:".length).trim();
      } else if (line.startsWith("data:")) {
        dataText += `${line.slice("data:".length).trim()}\n`;
      }
    }
    dataText = dataText.trim();
    if (!eventName || !dataText) {
      separatorIndex = buffer.indexOf("\n\n");
      continue;
    }

    try {
      const payload = JSON.parse(dataText) as Record<string, unknown>;
      if (eventName === "error") {
        const detail =
          typeof payload.detail === "string" && payload.detail.trim()
            ? payload.detail
            : "Stream error";
        throw new Error(detail);
      }
      onEvent(eventName, payload);
    } catch (error) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error("Invalid SSE payload");
    }

    separatorIndex = buffer.indexOf("\n\n");
  }
  return { remainder: buffer };
}

export async function sendMessageStream(
  personId: string,
  message: string,
  onDelta: (delta: string) => void
): Promise<Conversation> {
  const response = await fetch(`${API_BASE}/persons/${personId}/chat/stream`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message })
  });
  if (!response.ok) {
    let messageText = `Request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        messageText = payload.detail;
      }
    } catch {
      // Ignore parsing errors for stream setup failures.
    }
    throw new Error(messageText);
  }

  if (!response.body) {
    throw new Error("Streaming response body is empty");
  }

  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  let pending = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    pending += decoder.decode(value, { stream: true });
    const consumed = consumeSseBuffer(pending, (eventName, payload) => {
      if (eventName !== "message_delta") {
        return;
      }
      const delta = payload.delta;
      if (typeof delta === "string" && delta.length > 0) {
        onDelta(delta);
      }
    });
    pending = consumed.remainder;
  }

  if (pending.trim()) {
    consumeSseBuffer(`${pending}\n\n`, (eventName, payload) => {
      if (eventName !== "message_delta") {
        return;
      }
      const delta = payload.delta;
      if (typeof delta === "string" && delta.length > 0) {
        onDelta(delta);
      }
    });
  }
  return getConversation(personId);
}

export async function searchOpportunities(
  personId: string,
  query: string,
  maxResults = 6
): Promise<{ items: SearchResult[]; warnings: string[]; provider_status: SearchProviderStatus[] }> {
  const response = await fetch(`${API_BASE}/persons/${personId}/search`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, max_results: maxResults })
  });
  return parseResponse<{
    items: SearchResult[];
    warnings: string[];
    provider_status: SearchProviderStatus[];
  }>(response);
}

export async function saveOpportunityFromSearch(
  personId: string,
  result: SearchResult
): Promise<{ item: Opportunity; created: boolean }> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/from-search`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_provider: result.source_provider,
        source_url: result.source_url,
        title: result.title,
        company: result.company,
        location: result.location,
        snippet: result.snippet,
        normalized_payload: result.normalized_payload
      })
    }
  );
  return parseResponse<{ item: Opportunity; created: boolean }>(response);
}

export async function listOpportunities(personId: string): Promise<Opportunity[]> {
  const response = await fetch(`${API_BASE}/persons/${personId}/opportunities`, {
    method: "GET",
    credentials: "include"
  });
  const payload = await parseResponse<{ items: Opportunity[] }>(response);
  return payload.items;
}

export async function updateOpportunity(
  personId: string,
  opportunityId: string,
  payload: { status?: string; notes?: string }
): Promise<Opportunity> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/${opportunityId}`,
    {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
  return parseResponse<Opportunity>(response);
}

export async function analyzeOpportunity(
  personId: string,
  opportunityId: string
): Promise<AnalyzeOpportunityPayload> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/${opportunityId}/analyze`,
    {
      method: "POST",
      credentials: "include"
    }
  );
  return parseResponse<AnalyzeOpportunityPayload>(response);
}

export async function analyzeProfileMatch(
  personId: string,
  opportunityId: string,
  forceRecompute: boolean
): Promise<AnalyzeProfileMatchPayload> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/${opportunityId}/analyze/profile-match`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force_recompute: forceRecompute })
    }
  );
  return parseResponse<AnalyzeProfileMatchPayload>(response);
}

export async function analyzeCulturalFit(
  personId: string,
  opportunityId: string,
  forceRecompute: boolean
): Promise<AnalyzeCulturalFitPayload> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/${opportunityId}/analyze/cultural-fit`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force_recompute: forceRecompute })
    }
  );
  return parseResponse<AnalyzeCulturalFitPayload>(response);
}

export async function prepareOpportunity(
  personId: string,
  opportunityId: string,
  payload: { targets: Array<"guidance_text" | "cover_letter" | "experience_summary">; force_recompute: boolean }
): Promise<PrepareOpportunityPayload> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/${opportunityId}/prepare`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
  return parseResponse<PrepareOpportunityPayload>(response);
}

export async function analyzeOpportunityStream(
  personId: string,
  opportunityId: string,
  onDelta: (delta: string) => void
): Promise<AnalyzeOpportunityPayload> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/${opportunityId}/analyze/stream`,
    {
      method: "POST",
      credentials: "include"
    }
  );
  if (!response.ok) {
    let messageText = `Request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        messageText = payload.detail;
      }
    } catch {
      // Ignore parsing errors for stream setup failures.
    }
    throw new Error(messageText);
  }
  if (!response.body) {
    throw new Error("Streaming response body is empty");
  }

  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  let pending = "";
  let completedPayload: AnalyzeOpportunityPayload | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    pending += decoder.decode(value, { stream: true });
    const consumed = consumeSseBuffer(pending, (eventName, payload) => {
      if (eventName === "message_delta") {
        const delta = payload.delta;
        const channel = payload.channel;
        if (channel === "analysis_text" && typeof delta === "string" && delta.length > 0) {
          onDelta(delta);
        }
      } else if (eventName === "message_complete") {
        completedPayload = payload as unknown as AnalyzeOpportunityPayload;
      }
    });
    pending = consumed.remainder;
  }
  if (pending.trim()) {
    consumeSseBuffer(`${pending}\n\n`, (eventName, payload) => {
      if (eventName === "message_delta") {
        const delta = payload.delta;
        const channel = payload.channel;
        if (channel === "analysis_text" && typeof delta === "string" && delta.length > 0) {
          onDelta(delta);
        }
      } else if (eventName === "message_complete") {
        completedPayload = payload as unknown as AnalyzeOpportunityPayload;
      }
    });
  }

  if (!completedPayload) {
    throw new Error("Analyze stream ended without completion payload");
  }
  return completedPayload;
}

export async function analyzeProfileMatchStream(
  personId: string,
  opportunityId: string,
  forceRecompute: boolean,
  onDelta: (delta: string) => void
): Promise<AnalyzeProfileMatchPayload> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/${opportunityId}/analyze/profile-match/stream`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force_recompute: forceRecompute })
    }
  );
  if (!response.ok) {
    let messageText = `Request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        messageText = payload.detail;
      }
    } catch {
      // Ignore parsing errors for stream setup failures.
    }
    throw new Error(messageText);
  }
  if (!response.body) {
    throw new Error("Streaming response body is empty");
  }

  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  let pending = "";
  let completedPayload: AnalyzeProfileMatchPayload | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    pending += decoder.decode(value, { stream: true });
    const consumed = consumeSseBuffer(pending, (eventName, payload) => {
      if (eventName === "message_delta") {
        const delta = payload.delta;
        const channel = payload.channel;
        if (channel === "analysis_text" && typeof delta === "string" && delta.length > 0) {
          onDelta(delta);
        }
      } else if (eventName === "message_complete") {
        completedPayload = payload as unknown as AnalyzeProfileMatchPayload;
      }
    });
    pending = consumed.remainder;
  }
  if (pending.trim()) {
    consumeSseBuffer(`${pending}\n\n`, (eventName, payload) => {
      if (eventName === "message_delta") {
        const delta = payload.delta;
        const channel = payload.channel;
        if (channel === "analysis_text" && typeof delta === "string" && delta.length > 0) {
          onDelta(delta);
        }
      } else if (eventName === "message_complete") {
        completedPayload = payload as unknown as AnalyzeProfileMatchPayload;
      }
    });
  }
  if (!completedPayload) {
    throw new Error("Analyze profile-match stream ended without completion payload");
  }
  return completedPayload;
}

export async function analyzeCulturalFitStream(
  personId: string,
  opportunityId: string,
  forceRecompute: boolean,
  onDelta: (delta: string) => void
): Promise<AnalyzeCulturalFitPayload> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/${opportunityId}/analyze/cultural-fit/stream`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force_recompute: forceRecompute })
    }
  );
  if (!response.ok) {
    let messageText = `Request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        messageText = payload.detail;
      }
    } catch {
      // Ignore parsing errors for stream setup failures.
    }
    throw new Error(messageText);
  }
  if (!response.body) {
    throw new Error("Streaming response body is empty");
  }

  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  let pending = "";
  let completedPayload: AnalyzeCulturalFitPayload | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    pending += decoder.decode(value, { stream: true });
    const consumed = consumeSseBuffer(pending, (eventName, payload) => {
      if (eventName === "message_delta") {
        const delta = payload.delta;
        const channel = payload.channel;
        if (channel === "analysis_text" && typeof delta === "string" && delta.length > 0) {
          onDelta(delta);
        }
      } else if (eventName === "message_complete") {
        completedPayload = payload as unknown as AnalyzeCulturalFitPayload;
      }
    });
    pending = consumed.remainder;
  }
  if (pending.trim()) {
    consumeSseBuffer(`${pending}\n\n`, (eventName, payload) => {
      if (eventName === "message_delta") {
        const delta = payload.delta;
        const channel = payload.channel;
        if (channel === "analysis_text" && typeof delta === "string" && delta.length > 0) {
          onDelta(delta);
        }
      } else if (eventName === "message_complete") {
        completedPayload = payload as unknown as AnalyzeCulturalFitPayload;
      }
    });
  }
  if (!completedPayload) {
    throw new Error("Analyze cultural-fit stream ended without completion payload");
  }
  return completedPayload;
}

export async function prepareOpportunityStream(
  personId: string,
  opportunityId: string,
  payload: { targets: Array<"guidance_text" | "cover_letter" | "experience_summary">; force_recompute: boolean },
  onDelta: (channel: "guidance_text" | "cover_letter" | "experience_summary", delta: string) => void
): Promise<PrepareOpportunityPayload> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/${opportunityId}/prepare/stream`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
  if (!response.ok) {
    let messageText = `Request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        messageText = payload.detail;
      }
    } catch {
      // Ignore parsing errors for stream setup failures.
    }
    throw new Error(messageText);
  }
  if (!response.body) {
    throw new Error("Streaming response body is empty");
  }

  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  let pending = "";
  let completedPayload: PrepareOpportunityPayload | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    pending += decoder.decode(value, { stream: true });
    const consumed = consumeSseBuffer(pending, (eventName, payload) => {
      if (eventName === "message_delta") {
        const delta = payload.delta;
        const channel = payload.channel;
        if (
          (channel === "guidance_text" ||
            channel === "cover_letter" ||
            channel === "experience_summary") &&
          typeof delta === "string" &&
          delta.length > 0
        ) {
          onDelta(channel, delta);
        }
      } else if (eventName === "message_complete") {
        completedPayload = payload as unknown as PrepareOpportunityPayload;
      }
    });
    pending = consumed.remainder;
  }
  if (pending.trim()) {
    consumeSseBuffer(`${pending}\n\n`, (eventName, payload) => {
      if (eventName === "message_delta") {
        const delta = payload.delta;
        const channel = payload.channel;
        if (
          (channel === "guidance_text" ||
            channel === "cover_letter" ||
            channel === "experience_summary") &&
          typeof delta === "string" &&
          delta.length > 0
        ) {
          onDelta(channel, delta);
        }
      } else if (eventName === "message_complete") {
        completedPayload = payload as unknown as PrepareOpportunityPayload;
      }
    });
  }

  if (!completedPayload) {
    throw new Error("Prepare stream ended without completion payload");
  }
  return completedPayload;
}

export async function listOpportunityArtifacts(
  personId: string,
  opportunityId: string
): Promise<ApplicationArtifact[]> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/${opportunityId}/artifacts`,
    {
      method: "GET",
      credentials: "include"
    }
  );
  const payload = await parseResponse<{ items: ApplicationArtifact[] }>(response);
  return payload.items;
}

export async function listOpportunityAiRuns(
  personId: string,
  opportunityId: string,
  actionKey?: string
): Promise<AIRun[]> {
  const params = new URLSearchParams();
  if (actionKey && actionKey.trim()) {
    params.set("action_key", actionKey.trim());
  }
  const querySuffix = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/${opportunityId}/ai-runs${querySuffix}`,
    {
      method: "GET",
      credentials: "include"
    }
  );
  const payload = await parseResponse<{ items: AIRun[] }>(response);
  return payload.items;
}

export async function importOpportunityByUrl(
  personId: string,
  payload: {
    source_url: string;
    title?: string;
    company?: string;
    location?: string;
    raw_text?: string;
  }
): Promise<{ item: Opportunity; created: boolean }> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/import-url`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
  return parseResponse<{ item: Opportunity; created: boolean }>(response);
}

export async function importOpportunityByText(
  personId: string,
  payload: {
    title: string;
    company?: string;
    location?: string;
    raw_text: string;
  }
): Promise<Opportunity> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/import-text`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
  return parseResponse<Opportunity>(response);
}
