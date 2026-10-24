import os
import time
from datetime import datetime, timedelta
from typing import Literal, Optional

import psutil
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

# ---------- БД ----------
url = os.getenv("DATABASE_URL", "sqlite:///./kanban.db")
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg2://", 1)
elif url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(
    url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(String(1000), default="")
    status = Column(String(10), default="todo")


class Visit(Base):
    __tablename__ = "visits"
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, default=datetime.utcnow, index=True)


Base.metadata.create_all(engine)

# ---------- Метрики ----------
STARTED = time.time()
VISITS = Counter("app_visits_total", "Посещения страниц приложения")
CPU = Gauge("app_cpu_percent", "Загрузка CPU, %")
MEM_USED = Gauge("app_memory_used_bytes", "Память: используется")
MEM_TOTAL = Gauge("app_memory_total_bytes", "Память: всего")
DISK_USED = Gauge("app_disk_used_bytes", "Диск: используется")
DISK_TOTAL = Gauge("app_disk_total_bytes", "Диск: всего")


def system_info() -> dict:
    mem, disk = psutil.virtual_memory(), psutil.disk_usage("/")
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "mem_used": mem.used, "mem_total": mem.total,
        "disk_used": disk.used, "disk_total": disk.total,
        "uptime_sec": int(time.time() - STARTED),
    }


# ---------- Приложение ----------
app = FastAPI(title="Kanban")
Status = Literal["todo", "doing", "done"]


class CardIn(BaseModel):
    title: str
    description: str = ""
    status: Status = "todo"


class CardPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[Status] = None


def dump(c: Card) -> dict:
    return {"id": c.id, "title": c.title, "description": c.description, "status": c.status}


@app.middleware("http")
async def count_visits(request: Request, call_next):
    response = await call_next(request)
    # считаем только открытие страниц, а не /health, /metrics и /api
    if request.method == "GET" and request.url.path in ("/", "/dashboard"):
        VISITS.inc()
        with Session() as s:
            s.add(Visit())
            s.commit()
    return response


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "error", "db": "down"}, status_code=503)
    return {"status": "ok", "db": "ok", "uptime_sec": int(time.time() - STARTED)}


@app.get("/metrics")
def metrics():
    i = system_info()
    CPU.set(i["cpu_percent"])
    MEM_USED.set(i["mem_used"])
    MEM_TOTAL.set(i["mem_total"])
    DISK_USED.set(i["disk_used"])
    DISK_TOTAL.set(i["disk_total"])
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/cards")
def list_cards():
    with Session() as s:
        return [dump(c) for c in s.query(Card).order_by(Card.id)]


@app.post("/api/cards", status_code=201)
def create_card(data: CardIn):
    if not data.title.strip():
        raise HTTPException(422, "Название не может быть пустым")
    with Session() as s:
        c = Card(**data.model_dump())
        s.add(c)
        s.commit()
        s.refresh(c)
        return dump(c)


@app.patch("/api/cards/{card_id}")
def update_card(card_id: int, data: CardPatch):
    with Session() as s:
        c = s.get(Card, card_id)
        if not c:
            raise HTTPException(404, "Карточка не найдена")
        for k, v in data.model_dump(exclude_unset=True).items():
            if v is not None:
                setattr(c, k, v)
        s.commit()
        s.refresh(c)
        return dump(c)


@app.delete("/api/cards/{card_id}", status_code=204)
def delete_card(card_id: int):
    with Session() as s:
        c = s.get(Card, card_id)
        if not c:
            raise HTTPException(404, "Карточка не найдена")
        s.delete(c)
        s.commit()


@app.get("/api/system")
def api_system():
    return system_info()


@app.get("/api/stats/hourly")
def hourly():
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(hours=23)
    buckets = {(start + timedelta(hours=i)).strftime("%Y-%m-%d %H:00"): 0 for i in range(24)}
    with Session() as s:
        for (ts,) in s.query(Visit.ts).filter(Visit.ts >= start):
            key = ts.strftime("%Y-%m-%d %H:00")
            if key in buckets:
                buckets[key] += 1
    return [{"hour": k, "visits": v} for k, v in buckets.items()]


DASHBOARD = """<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Мониторинг Kanban</title>
<style>
body{font:16px system-ui;margin:2rem auto;max-width:760px;padding:0 1rem;color:#1d2433}
.row{display:grid;grid-template-columns:140px 1fr 190px;gap:.75rem;align-items:center;margin:.5rem 0}
.bar{background:#e3e8f0;height:14px;border-radius:7px;overflow:hidden}.bar i{display:block;height:100%;background:#0f766e}
.ok{color:#0f766e}.bad{color:#b91c1c}.bars{display:flex;align-items:flex-end;gap:3px;height:120px}
.bars b{flex:1;background:#0f766e;min-height:2px}
</style>
<h1>Мониторинг</h1>
<p>Health: <b id="h">…</b> · Аптайм: <span id="u"></span></p>
<div id="res"></div>
<h2>Посещения по часам (24 ч, UTC)</h2><div class="bars" id="v"></div>
<p><a href="/metrics">/metrics</a> · <a href="/health">/health</a> · <a href="/">Доска</a></p>
<script>
const mb=x=>(x/1048576).toFixed(0)+" МБ", gb=x=>(x/1073741824).toFixed(1)+" ГБ";
function row(n,used,total,f){const p=Math.round(used/total*100);
 return `<div class="row"><span>${n}</span><div class="bar"><i style="width:${p}%"></i></div><span>${f(used)} из ${f(total)} (${p}%)</span></div>`}
async function load(){
 const h=await fetch("/health");const hj=await h.json();
 document.getElementById("h").textContent=hj.status;document.getElementById("h").className=h.ok?"ok":"bad";
 const s=await (await fetch("/api/system")).json();
 document.getElementById("u").textContent=Math.floor(s.uptime_sec/60)+" мин";
 document.getElementById("res").innerHTML=
  `<div class="row"><span>CPU</span><div class="bar"><i style="width:${s.cpu_percent}%"></i></div><span>${s.cpu_percent}%</span></div>`+
  row("Память",s.mem_used,s.mem_total,mb)+row("Диск",s.disk_used,s.disk_total,gb);
 const v=await (await fetch("/api/stats/hourly")).json();const m=Math.max(1,...v.map(x=>x.visits));
 document.getElementById("v").innerHTML=v.map(x=>`<b title="${x.hour}: ${x.visits}" style="height:${x.visits/m*100}%"></b>`).join("");
}
load();setInterval(load,10000);
</script></html>"""


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD


STATIC_DIR = os.getenv("STATIC_DIR", "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
