type PersonCard = {
  id: string;
  name: string;
  focus: string;
};

const people: PersonCard[] = [
  { id: "p-001", name: "Camila Torres", focus: "Product Designer" },
  { id: "p-002", name: "Mateo Rojas", focus: "Data Analyst" }
];

export default function App() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">Tutor Workspace</p>
        <h1>Selecciona una persona consultada para abrir su contexto.</h1>
        <p className="lede">
          Este scaffold deja visible el primer flujo acordado: acceso del tutor,
          seleccion de perfil y entrada posterior a chat y oportunidades.
        </p>
      </section>

      <section className="panel">
        <header className="panelHeader">
          <div>
            <h2>Personas consultadas</h2>
            <p>Pool inicial de perfiles operados por el tutor.</p>
          </div>
          <button className="ghostButton" type="button">
            Crear perfil
          </button>
        </header>

        <div className="cards">
          {people.map((person) => (
            <article className="card" key={person.id}>
              <span className="cardTag">{person.id}</span>
              <h3>{person.name}</h3>
              <p>{person.focus}</p>
              <div className="cardActions">
                <button type="button">Abrir contexto</button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
