"""Trilha de auditoria.

Fecha as lacunas apontadas no Diagnóstico:
- vínculo ao artefato: grava o SHA-256 do conteúdo (prova sem guardar o texto);
- versão da política aplicada;
- timestamps de abertura/fechamento para recalcular SLA;
- registro encadeado (cada linha carrega o hash da anterior) para evidenciar adulteração.
O texto integral nunca é gravado.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "runtime" / "audit_log.jsonl"


@dataclass
class AuditRecord:
    id_evento: str
    aberto_em: str
    id_usuario: str
    area: str
    cargo: str
    gestor: str
    ferramenta: str
    finalidade: str
    tipos_informacao: list[str]
    sensibilidade: str
    qtd_itens: int
    decisao: str
    aplicada: bool
    risco: str
    regra: str
    versao_politica: str
    confianca: str
    hash_conteudo: str
    tamanho_conteudo: int
    notificados: list[str]
    origem: str = "Gateway (automático)"
    fechado_em: str | None = None
    hash_anterior: str = ""
    hash_registro: str = ""


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _last_hash() -> str:
    if not LOG.exists():
        return "0" * 64
    last = ""
    with LOG.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last = line
    return json.loads(last)["hash_registro"] if last else "0" * 64


def record(ctx, insp, dec, text: str) -> AuditRecord:
    now = datetime.now().isoformat(timespec="seconds")
    rec = AuditRecord(
        id_evento=f"GW-{uuid.uuid4().hex[:8].upper()}",
        aberto_em=now,
        id_usuario=ctx.user_id, area=ctx.area, cargo=ctx.cargo, gestor=ctx.manager,
        ferramenta=ctx.tool, finalidade=ctx.purpose,
        tipos_informacao=[f.name for f in insp.findings],
        sensibilidade=insp.sensitivity or "Não identificada",
        qtd_itens=insp.volume_items,
        decisao=dec.action, aplicada=dec.enforced, risco=dec.risk, regra=dec.rule_id,
        versao_politica=dec.policy_version, confianca=insp.confidence,
        hash_conteudo=content_hash(text), tamanho_conteudo=len(text or ""),
        notificados=dec.notify,
        # decisões que não retêm conteúdo já nascem encerradas; as demais abrem caso
        fechado_em=None if dec.stops_content and dec.enforced else now,
    )
    LOG.parent.mkdir(exist_ok=True)
    rec.hash_anterior = _last_hash()
    body = json.dumps({k: v for k, v in asdict(rec).items() if k != "hash_registro"}, ensure_ascii=False, sort_keys=True)
    rec.hash_registro = hashlib.sha256(body.encode("utf-8")).hexdigest()
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
    return rec


def read_all() -> list[dict]:
    if not LOG.exists():
        return []
    with LOG.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def verify_chain() -> tuple[bool, int]:
    """Recalcula a cadeia de hashes. Retorna (íntegra?, nº de registros)."""
    prev = "0" * 64
    rows = read_all()
    for r in rows:
        if r["hash_anterior"] != prev:
            return False, len(rows)
        body = json.dumps({k: v for k, v in r.items() if k != "hash_registro"}, ensure_ascii=False, sort_keys=True)
        if hashlib.sha256(body.encode("utf-8")).hexdigest() != r["hash_registro"]:
            return False, len(rows)
        prev = r["hash_registro"]
    return True, len(rows)


def clear():
    if LOG.exists():
        LOG.unlink()
