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

export async function searchOpportunities(
  personId: string,
  query: string,
  maxResults = 6
): Promise<{ items: SearchResult[]; warnings: string[] }> {
  const response = await fetch(`${API_BASE}/persons/${personId}/search`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, max_results: maxResults })
  });
  return parseResponse<{ items: SearchResult[]; warnings: string[] }>(response);
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
): Promise<{
  opportunity: Opportunity;
  analysis_text: string;
  cultural_confidence: string;
  cultural_warnings: string[];
  cultural_signals: CulturalSignal[];
  semantic_evidence: SemanticEvidence;
}> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/${opportunityId}/analyze`,
    {
      method: "POST",
      credentials: "include"
    }
  );
  return parseResponse<{
    opportunity: Opportunity;
    analysis_text: string;
    cultural_confidence: string;
    cultural_warnings: string[];
    cultural_signals: CulturalSignal[];
    semantic_evidence: SemanticEvidence;
  }>(response);
}

export async function prepareOpportunity(
  personId: string,
  opportunityId: string
): Promise<{
  opportunity: Opportunity;
  guidance_text: string;
  artifacts: ApplicationArtifact[];
  semantic_evidence: SemanticEvidence;
}> {
  const response = await fetch(
    `${API_BASE}/persons/${personId}/opportunities/${opportunityId}/prepare`,
    {
      method: "POST",
      credentials: "include"
    }
  );
  return parseResponse<{
    opportunity: Opportunity;
    guidance_text: string;
    artifacts: ApplicationArtifact[];
    semantic_evidence: SemanticEvidence;
  }>(response);
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
