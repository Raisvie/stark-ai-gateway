"""Gera apresentacao/stark-ai-gateway.html a partir do backend (mesmos números e decisões do app).

Rodar a partir da raiz do projeto:  python apresentacao/build.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import analytics  # noqa: E402
from backend.data_loader import load_base  # noqa: E402
from backend.detector import inspect, sanitize  # noqa: E402
from backend.education_agent import PLAYBOOKS, explain  # noqa: E402
from backend.policy_engine import Context, decide, resend_safely  # noqa: E402
from backend.validation import ADVERSARIAL, base_cases, run_suite  # noqa: E402
from ui.avatar import avatar_svg  # noqa: E402

HERE = Path(__file__).resolve().parent

LABEL = {
    "BLOCK": ("Bloqueado antes do envio", "crit"),
    "MASK": ("Liberado sem dados pessoais", "mask"),
    "APPROVAL": ("Aguardando o OK do gestor", "warn"),
    "REVIEW": ("Retido para análise", "warn"),
    "ALLOW_REGISTER": ("Liberado e registrado", "ok"),
    "ALLOW": ("Liberado", "ok"),
}

FOLHA = ("Analise a folha de pagamento de setembro e aponte desvios: Ana Souza, salário R$ 9.200, "
         "CPF 529.982.247-25; Bruno Lima, salário R$ 12.400.")
SCENARIOS = [
    ("Pessoas", "Analista de remuneração", "IA Pública A", "Analisar dados", 1, FOLHA,
     "Folha de pagamento numa IA pública"),
    ("Pessoas", "Analista de remuneração", "IA Pública A", "Analisar dados", 1, FOLHA,
     "A mesma tarefa, pelo caminho seguro"),
    ("Financeiro", "Controller", "IA Pública B", "Apoiar decisão", 1,
     "Resultado financeiro ainda não divulgado: receita de R$ 248 milhões e margem de 31%. Monte um resumo para a diretoria.",
     "Resultado antes da divulgação"),
    ("Comercial", "Gerente comercial", "Assistente Corporativo A", "Revisar texto", 10,
     "Lote com 10 arquivos de propostas comerciais confidenciais para revisão em massa.",
     "Dez propostas de uma vez"),
    ("Atendimento", "Analista de atendimento", "Copiloto de Produtividade", "Responder cliente", 1,
     "Responda ao cliente João Pereira (joao.p@email.com, (11) 98765-4321) pedindo desculpas pelo atraso no PIX de ontem.",
     "Resposta a um cliente"),
    ("Operações", "Analista de operações", "Copiloto de Produtividade", "Resumir documento", 1,
     "Resuma a ata de reunião interna sobre o novo fluxo de conciliação: decisões, pendências e responsáveis.",
     "Ata de reunião"),
    ("Operações", "Analista de operações", "Ferramenta desconhecida", "Classificar conteúdo", 1,
     "Classifique estes chamados internos por prioridade.",
     "Ferramenta fora do catálogo"),
]


def plain(md: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def scenario_data() -> list[dict]:
    out = []
    for i, (area, cargo, tool, purpose, qty, text, title) in enumerate(SCENARIOS):
        ctx = Context("USR-DEMO", area, cargo, tool, purpose, f"Gestor(a) de {area}")
        insp = inspect(text, qty)
        if i == 1:  # reenvio pela alternativa segura do cenário anterior
            ctx = resend_safely(ctx, insp)
            text = sanitize(text)
            insp = inspect(text, qty)
        dec = decide(ctx, insp)
        g = explain(ctx, insp, dec, text)
        label, tone = LABEL[dec.action]
        if dec.action == "BLOCK":
            sent = "Nada. O envio foi interrompido antes de chegar à ferramenta."
        elif dec.action in ("APPROVAL", "REVIEW"):
            sent = "Nada por enquanto. O pedido fica guardado até a decisão."
        elif dec.action == "MASK":
            sent = sanitize(text)
        else:
            sent = text
        out.append({
            "title": title, "area": area, "cargo": cargo, "tool": ctx.tool, "purpose": ctx.purpose, "qty": qty, "text": text,
            "label": label, "tone": tone, "found": sorted({f.name for f in insp.findings}),
            "sent": sent, "mood": g.mood, "headline": g.headline, "message": plain(g.message),
            "steps": [plain(s) for s in g.next_steps],
            "notify": [n.replace(" (orientação imediata do agente)", "") for n in dec.notify],
        })
    return out


def numbers() -> dict:
    b = load_base()
    k = analytics.kpis(b)
    rs = analytics.replay_summary(analytics.replay(b))
    mc = analytics.monthly_critical(b)
    cat = b.alertas["Informação"].map(dict(zip(b.tipos["Tipo de informação"], b.tipos["Categoria"])))
    groups = {
        "Dados financeiros e resultados": {"Cliente/Financeiro", "Estratégica/Financeira"},
        "Senhas e chaves de sistemas": {"Credencial"},
        "Dados pessoais de clientes e colaboradores": {"Dados pessoais"},
        "Estratégia e propostas comerciais": {"Estratégica", "Comercial"},
        "Contratos e pareceres": {"Cliente/Jurídico", "Jurídico"},
        "Código e arquitetura": {"Propriedade intelectual"},
    }
    leak = [{"label": g, "n": int(cat.isin(s).sum())} for g, s in groups.items()]
    suites = run_suite(base_cases()) + run_suite(ADVERSARIAL)
    month_names = {"06": "Jun", "07": "Jul", "08": "Ago", "09": "Set*"}
    return {
        "eventos": k["eventos"], "alertas": k["alertas"], "pendentes": k["pendentes"], "criticos": k["criticos"],
        "usuarios": k["usuarios"], "areas": k["areas"],
        "bloq": rs["criticos_bloqueados"], "crit": rs["criticos"], "altos_ret": rs["altos_retidos"], "altos": rs["altos"],
        "livres": rs["liberados_sem_atrito"], "total": rs["total"],
        "testes_ok": sum(r.status == "Correto" for r in suites), "testes": len(suites),
        "exposicoes": sum(r.status == "EXPOSIÇÃO" for r in suites),
        "leak": leak,
        "monthly": [{"m": month_names[m[-2:]], "v": round(float(v), 4)} for m, v in zip(mc["Mês"], mc["% crítico"])],
    }


def areas() -> dict:
    return {a: [{"tarefa": u.tarefa, "ferramenta": u.ferramenta, "prompt": u.prompt, "nunca": u.nunca, "ganho": u.ganho}
                for u in ucs] for a, ucs in PLAYBOOKS.items()}


def main():
    data = {"n": numbers(), "scenarios": scenario_data(), "areas": areas(),
            "avatars": {m: avatar_svg(m, 88) for m in ("ola", "alerta", "atencao", "mascara", "aprovado", "pensando")}}
    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    out = HERE / "stark-ai-gateway.html"
    out.write_text(html, encoding="utf-8")
    print("gerado:", out, f"({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()
