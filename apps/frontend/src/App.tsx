import { FormEvent, useEffect, useState } from "react";

import {
  ActiveCV,
  ApplicationArtifact,
  Conversation,
  CulturalSignal,
  Opportunity,
  Person,
  SearchResult,
  SemanticEvidence,
  analyzeOpportunity,
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
  saveOpportunityFromSearch,
  searchOpportunities,
  sendMessage,
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
    setIsSendingMessage(true);
    setErrorMessage(null);
    try {
      const updatedConversation = await sendMessage(selectedPersonId, chatInput.trim());
      setConversation(updatedConversation);
      setChatInput("");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo enviar el mensaje";
      setErrorMessage(message);
    } finally {
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
    setIsAnalyzing(true);
    setErrorMessage(null);
    try {
      const payload = await analyzeOpportunity(selectedPersonId, opportunityId);
      setAnalysisText(payload.analysis_text);
      setCulturalConfidence(payload.cultural_confidence);
      setCulturalWarnings(payload.cultural_warnings);
      setCulturalSignals(payload.cultural_signals);
      setSemanticEvidence(payload.semantic_evidence);
      const items = await listOpportunities(selectedPersonId);
      setSavedOpportunities(items);
      setSelectedOpportunityId(opportunityId);
    } catch (error) {
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
    setIsPreparing(true);
    setErrorMessage(null);
    try {
      const payload = await prepareOpportunity(selectedPersonId, opportunityId);
      setGuidanceText(payload.guidance_text);
      setArtifacts(payload.artifacts);
      setSemanticEvidence(payload.semantic_evidence);
      const items = await listOpportunities(selectedPersonId);
      setSavedOpportunities(items);
      setSelectedOpportunityId(opportunityId);
    } catch (error) {
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
          <div>
            <p className="lede">
              Perfil activo: <strong>{selectedPerson.full_name}</strong> (
              {selectedPerson.person_id}).
            </p>
            <p className="metaText">
              Skills base: {selectedPerson.skills.join(", ")}
            </p>
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
            {(conversation?.messages ?? []).length === 0 ? (
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
                {semanticEvidence.snippets.slice(0, 6).map((snippet, index) => (
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
