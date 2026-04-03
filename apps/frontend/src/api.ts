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
