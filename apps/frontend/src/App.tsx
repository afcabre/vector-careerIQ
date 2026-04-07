import { FormEvent, useEffect, useState } from "react";

import {
  AIRun,
  ActiveCV,
  ApplicationArtifact,
  Conversation,
  CulturalFieldPreference,
  CulturalSignal,
  Opportunity,
  Person,
  PromptConfig,
  PromptConfigVersion,
  RequestTrace,
  SearchProviderConfig,
  SearchProviderStatus,
  SearchResult,
  SemanticEvidence,
  analyzeCulturalFitStream,
  analyzeProfileMatchStream,
  analyzeCulturalFit,
  analyzeProfileMatch,
  createPerson,
  getConversation,
  getActiveCV,
  getActiveCVText,
  getSession,
  importOpportunityByUrl,
  listOpportunityAiRuns,
  listOpportunityArtifacts,
  listOpportunities,
  listPersons,
  listPromptConfigs,
  listPromptConfigVersions,
  listSearchProviderConfigs,
  listRequestTraces,
  login,
  logout,
  prepareOpportunityStream,
  prepareOpportunity,
  saveOpportunityFromSearch,
  searchOpportunities,
  sendMessage,
  sendMessageStream,
  rollbackPromptConfig as rollbackPromptConfigApi,
  updateSearchProviderConfig as updateSearchProviderConfigApi,
  updatePromptConfig as updatePromptConfigApi,
  updatePerson as updatePersonProfile,
  updateOpportunity,
  uploadCV
} from "./api";

type ViewState = "checking" | "login" | "workspace";
type WorkspacePage = "candidates" | "admin-prompts" | "profile" | "opportunities" | "analysis";
type ParsedWorkspaceRoute = {
  page: WorkspacePage;
  personId: string | null;
};

type ExternalUrlTextProps = {
  url: string | null | undefined;
  noValueText?: string;
};

function parseWorkspacePath(pathname: string): ParsedWorkspaceRoute {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  if (normalized === "/" || normalized === "/candidates") {
    return { page: "candidates", personId: null };
  }
  if (normalized === "/admin/prompts") {
    return { page: "admin-prompts", personId: null };
  }
  const match = normalized.match(/^\/c\/([^/]+)\/(profile|opportunities|analysis)$/);
  if (!match) {
    return { page: "candidates", personId: null };
  }
  const personId = decodeURIComponent(match[1]);
  const page = match[2] as WorkspacePage;
  return { page, personId };
}

function buildContextPath(personId: string, page: "profile" | "opportunities" | "analysis"): string {
  return `/c/${encodeURIComponent(personId)}/${page}`;
}

function toExternalUrl(url: string | null | undefined): string | null {
  const raw = (url ?? "").trim();
  if (!raw) {
    return null;
  }
  if (/^https?:\/\//i.test(raw)) {
    return raw;
  }
  return `https://${raw}`;
}

function ExternalUrlText({ url, noValueText = "URL no disponible" }: ExternalUrlTextProps) {
  const normalizedUrl = toExternalUrl(url);
  const raw = (url ?? "").trim();
  if (!normalizedUrl || !raw) {
    return <>{noValueText}</>;
  }
  return (
    <a className="inlineLink" href={normalizedUrl} rel="noreferrer" target="_blank">
      {raw}
    </a>
  );
}

const OPPORTUNITY_STATUSES = [
  "detected",
  "analyzed",
  "prioritized",
  "application_prepared",
  "applied",
  "discarded"
] as const;

const AI_RUN_ACTION_LABELS: Record<string, string> = {
  analyze_profile_match: "Analizar perfil-vacante",
  analyze_cultural_fit: "Analizar ajuste cultural",
  prepare_guidance_text: "Preparar guia de perfil",
  prepare_cover_letter: "Preparar carta de presentacion",
  prepare_experience_summary: "Preparar resumen de experiencia"
};

const AI_RUN_ACTION_FILTERS: Array<{ value: string; label: string }> = [
  { value: "", label: "Todas las acciones" },
  { value: "analyze_profile_match", label: "Analizar perfil-vacante" },
  { value: "analyze_cultural_fit", label: "Analizar ajuste cultural" },
  { value: "prepare_guidance_text", label: "Preparar guia de perfil" },
  { value: "prepare_cover_letter", label: "Preparar carta de presentacion" },
  { value: "prepare_experience_summary", label: "Preparar resumen de experiencia" }
];

const TRACE_DESTINATION_FILTERS: Array<{ value: string; label: string }> = [
  { value: "", label: "Todos los destinos" },
  { value: "openai", label: "OpenAI" },
  { value: "tavily", label: "Tavily" },
  { value: "adzuna", label: "Adzuna" },
  { value: "remotive", label: "Remotive" }
];

const PROMPT_FLOW_LABELS: Record<string, string> = {
  search_jobs_tavily: "Busqueda de vacantes (Tavily)",
  search_culture_tavily: "Fit cultural (Tavily)",
  guardrails_core: "Guardrails core (global)",
  system_identity: "Identidad del sistema (global)",
  task_chat: "Prompt de tarea: Chat",
  task_analyze_profile_match: "Prompt de tarea: Analizar perfil-vacante",
  task_analyze_cultural_fit: "Prompt de tarea: Analizar ajuste cultural",
  task_prepare_guidance: "Prompt de tarea: Preparar guia de perfil",
  task_prepare_cover_letter: "Prompt de tarea: Preparar carta",
  task_prepare_experience_summary: "Prompt de tarea: Preparar resumen"
};

const PROMPT_FLOW_ORDER: string[] = [
  "search_jobs_tavily",
  "search_culture_tavily",
  "guardrails_core",
  "system_identity",
  "task_chat",
  "task_analyze_profile_match",
  "task_analyze_cultural_fit",
  "task_prepare_guidance",
  "task_prepare_cover_letter",
  "task_prepare_experience_summary"
];
const PROMPT_SOURCE_FLOW_KEYS = new Set(["search_jobs_tavily", "search_culture_tavily"]);
const SEARCH_PROVIDER_LABELS: Record<string, string> = {
  adzuna: "Adzuna (RapidAPI)",
  remotive: "Remotive",
  tavily: "Tavily"
};
const CHAT_QUICK_STARTS = [
  "Resume el perfil actual en fortalezas y posibles brechas para postulacion.",
  "Que 3 vacantes deberia priorizar primero y por que?",
  "Que ajustes minimos recomiendas para mejorar fit con las vacantes activas?"
];

type PromptConfigDraft = {
  template_text: string;
  target_sources_input: string;
  is_active: boolean;
};

const CULTURAL_FIELDS: Array<{
  id: string;
  label: string;
  options: Array<{ value: string; label: string }>;
}> = [
  {
    id: "work_modality",
    label: "Modalidad de trabajo",
    options: [
      { value: "onsite", label: "Presencial" },
      { value: "hybrid", label: "Hibrido" },
      { value: "remote", label: "Remoto" }
    ]
  },
  {
    id: "schedule_flexibility",
    label: "Flexibilidad de horario",
    options: [
      { value: "fixed_schedule", label: "Horario fijo" },
      { value: "partial_flexibility", label: "Flexibilidad parcial" },
      { value: "high_flexibility", label: "Alta flexibilidad" }
    ]
  },
  {
    id: "work_intensity",
    label: "Intensidad laboral",
    options: [
      { value: "low", label: "Baja" },
      { value: "medium", label: "Media" },
      { value: "high", label: "Alta" }
    ]
  },
  {
    id: "environment_predictability",
    label: "Previsibilidad del entorno",
    options: [
      { value: "very_stable", label: "Muy estable" },
      { value: "moderately_stable", label: "Moderadamente estable" },
      { value: "balanced", label: "Balanceado" },
      { value: "moderately_dynamic", label: "Moderadamente dinamico" },
      { value: "very_dynamic", label: "Muy dinamico" }
    ]
  },
  {
    id: "company_scale",
    label: "Escala de empresa",
    options: [
      { value: "local", label: "Local" },
      { value: "regional", label: "Regional" },
      { value: "multilatina", label: "Multilatina" },
      { value: "multinational", label: "Multinacional" },
      { value: "family_owned", label: "Familiar" }
    ]
  },
  {
    id: "organization_structure_level",
    label: "Nivel de estructuracion",
    options: [
      { value: "low", label: "Baja" },
      { value: "medium_low", label: "Media-baja" },
      { value: "medium", label: "Media" },
      { value: "medium_high", label: "Media-alta" },
      { value: "high", label: "Alta" }
    ]
  },
  {
    id: "organizational_moment",
    label: "Momento organizacional",
    options: [
      { value: "consolidated", label: "Consolidada" },
      { value: "transformation", label: "En transformacion" },
      { value: "high_growth", label: "En crecimiento acelerado" },
      { value: "reorganization", label: "En reorganizacion" }
    ]
  },
  {
    id: "cultural_formality",
    label: "Formalidad cultural",
    options: [
      { value: "very_informal", label: "Muy informal" },
      { value: "more_informal", label: "Mas informal" },
      { value: "intermediate", label: "Intermedia" },
      { value: "more_formal", label: "Mas formal" },
      { value: "very_formal", label: "Muy formal" }
    ]
  }
];

function buildDefaultCulturalPreferences(): Record<string, CulturalFieldPreference> {
  const defaults: Record<string, CulturalFieldPreference> = {};
  for (const field of CULTURAL_FIELDS) {
    defaults[field.id] = {
      enabled: false,
      selected_values: [],
      criticality: "normal"
    };
  }
  return defaults;
}

function getPersonInitials(fullName: string): string {
  return fullName
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "NA";
}

function getArtifactTypeLabel(artifactType: string): string {
  if (artifactType === "cover_letter") {
    return "Carta de presentacion";
  }
  if (artifactType === "experience_summary") {
    return "Resumen de experiencia";
  }
  if (artifactType === "guidance_text") {
    return "Guia de perfil";
  }
  return artifactType;
}

function buildPromptConfigDrafts(
  configs: PromptConfig[]
): Record<string, PromptConfigDraft> {
  const drafts: Record<string, PromptConfigDraft> = {};
  for (const config of configs) {
    drafts[config.flow_key] = {
      template_text: config.template_text,
      target_sources_input: config.target_sources.join("\n"),
      is_active: config.is_active
    };
  }
  return drafts;
}

function getAiRunPreviewText(run: AIRun): string {
  const analysisText = run.result_payload["analysis_text"];
  if (typeof analysisText === "string" && analysisText.trim()) {
    return analysisText;
  }
  const content = run.result_payload["content"];
  if (typeof content === "string" && content.trim()) {
    return content;
  }
  return "";
}

function formatAiRunTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function formatRequestTraceTimestamp(value: string): string {
  return formatAiRunTimestamp(value);
}

type SearchProviderDiagnostic = {
  statusLabel: string;
  reasonLabel: string;
  rawReason: string;
  httpStatus: number | null;
};

function extractHttpStatus(rawReason: string): number | null {
  const candidates = [
    /\bHTTP Error\s+(\d{3})\b/i,
    /\bstatus(?:\s*code)?[:=\s]+(\d{3})\b/i
  ];
  for (const pattern of candidates) {
    const match = rawReason.match(pattern);
    if (!match) {
      continue;
    }
    const value = Number.parseInt(match[1], 10);
    if (Number.isFinite(value)) {
      return value;
    }
  }
  return null;
}

function getHttpStatusHint(httpStatus: number): string {
  if (httpStatus === 400) {
    return "Solicitud invalida para el proveedor";
  }
  if (httpStatus === 401) {
    return "Credenciales invalidas o ausentes";
  }
  if (httpStatus === 403) {
    return "Acceso denegado por el proveedor";
  }
  if (httpStatus === 404) {
    return "Endpoint no encontrado";
  }
  if (httpStatus === 429) {
    return "Rate limit del proveedor";
  }
  if (httpStatus >= 500) {
    return "Fallo temporal del proveedor";
  }
  return "Error HTTP del proveedor";
}

function buildSearchProviderDiagnostic(status: SearchProviderStatus): SearchProviderDiagnostic {
  const statusLabelMap: Record<SearchProviderStatus["status"], string> = {
    ok: "OK",
    error: "ERROR",
    skipped: "SKIPPED"
  };
  const reasonMap: Record<string, string> = {
    not_executed: "No ejecutado",
    disabled_from_admin: "Deshabilitado en administracion",
    missing_rapidapi_config: "Falta configuracion RapidAPI",
    missing_api_key: "Falta API key",
    no_results: "Sin resultados",
    results_found: "Con resultados",
    provider_error: "Error de proveedor",
    unexpected_error: "Error inesperado"
  };
  const canonicalReason = reasonMap[status.reason];
  const rawReason = (status.reason_detail ?? "").trim() || (canonicalReason ? "" : status.reason);
  const httpStatus =
    typeof status.http_status === "number"
      ? status.http_status
      : extractHttpStatus(rawReason);
  let reasonLabel = canonicalReason ?? "Error de proveedor";
  if (status.status === "error" && httpStatus) {
    reasonLabel = `HTTP ${httpStatus} · ${getHttpStatusHint(httpStatus)}`;
  } else if (status.status !== "error" && canonicalReason) {
    reasonLabel = canonicalReason;
  }
  return {
    statusLabel: statusLabelMap[status.status],
    reasonLabel,
    rawReason,
    httpStatus
  };
}

function normalizeSearchQuery(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function roleToken(role: string): string {
  return `"${role.replace(/"/g, "").trim()}"`;
}

function hasRoleToken(query: string, role: string): boolean {
  const token = roleToken(role);
  if (!token || token === "\"\"") {
    return false;
  }
  const pattern = new RegExp(`(?:^|\\s)${escapeRegex(token)}(?=\\s|$)`, "i");
  return pattern.test(query);
}

function addRoleToken(query: string, role: string): string {
  const token = roleToken(role);
  if (!token || token === "\"\"" || hasRoleToken(query, role)) {
    return normalizeSearchQuery(query);
  }
  return normalizeSearchQuery(`${query} ${token}`);
}

function removeRoleToken(query: string, role: string): string {
  const token = roleToken(role);
  if (!token || token === "\"\"") {
    return normalizeSearchQuery(query);
  }
  const pattern = new RegExp(`(?:^|\\s)${escapeRegex(token)}(?=\\s|$)`, "gi");
  return normalizeSearchQuery(query.replace(pattern, " "));
}

async function copyToClipboard(text: string): Promise<void> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  if (typeof document === "undefined") {
    throw new Error("Clipboard API unavailable");
  }
  const node = document.createElement("textarea");
  node.value = text;
  node.setAttribute("readonly", "true");
  node.style.position = "fixed";
  node.style.opacity = "0";
  document.body.appendChild(node);
  node.select();
  const copied = document.execCommand("copy");
  document.body.removeChild(node);
  if (!copied) {
    throw new Error("Clipboard copy command failed");
  }
}

