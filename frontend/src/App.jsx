import { useEffect, useState } from "react";
import "./App.css";

const COLS = [
  ["todo", "К выполнению"],
  ["doing", "В работе"],
  ["done", "Готово"],
];

async function api(path, opts = {}) {
  const r = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!r.ok) throw new Error("Ошибка " + r.status);
  return r.status === 204 ? null : r.json();
}

function Card({ card, onSave, onDelete }) {
  const [edit, setEdit] = useState(false);
  const [title, setTitle] = useState(card.title);
  const [desc, setDesc] = useState(card.description);
  const idx = COLS.findIndex(([k]) => k === card.status);
  const move = (d) => onSave(card.id, { status: COLS[idx + d][0] });

  if (edit)
    return (
      <div className="card">
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
        <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={3} />
        <div className="actions">
          <button onClick={() => { onSave(card.id, { title, description: desc }); setEdit(false); }}>
            Сохранить
          </button>
          <button className="ghost" onClick={() => setEdit(false)}>Отмена</button>
        </div>
      </div>
    );

  return (
    <div className="card" draggable onDragStart={(e) => e.dataTransfer.setData("id", card.id)}>
      <h3>{card.title}</h3>
      {card.description && <p>{card.description}</p>}
      <div className="actions">
        <button className="ghost" disabled={idx === 0} onClick={() => move(-1)} aria-label="Влево">←</button>
        <button className="ghost" disabled={idx === 2} onClick={() => move(1)} aria-label="Вправо">→</button>
        <button className="ghost" onClick={() => setEdit(true)}>Изменить</button>
        <button className="ghost danger" onClick={() => onDelete(card.id)}>Удалить</button>
      </div>
    </div>
  );
}

export default function App() {
  const [cards, setCards] = useState([]);
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");

  const load = () => api("/cards").then(setCards).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const run = (p) => p.then(load).catch((e) => setError(e.message));
  const add = (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    run(api("/cards", { method: "POST", body: JSON.stringify({ title }) }));
    setTitle("");
  };
  const save = (id, patch) => run(api("/cards/" + id, { method: "PATCH", body: JSON.stringify(patch) }));
  const del = (id) => run(api("/cards/" + id, { method: "DELETE" }));

  return (
    <main>
      <header>
        <h1>Доска задач</h1>
        <form onSubmit={add}>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Новая задача" />
          <button>Добавить</button>
        </form>
        <a href="/dashboard">Мониторинг</a>
      </header>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="board">
        {COLS.map(([key, label]) => (
          <section
            key={key}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => save(Number(e.dataTransfer.getData("id")), { status: key })}
          >
            <h2>{label} <span>{cards.filter((c) => c.status === key).length}</span></h2>
            {cards.filter((c) => c.status === key).map((c) => (
              <Card key={c.id + c.title + c.description} card={c} onSave={save} onDelete={del} />
            ))}
          </section>
        ))}
      </div>
    </main>
  );
}
