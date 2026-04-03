import { FormEvent, useEffect, useState } from "react";

import {
  Conversation,
  Person,
  getConversation,
  getSession,
  listPersons,
  login,
  logout,
  sendMessage
} from "./api";

type ViewState = "checking" | "login" | "workspace";

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
      {errorMessage ? <p className="errorText">{errorMessage}</p> : null}
    </main>
  );
}