function appendArtifactDelta(
  current: ApplicationArtifact[],
  personId: string,
  opportunityId: string,
  artifactType: "cover_letter" | "experience_summary",
  delta: string
): ApplicationArtifact[] {
  const now = new Date().toISOString();
  const index = current.findIndex((item) => item.artifact_type === artifactType);
  if (index >= 0) {
    return current.map((item, itemIndex) =>
      itemIndex === index
        ? {
            ...item,
            content: `${item.content}${delta}`,
            updated_at: now
          }
        : item
    );
  }
  return [
    ...current,
    {
      artifact_id: `stream-${artifactType}`,
      person_id: personId,
      opportunity_id: opportunityId,
      artifact_type: artifactType,
      content: delta,
      is_current: true,
      created_at: now,
      updated_at: now
    }
  ];
}

type RequestTraceGroup = {
  group_id: string;
  run_id: string;
  items: RequestTrace[];
  latest_created_at: string;
  opportunity_id: string;
};

function groupRequestTracesByRunId(items: RequestTrace[]): RequestTraceGroup[] {
  const grouped = new Map<string, RequestTraceGroup>();
  for (const trace of items) {
    const runId = trace.run_id.trim();
    const key = runId || "__no_run_id__";
    const current = grouped.get(key);
    if (!current) {
      grouped.set(key, {
        group_id: key,
        run_id: runId,
        items: [trace],
        latest_created_at: trace.created_at,
        opportunity_id: trace.opportunity_id
      });
      continue;
    }
    current.items.push(trace);
    if (trace.created_at > current.latest_created_at) {
      current.latest_created_at = trace.created_at;
    }
    if (!current.opportunity_id && trace.opportunity_id) {
      current.opportunity_id = trace.opportunity_id;
    }
  }

  const groups = Array.from(grouped.values());
  for (const group of groups) {
    group.items.sort((a, b) => b.created_at.localeCompare(a.created_at));
  }
  groups.sort((a, b) => b.latest_created_at.localeCompare(a.latest_created_at));
  return groups;
}

