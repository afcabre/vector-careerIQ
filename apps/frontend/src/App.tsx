import { FormEvent, useEffect, useState } from "react";

import {
  ActiveCV,
  ApplicationArtifact,
  Conversation,
  CulturalFieldPreference,
  CulturalSignal,
  Opportunity,
  Person,
  SearchResult,
  SemanticEvidence,
  analyzeOpportunity,
  analyzeOpportunityStream,
  getConversation,
  getActiveCV,
  getSession,
  importOpportunityByText,
  importOpportunityByUrl,
  listOpportunityArtifacts,
  listOpportunities,
  listPersons,
  login,
  logout,
  prepareOpportunity,
  prepareOpportunityStream,
  saveOpportunityFromSearch,
  searchOpportunities,
  sendMessage,
  sendMessageStream,
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

export default function App() {
  const [view, setView] = useState<ViewState>("checking");
  const [username, setUsername] = useState("tutor");
  const [password, setPassword] = useState("");
  const [operatorName, setOperatorName] = useState("");
  const [people, setPeople] = useState<Person[]>([]);
  const [selectedPersonId, setSelectedPersonId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [isConversationLoading, setIsConversationLoading] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [streamingAssistantText, setStreamingAssistantText] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
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
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isPreparing, setIsPreparing] = useState(false);
  const [isLoadingArtifacts, setIsLoadingArtifacts] = useState(false);
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

  const selectedPerson =
    people.find((person) => person.person_id === selectedPersonId) ?? null;

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
    setConversation(null);
    setStreamingAssistantText("");
    setChatInput("");
    setAnalysisText("");
    setCulturalConfidence("");
    setCulturalWarnings([]);
    setCulturalSignals([]);
    setSemanticEvidence(null);
    setActiveCv(null);
    setSelectedCvFile(null);
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
    } catch (error) {
      if (!streamedAnyDelta) {
        try {
          const updatedConversation = await sendMessage(selectedPersonId, messageToSend);
          setConversation(updatedConversation);
          setChatInput("");
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

  async function handleAnalyze(opportunityId: string) {
    if (!selectedPersonId) {
      return;
    }
    const personId = selectedPersonId;
    setSelectedOpportunityId(opportunityId);
    setIsAnalyzing(true);
    setErrorMessage(null);
    setAnalysisText("");
    let streamedAnyDelta = false;
    try {
      const payload = await analyzeOpportunityStream(
        personId,
        opportunityId,
        (delta) => {
          streamedAnyDelta = true;
          setAnalysisText((current) => `${current}${delta}`);
        }
      );
      setAnalysisText(payload.analysis_text);
      setCulturalConfidence(payload.cultural_confidence);
      setCulturalWarnings(payload.cultural_warnings);
      setCulturalSignals(payload.cultural_signals);
      setSemanticEvidence(payload.semantic_evidence);
      const items = await listOpportunities(personId);
      setSavedOpportunities(items);
      setSelectedOpportunityId(opportunityId);
    } catch (error) {
      if (!streamedAnyDelta) {
        try {
          const payload = await analyzeOpportunity(personId, opportunityId);
          setAnalysisText(payload.analysis_text);
          setCulturalConfidence(payload.cultural_confidence);
          setCulturalWarnings(payload.cultural_warnings);
          setCulturalSignals(payload.cultural_signals);
          setSemanticEvidence(payload.semantic_evidence);
          const items = await listOpportunities(personId);
          setSavedOpportunities(items);
          setSelectedOpportunityId(opportunityId);
          setErrorMessage("Streaming no disponible. Se uso analyze no-stream como fallback.");
          return;
        } catch {
          // Keep original stream failure message below.
        }
      }
      const message =
        error instanceof Error ? error.message : "No se pudo analizar la oportunidad";
      setErrorMessage(message);
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function handlePrepare(opportunityId: string) {
    if (!selectedPersonId) {
      return;
    }
    const personId = selectedPersonId;
    setSelectedOpportunityId(opportunityId);
    setIsPreparing(true);
    setErrorMessage(null);
    setGuidanceText("");
    setArtifacts([]);
    const draftTimestamp = new Date().toISOString();
    let draftCover = "";
    let draftSummary = "";
    let streamedAnyDelta = false;

    const setDraftArtifacts = () => {
      const draftItems: ApplicationArtifact[] = [];
      if (draftCover) {
        draftItems.push({
          artifact_id: "stream-cover-letter",
          person_id: personId,
          opportunity_id: opportunityId,
          artifact_type: "cover_letter",
          content: draftCover,
          is_current: true,
          created_at: draftTimestamp,
          updated_at: draftTimestamp
        });
      }
      if (draftSummary) {
        draftItems.push({
          artifact_id: "stream-experience-summary",
          person_id: personId,
          opportunity_id: opportunityId,
          artifact_type: "experience_summary",
          content: draftSummary,
          is_current: true,
          created_at: draftTimestamp,
          updated_at: draftTimestamp
        });
      }
      setArtifacts(draftItems);
    };

    try {
      const payload = await prepareOpportunityStream(
        personId,
        opportunityId,
        (channel, delta) => {
          streamedAnyDelta = true;
          if (channel === "guidance_text") {
            setGuidanceText((current) => `${current}${delta}`);
            return;
          }
          if (channel === "cover_letter") {
            draftCover += delta;
          } else {
            draftSummary += delta;
          }
          setDraftArtifacts();
        }
      );
      setGuidanceText(payload.guidance_text);
      setArtifacts(payload.artifacts);
      setSemanticEvidence(payload.semantic_evidence);
      const items = await listOpportunities(personId);
      setSavedOpportunities(items);
      setSelectedOpportunityId(opportunityId);
    } catch (error) {
      if (!streamedAnyDelta) {
        try {
          const payload = await prepareOpportunity(personId, opportunityId);
          setGuidanceText(payload.guidance_text);
          setArtifacts(payload.artifacts);
          setSemanticEvidence(payload.semantic_evidence);
          const items = await listOpportunities(personId);
          setSavedOpportunities(items);
          setSelectedOpportunityId(opportunityId);
          setErrorMessage("Streaming no disponible. Se uso prepare no-stream como fallback.");
          return;
        } catch {
          // Keep original stream failure message below.
        }
      }
      const message =
        error instanceof Error ? error.message : "No se pudo preparar postulacion";
      setErrorMessage(message);
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
              <article className="chatBubble chatBubbleAssistant" key={result.search_result_id}>
                <p className="chatRole">{result.source_provider}</p>
                <p className="chatContent">{result.title}</p>
                <p className="metaText">
                  {result.company || "Empresa no identificada"}
                  {result.source_url ? ` · ${result.source_url}` : ""}
                </p>
                <p className="metaText">{result.snippet}</p>
                <div className="cardActions">
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
                    disabled={isAnalyzing}
                    onClick={() => void handleAnalyze(item.opportunity_id)}
                    type="button"
                  >
                    {isAnalyzing && selectedOpportunityId === item.opportunity_id
                      ? "Analizando..."
                      : "Analyze"}
                  </button>
                  <button
                    disabled={isPreparing}
                    onClick={() => void handlePrepare(item.opportunity_id)}
                    type="button"
                  >
                    {isPreparing && selectedOpportunityId === item.opportunity_id
                      ? "Preparando..."
                      : "Prepare"}
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
      </section>
      {errorMessage ? <p className="errorText">{errorMessage}</p> : null}
    </main>
  );
}
