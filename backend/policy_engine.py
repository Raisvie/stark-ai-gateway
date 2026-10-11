"""Motor de política determinístico.

A IA (detector) produz sinais; a decisão é tomada aqui, por regras fixas, reproduzíveis e
auditáveis — avaliadas sempre na mesma ordem. Cada decisão cita a regra da aba Regras_Risco.

Ordem (primeira que casar vence):
  1. R03  Segredo/credencial em qualquer ferramenta ............ BLOQUEAR
  2. R01/R02/R04/R05/R06  Restrito em IA pública/não aprovada ... BLOQUEAR
  3. R13/R14  Ferramenta desconhecida ou sem classificação ...... REVISÃO HUMANA
  4. R11  Volume elevado de conteúdo restrito .................. PEDIR APROVAÇÃO
  5. R07 + LGPD  Dado pessoal em ferramenta aprovada ............ MASCARAR
  6. R10  Crítico em ambiente aprovado / finalidade incompatível  PEDIR APROVAÇÃO / REVISÃO
  7. R07  Confidencial em ferramenta aprovada .................. PERMITIR COM REGISTRO
  8. R08/R09  Público, interno ou anonimizado .................. PERMITIR
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .detector import Inspection, LEVEL

POLICY_VERSION = "POL-2026.10-v3"

# --- catálogo (espelha a aba Ferramentas_IA) ---
TOOLS = {
    "Assistente Corporativo A": {"id": "IA-01", "classe": "aprovada", "status": "Aprovada"},
    "Copiloto de Produtividade": {"id": "IA-02", "classe": "aprovada", "status": "Aprovada"},
    "Assistente de Código": {"id": "IA-03", "classe": "aprovada", "status": "Aprovada condicional"},
    "IA Pública A": {"id": "IA-04", "classe": "publica", "status": "Não aprovada"},
    "IA Pública B": {"id": "IA-05", "classe": "publica", "status": "Não aprovada"},
    "Assistente Jurídico": {"id": "IA-06", "classe": "aprovada", "status": "Aprovada"},
    "Plataforma de Dados IA": {"id": "IA-07", "classe": "aprovada", "status": "Aprovada condicional"},
    "Gerador de Imagens": {"id": "IA-08", "classe": "publica_restrita", "status": "Aprovada apenas para conteúdo público"},
    "Ferramenta desconhecida": {"id": "—", "classe": "desconhecida", "status": "Não catalogada (shadow AI)"},
}

PURPOSES = [
    "Criar rascunho", "Revisar texto", "Resumir documento", "Criar apresentação", "Responder cliente",
    "Analisar dados", "Apoiar decisão", "Pesquisar hipóteses", "Classificar conteúdo",
    "Criar conteúdo de campanha", "Gerar código", "Explicar código",
]

# finalidades aprovadas por ferramenta (Hipótese V10: política por finalidade)
TOOL_PURPOSES = {
    "Assistente Corporativo A": set(PURPOSES) - {"Gerar código", "Explicar código", "Criar conteúdo de campanha"},
    "Copiloto de Produtividade": {"Criar rascunho", "Revisar texto", "Resumir documento", "Criar apresentação",
                                  "Responder cliente", "Classificar conteúdo"},
    "Assistente de Código": {"Gerar código", "Explicar código"},
    "Assistente Jurídico": {"Criar rascunho", "Revisar texto", "Resumir documento", "Pesquisar hipóteses",
                            "Apoiar decisão", "Classificar conteúdo"},
    "Plataforma de Dados IA": {"Analisar dados", "Apoiar decisão", "Pesquisar hipóteses", "Classificar conteúdo"},
    "Gerador de Imagens": {"Criar conteúdo de campanha", "Criar apresentação"},
}

# ferramenta indicada por finalidade — usada no "reenviar pelo canal seguro" e pelo agente
BEST_TOOL = {
    "Gerar código": "Assistente de Código", "Explicar código": "Assistente de Código",
    "Analisar dados": "Plataforma de Dados IA", "Criar conteúdo de campanha": "Gerador de Imagens",
    "Criar apresentação": "Copiloto de Produtividade", "Responder cliente": "Copiloto de Produtividade",
    "Criar rascunho": "Copiloto de Produtividade", "Revisar texto": "Copiloto de Produtividade",
}

ACTIONS = {
    "BLOCK": {"titulo": "ENVIO BLOQUEADO", "sub": "A exposição foi evitada antes de chegar à ferramenta.", "tom": "crit", "icone": "✕"},
    "REVIEW": {"titulo": "REVISÃO HUMANA", "sub": "O conteúdo fica retido até a governança classificar.", "tom": "warn", "icone": "?"},
    "APPROVAL": {"titulo": "APROVAÇÃO NECESSÁRIA", "sub": "O gestor precisa autorizar antes do envio.", "tom": "warn", "icone": "!"},
    "MASK": {"titulo": "CONTEÚDO MASCARADO", "sub": "Só a versão sem identificadores segue para a IA.", "tom": "mask", "icone": "◐"},
    "ALLOW_REGISTER": {"titulo": "PERMITIDO COM REGISTRO", "sub": "Uso aprovado e rastreável.", "tom": "ok", "icone": "✓"},
    "ALLOW": {"titulo": "ENVIO PERMITIDO", "sub": "Uso compatível com a política.", "tom": "ok", "icone": "✓"},
}
RANK = {"ALLOW": 0, "ALLOW_REGISTER": 1, "MASK": 2, "APPROVAL": 3, "REVIEW": 4, "BLOCK": 5}
EXPECTED_TO_ACTION = {"CRÍTICO": "BLOCK", "ALTO": "APPROVAL", "MÉDIO": "ALLOW_REGISTER", "BAIXO": "ALLOW", "REVISAR": "REVIEW"}


@dataclass
class Context:
    user_id: str = "USR-0000"
    area: str = "Qualquer"
    cargo: str = ""
    tool: str = "Assistente Corporativo A"
    purpose: str = "Criar rascunho"
    manager: str = "Gestor da área"


@dataclass
class Decision:
    action: str
    risk: str               # Baixo | Médio | Alto | Crítico | Revisar
    rule_id: str
    rule_text: str
    reason: str
    tool_class: str
    purpose_ok: bool
    suggested_tool: str | None
    notify: list[str] = field(default_factory=list)
    enforced: bool = True
    policy_version: str = POLICY_VERSION

    @property
    def meta(self) -> dict:
        return ACTIONS[self.action]

    @property
    def stops_content(self) -> bool:
        return self.action in ("BLOCK", "REVIEW", "APPROVAL")


def tool_class(tool: str) -> str:
    return TOOLS.get(tool, TOOLS["Ferramenta desconhecida"])["classe"]


def suggest_tool(purpose: str, inspection: Inspection) -> str:
    ids = inspection.ids
    if ids & {"INF-04", "INF-14"}:
        return "Assistente Jurídico"
    if ids & {"INF-01", "INF-03"}:
        return "Assistente de Código"
    if ids & {"INF-08", "INF-18"}:
        return "Plataforma de Dados IA"
    return BEST_TOOL.get(purpose, "Assistente Corporativo A")


def decide(ctx: Context, insp: Inspection, enforce: bool = True) -> Decision:
    cls = tool_class(ctx.tool)
    sens = insp.sensitivity
    restricted = insp.restricted
    purpose_ok = ctx.purpose in TOOL_PURPOSES.get(ctx.tool, set()) if cls != "publica" else True
    suggestion = suggest_tool(ctx.purpose, insp)
    public_like = cls in ("publica", "publica_restrita")

    def d(action, risk, rule, text, reason):
        return Decision(action, risk, rule, text, reason, cls, purpose_ok,
                        suggestion if suggestion != ctx.tool else None)

    # 1 — segredo bloqueia sempre
    if insp.has_secret:
        dec = d("BLOCK", "Crítico", "R03", "Secrets, tokens ou chaves em qualquer prompt/arquivo",
                "Credenciais nunca podem ser enviadas a uma IA — nem às aprovadas.")
    # 2 — conteúdo restrito fora do ambiente controlado
    elif public_like and restricted:
        ids = insp.ids
        if ids & {"INF-07", "INF-11", "INF-12", "INF-13"}:
            rule, text = "R04", "Dados pessoais identificáveis em IA pública"
        elif "INF-09" in ids:
            rule, text = "R05", "Resultado financeiro não divulgado em ferramenta pública"
        elif sens == "Crítica":
            rule, text = "R02", "Qualquer informação Crítica em IA não aprovada"
        elif "INF-01" in ids:
            rule, text = "R06", "Código confidencial em ferramenta pública"
        else:
            rule, text = "R01", "Qualquer informação Confidencial em IA não aprovada"
        dec = d("BLOCK", "Crítico", rule, text,
                f"'{ctx.tool}' não tem contrato corporativo nem logs: conteúdo {sens.lower()} não pode sair do ambiente controlado.")
    # 3 — sem base para decidir: falha segura
    elif cls == "desconhecida":
        dec = d("REVIEW", "Revisar", "R14", "Evento sem usuário/ferramenta/data confiável",
                "Ferramenta fora do catálogo: sem logs nem contrato, a decisão fica com a governança.")
    elif insp.unclassified_marker or (not insp.findings and insp.volume_items > 1):
        dec = d("REVIEW", "Revisar", "R13", "Conteúdo sem classificação suficiente",
                "O sistema não inventa classificação quando a confiança é baixa.")
    # 4 — volume
    elif restricted and insp.volume_items >= 10:
        dec = d("APPROVAL", "Alto", "R11", "Upload massivo de arquivos confidenciais em curto período",
                f"{insp.volume_items} itens {sens.lower()}s de uma vez exigem autorização de {ctx.manager}.")
    # 5 — dado pessoal em ambiente aprovado
    elif insp.has_personal:
        dec = d("MASK", "Médio", "R07", "Confidencial em ferramenta corporativa aprovada (+ LGPD: minimização)",
                "Ferramenta aprovada, mas identificadores pessoais não são necessários para a tarefa.")
    # 6 — crítico ou finalidade incompatível em ambiente aprovado
    elif sens == "Crítica":
        dec = d("APPROVAL", "Alto", "R10", "Uso incompatível com finalidade aprovada da ferramenta",
                "Informação crítica em ambiente controlado: a finalidade precisa ser validada pelo gestor.")
    elif restricted and not purpose_ok:
        dec = d("REVIEW", "Alto", "R10", "Uso incompatível com finalidade aprovada da ferramenta",
                f"'{ctx.purpose}' não é finalidade aprovada de '{ctx.tool}'. Use {suggestion}.")
    # 7 — confidencial em aprovada
    elif restricted:
        dec = d("ALLOW_REGISTER", "Médio", "R07", "Confidencial em ferramenta corporativa aprovada",
                "Ferramenta aprovada e finalidade compatível: segue com rastreabilidade.")
    # 8 — público / interno / anonimizado
    else:
        rule = "R08" if sens == "Pública" else "R09"
        text = ("Informação pública em ferramenta aprovada" if rule == "R08"
                else "Dados agregados/anonimizados em ferramenta aprovada")
        reason = "Sem dado restrito identificado."
        if cls == "publica":
            reason += " Mesmo assim, prefira a ferramenta corporativa: ela guarda histórico e não treina com seus dados."
        elif not purpose_ok:
            reason += f" Dica: para '{ctx.purpose}', {suggestion} entrega melhor resultado."
        dec = d("ALLOW", "Baixo", rule, text, reason)

    dec.enforced = enforce
    dec.notify = notify_list(dec, insp, ctx)
    return dec


def notify_list(dec: Decision, insp: Inspection, ctx: Context) -> list[str]:
    who = ["Colaborador (orientação imediata do agente)"]
    if dec.risk in ("Crítico", "Alto"):
        who.append(f"Gestor: {ctx.manager}")
    if insp.has_secret:
        who.append("Segurança da Informação (rotacionar credencial)")
    if insp.has_personal and dec.action == "BLOCK":
        who.append("DPO / Privacidade (LGPD)")
    if dec.rule_id in ("R05", "R02") and "INF-09" in insp.ids:
        who.append("Compliance / RI")
    return who


def resend_safely(ctx: Context, insp: Inspection) -> Context:
    """Contexto para reenviar pelo canal corporativo indicado (botão 'usar a alternativa segura')."""
    target = suggest_tool(ctx.purpose, insp)
    purpose = ctx.purpose if ctx.purpose in TOOL_PURPOSES.get(target, set()) else sorted(TOOL_PURPOSES[target])[0]
    return Context(ctx.user_id, ctx.area, ctx.cargo, target, purpose, ctx.manager)


def is_worse_or_equal(obtained: str, expected: str) -> bool:
    return RANK[obtained] >= RANK[expected]


__all__ = ["Context", "Decision", "decide", "TOOLS", "PURPOSES", "TOOL_PURPOSES", "ACTIONS", "RANK",
           "EXPECTED_TO_ACTION", "POLICY_VERSION", "resend_safely", "tool_class", "LEVEL"]