export default function App() {
  const [view, setView] = useState<ViewState>("checking");
  const [currentPath, setCurrentPath] = useState<string>(() => {
    if (typeof window === "undefined") {
      return "/candidates";
    }
    return window.location.pathname || "/candidates";
  });
  const [username, setUsername] = useState("tutor");
  const [password, setPassword] = useState("");
  const [operatorName, setOperatorName] = useState("");
  const [people, setPeople] = useState<Person[]>([]);
  const [selectedPersonId, setSelectedPersonId] = useState<string | null>(null);
  const [promptConfigs, setPromptConfigs] = useState<PromptConfig[]>([]);
  const [promptConfigDrafts, setPromptConfigDrafts] = useState<
    Record<string, PromptConfigDraft>
  >({});
  const [isLoadingPromptConfigs, setIsLoadingPromptConfigs] = useState(false);
  const [promptConfigReloadToken, setPromptConfigReloadToken] = useState(0);
  const [savingPromptFlowKey, setSavingPromptFlowKey] = useState<string | null>(null);
  const [searchProviderConfigs, setSearchProviderConfigs] = useState<SearchProviderConfig[]>([]);
  const [isLoadingSearchProviderConfigs, setIsLoadingSearchProviderConfigs] = useState(false);
  const [savingSearchProviderKey, setSavingSearchProviderKey] = useState<string | null>(null);
  const [promptVersionsByFlow, setPromptVersionsByFlow] = useState<
    Record<string, PromptConfigVersion[]>
  >({});
  const [expandedPromptVersions, setExpandedPromptVersions] = useState<
    Record<string, boolean>
  >({});
  const [loadingPromptVersionsFlowKey, setLoadingPromptVersionsFlowKey] = useState<string | null>(
    null
  );
  const [rollingBackPromptFlowKey, setRollingBackPromptFlowKey] = useState<string | null>(null);
  const [newPersonFullName, setNewPersonFullName] = useState("");
  const [newPersonTargetRolesInput, setNewPersonTargetRolesInput] = useState("");
  const [newPersonLocation, setNewPersonLocation] = useState("");
  const [newPersonYearsExperienceInput, setNewPersonYearsExperienceInput] = useState("");
  const [newPersonSkillsInput, setNewPersonSkillsInput] = useState("");
  const [isCreateProfileFormOpen, setIsCreateProfileFormOpen] = useState(false);
  const [isCreatingPerson, setIsCreatingPerson] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [isConversationLoading, setIsConversationLoading] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [streamingAssistantText, setStreamingAssistantText] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchProviderStatus, setSearchProviderStatus] = useState<SearchProviderStatus[]>([]);
  const [selectedSearchResultId, setSelectedSearchResultId] = useState<string | null>(null);
  const [searchWarnings, setSearchWarnings] = useState<string[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [opportunityDiscoveryMode, setOpportunityDiscoveryMode] = useState<"search" | "manual">(
    "search"
  );
  const [manualUrl, setManualUrl] = useState("");
  const [manualUrlTitle, setManualUrlTitle] = useState("");
  const [manualUrlCompany, setManualUrlCompany] = useState("");
  const [manualUrlLocation, setManualUrlLocation] = useState("");
  const [manualUrlRawText, setManualUrlRawText] = useState("");
  const [isImportingUrl, setIsImportingUrl] = useState(false);
  const [savedOpportunities, setSavedOpportunities] = useState<Opportunity[]>([]);
  const [activeCv, setActiveCv] = useState<ActiveCV | null>(null);
  const [activeCvFullText, setActiveCvFullText] = useState("");
  const [selectedCvFile, setSelectedCvFile] = useState<File | null>(null);
  const [isLoadingCv, setIsLoadingCv] = useState(false);
  const [isUploadingCv, setIsUploadingCv] = useState(false);
  const [isLoadingCvFullText, setIsLoadingCvFullText] = useState(false);
  const [isCvUploadFormOpen, setIsCvUploadFormOpen] = useState(false);
  const [isCvPreviewExpanded, setIsCvPreviewExpanded] = useState(false);
  const [isLoadingOpportunities, setIsLoadingOpportunities] = useState(false);
  const [savingResultId, setSavingResultId] = useState<string | null>(null);
  const [selectedOpportunityId, setSelectedOpportunityId] = useState<string | null>(null);
  const [analysisText, setAnalysisText] = useState("");
  const [culturalConfidence, setCulturalConfidence] = useState("");
  const [culturalWarnings, setCulturalWarnings] = useState<string[]>([]);
  const [culturalSignals, setCulturalSignals] = useState<CulturalSignal[]>([]);
  const [semanticEvidence, setSemanticEvidence] = useState<SemanticEvidence | null>(null);
  const [guidanceText, setGuidanceText] = useState("");
  const [artifacts, setArtifacts] = useState<ApplicationArtifact[]>([]);
  const [aiRuns, setAiRuns] = useState<AIRun[]>([]);
  const [isLoadingAiRuns, setIsLoadingAiRuns] = useState(false);
  const [aiRunActionFilter, setAiRunActionFilter] = useState("");
  const [requestTraces, setRequestTraces] = useState<RequestTrace[]>([]);
  const [isLoadingRequestTraces, setIsLoadingRequestTraces] = useState(false);
  const [traceDestinationFilter, setTraceDestinationFilter] = useState("");
  const [traceOnlyActiveOpportunity, setTraceOnlyActiveOpportunity] = useState(false);
  const [traceRunIdFilter, setTraceRunIdFilter] = useState("");
  const [focusedRunId, setFocusedRunId] = useState("");
  const [isAnalyzingProfile, setIsAnalyzingProfile] = useState(false);
  const [isAnalyzingCultural, setIsAnalyzingCultural] = useState(false);
  const [isPreparing, setIsPreparing] = useState(false);
  const [isLoadingArtifacts, setIsLoadingArtifacts] = useState(false);
  const [forceRecomputeAi, setForceRecomputeAi] = useState(false);
  const [prepareGuidanceSelected, setPrepareGuidanceSelected] = useState(true);
  const [prepareCoverSelected, setPrepareCoverSelected] = useState(true);
  const [prepareSummarySelected, setPrepareSummarySelected] = useState(true);
  const [opportunityNotes, setOpportunityNotes] = useState("");
  const [isSavingNotes, setIsSavingNotes] = useState(false);
  const [opportunityStatus, setOpportunityStatus] = useState<string>("detected");
  const [isSavingStatus, setIsSavingStatus] = useState(false);
  const [culturePreferencesState, setCulturePreferencesState] = useState<
    Record<string, CulturalFieldPreference>
  >(buildDefaultCulturalPreferences());
  const [culturePreferencesNotes, setCulturePreferencesNotes] = useState("");
  const [isSavingCulturePreferences, setIsSavingCulturePreferences] = useState(false);
  const [profileFullName, setProfileFullName] = useState("");
  const [profileTargetRolesInput, setProfileTargetRolesInput] = useState("");
  const [profileLocation, setProfileLocation] = useState("");
  const [profileYearsExperienceInput, setProfileYearsExperienceInput] = useState("");
  const [profileSkillsInput, setProfileSkillsInput] = useState("");
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isChatDrawerOpen, setIsChatDrawerOpen] = useState(false);
  const [isPersonContextMenuOpen, setIsPersonContextMenuOpen] = useState(false);
  const [copiedArtifactKey, setCopiedArtifactKey] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const onPopState = () => {
      setCurrentPath(window.location.pathname || "/candidates");
    };
    window.addEventListener("popstate", onPopState);
    return () => {
      window.removeEventListener("popstate", onPopState);
    };
  }, []);

  useEffect(() => {
    const boot = async () => {
      try {
        const session = await getSession();
        setOperatorName(session.username);
        const items = await listPersons();
        setPeople(items);
        if (items.length > 0) {
          setSelectedPersonId(items[0].person_id);
        }
        setView("workspace");
        if ((window.location.pathname || "/") === "/login") {
          navigateTo("/candidates", { replace: true });
        }
      } catch {
        setView("login");
        navigateTo("/login", { replace: true });
      }
    };
    void boot();
  }, []);

  useEffect(() => {
    if (view !== "workspace") {
      return;
    }
    const route = parseWorkspacePath(currentPath);
    if (!route.personId) {
      if (currentPath === "/" || currentPath === "/login") {
        navigateTo("/candidates", { replace: true });
      }
      return;
    }
    if (people.length === 0) {
      navigateTo("/candidates", { replace: true });
      return;
    }
    const exists = people.some((item) => item.person_id === route.personId);
    if (!exists) {
      navigateTo(`/c/${people[0].person_id}/profile`, { replace: true });
      return;
    }
    if (selectedPersonId !== route.personId) {
      setSelectedPersonId(route.personId);
    }
  }, [view, currentPath, people, selectedPersonId]);

  useEffect(() => {
    const loadPromptConfigs = async () => {
      if (view !== "workspace") {
        setSearchProviderConfigs([]);
        setPromptConfigs([]);
        setPromptConfigDrafts({});
        setPromptVersionsByFlow({});
        setExpandedPromptVersions({});
        return;
      }
      setIsLoadingPromptConfigs(true);
      setIsLoadingSearchProviderConfigs(true);
      setErrorMessage(null);
      try {
        const [items, providerItems] = await Promise.all([
          listPromptConfigs(),
          listSearchProviderConfigs()
        ]);
        setPromptConfigs(items);
        setPromptConfigDrafts(buildPromptConfigDrafts(items));
        setSearchProviderConfigs(providerItems);
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "No se pudo cargar configuraciones de administracion";
        setErrorMessage(message);
      } finally {
        setIsLoadingPromptConfigs(false);
        setIsLoadingSearchProviderConfigs(false);
      }
    };
    void loadPromptConfigs();
  }, [view, promptConfigReloadToken]);

  const selectedPerson =
    people.find((person) => person.person_id === selectedPersonId) ?? null;
  const orderedPromptConfigs = [...promptConfigs].sort((a, b) => {
    const indexA = PROMPT_FLOW_ORDER.indexOf(a.flow_key);
    const indexB = PROMPT_FLOW_ORDER.indexOf(b.flow_key);
    const rankA = indexA >= 0 ? indexA : Number.MAX_SAFE_INTEGER;
    const rankB = indexB >= 0 ? indexB : Number.MAX_SAFE_INTEGER;
    return rankA - rankB;
  });
  const searchProviderOrder: Array<SearchProviderConfig["provider_key"]> = [
    "tavily",
    "adzuna",
    "remotive"
  ];
  const orderedSearchProviderConfigs = [...searchProviderConfigs].sort((a, b) => {
    const indexA = searchProviderOrder.indexOf(a.provider_key);
    const indexB = searchProviderOrder.indexOf(b.provider_key);
    return indexA - indexB;
  });
  const parsedRoute = parseWorkspacePath(currentPath);
  const showCandidatesPage = parsedRoute.page === "candidates";
  const showAdminPromptsPage = parsedRoute.page === "admin-prompts";
  const showProfilePage = parsedRoute.page === "profile";
  const showOpportunitiesPage = parsedRoute.page === "opportunities";
  const showAnalysisPage = parsedRoute.page === "analysis";
  const showContextualSidebar = showProfilePage || showOpportunitiesPage || showAnalysisPage;
  const showConversationSection = showContextualSidebar;
  const shellClassName =
    showConversationSection && isChatDrawerOpen ? "shell shellWithChatDrawer" : "shell";
  const currentPageLabel = showCandidatesPage
    ? "Seleccion de candidato"
    : showAdminPromptsPage
      ? "Administracion global"
      : showProfilePage
        ? "Perfil"
        : showOpportunitiesPage
          ? "Busqueda de oportunidades"
          : "Análisis";
  const currentPageTitle = showCandidatesPage
    ? "Selecciona un perfil para abrir su contexto."
    : showAdminPromptsPage
      ? "Ajusta prompts globales y proveedores de busqueda."
      : showProfilePage
        ? "Gestiona perfil y CV del perfil activo."
        : showOpportunitiesPage
          ? "Busca, revisa e importa oportunidades para el contexto activo."
          : "Analiza el perfil y prepara entregables por oportunidad.";
  const currentPageLede = showContextualSidebar
    ? showProfilePage
      ? null
      : "Usa las pestañas para gestionar perfil, busqueda y análisis."
    : "Este flujo separa acceso del tutor y contexto del perfil consultado.";
  const searchRoleKeywords = Array.from(
    new Set(
      (selectedPerson?.target_roles ?? [])
        .map((item) => item.trim())
        .filter(Boolean)
    )
  );
  const selectedSearchRoleCount = searchRoleKeywords.filter((role) =>
    hasRoleToken(searchQuery, role)
  ).length;
  const chatQuickStarts = selectedPerson
    ? [
        `Cual es el foco de posicionamiento para ${selectedPerson.full_name} hoy?`,
        `Que vacantes deberia priorizar para ${selectedPerson.full_name}?`,
        "Que mejoras de perfil recomiendas antes de postular?"
      ]
    : CHAT_QUICK_STARTS;
  const cvPreviewLineLimit = 8;
  const cvPreviewText = (activeCv?.extracted_text_preview ?? "").trim();
  const cvExpandedText = (activeCvFullText || cvPreviewText).trim();
  const cvPreviewLines = cvPreviewText ? cvPreviewText.split(/\r?\n/) : [];
  const cvPreviewShortText = cvPreviewLines
    .slice(0, cvPreviewLineLimit)
    .join("\n")
    .trim();
  const hasMoreCvPreview =
    cvPreviewLines.length > cvPreviewLineLimit ||
    cvPreviewText.length > cvPreviewShortText.length ||
    (activeCv?.text_length ?? 0) > cvPreviewText.length;

  useEffect(() => {
    setIsPersonContextMenuOpen(false);
  }, [currentPath, selectedPersonId]);

  useEffect(() => {
    if (showCandidatesPage && people.length === 0) {
      setIsCreateProfileFormOpen(true);
    }
  }, [showCandidatesPage, people.length]);

  useEffect(() => {
    setActiveCvFullText("");
    if (!activeCv) {
      setIsCvUploadFormOpen(true);
      setIsCvPreviewExpanded(false);
      return;
    }
    setIsCvUploadFormOpen(false);
    setIsCvPreviewExpanded(false);
  }, [activeCv?.cv_id]);

  function navigateTo(path: string, options?: { replace?: boolean }) {
    if (typeof window === "undefined") {
      setCurrentPath(path);
      return;
    }
    const replace = Boolean(options?.replace);
    if (window.location.pathname === path) {
      setCurrentPath(path);
      return;
    }
    if (replace) {
      window.history.replaceState({}, "", path);
    } else {
      window.history.pushState({}, "", path);
    }
    setCurrentPath(path);
  }

  useEffect(() => {
    const loadConversation = async () => {
      if (!selectedPersonId || view !== "workspace") {
        setConversation(null);
        setStreamingAssistantText("");
        return;
      }
      setIsConversationLoading(true);
      setErrorMessage(null);
      try {
        const payload = await getConversation(selectedPersonId);
        setConversation(payload);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "No se pudo cargar la conversacion";
        setErrorMessage(message);
      } finally {
        setIsConversationLoading(false);
      }
    };
    void loadConversation();
  }, [selectedPersonId, view]);

  useEffect(() => {
    const loadOpportunities = async () => {
      if (!selectedPersonId || view !== "workspace") {
        setSavedOpportunities([]);
        setSelectedOpportunityId(null);
        setAnalysisText("");
        setCulturalConfidence("");
        setCulturalWarnings([]);
        setCulturalSignals([]);
        setSemanticEvidence(null);
        setGuidanceText("");
        setArtifacts([]);
        setAiRuns([]);
        setAiRunActionFilter("");
        setRequestTraces([]);
        setTraceDestinationFilter("");
        setTraceOnlyActiveOpportunity(false);
        setTraceRunIdFilter("");
        setFocusedRunId("");
        setOpportunityNotes("");
        setOpportunityStatus("detected");
        return;
      }
      setIsLoadingOpportunities(true);
      setErrorMessage(null);
      try {
        const items = await listOpportunities(selectedPersonId);
        setSavedOpportunities(items);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "No se pudieron cargar oportunidades";
        setErrorMessage(message);
      } finally {
        setIsLoadingOpportunities(false);
      }
    };
    void loadOpportunities();
  }, [selectedPersonId, view]);

  useEffect(() => {
    const loadActiveCv = async () => {
      if (!selectedPersonId || view !== "workspace") {
        setActiveCv(null);
        setActiveCvFullText("");
        setSelectedCvFile(null);
        return;
      }
      setIsLoadingCv(true);
      setErrorMessage(null);
      try {
        const item = await getActiveCV(selectedPersonId);
        setActiveCv(item);
        setActiveCvFullText("");
      } catch (error) {
        const message = error instanceof Error ? error.message : "No se pudo cargar el CV activo";
        setErrorMessage(message);
      } finally {
        setIsLoadingCv(false);
      }
    };
    void loadActiveCv();
  }, [selectedPersonId, view]);

  useEffect(() => {
    if (!showAnalysisPage || selectedOpportunityId || savedOpportunities.length === 0) {
      return;
    }
    setSelectedOpportunityId(savedOpportunities[0].opportunity_id);
  }, [showAnalysisPage, savedOpportunities, selectedOpportunityId]);

  useEffect(() => {
    if (showConversationSection && selectedPersonId) {
      return;
    }
    setIsChatDrawerOpen(false);
  }, [showConversationSection, selectedPersonId]);

  const selectedOpportunity =
    savedOpportunities.find((item) => item.opportunity_id === selectedOpportunityId) ?? null;
  const aiRunsById = new Map(aiRuns.map((item) => [item.run_id, item] as const));
  const requestTraceGroups = groupRequestTracesByRunId(requestTraces);
  const focusedRun = focusedRunId ? aiRunsById.get(focusedRunId) ?? null : null;
  const focusedRunRequestTraces = focusedRunId
    ? requestTraces.filter((item) => item.run_id === focusedRunId)
    : [];

  useEffect(() => {
    if (!selectedPersonId || !selectedOpportunityId) {
      setAiRuns([]);
      return;
    }
    void refreshAiRunsFor(selectedPersonId, selectedOpportunityId, aiRunActionFilter);
  }, [selectedPersonId, selectedOpportunityId, aiRunActionFilter]);

  useEffect(() => {
    if (!selectedPersonId) {
      setRequestTraces([]);
      return;
    }
    void refreshRequestTracesFor(
      selectedPersonId,
      traceDestinationFilter,
      traceOnlyActiveOpportunity,
      selectedOpportunityId,
      traceRunIdFilter
    );
  }, [
    selectedPersonId,
    selectedOpportunityId,
    traceDestinationFilter,
    traceOnlyActiveOpportunity,
    traceRunIdFilter
  ]);

  useEffect(() => {
    setSearchQuery("");
    setSearchResults([]);
    setSearchProviderStatus([]);
    setSelectedSearchResultId(null);
    setSearchWarnings([]);
  }, [selectedPersonId]);

  useEffect(() => {
    setOpportunityDiscoveryMode("search");
  }, [selectedPersonId]);

  useEffect(() => {
    if (!selectedSearchResultId) {
      return;
    }
    if (searchResults.some((item) => item.search_result_id === selectedSearchResultId)) {
      return;
    }
    setSelectedSearchResultId(null);
  }, [searchResults, selectedSearchResultId]);

  useEffect(() => {
    if (!selectedOpportunityId && traceOnlyActiveOpportunity) {
      setTraceOnlyActiveOpportunity(false);
    }
  }, [selectedOpportunityId, traceOnlyActiveOpportunity]);

  useEffect(() => {
    setOpportunityNotes(selectedOpportunity?.notes ?? "");
  }, [selectedOpportunity?.opportunity_id, selectedOpportunity?.notes]);

  useEffect(() => {
    setOpportunityStatus(selectedOpportunity?.status ?? "detected");
  }, [selectedOpportunity?.opportunity_id, selectedOpportunity?.status]);

  useEffect(() => {
    if (!selectedPerson) {
      setProfileFullName("");
      setProfileTargetRolesInput("");
      setProfileLocation("");
      setProfileYearsExperienceInput("");
      setProfileSkillsInput("");
      setCulturePreferencesState(buildDefaultCulturalPreferences());
      setCulturePreferencesNotes("");
      return;
    }
    setProfileFullName(selectedPerson.full_name ?? "");
    setProfileTargetRolesInput((selectedPerson.target_roles ?? []).join(", "));
    setProfileLocation(selectedPerson.location ?? "");
    setProfileYearsExperienceInput(String(selectedPerson.years_experience ?? 0));
    setProfileSkillsInput((selectedPerson.skills ?? []).join(", "));

    const defaults = buildDefaultCulturalPreferences();
    const incoming = selectedPerson.cultural_fit_preferences ?? {};
    const nextState: Record<string, CulturalFieldPreference> = { ...defaults };

    for (const field of CULTURAL_FIELDS) {
      const raw = incoming[field.id];
      if (!raw) {
        continue;
      }
      const allowedOptions = new Set(field.options.map((item) => item.value));
      const selectedValues = (raw.selected_values ?? []).filter((item) =>
        allowedOptions.has(item)
      );
      nextState[field.id] = {
        enabled: selectedValues.length > 0,
        selected_values: selectedValues,
        criticality:
          raw.criticality === "high_penalty" || raw.criticality === "non_negotiable"
            ? raw.criticality
            : "normal"
      };
    }

    setCulturePreferencesState(nextState);
    setCulturePreferencesNotes(selectedPerson.culture_preferences_notes ?? "");
  }, [
    selectedPerson?.person_id,
    selectedPerson?.full_name,
    selectedPerson?.target_roles,
    selectedPerson?.location,
    selectedPerson?.years_experience,
    selectedPerson?.skills,
    selectedPerson?.cultural_fit_preferences,
    selectedPerson?.culture_preferences_notes
  ]);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);
    try {
      const session = await login(username, password);
      setOperatorName(session.username);
      setPassword("");
      const items = await listPersons();
      setPeople(items);
      if (items.length > 0) {
        setSelectedPersonId(items[0].person_id);
      }
      setView("workspace");
      navigateTo("/candidates", { replace: true });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo iniciar sesion";
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleLogout() {
    setErrorMessage(null);
    try {
      await logout();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo cerrar sesion";
      setErrorMessage(message);
      return;
    }
    setView("login");
    navigateTo("/login", { replace: true });
    setOperatorName("");
    setPassword("");
    setSelectedPersonId(null);
    setPeople([]);
    setSearchProviderConfigs([]);
    setPromptConfigs([]);
    setPromptConfigDrafts({});
    setPromptVersionsByFlow({});
    setExpandedPromptVersions({});
    setNewPersonFullName("");
    setNewPersonTargetRolesInput("");
    setNewPersonLocation("");
    setNewPersonYearsExperienceInput("");
    setNewPersonSkillsInput("");
    setConversation(null);
    setStreamingAssistantText("");
    setChatInput("");
    setAnalysisText("");
    setCulturalConfidence("");
    setCulturalWarnings([]);
    setCulturalSignals([]);
    setSemanticEvidence(null);
    setForceRecomputeAi(false);
    setPrepareGuidanceSelected(true);
    setPrepareCoverSelected(true);
    setPrepareSummarySelected(true);
    setAiRuns([]);
    setAiRunActionFilter("");
    setRequestTraces([]);
    setTraceDestinationFilter("");
    setTraceOnlyActiveOpportunity(false);
    setTraceRunIdFilter("");
    setFocusedRunId("");
    setActiveCv(null);
    setActiveCvFullText("");
    setSelectedCvFile(null);
  }

  async function handleCreatePerson(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isCreatingPerson) {
      return;
    }

    const fullName = newPersonFullName.trim();
    const location = newPersonLocation.trim();
    const yearsExperience = Number.parseInt(newPersonYearsExperienceInput.trim(), 10);
    const targetRoles = newPersonTargetRolesInput
      .split(/[\n,]/g)
      .map((item) => item.trim())
      .filter(Boolean);
    const skills = newPersonSkillsInput
      .split(/[\n,]/g)
      .map((item) => item.trim())
      .filter(Boolean);

    if (!fullName || !location || targetRoles.length === 0 || skills.length === 0) {
      setErrorMessage(
        "Nuevo perfil incompleto: nombre, ubicacion, roles y skills son obligatorios."
      );
      return;
    }
    if (!Number.isFinite(yearsExperience) || yearsExperience < 0 || yearsExperience > 80) {
      setErrorMessage("Años de experiencia debe estar entre 0 y 80.");
      return;
    }

    setIsCreatingPerson(true);
    setErrorMessage(null);
    try {
      const created = await createPerson({
        full_name: fullName,
        target_roles: targetRoles,
        location,
        years_experience: yearsExperience,
        skills
      });
      const items = await listPersons();
      setPeople(items);
      setSelectedPersonId(created.person_id);
      navigateTo(buildContextPath(created.person_id, "profile"));
      setNewPersonFullName("");
      setNewPersonTargetRolesInput("");
      setNewPersonLocation("");
      setNewPersonYearsExperienceInput("");
      setNewPersonSkillsInput("");
      setIsCreateProfileFormOpen(false);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo crear el nuevo perfil";
      setErrorMessage(message);
    } finally {
      setIsCreatingPerson(false);
    }
  }

  function handlePromptDraftChange(
    flowKey: string,
    patch: Partial<PromptConfigDraft>
  ) {
    setPromptConfigDrafts((current) => {
      const currentDraft = current[flowKey] ?? {
        template_text: "",
        target_sources_input: "",
        is_active: true
      };
      return {
        ...current,
        [flowKey]: {
          ...currentDraft,
          ...patch
        }
      };
    });
  }

  async function handleSavePromptConfig(flowKey: string) {
    const draft = promptConfigDrafts[flowKey];
    if (!draft || savingPromptFlowKey) {
      return;
    }

    const templateText = draft.template_text.trim();
    const targetSources = draft.target_sources_input
      .split(/[\n,]/g)
      .map((item) => item.trim())
      .filter(Boolean);

    if (!templateText) {
      setErrorMessage("La plantilla de prompt no puede estar vacia.");
      return;
    }
    if (PROMPT_SOURCE_FLOW_KEYS.has(flowKey) && targetSources.length === 0) {
      setErrorMessage("Debes incluir al menos una fuente objetivo.");
      return;
    }

    setSavingPromptFlowKey(flowKey);
    setErrorMessage(null);
    try {
      const updated = await updatePromptConfigApi(flowKey, {
        template_text: templateText,
        target_sources: PROMPT_SOURCE_FLOW_KEYS.has(flowKey) ? targetSources : [],
        is_active: draft.is_active
      });
      setPromptConfigs((current) =>
        current.map((item) => (item.flow_key === updated.flow_key ? updated : item))
      );
      setPromptConfigDrafts((current) => ({
        ...current,
        [flowKey]: {
          template_text: updated.template_text,
          target_sources_input: updated.target_sources.join("\n"),
          is_active: updated.is_active
        }
      }));
      if (expandedPromptVersions[flowKey]) {
        await loadPromptVersions(flowKey, true);
      }
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "No se pudo guardar la configuracion del prompt";
      setErrorMessage(message);
    } finally {
      setSavingPromptFlowKey(null);
    }
  }

  async function handleToggleSearchProvider(
    providerKey: "adzuna" | "remotive" | "tavily",
    isEnabled: boolean
  ) {
    if (savingSearchProviderKey) {
      return;
    }
    setSavingSearchProviderKey(providerKey);
    setErrorMessage(null);
    try {
      const updated = await updateSearchProviderConfigApi(providerKey, isEnabled);
      setSearchProviderConfigs((current) =>
        current.map((item) => (item.provider_key === updated.provider_key ? updated : item))
      );
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo actualizar el proveedor";
      setErrorMessage(message);
    } finally {
      setSavingSearchProviderKey((current) => (current === providerKey ? null : current));
    }
  }

  async function loadPromptVersions(flowKey: string, force = false) {
    if (!force && promptVersionsByFlow[flowKey]) {
      return;
    }
    setLoadingPromptVersionsFlowKey(flowKey);
    try {
      const items = await listPromptConfigVersions(flowKey, 20);
      setPromptVersionsByFlow((current) => ({
        ...current,
        [flowKey]: items
      }));
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo cargar historial de versiones";
      setErrorMessage(message);
    } finally {
      setLoadingPromptVersionsFlowKey((current) =>
        current === flowKey ? null : current
      );
    }
  }

  function handleTogglePromptVersions(flowKey: string) {
    setExpandedPromptVersions((current) => {
      const next = !current[flowKey];
      const updated = {
        ...current,
        [flowKey]: next
      };
      if (next) {
        void loadPromptVersions(flowKey);
      }
      return updated;
    });
  }

  async function handleRollbackPromptConfig(flowKey: string, versionId: string) {
    if (!versionId.trim() || rollingBackPromptFlowKey) {
      return;
    }
    const confirmed = window.confirm(
      "Se restaurara esta version y se sobrescribira la configuracion actual. Continuar?"
    );
    if (!confirmed) {
      return;
    }
    setRollingBackPromptFlowKey(flowKey);
    setErrorMessage(null);
    try {
      const updated = await rollbackPromptConfigApi(flowKey, versionId);
      setPromptConfigs((current) =>
        current.map((item) => (item.flow_key === updated.flow_key ? updated : item))
      );
      setPromptConfigDrafts((current) => ({
        ...current,
        [flowKey]: {
          template_text: updated.template_text,
          target_sources_input: updated.target_sources.join("\n"),
          is_active: updated.is_active
        }
      }));
      await loadPromptVersions(flowKey, true);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo restaurar la version seleccionada";
      setErrorMessage(message);
    } finally {
      setRollingBackPromptFlowKey((current) => (current === flowKey ? null : current));
    }
  }

  async function submitChatMessage(rawMessage: string) {
    if (!selectedPersonId || !rawMessage.trim() || isSendingMessage) {
      return;
    }
    const personId = selectedPersonId;
    const messageToSend = rawMessage.trim();
    setIsSendingMessage(true);
    setStreamingAssistantText("");
    setErrorMessage(null);
    let streamedAnyDelta = false;
    try {
      const updatedConversation = await sendMessageStream(
        personId,
        messageToSend,
        (delta) => {
          streamedAnyDelta = true;
          setStreamingAssistantText((current) => `${current}${delta}`);
        }
      );
      setConversation(updatedConversation);
      setChatInput("");
      await refreshRequestTracesFor(
        personId,
        traceDestinationFilter,
        traceOnlyActiveOpportunity,
        selectedOpportunityId,
        traceRunIdFilter
      );
    } catch (error) {
      if (!streamedAnyDelta) {
        try {
          const updatedConversation = await sendMessage(personId, messageToSend);
          setConversation(updatedConversation);
          setChatInput("");
          await refreshRequestTracesFor(
            personId,
            traceDestinationFilter,
            traceOnlyActiveOpportunity,
            selectedOpportunityId,
            traceRunIdFilter
          );
          setErrorMessage("Streaming no disponible. Se uso envio sin streaming como respaldo.");
          return;
        } catch {
          // Keep original stream failure message below.
        }
      }
      const message = error instanceof Error ? error.message : "No se pudo enviar el mensaje";
      setErrorMessage(message);
    } finally {
      setStreamingAssistantText("");
      setIsSendingMessage(false);
    }
  }

  async function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitChatMessage(chatInput);
  }

  async function handleQuickStart(message: string) {
    if (!isChatDrawerOpen) {
      setIsChatDrawerOpen(true);
    }
    setChatInput(message);
    await submitChatMessage(message);
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPersonId || !searchQuery.trim()) {
      return;
    }
    setIsSearching(true);
    setErrorMessage(null);
    setSearchProviderStatus([]);
    try {
      const payload = await searchOpportunities(selectedPersonId, searchQuery.trim(), 6);
      setSearchResults(payload.items);
      setSearchWarnings(payload.warnings);
      setSearchProviderStatus(payload.provider_status ?? []);
      setSelectedSearchResultId(null);
      await refreshRequestTracesFor(
        selectedPersonId,
        traceDestinationFilter,
        traceOnlyActiveOpportunity,
        selectedOpportunityId,
        traceRunIdFilter
      );
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo ejecutar la busqueda";
      setErrorMessage(message);
    } finally {
      setIsSearching(false);
    }
  }

  async function handleSaveSearchResult(result: SearchResult) {
    if (!selectedPersonId) {
      return;
    }
    setSavingResultId(result.search_result_id);
    setErrorMessage(null);
    try {
      await saveOpportunityFromSearch(selectedPersonId, result);
      const items = await listOpportunities(selectedPersonId);
      setSavedOpportunities(items);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo guardar la oportunidad";
      setErrorMessage(message);
    } finally {
      setSavingResultId(null);
    }
  }

  async function handleCopyArtifactContent(copyKey: string, content: string) {
    const payload = content.trim();
    if (!payload) {
      setErrorMessage("No hay contenido para copiar.");
      return;
    }
    try {
      await copyToClipboard(payload);
      setCopiedArtifactKey(copyKey);
      window.setTimeout(() => {
        setCopiedArtifactKey((current) => (current === copyKey ? null : current));
      }, 1600);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo copiar el artefacto";
      setErrorMessage(message);
    }
  }

  async function handleToggleCvPreview() {
    if (!activeCv) {
      return;
    }
    if (isCvPreviewExpanded) {
      setIsCvPreviewExpanded(false);
      return;
    }
    if (!activeCvFullText && !isLoadingCvFullText) {
      setIsLoadingCvFullText(true);
      try {
        const payload = await getActiveCVText(activeCv.person_id);
        setActiveCvFullText(payload.extracted_text);
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "No se pudo cargar el texto completo del CV";
        setErrorMessage(message);
      } finally {
        setIsLoadingCvFullText(false);
      }
    }
    setIsCvPreviewExpanded(true);
  }

  async function handleUploadCv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPersonId || !selectedCvFile || isUploadingCv) {
      return;
    }
    setIsUploadingCv(true);
    setErrorMessage(null);
    try {
      const payload = await uploadCV(selectedPersonId, selectedCvFile);
      setActiveCv(payload);
      setSelectedCvFile(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo cargar el CV";
      setErrorMessage(message);
    } finally {
      setIsUploadingCv(false);
    }
  }

  async function handleImportByUrl(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const sourceUrl = manualUrl.trim();
    const rawText = manualUrlRawText.trim();
    if (!selectedPersonId || !sourceUrl || isImportingUrl) {
      return;
    }
    if (rawText.length < 8) {
      setErrorMessage("La descripcion/snapshot es obligatoria (minimo 8 caracteres).");
      return;
    }
    setIsImportingUrl(true);
    setErrorMessage(null);
    try {
      const payload = await importOpportunityByUrl(selectedPersonId, {
        source_url: sourceUrl,
        title: manualUrlTitle.trim(),
        company: manualUrlCompany.trim(),
        location: manualUrlLocation.trim(),
        raw_text: rawText
      });
      const items = await listOpportunities(selectedPersonId);
      setSavedOpportunities(items);
      setSelectedOpportunityId(payload.item.opportunity_id);
      setManualUrl("");
      setManualUrlTitle("");
      setManualUrlCompany("");
      setManualUrlLocation("");
      setManualUrlRawText("");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo importar por URL";
      setErrorMessage(message);
    } finally {
      setIsImportingUrl(false);
    }
  }

  function handleToggleSearchRole(role: string) {
    setSearchQuery((current) =>
      hasRoleToken(current, role)
        ? removeRoleToken(current, role)
        : addRoleToken(current, role)
    );
  }

  function handleSelectAllSearchRoles() {
    setSearchQuery((current) => {
      let next = current;
      for (const role of searchRoleKeywords) {
        next = addRoleToken(next, role);
      }
      return next;
    });
  }

  function handleClearSearchRoles() {
    setSearchQuery((current) => {
      let next = current;
      for (const role of searchRoleKeywords) {
        next = removeRoleToken(next, role);
      }
      return next;
    });
  }

  async function refreshAiRunsFor(
    personId: string,
    opportunityId: string,
    actionKey: string
  ) {
    setIsLoadingAiRuns(true);
    try {
      const items = await listOpportunityAiRuns(
        personId,
        opportunityId,
        actionKey || undefined
      );
      setAiRuns(items);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo cargar el historico IA";
      setErrorMessage(message);
    } finally {
      setIsLoadingAiRuns(false);
    }
  }

  async function refreshRequestTracesFor(
    personId: string,
    destination: string,
    onlyActiveOpportunity: boolean,
    selectedOpportunityForScope: string | null,
    runId: string = ""
  ) {
    setIsLoadingRequestTraces(true);
    try {
      const items = await listRequestTraces(personId, {
        destination: destination || undefined,
        opportunityId:
          onlyActiveOpportunity && selectedOpportunityForScope
            ? selectedOpportunityForScope
            : undefined,
        runId: runId || undefined,
        limit: 60
      });
      setRequestTraces(items);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo cargar trazas de prompts/API";
      setErrorMessage(message);
    } finally {
      setIsLoadingRequestTraces(false);
    }
  }

  function handleFocusRunTrace(runId: string, opportunityId: string) {
    setFocusedRunId(runId);
    setTraceRunIdFilter(runId);
    if (opportunityId) {
      setSelectedOpportunityId(opportunityId);
      setTraceOnlyActiveOpportunity(true);
    }
  }

  function handleFocusRunResponse(runId: string, opportunityId: string) {
    if (!runId) {
      return;
    }
    setFocusedRunId(runId);
    setAiRunActionFilter("");
    if (opportunityId) {
      setSelectedOpportunityId(opportunityId);
    }
  }

  async function refreshArtifacts(opportunityId: string) {
    if (!selectedPersonId) {
      return;
    }
    setIsLoadingArtifacts(true);
    try {
      const items = await listOpportunityArtifacts(selectedPersonId, opportunityId);
      setArtifacts(items);
    } finally {
      setIsLoadingArtifacts(false);
    }
  }

  async function handleAnalyzeProfileMatch(opportunityId: string) {
    if (!selectedPersonId) {
      return;
    }
    const personId = selectedPersonId;
    setSelectedOpportunityId(opportunityId);
    setIsAnalyzingProfile(true);
    setErrorMessage(null);
    setAnalysisText("");
    setCulturalConfidence("");
    setCulturalWarnings([]);
    setCulturalSignals([]);
    try {
      const payload = await analyzeProfileMatchStream(
        personId,
        opportunityId,
        forceRecomputeAi,
        (delta) => {
          setAnalysisText((current) => `${current}${delta}`);
        }
      );
      setAnalysisText(payload.analysis_text);
      setSemanticEvidence(payload.semantic_evidence);
      const items = await listOpportunities(personId);
      setSavedOpportunities(items);
      setSelectedOpportunityId(opportunityId);
      await refreshAiRunsFor(personId, opportunityId, aiRunActionFilter);
      await refreshRequestTracesFor(
        personId,
        traceDestinationFilter,
        traceOnlyActiveOpportunity,
        opportunityId,
        traceRunIdFilter
      );
    } catch (error) {
      try {
        const payload = await analyzeProfileMatch(personId, opportunityId, forceRecomputeAi);
        setAnalysisText(payload.analysis_text);
        setSemanticEvidence(payload.semantic_evidence);
        const items = await listOpportunities(personId);
        setSavedOpportunities(items);
        setSelectedOpportunityId(opportunityId);
        await refreshAiRunsFor(personId, opportunityId, aiRunActionFilter);
        await refreshRequestTracesFor(
          personId,
          traceDestinationFilter,
          traceOnlyActiveOpportunity,
          opportunityId,
          traceRunIdFilter
        );
        setErrorMessage(
          "Streaming de analisis no disponible. Se uso endpoint sin streaming como respaldo."
        );
      } catch {
        const message =
          error instanceof Error ? error.message : "No se pudo analizar perfil-vacante";
        setErrorMessage(message);
      }
    } finally {
      setIsAnalyzingProfile(false);
    }
  }

  async function handleAnalyzeCulturalFit(opportunityId: string) {
    if (!selectedPersonId) {
      return;
    }
    const personId = selectedPersonId;
    setSelectedOpportunityId(opportunityId);
    setIsAnalyzingCultural(true);
    setErrorMessage(null);
    setCulturalConfidence("");
    setCulturalWarnings([]);
    setCulturalSignals([]);
    setAnalysisText("");
    setSemanticEvidence(null);
    try {
      const payload = await analyzeCulturalFitStream(
        personId,
        opportunityId,
        forceRecomputeAi,
        (delta) => {
          setAnalysisText((current) => `${current}${delta}`);
        }
      );
      setAnalysisText(payload.analysis_text);
      setCulturalConfidence(payload.cultural_confidence);
      setCulturalWarnings(payload.cultural_warnings);
      setCulturalSignals(payload.cultural_signals);
      const items = await listOpportunities(personId);
      setSavedOpportunities(items);
      setSelectedOpportunityId(opportunityId);
      await refreshAiRunsFor(personId, opportunityId, aiRunActionFilter);
      await refreshRequestTracesFor(
        personId,
        traceDestinationFilter,
        traceOnlyActiveOpportunity,
        opportunityId,
        traceRunIdFilter
      );
    } catch (error) {
      try {
        const payload = await analyzeCulturalFit(personId, opportunityId, forceRecomputeAi);
        setAnalysisText(payload.analysis_text);
        setCulturalConfidence(payload.cultural_confidence);
        setCulturalWarnings(payload.cultural_warnings);
        setCulturalSignals(payload.cultural_signals);
        const items = await listOpportunities(personId);
        setSavedOpportunities(items);
        setSelectedOpportunityId(opportunityId);
        await refreshAiRunsFor(personId, opportunityId, aiRunActionFilter);
        await refreshRequestTracesFor(
          personId,
          traceDestinationFilter,
          traceOnlyActiveOpportunity,
          opportunityId,
          traceRunIdFilter
        );
        setErrorMessage(
          "Streaming de analisis no disponible. Se uso endpoint sin streaming como respaldo."
        );
      } catch {
        const message = error instanceof Error ? error.message : "No se pudo analizar fit cultural";
        setErrorMessage(message);
      }
    } finally {
      setIsAnalyzingCultural(false);
    }
  }

  async function handlePrepare(opportunityId: string) {
    if (!selectedPersonId) {
      return;
    }
    const personId = selectedPersonId;
    const targets: Array<"guidance_text" | "cover_letter" | "experience_summary"> = [];
    if (prepareGuidanceSelected) {
      targets.push("guidance_text");
    }
    if (prepareCoverSelected) {
      targets.push("cover_letter");
    }
    if (prepareSummarySelected) {
      targets.push("experience_summary");
    }
    if (targets.length === 0) {
      setErrorMessage("Selecciona al menos un material para preparar.");
      return;
    }

    setSelectedOpportunityId(opportunityId);
    setIsPreparing(true);
    setErrorMessage(null);
    setGuidanceText("");
    setArtifacts([]);

    try {
      const payload = await prepareOpportunityStream(
        personId,
        opportunityId,
        {
          targets,
          force_recompute: forceRecomputeAi
        },
        (channel, delta) => {
          if (channel === "guidance_text") {
            setGuidanceText((current) => `${current}${delta}`);
            return;
          }
          if (channel === "cover_letter") {
            setArtifacts((current) =>
              appendArtifactDelta(
                current,
                personId,
                opportunityId,
                "cover_letter",
                delta
              )
            );
            return;
          }
          if (channel === "experience_summary") {
            setArtifacts((current) =>
              appendArtifactDelta(
                current,
                personId,
                opportunityId,
                "experience_summary",
                delta
              )
            );
          }
        }
      );
      setGuidanceText(payload.guidance_text);
      setArtifacts(payload.artifacts);
      setSemanticEvidence(payload.semantic_evidence);
      const items = await listOpportunities(personId);
      setSavedOpportunities(items);
      setSelectedOpportunityId(opportunityId);
      await refreshAiRunsFor(personId, opportunityId, aiRunActionFilter);
      await refreshRequestTracesFor(
        personId,
        traceDestinationFilter,
        traceOnlyActiveOpportunity,
        opportunityId,
        traceRunIdFilter
      );
    } catch (error) {
      try {
        const payload = await prepareOpportunity(
          personId,
          opportunityId,
          {
            targets,
            force_recompute: forceRecomputeAi
          }
        );
        setGuidanceText(payload.guidance_text);
        setArtifacts(payload.artifacts);
        setSemanticEvidence(payload.semantic_evidence);
        const items = await listOpportunities(personId);
        setSavedOpportunities(items);
        setSelectedOpportunityId(opportunityId);
        await refreshAiRunsFor(personId, opportunityId, aiRunActionFilter);
        await refreshRequestTracesFor(
          personId,
          traceDestinationFilter,
          traceOnlyActiveOpportunity,
          opportunityId,
          traceRunIdFilter
        );
        setErrorMessage(
          "Streaming de preparacion no disponible. Se uso endpoint sin streaming como respaldo."
        );
      } catch {
        const message =
          error instanceof Error ? error.message : "No se pudo preparar postulacion";
        setErrorMessage(message);
      }
    } finally {
      setIsPreparing(false);
    }
  }

  async function handleSaveNotes() {
    if (!selectedPersonId || !selectedOpportunityId || isSavingNotes) {
      return;
    }
    setIsSavingNotes(true);
    setErrorMessage(null);
    try {
      const updated = await updateOpportunity(selectedPersonId, selectedOpportunityId, {
        notes: opportunityNotes
      });
      setSavedOpportunities((current) =>
        current.map((item) =>
          item.opportunity_id === updated.opportunity_id ? updated : item
        )
      );
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudieron guardar las notas";
      setErrorMessage(message);
    } finally {
      setIsSavingNotes(false);
    }
  }

  async function handleSaveStatus() {
    if (!selectedPersonId || !selectedOpportunityId || isSavingStatus) {
      return;
    }
    setIsSavingStatus(true);
    setErrorMessage(null);
    try {
      const updated = await updateOpportunity(selectedPersonId, selectedOpportunityId, {
        status: opportunityStatus
      });
      setSavedOpportunities((current) =>
        current.map((item) =>
          item.opportunity_id === updated.opportunity_id ? updated : item
        )
      );
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo guardar el estado";
      setErrorMessage(message);
    } finally {
      setIsSavingStatus(false);
    }
  }

  async function handleSaveCulturePreferences() {
    if (!selectedPersonId || isSavingCulturePreferences) {
      return;
    }
    setIsSavingCulturePreferences(true);
    setErrorMessage(null);
    try {
      const updated = await updatePersonProfile(selectedPersonId, {
        cultural_fit_preferences: culturePreferencesState,
        culture_preferences_notes: culturePreferencesNotes
      });
      setPeople((current) =>
        current.map((item) => (item.person_id === updated.person_id ? updated : item))
      );
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudieron guardar las preferencias";
      setErrorMessage(message);
    } finally {
      setIsSavingCulturePreferences(false);
    }
  }

  async function handleSaveProfile() {
    if (!selectedPersonId || isSavingProfile) {
      return;
    }
    const fullName = profileFullName.trim();
    const location = profileLocation.trim();
    const yearsExperience = Number.parseInt(profileYearsExperienceInput.trim(), 10);
    const targetRoles = profileTargetRolesInput
      .split(/[\n,]/g)
      .map((item) => item.trim())
      .filter(Boolean);
    const skills = profileSkillsInput
      .split(/[\n,]/g)
      .map((item) => item.trim())
      .filter(Boolean);

    if (!fullName || !location || targetRoles.length === 0 || skills.length === 0) {
      setErrorMessage("Perfil incompleto: nombre, ubicacion, roles y skills son obligatorios.");
      return;
    }
    if (!Number.isFinite(yearsExperience) || yearsExperience < 0 || yearsExperience > 80) {
      setErrorMessage("Años de experiencia debe estar entre 0 y 80.");
      return;
    }

    setIsSavingProfile(true);
    setErrorMessage(null);
    try {
      const updated = await updatePersonProfile(selectedPersonId, {
        full_name: fullName,
        target_roles: targetRoles,
        location,
        years_experience: yearsExperience,
        skills
      });
      setPeople((current) =>
        current.map((item) => (item.person_id === updated.person_id ? updated : item))
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo guardar el perfil";
      setErrorMessage(message);
    } finally {
      setIsSavingProfile(false);
    }
  }

  function handleToggleCulturalOption(fieldId: string, optionValue: string, checked: boolean) {
    setCulturePreferencesState((current) => {
      const existing = current[fieldId] ?? {
        enabled: false,
        selected_values: [],
        criticality: "normal"
      };
      const selected = checked
        ? Array.from(new Set([...existing.selected_values, optionValue]))
        : existing.selected_values.filter((value) => value !== optionValue);
      return {
        ...current,
        [fieldId]: {
          ...existing,
          enabled: selected.length > 0,
          selected_values: selected
        }
      };
    });
  }

  if (view === "checking") {
    return (
      <main className="shell">
        <section className="panel">
          <p className="eyebrow">Tutor Workspace</p>
          <h1 className="compactTitle">Validando sesion...</h1>
        </section>
      </main>
    );
  }

  if (view === "login") {
    return (
      <main className="shell">
        <section className="hero">
          <p className="eyebrow">Tutor Workspace</p>
          <h1>Acceso protegido del tutor.</h1>
          <p className="lede">
            Inicia sesion para seleccionar un perfil y abrir su
            contexto de trabajo.
          </p>
        </section>

        <section className="panel authPanel">
          <form className="authForm" onSubmit={handleLogin}>
            <label className="field">
              Usuario
              <input
                autoComplete="username"
                name="username"
                onChange={(event) => setUsername(event.target.value)}
                value={username}
              />
            </label>
            <label className="field">
              Contrasena
              <input
                autoComplete="current-password"
                name="password"
                onChange={(event) => setPassword(event.target.value)}
                type="password"
                value={password}
              />
            </label>
            {errorMessage ? <p className="errorText">{errorMessage}</p> : null}
            <button className="primaryButton" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Ingresando..." : "Ingresar"}
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className={shellClassName}>
      <section className="panel workspaceTopbar">
        <div className="workspaceBrand">
          <p className="eyebrow">CareerIQ</p>
        </div>
        <div className="workspaceCenter">
          {selectedPerson ? (
            <div className="contextSelector">
              <button
                className="contextSelectorButton"
                onClick={() =>
                  setIsPersonContextMenuOpen((current) => !current)
                }
                type="button"
              >
                <span className="candidateAvatar contextSelectorAvatar">
                  {getPersonInitials(selectedPerson.full_name)}
                </span>
                <span className="contextSelectorText">
                  <strong>{selectedPerson.full_name}</strong>
                  <span>{selectedPerson.target_roles[0] ?? "Sin rol objetivo"}</span>
                </span>
                <span className="contextSelectorChevron">
                  {isPersonContextMenuOpen ? "▴" : "▾"}
                </span>
              </button>
              {isPersonContextMenuOpen ? (
                <article className="contextSelectorMenu">
                  <p className="metaText">
                    Operador: <strong>{operatorName}</strong>
                  </p>
                  <div className="contextSelectorMenuActions">
                    <button
                      onClick={() => {
                        setIsPersonContextMenuOpen(false);
                        navigateTo("/candidates");
                      }}
                      type="button"
                    >
                      Cambiar candidato
                    </button>
                    <button
                      onClick={() => {
                        setIsPersonContextMenuOpen(false);
                        navigateTo(buildContextPath(selectedPerson.person_id, "profile"));
                      }}
                      type="button"
                    >
                      Ver perfil activo
                    </button>
                  </div>
                </article>
              ) : null}
            </div>
          ) : (
            <button
              className="contextSelectorButton contextSelectorButtonEmpty"
              onClick={() => navigateTo("/candidates")}
              type="button"
            >
              Seleccionar candidato
            </button>
          )}
        </div>
        <div className="workspaceRight">
          {selectedPerson ? (
            <nav className="workspaceTabs" aria-label="Navegacion contextual">
              <button
                className={showProfilePage ? "workspaceTabButton workspaceTabButtonActive" : "workspaceTabButton"}
                onClick={() => navigateTo(buildContextPath(selectedPerson.person_id, "profile"))}
                type="button"
              >
                Perfil
              </button>
              <button
                className={
                  showOpportunitiesPage
                    ? "workspaceTabButton workspaceTabButtonActive"
                    : "workspaceTabButton"
                }
                onClick={() =>
                  navigateTo(buildContextPath(selectedPerson.person_id, "opportunities"))
                }
                type="button"
              >
                Busqueda
              </button>
              <button
                className={
                  showAnalysisPage
                    ? "workspaceTabButton workspaceTabButtonActive"
                    : "workspaceTabButton"
                }
                onClick={() => navigateTo(buildContextPath(selectedPerson.person_id, "analysis"))}
                type="button"
              >
                Análisis
              </button>
            </nav>
          ) : null}
          <div className="iconActionGroup">
            <button
              className={
                showAdminPromptsPage
                  ? "iconActionButton iconActionButtonActive"
                  : "iconActionButton"
              }
              onClick={() => navigateTo("/admin/prompts")}
              title="Administracion"
              type="button"
            >
              <svg
                aria-hidden="true"
                className="iconActionSvg"
                fill="none"
                height="16"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.8"
                viewBox="0 0 24 24"
                width="16"
              >
                <circle cx="12" cy="12" r="3.25" />
                <path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a2 2 0 1 1-4 0v-.2a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a2 2 0 0 1-2.8-2.8l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a2 2 0 1 1 0-4h.2a1 1 0 0 0 .9-.6 1 1 0 0 0-.2-1.1l-.1-.1a2 2 0 0 1 2.8-2.8l.1.1a1 1 0 0 0 1.1.2h.1a1 1 0 0 0 .6-.9V4a2 2 0 1 1 4 0v.2a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1a2 2 0 0 1 2.8 2.8l-.1.1a1 1 0 0 0-.2 1.1v.1a1 1 0 0 0 .9.6H20a2 2 0 1 1 0 4h-.2a1 1 0 0 0-.9.6z" />
              </svg>
              <span className="srOnly">Administracion</span>
            </button>
            <button
              className="iconActionButton"
              onClick={handleLogout}
              title="Cerrar sesion"
              type="button"
            >
              <svg
                aria-hidden="true"
                className="iconActionSvg"
                fill="none"
                height="16"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.8"
                viewBox="0 0 24 24"
                width="16"
              >
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <path d="m16 17 5-5-5-5" />
                <path d="M21 12H9" />
              </svg>
              <span className="srOnly">Cerrar sesion</span>
            </button>
          </div>
        </div>
      </section>

      <section className={showProfilePage ? "hero heroCompact" : "hero"}>
        <p className="eyebrow">{currentPageLabel}</p>
        <h1 className={showProfilePage ? "heroTitleCompact" : undefined}>{currentPageTitle}</h1>
        {currentPageLede ? <p className="lede">{currentPageLede}</p> : null}
      </section>

      {showCandidatesPage ? (
        <section className="panel">
        <header className="panelHeader">
          <div>
            <h2>Perfiles consultados</h2>
            <p>Selecciona el perfil activo para continuar a busqueda y alineacion.</p>
          </div>
          <div className="cardActions">
            <p className="metaText">{people.length} registrados</p>
            <button
              className={isCreateProfileFormOpen ? "activeButton" : ""}
              onClick={() =>
                setIsCreateProfileFormOpen((current) => !current)
              }
              type="button"
            >
              {isCreateProfileFormOpen ? "Ocultar alta" : "Agregar perfil"}
            </button>
          </div>
        </header>

        <div className="cards">
          {people.map((person) => (
            <article className="card" key={person.person_id}>
              <div className="cardHeader">
                <div className="candidateAvatar">{getPersonInitials(person.full_name)}</div>
                <div>
                  <span className="cardTag">{person.person_id}</span>
                  <h3>{person.full_name}</h3>
                </div>
              </div>
              <p>{person.target_roles[0] ?? "Sin rol objetivo"}</p>
              <p className="metaText">
                {person.location} · {person.years_experience} años
              </p>
              <div className="cardActions">
                <button
                  className={
                    person.person_id === selectedPersonId ? "activeButton" : ""
                  }
                  onClick={() => {
                    setSelectedPersonId(person.person_id);
                    navigateTo(buildContextPath(person.person_id, "profile"));
                  }}
                  type="button"
                >
                  {person.person_id === selectedPersonId
                    ? "Contexto activo"
                    : "Abrir perfil"}
                </button>
              </div>
            </article>
          ))}
        </div>
        {isCreateProfileFormOpen ? (
          <>
            <h3 className="subheading">Agregar perfil</h3>
            <form className="manualCard" onSubmit={handleCreatePerson}>
              <label className="field">
                Nombre completo
                <input
                  disabled={isCreatingPerson}
                  onChange={(event) => setNewPersonFullName(event.target.value)}
                  value={newPersonFullName}
                />
              </label>
              <div className="manualRow">
                <label className="field">
                  Ubicacion
                  <input
                    disabled={isCreatingPerson}
                    onChange={(event) => setNewPersonLocation(event.target.value)}
                    value={newPersonLocation}
                  />
                </label>
                <label className="field">
                  Años de experiencia
                  <input
                    disabled={isCreatingPerson}
                    max={80}
                    min={0}
                    onChange={(event) => setNewPersonYearsExperienceInput(event.target.value)}
                    type="number"
                    value={newPersonYearsExperienceInput}
                  />
                </label>
              </div>
              <label className="field">
                Roles objetivo (coma o salto de linea)
                <textarea
                  disabled={isCreatingPerson}
                  onChange={(event) => setNewPersonTargetRolesInput(event.target.value)}
                  rows={2}
                  value={newPersonTargetRolesInput}
                />
              </label>
              <label className="field">
                Skills (coma o salto de linea)
                <textarea
                  disabled={isCreatingPerson}
                  onChange={(event) => setNewPersonSkillsInput(event.target.value)}
                  rows={2}
                  value={newPersonSkillsInput}
                />
              </label>
              <div className="cardActions">
                <button className="primaryButton" disabled={isCreatingPerson} type="submit">
                  {isCreatingPerson ? "Creando..." : "Crear perfil"}
                </button>
              </div>
            </form>
          </>
        ) : null}
        </section>
      ) : null}

      {showAdminPromptsPage ? (
        <section className="panel selectedPanel">
        <header className="panelHeader">
          <div>
            <h2>Administracion de proveedores de busqueda</h2>
            <p>
              Habilita o deshabilita proveedores de vacantes desde UI para controlar
              conectividad y diagnostico.
            </p>
          </div>
          <button
            className="ghostButton"
            disabled={isLoadingSearchProviderConfigs || isLoadingPromptConfigs}
            onClick={() => setPromptConfigReloadToken((current) => current + 1)}
            type="button"
          >
            {isLoadingSearchProviderConfigs ? "Actualizando..." : "Refrescar"}
          </button>
        </header>
        {isLoadingSearchProviderConfigs ? (
          <p className="metaText">Cargando proveedores...</p>
        ) : orderedSearchProviderConfigs.length === 0 ? (
          <p className="metaText">No hay proveedores configurados.</p>
        ) : (
          <div className="promptConfigGrid">
            {orderedSearchProviderConfigs.map((provider) => {
              const isSaving = savingSearchProviderKey === provider.provider_key;
              return (
                <article className="manualCard" key={provider.provider_key}>
                  <p className="chatRole">
                    {SEARCH_PROVIDER_LABELS[provider.provider_key] ?? provider.provider_key}
                  </p>
                  <p className="metaText">provider_key: {provider.provider_key}</p>
                  <label className="checkboxRow">
                    <input
                      checked={provider.is_enabled}
                      disabled={isSaving}
                      onChange={(event) =>
                        void handleToggleSearchProvider(
                          provider.provider_key,
                          event.target.checked
                        )
                      }
                      type="checkbox"
                    />
                    <span>Proveedor habilitado</span>
                  </label>
                  <p className="metaText">
                    Ultima actualizacion: {new Date(provider.updated_at).toLocaleString()} por{" "}
                    {provider.updated_by}
                  </p>
                </article>
              );
            })}
          </div>
        )}
        </section>
      ) : null}

      {showAdminPromptsPage ? (
        <section className="panel selectedPanel">
        <header className="panelHeader">
          <div>
            <h2>Administracion de prompts (global V1)</h2>
            <p>
              Ajusta guardrails, identidad y prompts de tarea para chat/analisis/preparacion. Tambien
              puedes editar consultas Tavily para busqueda y fit cultural.
            </p>
          </div>
          <button
            className="ghostButton"
            disabled={isLoadingPromptConfigs}
            onClick={() => setPromptConfigReloadToken((current) => current + 1)}
            type="button"
          >
            {isLoadingPromptConfigs ? "Actualizando..." : "Refrescar"}
          </button>
        </header>
        {isLoadingPromptConfigs ? (
          <p className="metaText">Cargando configuracion de prompts...</p>
        ) : promptConfigs.length === 0 ? (
          <p className="metaText">No hay flujos de prompts configurados.</p>
        ) : (
          <div className="promptConfigGrid">
            {orderedPromptConfigs.map((config) => {
              const draft = promptConfigDrafts[config.flow_key] ?? {
                template_text: config.template_text,
                target_sources_input: config.target_sources.join("\n"),
                is_active: config.is_active
              };
              const isSaving = savingPromptFlowKey === config.flow_key;
              const isExpanded = Boolean(expandedPromptVersions[config.flow_key]);
              const isLoadingVersions = loadingPromptVersionsFlowKey === config.flow_key;
              const isRollingBack = rollingBackPromptFlowKey === config.flow_key;
              const versions = promptVersionsByFlow[config.flow_key] ?? [];
              return (
                <article className="manualCard" key={config.flow_key}>
                  <p className="chatRole">
                    {PROMPT_FLOW_LABELS[config.flow_key] ?? config.flow_key}
                  </p>
                  <p className="metaText">flow_key: {config.flow_key}</p>
                  <label className="checkboxRow">
                    <input
                      checked={draft.is_active}
                      disabled={isSaving}
                      onChange={(event) =>
                        handlePromptDraftChange(config.flow_key, {
                          is_active: event.target.checked
                        })
                      }
                      type="checkbox"
                    />
                    <span>Configuracion activa</span>
                  </label>
                  <label className="field">
                    Plantilla de prompt
                    <textarea
                      disabled={isSaving}
                      onChange={(event) =>
                        handlePromptDraftChange(config.flow_key, {
                          template_text: event.target.value
                        })
                      }
                      rows={5}
                      value={draft.template_text}
                    />
                  </label>
                  {PROMPT_SOURCE_FLOW_KEYS.has(config.flow_key) ? (
                    <label className="field">
                      Fuentes objetivo (coma o salto de linea)
                      <textarea
                        disabled={isSaving}
                        onChange={(event) =>
                          handlePromptDraftChange(config.flow_key, {
                            target_sources_input: event.target.value
                          })
                        }
                        rows={5}
                        value={draft.target_sources_input}
                      />
                    </label>
                  ) : (
                    <p className="metaText">Este flujo no usa fuentes objetivo.</p>
                  )}
                  <p className="metaText">
                    Ultima actualizacion: {new Date(config.updated_at).toLocaleString()} por{" "}
                    {config.updated_by}
                  </p>
                  <div className="cardActions">
                    <button
                      disabled={isSaving}
                      onClick={() => void handleSavePromptConfig(config.flow_key)}
                      type="button"
                    >
                      {isSaving ? "Guardando..." : "Guardar configuracion"}
                    </button>
                    <button
                      disabled={isSaving || isRollingBack}
                      onClick={() => handleTogglePromptVersions(config.flow_key)}
                      type="button"
                    >
                      {isExpanded ? "Ocultar versiones" : "Ver versiones"}
                    </button>
                  </div>
                  {isExpanded ? (
                    <div className="chatList">
                      {isLoadingVersions ? (
                        <p className="metaText">Cargando historial...</p>
                      ) : versions.length === 0 ? (
                        <p className="metaText">Sin versiones registradas para este flujo.</p>
                      ) : (
                        versions.map((version) => (
                          <article
                            className="chatBubble chatBubbleAssistant"
                            key={version.version_id}
                          >
                            <p className="chatRole">
                              version: {version.version_id}
                            </p>
                            <p className="metaText">
                              creada: {formatAiRunTimestamp(version.created_at)} por{" "}
                              {version.created_by} · motivo: {version.reason}
                            </p>
                            <p className="metaText">
                              snapshot origen: {version.source_updated_by} ·{" "}
                              {formatAiRunTimestamp(version.source_updated_at)}
                            </p>
                            <details className="payloadDetails">
                              <summary>Ver template versionado</summary>
                              <pre className="payloadPre">{version.template_text}</pre>
                            </details>
                            {PROMPT_SOURCE_FLOW_KEYS.has(config.flow_key) ? (
                              <details className="payloadDetails">
                                <summary>Ver target_sources versionados</summary>
                                <pre className="payloadPre">
                                  {JSON.stringify(version.target_sources, null, 2)}
                                </pre>
                              </details>
                            ) : null}
                            <div className="cardActions">
                              <button
                                disabled={isRollingBack}
                                onClick={() =>
                                  void handleRollbackPromptConfig(
                                    config.flow_key,
                                    version.version_id
                                  )
                                }
                                type="button"
                              >
                                {isRollingBack
                                  ? "Restaurando..."
                                  : "Restaurar esta version"}
                              </button>
                            </div>
                          </article>
                        ))
                      )}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
        </section>
      ) : null}

      {showProfilePage ? (
        <section className="panel selectedPanel">
        <h2>Candidato</h2>
        {selectedPerson ? (
          <div className="cvCard">
            <div className="profileSplitGrid">
              <article className="manualCard profileSectionCard">
                <label className="field">
                  Nombre completo
                  <input
                    disabled={isSavingProfile}
                    onChange={(event) => setProfileFullName(event.target.value)}
                    value={profileFullName}
                  />
                </label>
                <div className="manualRow">
                  <label className="field">
                    Ubicacion
                    <input
                      disabled={isSavingProfile}
                      onChange={(event) => setProfileLocation(event.target.value)}
                      value={profileLocation}
                    />
                  </label>
                  <label className="field">
                    Años de experiencia
                    <input
                      disabled={isSavingProfile}
                      max={80}
                      min={0}
                      onChange={(event) => setProfileYearsExperienceInput(event.target.value)}
                      type="number"
                      value={profileYearsExperienceInput}
                    />
                  </label>
                </div>
                <label className="field">
                  Roles objetivo (coma o salto de linea)
                  <textarea
                    disabled={isSavingProfile}
                    onChange={(event) => setProfileTargetRolesInput(event.target.value)}
                    rows={2}
                    value={profileTargetRolesInput}
                  />
                </label>
                <label className="field">
                  Skills (coma o salto de linea)
                  <textarea
                    disabled={isSavingProfile}
                    onChange={(event) => setProfileSkillsInput(event.target.value)}
                    rows={2}
                    value={profileSkillsInput}
                  />
                </label>
                <div className="cardActions">
                  <button
                    className="primaryButton buttonCompact"
                    disabled={isSavingProfile}
                    onClick={() => void handleSaveProfile()}
                    type="button"
                  >
                    {isSavingProfile ? "Guardando..." : "Guardar perfil"}
                  </button>
                </div>
              </article>

              <article className="manualCard profileSectionCard">
                <h3 className="subheading subheadingCompact">
                  Condiciones de trabajo y preferencias culturales
                </h3>
                <div className="cultureGrid cultureGridCompact">
                  {CULTURAL_FIELDS.map((field) => {
                    const value = culturePreferencesState[field.id] ?? {
                      enabled: false,
                      selected_values: [],
                      criticality: "normal"
                    };
                    const selectedCount = value.selected_values.length;
                    return (
                      <article className="manualCard cultureFieldCard" key={field.id}>
                        <p className="chatRole">{field.label}</p>
                        <div className="optionList optionListCompact">
                          {field.options.map((option) => (
                            <label
                              className="checkboxRow checkboxRowCompact"
                              key={`${field.id}-${option.value}`}
                            >
                              <input
                                checked={value.selected_values.includes(option.value)}
                                disabled={isSavingCulturePreferences}
                                onChange={(event) =>
                                  handleToggleCulturalOption(
                                    field.id,
                                    option.value,
                                    event.target.checked
                                  )
                                }
                                type="checkbox"
                              />
                              <span>{option.label}</span>
                            </label>
                          ))}
                        </div>
                        <div className="cultureFieldFooter">
                          {selectedCount > 0 ? (
                            <p className="metaText">{selectedCount} opcion(es) seleccionada(s)</p>
                          ) : null}
                        </div>
                      </article>
                    );
                  })}
                </div>
                <label className="field">
                  Notas abiertas sobre cultura y condiciones laborales
                  <textarea
                    disabled={isSavingCulturePreferences}
                    onChange={(event) => setCulturePreferencesNotes(event.target.value)}
                    rows={3}
                    value={culturePreferencesNotes}
                  />
                </label>
                <div className="cardActions">
                  <button
                    className="primaryButton buttonCompact"
                    disabled={isSavingCulturePreferences}
                    onClick={() => void handleSaveCulturePreferences()}
                    type="button"
                  >
                    {isSavingCulturePreferences ? "Guardando..." : "Guardar preferencias"}
                  </button>
                </div>
              </article>
            </div>
          </div>
        ) : (
          <p className="metaText">
            No hay perfil seleccionado. Elige uno para continuar.
          </p>
        )}
        </section>
      ) : null}
      {showProfilePage ? (
        <section className="panel selectedPanel">
        <header className="panelHeader">
          <div>
            <h2>CV</h2>
            <p>
              {activeCv
                ? "Resumen y vista previa del CV activo."
                : "Sube el CV para enriquecer el analisis y las respuestas."}
            </p>
          </div>
          {activeCv ? (
            <div className="cardActions">
              <button
                className={isCvUploadFormOpen ? "activeButton" : ""}
                onClick={() =>
                  setIsCvUploadFormOpen((current) => !current)
                }
                type="button"
              >
                {isCvUploadFormOpen ? "Ocultar carga" : "Reemplazar CV"}
              </button>
            </div>
          ) : null}
        </header>
        {isLoadingCv ? (
          <p className="metaText">Consultando CV activo...</p>
        ) : activeCv ? (
          <div className="cvCard">
            <article className="manualCard cvSummaryCard">
              <p className="metaText">
                Archivo: <strong>{activeCv.source_filename}</strong>
              </p>
              <div className="metaChips">
                <span className="metaChip">Extraccion: {activeCv.extraction_status}</span>
                <span className="metaChip">
                  Vector: {activeCv.vector_index_status} · chunks {activeCv.vector_chunks_indexed}
                </span>
                <span className="metaChip">
                  Texto: {activeCv.text_length} caracteres
                  {activeCv.text_truncated ? " (truncado)" : ""}
                </span>
              </div>
              <article className="chatBubble chatBubbleAssistant cvPreviewSection">
                <p className="chatRole">Vista previa extraida</p>
                <p
                  className={
                    isCvPreviewExpanded
                      ? "chatContent cvPreviewText"
                      : "chatContent cvPreviewText cvPreviewTextCollapsed"
                  }
                >
                  {isCvPreviewExpanded
                    ? cvExpandedText || "No se obtuvo texto util del archivo."
                    : cvPreviewShortText || "No se obtuvo texto util del archivo."}
                </p>
                {isCvPreviewExpanded && isLoadingCvFullText ? (
                  <p className="metaText">Cargando texto completo...</p>
                ) : null}
                {hasMoreCvPreview ? (
                  <div className="cardActions">
                    <button
                      className="ghostButton buttonCompact"
                      disabled={isLoadingCvFullText}
                      onClick={() => void handleToggleCvPreview()}
                      type="button"
                    >
                      {isCvPreviewExpanded ? "Ver menos" : "Ver mas"}
                    </button>
                  </div>
                ) : null}
              </article>
            </article>
          </div>
        ) : (
          <p className="metaText">
            No hay CV activo para este perfil. Puedes operar sin CV y cargarlo despues.
          </p>
        )}
        {isCvUploadFormOpen ? (
          <>
            <form className="cvForm cvFormCompact" onSubmit={handleUploadCv}>
              <label className="ghostButton buttonCompact filePickerButton" htmlFor="cv-upload-input">
                Seleccionar archivo
              </label>
              <input
                className="filePickerInput"
                accept=".pdf,.txt,.md"
                disabled={!selectedPersonId || isUploadingCv}
                id="cv-upload-input"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  setSelectedCvFile(file);
                }}
                type="file"
              />
              <button
                className="primaryButton buttonCompact"
                disabled={!selectedPersonId || !selectedCvFile || isUploadingCv}
                type="submit"
              >
                {isUploadingCv ? "Cargando..." : activeCv ? "Reemplazar CV" : "Subir CV"}
              </button>
            </form>
            <p className="metaText">
              Archivo para subir:{" "}
              <strong>{selectedCvFile ? selectedCvFile.name : "Ninguno seleccionado"}</strong>
            </p>
          </>
        ) : null}
        </section>
      ) : null}
      {showConversationSection ? (
        <>
          <button
            className="chatDrawerToggle"
            onClick={() => setIsChatDrawerOpen((current) => !current)}
            type="button"
          >
            {isChatDrawerOpen ? "Cerrar chat" : "Chat IA"}
          </button>
          <aside
            aria-hidden={!isChatDrawerOpen}
            className={isChatDrawerOpen ? "chatDrawer chatDrawerOpen" : "chatDrawer"}
          >
            <header className="chatDrawerHeader">
              <div>
                <p className="eyebrow">Asistente IA</p>
                <h2>Conversacion contextual</h2>
                <p className="metaText">
                  {selectedPerson ? selectedPerson.full_name : "Sin persona activa"}
                </p>
              </div>
              <button
                className="ghostButton"
                onClick={() => setIsChatDrawerOpen(false)}
                type="button"
              >
                Cerrar
              </button>
            </header>
            <div className="chatDrawerBody">
              {isConversationLoading ? (
                <p className="metaText">Cargando conversacion...</p>
              ) : (
                <div className="chatList">
                  {(conversation?.messages ?? []).length === 0 && !isSendingMessage ? (
                    <p className="metaText">No hay mensajes aun para este perfil.</p>
                  ) : (
                    conversation?.messages.map((message) => (
                      <article
                        className={
                          message.role === "user"
                            ? "chatBubble chatBubbleUser"
                            : "chatBubble chatBubbleAssistant"
                        }
                        key={message.message_id}
                      >
                        <p className="chatRole">{message.role === "user" ? "Tutor" : "Asistente"}</p>
                        <p className="chatContent">{message.content}</p>
                      </article>
                    ))
                  )}
                  {isSendingMessage ? (
                    <article className="chatBubble chatBubbleAssistant">
                      <p className="chatRole">Asistente (SSE)</p>
                      <p className="chatContent">
                        {streamingAssistantText || "Procesando respuesta..."}
                      </p>
                    </article>
                  ) : null}
                </div>
              )}
            </div>
            <div className="chatQuickStarts">
              {chatQuickStarts.map((message) => (
                <button
                  disabled={!selectedPersonId || isSendingMessage}
                  key={message}
                  onClick={() => void handleQuickStart(message)}
                  type="button"
                >
                  {message}
                </button>
              ))}
            </div>
            <form className="chatForm chatDrawerForm" onSubmit={handleSendMessage}>
              <input
                disabled={!selectedPersonId || isSendingMessage}
                onChange={(event) => setChatInput(event.target.value)}
                placeholder="Escribe un mensaje para este perfil..."
                value={chatInput}
              />
              <button
                className="primaryButton"
                disabled={!selectedPersonId || isSendingMessage || !chatInput.trim()}
                type="submit"
              >
                {isSendingMessage ? "Enviando..." : "Enviar"}
              </button>
            </form>
          </aside>
        </>
      ) : null}
      {showOpportunitiesPage ? (
        <section className="panel selectedPanel">
        <h2>Descubrimiento de vacantes</h2>
        <div className="opportunityModeTabs" role="tablist" aria-label="Modo de descubrimiento">
          <button
            className={
              opportunityDiscoveryMode === "search"
                ? "opportunityModeTab opportunityModeTabActive"
                : "opportunityModeTab"
            }
            aria-selected={opportunityDiscoveryMode === "search"}
            onClick={() => setOpportunityDiscoveryMode("search")}
            role="tab"
            type="button"
          >
            Búsqueda
          </button>
          <button
            className={
              opportunityDiscoveryMode === "manual"
                ? "opportunityModeTab opportunityModeTabActive"
                : "opportunityModeTab"
            }
            aria-selected={opportunityDiscoveryMode === "manual"}
            onClick={() => setOpportunityDiscoveryMode("manual")}
            role="tab"
            type="button"
          >
            Carga manual
          </button>
        </div>
        {opportunityDiscoveryMode === "search" ? (
          <>
            <form className="chatForm searchComposerForm" onSubmit={handleSearch}>
              <label className="field">
                Buscar oportunidades, roles o empresas
                <input
                  disabled={!selectedPersonId || isSearching}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Product Designer, UX Researcher, Bogota..."
                  value={searchQuery}
                />
              </label>
              {searchRoleKeywords.length > 0 ? (
                <article className="manualCard searchRoleComposer">
                  <div className="searchRoleHeader">
                    <div className="metaChips roleChipGroup">
                      {searchRoleKeywords.map((role) => {
                        const selected = hasRoleToken(searchQuery, role);
                        return (
                          <button
                            className={selected ? "metaChip metaChipActive" : "metaChip"}
                            key={`search-role-${role}`}
                            onClick={() => handleToggleSearchRole(role)}
                            type="button"
                          >
                            {role}
                          </button>
                        );
                      })}
                    </div>
                    <div className="cardActions searchRoleActions">
                      <button
                        className="ghostButton miniButton"
                        disabled={!selectedPersonId || searchRoleKeywords.length === 0}
                        onClick={handleSelectAllSearchRoles}
                        type="button"
                      >
                        Seleccionar todas
                      </button>
                      <button
                        className="ghostButton miniButton"
                        disabled={!selectedPersonId || selectedSearchRoleCount === 0}
                        onClick={handleClearSearchRoles}
                        type="button"
                      >
                        Limpiar seleccion
                      </button>
                    </div>
                  </div>
                </article>
              ) : null}
              <div className="searchActionRow">
                <button
                  className="primaryButton searchSubmitButton"
                  disabled={!selectedPersonId || isSearching || !searchQuery.trim()}
                  type="submit"
                >
                  {isSearching ? "Buscando..." : "Buscar"}
                </button>
              </div>
            </form>
            {searchWarnings.length > 0 ? (
              <p className="metaText">Avisos: {searchWarnings.join(" | ")}</p>
            ) : null}
            <div className="chatList">
              {searchResults.length === 0 ? (
                <p className="metaText">No hay resultados de busqueda recientes.</p>
              ) : (
                searchResults.map((result) => (
                  <article
                    className={
                      selectedSearchResultId === result.search_result_id
                        ? "chatBubble chatBubbleAssistant searchResultCard searchResultCardActive"
                        : "chatBubble chatBubbleAssistant searchResultCard"
                    }
                    key={result.search_result_id}
                  >
                    <p className="chatRole">{result.source_provider}</p>
                    <p className="chatContent">{result.title}</p>
                    <div className="metaChips">
                      <span className="metaChip">{result.company || "Empresa no identificada"}</span>
                      <span className="metaChip">{result.location || "Ubicacion no especificada"}</span>
                    </div>
                    <p className="metaText">
                      <ExternalUrlText url={result.source_url} />
                    </p>
                    <p className="metaText">{result.snippet}</p>
                    <div className="cardActions">
                      <button
                        className={
                          selectedSearchResultId === result.search_result_id ? "activeButton" : ""
                        }
                        onClick={() =>
                          setSelectedSearchResultId((current) =>
                            current === result.search_result_id ? null : result.search_result_id
                          )
                        }
                        type="button"
                      >
                        {selectedSearchResultId === result.search_result_id
                          ? "Cerrar detalle"
                          : "Abrir detalle"}
                      </button>
                      <button
                        disabled={savingResultId === result.search_result_id}
                        onClick={() => void handleSaveSearchResult(result)}
                        type="button"
                      >
                        {savingResultId === result.search_result_id
                          ? "Guardando..."
                          : "Guardar como oportunidad"}
                      </button>
                    </div>
                    {selectedSearchResultId === result.search_result_id ? (
                      <article className="inlineDetailCard">
                        <p className="chatRole">Detalle (no persistido)</p>
                        <p className="metaText">
                          Proveedor: {result.source_provider} · Empresa:{" "}
                          {result.company || "No identificada"} · Ubicacion:{" "}
                          {result.location || "No especificada"}
                        </p>
                        <p className="metaText">
                          URL: <ExternalUrlText noValueText="No disponible" url={result.source_url} />
                        </p>
                        <article className="chatBubble chatBubbleAssistant">
                          <p className="chatRole">Snippet</p>
                          <p className="chatContent">{result.snippet || "Sin snippet"}</p>
                        </article>
                        <article className="chatBubble chatBubbleUser">
                          <p className="chatRole">Payload normalizado</p>
                          <pre className="payloadPre">
                            {JSON.stringify(result.normalized_payload, null, 2)}
                          </pre>
                        </article>
                        <p className="metaText">
                          Capturado: {new Date(result.captured_at).toLocaleString()}
                        </p>
                      </article>
                    ) : null}
                  </article>
                ))
              )}
            </div>
            {searchProviderStatus.length > 0 ? (
              <details className="collapsibleSection providerStatusPanel">
                <summary>Log tecnico de proveedores (ultima busqueda)</summary>
                <div className="providerStatusList">
                  {searchProviderStatus.map((status) => {
                    const diagnostic = buildSearchProviderDiagnostic(status);
                    const providerLabel =
                      SEARCH_PROVIDER_LABELS[status.provider_key] ?? status.provider_key;
                    return (
                      <article
                        className="providerStatusItem"
                        key={`provider-status-${status.provider_key}`}
                      >
                        <p className="providerStatusTitle">{providerLabel}</p>
                        <pre className="providerStatusLog">{`${status.provider_key} | ${diagnostic.statusLabel} | results=${status.results_count} | reason=${status.reason}`}</pre>
                        {status.query_truncated ? (
                          <p className="providerStatusHint">query_truncated=true</p>
                        ) : null}
                        {diagnostic.rawReason ? (
                          <details className="payloadDetails">
                            <summary>Detalle tecnico</summary>
                            <pre className="providerStatusLog providerStatusLogMuted">
                              {diagnostic.rawReason}
                            </pre>
                          </details>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              </details>
            ) : null}
          </>
        ) : (
          <form className="manualCard opportunityManualPanel" onSubmit={handleImportByUrl}>
            <p className="chatRole">Carga manual de oportunidades</p>
            <input
              disabled={!selectedPersonId || isImportingUrl}
              onChange={(event) => setManualUrl(event.target.value)}
              placeholder="https://sitio.com/vacante"
              value={manualUrl}
            />
            <input
              disabled={!selectedPersonId || isImportingUrl}
              onChange={(event) => setManualUrlTitle(event.target.value)}
              placeholder="Titulo (opcional)"
              value={manualUrlTitle}
            />
            <div className="manualRow">
              <input
                disabled={!selectedPersonId || isImportingUrl}
                onChange={(event) => setManualUrlCompany(event.target.value)}
                placeholder="Empresa (opcional)"
                value={manualUrlCompany}
              />
              <input
                disabled={!selectedPersonId || isImportingUrl}
                onChange={(event) => setManualUrlLocation(event.target.value)}
                placeholder="Ubicacion (opcional)"
                value={manualUrlLocation}
              />
            </div>
            <textarea
              disabled={!selectedPersonId || isImportingUrl}
              onChange={(event) => setManualUrlRawText(event.target.value)}
              placeholder="Descripcion o snapshot textual (obligatorio)"
              rows={3}
              value={manualUrlRawText}
            />
            <p className="metaText">
              Requerido: describe la vacante (minimo 8 caracteres).
            </p>
            <button
              className="primaryButton"
              disabled={
                !selectedPersonId ||
                isImportingUrl ||
                !manualUrl.trim() ||
                manualUrlRawText.trim().length < 8
              }
              type="submit"
            >
              {isImportingUrl ? "Importando..." : "Cargar"}
            </button>
          </form>
        )}
        <h3 className="subheading savedOpportunitiesHeading">Oportunidades guardadas</h3>
        {isLoadingOpportunities ? (
          <p className="metaText">Cargando oportunidades...</p>
        ) : savedOpportunities.length === 0 ? (
          <p className="metaText">No hay oportunidades guardadas para este perfil.</p>
        ) : (
          <div className="chatList">
            {savedOpportunities.map((item) => (
              <article
                className="chatBubble chatBubbleUser savedOpportunityCard"
                key={item.opportunity_id}
              >
                <p className="chatRole savedOpportunityStatus">{item.status.toUpperCase()}</p>
                <p className="chatContent savedOpportunityTitle">{item.title}</p>
                <div className="metaChips">
                  <span className="metaChip">{item.company || "Empresa no identificada"}</span>
                  <span className="metaChip">{item.location || "Ubicacion no especificada"}</span>
                </div>
                <p className="metaText savedOpportunityLink">
                  <ExternalUrlText url={item.source_url} />
                </p>
              </article>
            ))}
          </div>
        )}
        </section>
      ) : null}
      {showAnalysisPage ? (
        <section className="panel selectedPanel">
        <h2>Analisis y artefactos</h2>
        <h3 className="subheading">Oportunidades guardadas (acciones IA)</h3>
        {isLoadingOpportunities ? (
          <p className="metaText">Cargando oportunidades...</p>
        ) : savedOpportunities.length === 0 ? (
          <p className="metaText">No hay oportunidades guardadas para este perfil.</p>
        ) : (
          <div className="chatList">
            {savedOpportunities.map((item) => (
              <article className="chatBubble chatBubbleUser" key={`analysis-${item.opportunity_id}`}>
                <p className="chatRole">{item.status}</p>
                <p className="chatContent">{item.title}</p>
                <div className="metaChips">
                  <span className="metaChip">{item.company || "Empresa no identificada"}</span>
                  <span className="metaChip">{item.location || "Ubicacion no especificada"}</span>
                </div>
                <p className="metaText">
                  <ExternalUrlText url={item.source_url} />
                </p>
                <div className="cardActions">
                  <button
                    className={
                      selectedOpportunityId === item.opportunity_id ? "activeButton" : ""
                    }
                    onClick={() => setSelectedOpportunityId(item.opportunity_id)}
                    type="button"
                  >
                    {selectedOpportunityId === item.opportunity_id ? "Seleccionada" : "Seleccionar"}
                  </button>
                  <button
                    disabled={isAnalyzingProfile}
                    onClick={() => void handleAnalyzeProfileMatch(item.opportunity_id)}
                    type="button"
                  >
                    {isAnalyzingProfile && selectedOpportunityId === item.opportunity_id
                      ? "Analizando perfil..."
                      : "Analizar perfil"}
                  </button>
                  <button
                    disabled={isAnalyzingCultural}
                    onClick={() => void handleAnalyzeCulturalFit(item.opportunity_id)}
                    type="button"
                  >
                    {isAnalyzingCultural && selectedOpportunityId === item.opportunity_id
                      ? "Analizando cultura..."
                      : "Analizar cultura"}
                  </button>
                  <button
                    disabled={isPreparing}
                    onClick={() => void handlePrepare(item.opportunity_id)}
                    type="button"
                  >
                    {isPreparing && selectedOpportunityId === item.opportunity_id
                      ? "Preparando..."
                      : "Preparar seleccion"}
                  </button>
                  <button
                    disabled={isLoadingArtifacts}
                    onClick={() => void refreshArtifacts(item.opportunity_id)}
                    type="button"
                  >
                    {isLoadingArtifacts && selectedOpportunityId === item.opportunity_id
                      ? "Cargando..."
                      : "Artefactos"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
        {selectedOpportunity ? (
          <div className="cvCard">
            <p className="metaText">
              Oportunidad activa: <strong>{selectedOpportunity.title}</strong>
            </p>
            <label className="field">
              Estado (V1)
              <select
                disabled={isSavingStatus}
                onChange={(event) => setOpportunityStatus(event.target.value)}
                value={opportunityStatus}
              >
                {OPPORTUNITY_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
            <div className="cardActions">
              <button
                disabled={isSavingStatus}
                onClick={() => void handleSaveStatus()}
                type="button"
              >
                {isSavingStatus ? "Guardando estado..." : "Guardar estado"}
              </button>
            </div>
            <label className="field">
              Notas operativas (V1)
              <textarea
                disabled={isSavingNotes}
                onChange={(event) => setOpportunityNotes(event.target.value)}
                rows={4}
                value={opportunityNotes}
              />
            </label>
            <div className="cardActions">
              <button
                disabled={isSavingNotes}
                onClick={() => void handleSaveNotes()}
                type="button"
              >
                {isSavingNotes ? "Guardando notas..." : "Guardar notas"}
              </button>
            </div>
            <label className="checkboxRow">
              <input
                checked={forceRecomputeAi}
                onChange={(event) => setForceRecomputeAi(event.target.checked)}
                type="checkbox"
              />
              <span>Forzar recalculo IA (si no, usa ultimo persistido)</span>
            </label>
            <p className="metaText">Preparar materiales: selecciona lo que quieres generar.</p>
            <div className="optionList">
              <label className="checkboxRow">
                <input
                  checked={prepareGuidanceSelected}
                  onChange={(event) => setPrepareGuidanceSelected(event.target.checked)}
                  type="checkbox"
                />
                <span>Ayuda textual</span>
              </label>
              <label className="checkboxRow">
                <input
                  checked={prepareCoverSelected}
                  onChange={(event) => setPrepareCoverSelected(event.target.checked)}
                  type="checkbox"
                />
                <span>Carta de presentacion</span>
              </label>
              <label className="checkboxRow">
                <input
                  checked={prepareSummarySelected}
                  onChange={(event) => setPrepareSummarySelected(event.target.checked)}
                  type="checkbox"
                />
                <span>Resumen adaptado</span>
              </label>
            </div>
            <div className="manualRow">
              <label className="field">
                Filtro historico IA
                <select
                  onChange={(event) => setAiRunActionFilter(event.target.value)}
                  value={aiRunActionFilter}
                >
                  {AI_RUN_ACTION_FILTERS.map((item) => (
                    <option key={item.value || "all"} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="cardActions alignEnd">
                <button
                  disabled={isLoadingAiRuns}
                  onClick={() =>
                    selectedPersonId && selectedOpportunity
                      ? void refreshAiRunsFor(
                          selectedPersonId,
                          selectedOpportunity.opportunity_id,
                          aiRunActionFilter
                        )
                      : undefined
                  }
                  type="button"
                >
                  {isLoadingAiRuns ? "Cargando historico..." : "Refrescar historico IA"}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <p className="metaText">
            Selecciona una oportunidad guardada para analizar y preparar postulacion.
          </p>
        )}
        <article className="manualCard analysisResultsPanel">
          <p className="chatRole">Resultados</p>
          {!analysisText &&
          !culturalConfidence &&
          culturalWarnings.length === 0 &&
          culturalSignals.length === 0 &&
          !semanticEvidence &&
          !guidanceText &&
          artifacts.length === 0 ? (
            <p className="metaText">
              Todavia no hay resultados generados para la oportunidad activa.
            </p>
          ) : null}
          {analysisText ? (
            <article className="chatBubble chatBubbleAssistant">
              <p className="chatRole">Analisis</p>
              <p className="chatContent">{analysisText}</p>
            </article>
          ) : null}
          {culturalConfidence ? (
            <p className="metaText">
              Confianza fit cultural: <strong>{culturalConfidence}</strong>
            </p>
          ) : null}
          {culturalWarnings.length > 0 ? (
            <article className="chatBubble chatBubbleAssistant">
              <p className="chatRole">Advertencias culturales</p>
              <p className="chatContent">{culturalWarnings.join("\n")}</p>
            </article>
          ) : null}
          {culturalSignals.length > 0 ? (
            <details className="collapsibleSection">
              <summary>Senales culturales ({culturalSignals.length})</summary>
              <div className="chatList">
                {culturalSignals.map((signal) => (
                  <article
                    className="chatBubble chatBubbleAssistant"
                    key={`${signal.source_url}|${signal.title}`}
                  >
                    <p className="chatRole">{signal.source_provider}</p>
                    <p className="chatContent">{signal.title}</p>
                    <p className="metaText">
                      <ExternalUrlText noValueText="URL no disponible" url={signal.source_url} />
                    </p>
                    <p className="metaText">{signal.snippet}</p>
                  </article>
                ))}
              </div>
            </details>
          ) : null}
          {semanticEvidence ? (
            <details className="collapsibleSection">
              <summary>Evidencia semantica CV ({semanticEvidence.source})</summary>
              <article className="chatBubble chatBubbleAssistant">
                <p className="metaText">top_k: {semanticEvidence.top_k}</p>
                <p className="metaText">{semanticEvidence.query}</p>
                {semanticEvidence.snippets.length > 0 ? (
                  <div className="chatList">
                    {semanticEvidence.snippets.map((snippet, index) => (
                      <article
                        className="chatBubble chatBubbleUser semanticSnippetBubble"
                        key={`cv-snippet-${index}`}
                      >
                        <p className="chatRole">CV-{index + 1}</p>
                        <p className="chatContent">{snippet}</p>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="chatContent">No hay snippets disponibles para esta oportunidad.</p>
                )}
              </article>
            </details>
          ) : null}
          <article className="manualCard artifactPanel">
            <p className="chatRole">Panel de artefactos (V1)</p>
            {!guidanceText && artifacts.length === 0 ? (
              <p className="metaText">
                Aun no hay materiales generados para esta oportunidad.
              </p>
            ) : (
              <div className="artifactList">
                {guidanceText ? (
                  <article className="artifactItem">
                    <div className="panelHeader">
                      <div>
                        <p className="chatRole">Guia de perfil</p>
                        <p className="metaText">Ayuda textual contextual</p>
                      </div>
                      <div className="cardActions">
                        <button
                          onClick={() =>
                            void handleCopyArtifactContent("guidance_text", guidanceText)
                          }
                          type="button"
                        >
                          {copiedArtifactKey === "guidance_text" ? "Copiado" : "Copiar"}
                        </button>
                      </div>
                    </div>
                    <p className="chatContent artifactContent">{guidanceText}</p>
                  </article>
                ) : null}
                {artifacts.map((artifact) => {
                  const copyKey = `${artifact.artifact_type}:${artifact.artifact_id}`;
                  return (
                    <article className="artifactItem" key={artifact.artifact_id}>
                      <div className="panelHeader">
                        <div>
                          <p className="chatRole">{getArtifactTypeLabel(artifact.artifact_type)}</p>
                          <p className="metaText">artifact_id: {artifact.artifact_id}</p>
                        </div>
                        <div className="cardActions">
                          <button
                            onClick={() =>
                              void handleCopyArtifactContent(copyKey, artifact.content)
                            }
                            type="button"
                          >
                            {copiedArtifactKey === copyKey ? "Copiado" : "Copiar"}
                          </button>
                        </div>
                      </div>
                      <p className="chatContent artifactContent">{artifact.content}</p>
                    </article>
                  );
                })}
              </div>
            )}
          </article>
        </article>
        {selectedOpportunity ? (
          <details className="collapsibleSection">
            <summary>Historico IA (persistido)</summary>
            <article className="manualCard">
              {isLoadingAiRuns ? (
                <p className="metaText">Cargando ejecuciones...</p>
              ) : aiRuns.length === 0 ? (
                <p className="metaText">
                  No hay ejecuciones para el filtro seleccionado.
                </p>
              ) : (
                <div className="chatList">
                  {aiRuns.map((run) => {
                    const previewText = getAiRunPreviewText(run);
                    const isFocused = focusedRunId === run.run_id;
                    return (
                      <article
                        className={
                          isFocused
                            ? "chatBubble chatBubbleAssistant searchResultCard searchResultCardActive"
                            : "chatBubble chatBubbleAssistant"
                        }
                        key={run.run_id}
                      >
                        <p className="chatRole">
                          {AI_RUN_ACTION_LABELS[run.action_key] ?? run.action_key}
                        </p>
                        <p className="metaText">
                          run_id: {run.run_id} · actualizado:{" "}
                          {formatAiRunTimestamp(run.updated_at)}
                          {run.is_current ? " · vigente" : ""}
                        </p>
                        <div className="cardActions">
                          <button
                            onClick={() =>
                              handleFocusRunTrace(run.run_id, run.opportunity_id)
                            }
                            type="button"
                          >
                            Ver request exacto
                          </button>
                          <button
                            onClick={() =>
                              handleFocusRunResponse(run.run_id, run.opportunity_id)
                            }
                            type="button"
                          >
                            Ver request + response
                          </button>
                        </div>
                        {previewText ? (
                          <p className="chatContent">{previewText}</p>
                        ) : (
                          <p className="metaText">
                            Sin resumen textual directo. Revisa payload estructurado.
                          </p>
                        )}
                        <details className="payloadDetails">
                          <summary>Ver payload</summary>
                          <pre className="payloadPre">
                            {JSON.stringify(run.result_payload, null, 2)}
                          </pre>
                        </details>
                      </article>
                    );
                  })}
                </div>
              )}
            </article>
          </details>
        ) : null}
        </section>
      ) : null}
      {showAnalysisPage ? (
        <section className="panel selectedPanel">
        <header className="panelHeader">
          <div>
            <h2>Trazas de requests IA/API</h2>
            <p>
              Guarda y muestra el request exacto enviado a OpenAI, Tavily y proveedores
              de busqueda.
            </p>
          </div>
          <button
            className="ghostButton"
            disabled={!selectedPersonId || isLoadingRequestTraces}
            onClick={() =>
              selectedPersonId
                ? void refreshRequestTracesFor(
                    selectedPersonId,
                    traceDestinationFilter,
                    traceOnlyActiveOpportunity,
                    selectedOpportunityId,
                    traceRunIdFilter
                  )
                : undefined
            }
            type="button"
          >
            {isLoadingRequestTraces ? "Refrescando..." : "Refrescar trazas"}
          </button>
        </header>
        <details className="collapsibleSection">
          <summary>Trazas IA/API</summary>
          {!selectedPersonId ? (
            <p className="metaText">Selecciona una persona para consultar trazas.</p>
          ) : (
            <>
            <div className="manualRow">
              <label className="field">
                Destino
                <select
                  onChange={(event) => setTraceDestinationFilter(event.target.value)}
                  value={traceDestinationFilter}
                >
                  {TRACE_DESTINATION_FILTERS.map((item) => (
                    <option key={item.value || "all"} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="checkboxRow alignEnd">
                <input
                  checked={traceOnlyActiveOpportunity}
                  disabled={!selectedOpportunityId}
                  onChange={(event) => setTraceOnlyActiveOpportunity(event.target.checked)}
                  type="checkbox"
                />
                <span>Solo oportunidad activa</span>
              </label>
            </div>
            {traceRunIdFilter ? (
              <div className="cardActions">
                <p className="metaText">Filtro run_id activo: {traceRunIdFilter}</p>
                <button
                  onClick={() => {
                    setTraceRunIdFilter("");
                    setFocusedRunId("");
                  }}
                  type="button"
                >
                  Limpiar filtro run_id
                </button>
              </div>
            ) : null}
            {focusedRunId ? (
              <article className="manualCard">
                <p className="chatRole">Vista unificada por run_id</p>
                <p className="metaText">
                  run_id: {focusedRunId} · requests: {focusedRunRequestTraces.length}
                </p>
                {focusedRun ? (
                  <>
                    <p className="metaText">
                      accion:{" "}
                      {AI_RUN_ACTION_LABELS[focusedRun.action_key] ?? focusedRun.action_key} ·
                      actualizado: {formatAiRunTimestamp(focusedRun.updated_at)}
                    </p>
                    <details className="payloadDetails">
                      <summary>Ver response payload persistido</summary>
                      <pre className="payloadPre">
                        {JSON.stringify(focusedRun.result_payload, null, 2)}
                      </pre>
                    </details>
                  </>
                ) : (
                  <p className="metaText">
                    La respuesta de este run no esta cargada en el panel actual.
                  </p>
                )}
              </article>
            ) : null}
            {isLoadingRequestTraces ? (
              <p className="metaText">Cargando trazas...</p>
            ) : requestTraces.length === 0 ? (
              <p className="metaText">No hay trazas para los filtros seleccionados.</p>
            ) : (
              <div className="chatList">
                {requestTraceGroups.map((group) => {
                  const linkedRun = group.run_id ? aiRunsById.get(group.run_id) ?? null : null;
                  return (
                    <article className="manualCard" key={group.group_id}>
                      <p className="chatRole">
                        {group.run_id ? `run_id: ${group.run_id}` : "run_id: N/A"}
                      </p>
                      <p className="metaText">
                        {group.run_id
                          ? linkedRun
                            ? `accion: ${AI_RUN_ACTION_LABELS[linkedRun.action_key] ?? linkedRun.action_key}`
                            : "accion: sin respuesta cargada"
                          : "trazas sin enlace a ejecucion IA persistida"}
                        {" · "}
                        total requests: {group.items.length}
                      </p>
                      {group.run_id ? (
                        <div className="cardActions">
                          <button
                            onClick={() =>
                              handleFocusRunResponse(group.run_id, group.opportunity_id)
                            }
                            type="button"
                          >
                            Ver response asociada
                          </button>
                          <button
                            onClick={() =>
                              handleFocusRunTrace(group.run_id, group.opportunity_id)
                            }
                            type="button"
                          >
                            Filtrar requests de este run
                          </button>
                        </div>
                      ) : null}
                      <div className="chatList">
                        {group.items.map((trace) => (
                          <article className="chatBubble chatBubbleAssistant" key={trace.trace_id}>
                            <p className="chatRole">
                              {trace.destination.toUpperCase()} · {trace.flow_key}
                            </p>
                            <p className="metaText">
                              trace_id: {trace.trace_id} · oportunidad:{" "}
                              {trace.opportunity_id || "N/A"} · run_id:{" "}
                              {trace.run_id || "N/A"} · fecha:{" "}
                              {formatRequestTraceTimestamp(trace.created_at)}
                            </p>
                            <details className="payloadDetails">
                              <summary>Ver request exacto</summary>
                              <pre className="payloadPre">
                                {JSON.stringify(trace.request_payload, null, 2)}
                              </pre>
                            </details>
                          </article>
                        ))}
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
            </>
          )}
        </details>
        </section>
      ) : null}
      {errorMessage ? <p className="errorText">{errorMessage}</p> : null}
    </main>
  );
}
