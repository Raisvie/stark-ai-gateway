"""API REST do gateway — o ponto que uma extensão de navegador ou um proxy chamaria antes de
liberar o envio para a ferramenta de IA.

Rodar:  uvicorn api:app --reload --port 8000     (documentação em http://localhost:8000/docs)
"""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from backend import audit
from backend.detector import inspect, sanitize
from backend.education_agent import chat, explain
from backend.policy_engine import POLICY_VERSION, Context, decide

app = FastAPI(title="Stark AI Gateway", version=POLICY_VERSION,
              description="Inspeção e decisão antes do envio de conteúdo para ferramentas de IA. Dados fictícios.")


class InspectRequest(BaseModel):
    user_id: str = "USR-0003"
    area: str = "Financeiro"
    cargo: str = "FP&A"
    manager: str = "Gestor(a) de Financeiro"
    tool: str = "IA Pública A"
    purpose: str = "Analisar dados"
    items: int = Field(1, ge=1)
    content: str
    enforce: bool = True


class InspectResponse(BaseModel):
    event_id: str
    action: str
    allowed_to_send: bool
    content_to_send: str | None
    risk: str
    rule: str
    reason: str
    findings: list[str]
    notify: list[str]
    suggested_tool: str | None
    policy_version: str
    content_sha256: str
    agent_headline: str
    agent_message: str
    agent_steps: list[str]


@app.post("/v1/inspect", response_model=InspectResponse)
def inspect_and_decide(req: InspectRequest) -> InspectResponse:
    ctx = Context(req.user_id, req.area, req.cargo, req.tool, req.purpose, req.manager)
    insp = inspect(req.content, declared_items=req.items)
    dec = decide(ctx, insp, enforce=req.enforce)
    rec = audit.record(ctx, insp, dec, req.content)
    guide = explain(ctx, insp, dec, req.content)
    blocked = dec.stops_content and dec.enforced
    to_send = None if blocked else (sanitize(req.content) if dec.action == "MASK" else req.content)
    return InspectResponse(
        event_id=rec.id_evento, action=dec.action, allowed_to_send=not blocked, content_to_send=to_send,
        risk=dec.risk, rule=dec.rule_id, reason=dec.reason, findings=[f.name for f in insp.findings],
        notify=dec.notify, suggested_tool=dec.suggested_tool, policy_version=dec.policy_version,
        content_sha256=rec.hash_conteudo, agent_headline=guide.headline, agent_message=guide.message,
        agent_steps=guide.next_steps,
    )


class ChatRequest(BaseModel):
    area: str = "Financeiro"
    cargo: str = ""
    message: str
    history: list[dict] = []


@app.post("/v1/agent/chat")
def agent_chat(req: ChatRequest) -> dict:
    turn = chat(req.message, Context(area=req.area, cargo=req.cargo), req.history)
    return {"reply": turn.reply, "sanitized_message": turn.sanitized, "used_llm": turn.used_llm}


@app.get("/v1/audit/verify")
def audit_verify() -> dict:
    ok, n = audit.verify_chain()
    return {"intact": ok, "records": n}
