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
  SearchResult,
  SemanticEvidence,
  analyzeCulturalFitStream,
  analyzeProfileMatchStream,
  analyzeCulturalFit,
  analyzeProfileMatch,
  createPerson,
  getConversation,
  getActiveCV,
  getSession,
  importOpportunityByText,
  importOpportunityByUrl,
  listOpportunityAiRuns,
  listOpportunityArtifacts,
  listOpportunities,
  listPersons,
  listPromptConfigs,
  listPromptConfigVersions,
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
  updatePromptConfig as updatePromptConfigApi,
  updatePerson as updatePersonProfile,
  updateOpportunity,
  uploadCV
} from "./api";

type ViewState = "checking" | "login" | "workspace";
const OPPORTUNITY_STATUSES = [
  "detected",
  "analyzed",
  "prioritized",
  "application_prepared",
  "applied",
  "discarded"
] as const;

const AI_RUN_ACTION_LABELS: Record<string, string> = {
  analyze_profile_match: "Analyze perfil-vacante",
  analyze_cultural_fit: "Analyze fit cultural",
  prepare_guidance_text: "Prepare ayuda textual",
  prepare_cover_letter: "Prepare carta de presentacion",
  prepare_experience_summary: "Prepare resumen de experiencia"
};

const AI_RUN_ACTION_FILTERS: Array<{ value: string; label: string }> = [
  { value: "", label: "Todas las acciones" },
  { value: "analyze_profile_match", label: "Analyze perfil-vacante" },
  { value: "analyze_cultural_fit", label: "Analyze fit cultural" },
  { value: "prepare_guidance_text", label: "Prepare ayuda textual" },
  { value: "prepare_cover_letter", label: "Prepare carta de presentacion" },
  { value: "prepare_experience_summary", label: "Prepare resumen de experiencia" }
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
  guardrails_core: "Guardrails Core (global)",
  system_identity: "System Identity (global)",
  task_chat: "Task Prompt: Chat",
  task_analyze_profile_match: "Task Prompt: Analyze Perfil-Vacante",
  task_analyze_cultural_fit: "Task Prompt: Analyze Fit Cultural",
  task_prepare_guidance: "Task Prompt: Prepare Guidance",
  task_prepare_cover_letter: "Task Prompt: Prepare Carta",
  task_prepare_experience_summary: "Task Prompt: Prepare Resumen"
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

type PromptConfigDraft = {
  template_text: string;
  target_sources_input: string;
  is_active: boolean;
};

const CRITICALITY_OPTIONS: Array<{
  value: CulturalFieldPreference["criticality"];
  label: string;
}> = [
  { value: "normal", label: "Normal" },
  { value: "high_penalty", label: "Penalizacion alta" },
  { value: "non_negotiable", label: "No negociable" }
];

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
  const [selectedSearchResultId, setSelectedSearchResultId] = useState<string | null>(null);
  const [searchWarnings, setSearchWarnings] = useState<string[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [manualUrl, setManualUrl] = useState("");
  const [manualUrlTitle, setManualUrlTitle] = useState("");
  const [manualUrlCompany, setManualUrlCompany] = useState("");
  const [manualUrlLocation, setManualUrlLocation] = useState("");
  const [manualUrlRawText, setManualUrlRawText] = useState("");
  const [manualTextTitle, setManualTextTitle] = useState("");
  const [manualTextCompany, setManualTextCompany] = useState("");
  const [manualTextLocation, setManualTextLocation] = useState("");
  const [manualTextRawText, setManualTextRawText] = useState("");
  const [isImportingUrl, setIsImportingUrl] = useState(false);
  const [isImportingText, setIsImportingText] = useState(false);
  const [savedOpportunities, setSavedOpportunities] = useState<Opportunity[]>([]);
  const [activeCv, setActiveCv] = useState<ActiveCV | null>(null);
  const [selectedCvFile, setSelectedCvFile] = useState<File | null>(null);
  const [isLoadingCv, setIsLoadingCv] = useState(false);
  const [isUploadingCv, setIsUploadingCv] = useState(false);
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
      } catch {
        setView("login");
      }
    };
    void boot();
  }, []);

  useEffect(() => {
    const loadPromptConfigs = async () => {
      if (view !== "workspace") {
        setPromptConfigs([]);
        setPromptConfigDrafts({});
        setPromptVersionsByFlow({});
        setExpandedPromptVersions({});
        return;
      }
      setIsLoadingPromptConfigs(true);
      setErrorMessage(null);
      try {
        const items = await listPromptConfigs();
        setPromptConfigs(items);
        setPromptConfigDrafts(buildPromptConfigDrafts(items));
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "No se pudo cargar la configuracion de prompts";
        setErrorMessage(message);
      } finally {
        setIsLoadingPromptConfigs(false);
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
        setSelectedCvFile(null);
        return;
      }
      setIsLoadingCv(true);
      setErrorMessage(null);
      try {
        const item = await getActiveCV(selectedPersonId);
        setActiveCv(item);
      } catch (error) {
        const message = error instanceof Error ? error.message : "No se pudo cargar el CV activo";
        setErrorMessage(message);
      } finally {
        setIsLoadingCv(false);
      }
    };
    void loadActiveCv();
  }, [selectedPersonId, view]);

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
    setSelectedSearchResultId(null);
    setSearchWarnings([]);
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
        enabled: Boolean(raw.enabled),
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
    setOperatorName("");
    setPassword("");
    setSelectedPersonId(null);
    setPeople([]);
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
        "Nueva persona incompleta: nombre, ubicacion, roles y skills son obligatorios."
      );
      return;
    }
    if (!Number.isFinite(yearsExperience) || yearsExperience < 0 || yearsExperience > 80) {
      setErrorMessage("Anos de experiencia debe estar entre 0 y 80.");
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
      setNewPersonFullName("");
      setNewPersonTargetRolesInput("");
      setNewPersonLocation("");
      setNewPersonYearsExperienceInput("");
      setNewPersonSkillsInput("");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo crear la nueva persona";
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

  async function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPersonId || !chatInput.trim() || isSendingMessage) {
      return;
    }
    const messageToSend = chatInput.trim();
    setIsSendingMessage(true);
    setStreamingAssistantText("");
    setErrorMessage(null);
    let streamedAnyDelta = false;
    try {
      const updatedConversation = await sendMessageStream(
        selectedPersonId,
        messageToSend,
        (delta) => {
          streamedAnyDelta = true;
          setStreamingAssistantText((current) => `${current}${delta}`);
        }
      );
      setConversation(updatedConversation);
      setChatInput("");
      await refreshRequestTracesFor(
        selectedPersonId,
        traceDestinationFilter,
        traceOnlyActiveOpportunity,
        selectedOpportunityId,
        traceRunIdFilter
      );
    } catch (error) {
      if (!streamedAnyDelta) {
        try {
          const updatedConversation = await sendMessage(selectedPersonId, messageToSend);
          setConversation(updatedConversation);
          setChatInput("");
          await refreshRequestTracesFor(
            selectedPersonId,
            traceDestinationFilter,
            traceOnlyActiveOpportunity,
            selectedOpportunityId,
            traceRunIdFilter
          );
          setErrorMessage("Streaming no disponible. Se uso envio no-stream como fallback.");
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

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPersonId || !searchQuery.trim()) {
      return;
    }
    setIsSearching(true);
    setErrorMessage(null);
    try {
      const payload = await searchOpportunities(selectedPersonId, searchQuery.trim(), 6);
      setSearchResults(payload.items);
      setSearchWarnings(payload.warnings);
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
    if (!selectedPersonId || !manualUrl.trim() || isImportingUrl) {
      return;
    }
    setIsImportingUrl(true);
    setErrorMessage(null);
    try {
      const payload = await importOpportunityByUrl(selectedPersonId, {
        source_url: manualUrl.trim(),
        title: manualUrlTitle.trim(),
        company: manualUrlCompany.trim(),
        location: manualUrlLocation.trim(),
        raw_text: manualUrlRawText.trim()
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

  async function handleImportByText(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      !selectedPersonId ||
      !manualTextTitle.trim() ||
      !manualTextRawText.trim() ||
      isImportingText
    ) {
      return;
    }
    setIsImportingText(true);
    setErrorMessage(null);
    try {
      const item = await importOpportunityByText(selectedPersonId, {
        title: manualTextTitle.trim(),
        company: manualTextCompany.trim(),
        location: manualTextLocation.trim(),
        raw_text: manualTextRawText.trim()
      });
      const items = await listOpportunities(selectedPersonId);
      setSavedOpportunities(items);
      setSelectedOpportunityId(item.opportunity_id);
      setManualTextTitle("");
      setManualTextCompany("");
      setManualTextLocation("");
      setManualTextRawText("");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo importar por texto";
      setErrorMessage(message);
    } finally {
      setIsImportingText(false);
    }
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
          "Streaming de analyze no disponible. Se uso endpoint no-stream como fallback."
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
          "Streaming de analyze no disponible. Se uso endpoint no-stream como fallback."
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
    if (!targets.includes("guidance_text")) {
      setGuidanceText("");
    }
    if (!targets.includes("cover_letter") && !targets.includes("experience_summary")) {
      setArtifacts([]);
    }

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
          "Streaming de prepare no disponible. Se uso endpoint no-stream como fallback."
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
      setErrorMessage("Anos de experiencia debe estar entre 0 y 80.");
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

  function handleToggleCulturalField(fieldId: string, enabled: boolean) {
    setCulturePreferencesState((current) => ({
      ...current,
      [fieldId]: {
        ...(current[fieldId] ?? {
          enabled: false,
          selected_values: [],
          criticality: "normal"
        }),
        enabled
      }
    }));
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
          selected_values: selected
        }
      };
    });
  }

  function handleChangeCulturalCriticality(
    fieldId: string,
    criticality: CulturalFieldPreference["criticality"]
  ) {
    setCulturePreferencesState((current) => ({
      ...current,
      [fieldId]: {
        ...(current[fieldId] ?? {
          enabled: false,
          selected_values: [],
          criticality: "normal"
        }),
        criticality
      }
    }));
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
            Inicia sesion para seleccionar una persona consultada y abrir su
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
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">Tutor Workspace</p>
        <h1>Selecciona una persona consultada para abrir su contexto.</h1>
        <p className="lede">
          Operador autenticado: <strong>{operatorName}</strong>. Este flujo ya
          separa acceso del tutor y contexto de la persona consultada.
        </p>
      </section>

      <section className="panel">
        <header className="panelHeader">
          <div>
            <h2>Personas consultadas</h2>
            <p>Selecciona el perfil activo para continuar a chat y oportunidades.</p>
          </div>
          <button className="ghostButton" onClick={handleLogout} type="button">
            Cerrar sesion
          </button>
        </header>

        <div className="cards">
          {people.map((person) => (
            <article className="card" key={person.person_id}>
              <span className="cardTag">{person.person_id}</span>
              <h3>{person.full_name}</h3>
              <p>{person.target_roles.join(", ")}</p>
              <p className="metaText">
                {person.location} · {person.years_experience} anos
              </p>
              <div className="cardActions">
                <button
                  className={
                    person.person_id === selectedPersonId ? "activeButton" : ""
                  }
                  onClick={() => setSelectedPersonId(person.person_id)}
                  type="button"
                >
                  {person.person_id === selectedPersonId
                    ? "Contexto activo"
                    : "Abrir contexto"}
                </button>
              </div>
            </article>
          ))}
        </div>
        <h3 className="subheading">Agregar persona consultada</h3>
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
              Anos de experiencia
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
              {isCreatingPerson ? "Creando..." : "Crear persona"}
            </button>
          </div>
        </form>
      </section>

      <section className="panel selectedPanel">
        <header className="panelHeader">
          <div>
            <h2>Administracion de prompts (global V1)</h2>
            <p>
              Ajusta guardrails, identidad y task prompts de chat/analyze/prepare. Tambien
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

      <section className="panel selectedPanel">
        <h2>Contexto activo</h2>
        {selectedPerson ? (
          <div className="cvCard">
            <p className="lede">
              Perfil activo: <strong>{selectedPerson.full_name}</strong> (
              {selectedPerson.person_id}).
            </p>
            <p className="metaText">
              Skills base: {selectedPerson.skills.join(", ")}
            </p>
            <h3 className="subheading">Perfil base editable</h3>
            <article className="manualCard">
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
                  Anos de experiencia
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
                  disabled={isSavingProfile}
                  onClick={() => void handleSaveProfile()}
                  type="button"
                >
                  {isSavingProfile ? "Guardando perfil..." : "Guardar perfil"}
                </button>
              </div>
            </article>
            <h3 className="subheading">Preferencias culturales y condiciones de trabajo</h3>
            <div className="cultureGrid">
              {CULTURAL_FIELDS.map((field) => {
                const value = culturePreferencesState[field.id] ?? {
                  enabled: false,
                  selected_values: [],
                  criticality: "normal"
                };
                return (
                  <article className="manualCard" key={field.id}>
                    <label className="checkboxRow">
                      <input
                        checked={value.enabled}
                        disabled={isSavingCulturePreferences}
                        onChange={(event) =>
                          handleToggleCulturalField(field.id, event.target.checked)
                        }
                        type="checkbox"
                      />
                      <span>{field.label}</span>
                    </label>
                    {value.enabled ? (
                      <>
                        <div className="optionList">
                          {field.options.map((option) => (
                            <label className="checkboxRow" key={`${field.id}-${option.value}`}>
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
                        <label className="field">
                          Criticidad
                          <select
                            disabled={isSavingCulturePreferences}
                            onChange={(event) =>
                              handleChangeCulturalCriticality(
                                field.id,
                                event.target.value as CulturalFieldPreference["criticality"]
                              )
                            }
                            value={value.criticality}
                          >
                            {CRITICALITY_OPTIONS.map((option) => (
                              <option key={`${field.id}-${option.value}`} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        </label>
                      </>
                    ) : (
                      <p className="metaText">Factor no relevante para esta persona.</p>
                    )}
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
                disabled={isSavingCulturePreferences}
                onClick={() => void handleSaveCulturePreferences()}
                type="button"
              >
                {isSavingCulturePreferences
                  ? "Guardando preferencias..."
                  : "Guardar preferencias"}
              </button>
            </div>
          </div>
        ) : (
          <p className="metaText">
            No hay persona consultada seleccionada. Elige un perfil para
            continuar.
          </p>
        )}
      </section>
      <section className="panel selectedPanel">
        <h2>CV activo</h2>
        <form className="cvForm" onSubmit={handleUploadCv}>
          <input
            accept=".pdf,.txt,.md"
            disabled={!selectedPersonId || isUploadingCv}
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              setSelectedCvFile(file);
            }}
            type="file"
          />
          <button
            className="primaryButton"
            disabled={!selectedPersonId || !selectedCvFile || isUploadingCv}
            type="submit"
          >
            {isUploadingCv ? "Cargando..." : "Cargar CV"}
          </button>
        </form>
        {isLoadingCv ? (
          <p className="metaText">Consultando CV activo...</p>
        ) : activeCv ? (
          <div className="cvCard">
            <p className="metaText">
              Archivo: <strong>{activeCv.source_filename}</strong> · estado extraccion:{" "}
              {activeCv.extraction_status}
            </p>
            <p className="metaText">
              Indexacion vectorial: {activeCv.vector_index_status} · chunks:{" "}
              {activeCv.vector_chunks_indexed}
            </p>
            <p className="metaText">
              Longitud detectada: {activeCv.text_length} caracteres
              {activeCv.text_truncated ? " (truncado para V1)" : ""}
            </p>
            <article className="chatBubble chatBubbleAssistant">
              <p className="chatRole">Preview</p>
              <p className="chatContent">
                {activeCv.extracted_text_preview || "No se obtuvo texto util del archivo."}
              </p>
            </article>
          </div>
        ) : (
          <p className="metaText">
            No hay CV activo para esta persona. Puedes operar sin CV y cargarlo despues.
          </p>
        )}
      </section>
      <section className="panel selectedPanel">
        <h2>Conversacion</h2>
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
                <p className="chatRole">Asistente (stream)</p>
                <p className="chatContent">
                  {streamingAssistantText || "Procesando respuesta..."}
                </p>
              </article>
            ) : null}
          </div>
        )}
        <form className="chatForm" onSubmit={handleSendMessage}>
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
      </section>
      <section className="panel selectedPanel">
        <h2>Busqueda y oportunidades</h2>
        <form className="chatForm" onSubmit={handleSearch}>
          <input
            disabled={!selectedPersonId || isSearching}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Buscar vacantes para el perfil activo..."
            value={searchQuery}
          />
          <button
            className="primaryButton"
            disabled={!selectedPersonId || isSearching || !searchQuery.trim()}
            type="submit"
          >
            {isSearching ? "Buscando..." : "Buscar"}
          </button>
        </form>
        {searchWarnings.length > 0 ? (
          <p className="metaText">Avisos: {searchWarnings.join(" | ")}</p>
        ) : null}
        <h3 className="subheading">Carga manual de vacantes</h3>
        <div className="manualGrid">
          <form className="manualCard" onSubmit={handleImportByUrl}>
            <p className="chatRole">Desde URL</p>
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
              placeholder="Snapshot o resumen textual (opcional)"
              rows={3}
              value={manualUrlRawText}
            />
            <button
              className="primaryButton"
              disabled={!selectedPersonId || isImportingUrl || !manualUrl.trim()}
              type="submit"
            >
              {isImportingUrl ? "Importando..." : "Importar URL"}
            </button>
          </form>
          <form className="manualCard" onSubmit={handleImportByText}>
            <p className="chatRole">Desde texto</p>
            <input
              disabled={!selectedPersonId || isImportingText}
              onChange={(event) => setManualTextTitle(event.target.value)}
              placeholder="Titulo de la vacante"
              value={manualTextTitle}
            />
            <div className="manualRow">
              <input
                disabled={!selectedPersonId || isImportingText}
                onChange={(event) => setManualTextCompany(event.target.value)}
                placeholder="Empresa (opcional)"
                value={manualTextCompany}
              />
              <input
                disabled={!selectedPersonId || isImportingText}
                onChange={(event) => setManualTextLocation(event.target.value)}
                placeholder="Ubicacion (opcional)"
                value={manualTextLocation}
              />
            </div>
            <textarea
              disabled={!selectedPersonId || isImportingText}
              onChange={(event) => setManualTextRawText(event.target.value)}
              placeholder="Pega aqui el contenido de la vacante"
              rows={3}
              value={manualTextRawText}
            />
            <button
              className="primaryButton"
              disabled={
                !selectedPersonId ||
                isImportingText ||
                !manualTextTitle.trim() ||
                !manualTextRawText.trim()
              }
              type="submit"
            >
              {isImportingText ? "Importando..." : "Importar texto"}
            </button>
          </form>
        </div>
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
                <p className="metaText">
                  {result.company || "Empresa no identificada"}
                  {result.source_url ? ` · ${result.source_url}` : ""}
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
                    <p className="metaText">URL: {result.source_url || "No disponible"}</p>
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
        <h3 className="subheading">Oportunidades guardadas</h3>
        {isLoadingOpportunities ? (
          <p className="metaText">Cargando oportunidades...</p>
        ) : savedOpportunities.length === 0 ? (
          <p className="metaText">No hay oportunidades guardadas para este perfil.</p>
        ) : (
          <div className="chatList">
            {savedOpportunities.map((item) => (
              <article className="chatBubble chatBubbleUser" key={item.opportunity_id}>
                <p className="chatRole">{item.status}</p>
                <p className="chatContent">{item.title}</p>
                <p className="metaText">
                  {item.company || "Empresa no identificada"}
                  {item.source_url ? ` · ${item.source_url}` : ""}
                </p>
                <div className="cardActions">
                  <button
                    className={
                      selectedOpportunityId === item.opportunity_id ? "activeButton" : ""
                    }
                    onClick={() => setSelectedOpportunityId(item.opportunity_id)}
                    type="button"
                  >
                    {selectedOpportunityId === item.opportunity_id ? "Activa" : "Abrir"}
                  </button>
                  <button
                    disabled={isAnalyzingProfile}
                    onClick={() => void handleAnalyzeProfileMatch(item.opportunity_id)}
                    type="button"
                  >
                    {isAnalyzingProfile && selectedOpportunityId === item.opportunity_id
                      ? "Analizando perfil..."
                      : "Analyze perfil"}
                  </button>
                  <button
                    disabled={isAnalyzingCultural}
                    onClick={() => void handleAnalyzeCulturalFit(item.opportunity_id)}
                    type="button"
                  >
                    {isAnalyzingCultural && selectedOpportunityId === item.opportunity_id
                      ? "Analizando cultura..."
                      : "Analyze cultura"}
                  </button>
                  <button
                    disabled={isPreparing}
                    onClick={() => void handlePrepare(item.opportunity_id)}
                    type="button"
                  >
                    {isPreparing && selectedOpportunityId === item.opportunity_id
                      ? "Preparando..."
                      : "Prepare seleccionado"}
                  </button>
                  <button
                    disabled={isLoadingArtifacts}
                    onClick={() => void refreshArtifacts(item.opportunity_id)}
                    type="button"
                  >
                    {isLoadingArtifacts && selectedOpportunityId === item.opportunity_id
                      ? "Cargando..."
                      : "Artifacts"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
      <section className="panel selectedPanel">
        <h2>Analisis y artefactos</h2>
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
            <p className="metaText">Preparar materiales: selecciona lo que quieras generar.</p>
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
          <div className="chatList">
            {culturalSignals.map((signal) => (
              <article className="chatBubble chatBubbleAssistant" key={`${signal.source_url}|${signal.title}`}>
                <p className="chatRole">{signal.source_provider}</p>
                <p className="chatContent">{signal.title}</p>
                <p className="metaText">{signal.source_url}</p>
                <p className="metaText">{signal.snippet}</p>
              </article>
            ))}
          </div>
        ) : null}
        {semanticEvidence ? (
          <article className="chatBubble chatBubbleAssistant">
            <p className="chatRole">Evidencia semantica CV ({semanticEvidence.source})</p>
            <p className="metaText">top_k: {semanticEvidence.top_k}</p>
            <p className="metaText">{semanticEvidence.query}</p>
            {semanticEvidence.snippets.length > 0 ? (
              <div className="chatList">
                {semanticEvidence.snippets.map((snippet, index) => (
                  <article className="chatBubble chatBubbleUser" key={`cv-snippet-${index}`}>
                    <p className="chatRole">CV-{index + 1}</p>
                    <p className="chatContent">{snippet}</p>
                  </article>
                ))}
              </div>
            ) : (
              <p className="chatContent">No hay snippets disponibles para esta oportunidad.</p>
            )}
          </article>
        ) : null}
        {guidanceText ? (
          <article className="chatBubble chatBubbleAssistant">
            <p className="chatRole">Guidance</p>
            <p className="chatContent">{guidanceText}</p>
          </article>
        ) : null}
        {artifacts.length > 0 ? (
          <div className="chatList">
            {artifacts.map((artifact) => (
              <article className="chatBubble chatBubbleUser" key={artifact.artifact_id}>
                <p className="chatRole">{artifact.artifact_type}</p>
                <p className="chatContent">{artifact.content}</p>
              </article>
            ))}
          </div>
        ) : null}
        {selectedOpportunity ? (
          <article className="manualCard">
            <p className="chatRole">Historico IA (persistido)</p>
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
        ) : null}
      </section>
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
      </section>
      {errorMessage ? <p className="errorText">{errorMessage}</p> : null}
    </main>
  );
}
