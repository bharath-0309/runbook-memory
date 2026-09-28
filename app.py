from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import agent, memory, data

app = FastAPI(title="Runbook Memory")
app.mount("/static", StaticFiles(directory="static"), name="static")

class Triage(BaseModel):
    service: str; alert: str; deploy: str = ""; use_memory: bool = True
class Outcome(BaseModel):
    incident_id: str; service: str; alert: str; fix: str; outcome: str; root_cause: str = ""
class Reflect(BaseModel):
    service: str

@app.get("/")
def index(): return FileResponse("static/index.html")

@app.post("/api/seed")
def seed():
    for i in data.INCIDENTS:
        memory.retain(data.as_memory(i), context=f"{i['service']} incident history")
    return {"retained": len(data.INCIDENTS)}

@app.post("/api/triage")
def triage(b: Triage): return agent.triage(b.service, b.alert, b.deploy, b.use_memory)

@app.post("/api/outcome")
def outcome(b: Outcome):
    text = (f"Incident {b.incident_id} in {b.service}. Alert: {b.alert}. "
            f"Fix tried: {b.fix} -> {b.outcome.upper()}. Root cause: {b.root_cause or 'unknown'}.")
    memory.retain(text, context=f"{b.service} fix outcome")
    return {"retained": text}

@app.post("/api/reflect")
def reflect(b: Reflect):
    q = (f"For {b.service}: list recurring root causes, which fixes worked or failed and how often, "
         "and write a concise runbook (numbered steps, what NOT to try).")
    return {"runbook": memory.reflect(q)}
