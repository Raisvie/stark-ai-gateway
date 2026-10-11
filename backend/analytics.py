"""Indicadores calculados a partir da base real do desafio (sem dados aleatórios)."""
from __future__ import annotations

import pandas as pd

from .data_loader import StarkBase, load_base
from .detector import inspect_declared
from .policy_engine import Context, decide

RULE_CAUSE = {
    "R10": "Finalidade incompatível", "R11": "Volume elevado", "R03": "Credenciais e secrets",
    "R01": "IA não aprovada", "R02": "IA não aprovada",
}
RISK_ORDER = ["Baixo", "Médio", "Alto", "Crítico"]
ADMIN_AREAS = ["Financeiro", "Pessoas", "Jurídico", "Comercial", "Atendimento", "Operações", "Risco & Compliance", "Marketing"]


def kpis(base: StarkBase | None = None) -> dict:
    b = base or load_base()
    ev, al = b.eventos, b.alertas
    n = len(ev)
    crit = int((ev["Risco"] == "Crítico").sum())
    pend = int(al["Status"].isin(["Aberto", "Em análise"]).sum())
    manual = int((ev["Origem do registro"] == "Registro manual").sum())
    public = int(ev["Ferramenta"].isin(["IA Pública A", "IA Pública B"]).sum())
    return {
        "eventos": n, "usuarios": ev["ID Usuário"].nunique(), "areas": ev["Área"].nunique(),
        "ferramentas": ev["Ferramenta"].nunique(),
        "alertas": len(al), "alertas_pct": len(al) / n,
        "criticos": crit, "criticos_pct": crit / n,
        "pendentes": pend, "pendentes_pct": pend / len(al),
        "tratados": int((al["Status"] == "Tratado").sum()),
        "manuais": manual, "manuais_pct": manual / n,
        "ia_publica": public, "ia_publica_pct": public / n,
        "periodo": (ev["Data/hora"].min(), ev["Data/hora"].max()),
    }


def pareto(base: StarkBase | None = None) -> pd.DataFrame:
    al = (base or load_base()).alertas
    s = al["Regra"].map(RULE_CAUSE).value_counts()
    df = s.rename_axis("Causa").reset_index(name="Alertas")
    df["%"] = df["Alertas"] / df["Alertas"].sum()
    df["% acumulado"] = df["%"].cumsum()
    return df


def risk_by_area(base: StarkBase | None = None) -> pd.DataFrame:
    ev = (base or load_base()).eventos
    t = pd.crosstab(ev["Área"], ev["Risco"]).reindex(columns=RISK_ORDER, fill_value=0)
    t["Total"] = t.sum(axis=1)
    t["% alto/crítico"] = (t["Alto"] + t["Crítico"]) / t["Total"]
    return t.sort_values("% alto/crítico", ascending=False)


def risk_by_tool(base: StarkBase | None = None) -> pd.DataFrame:
    ev = (base or load_base()).eventos
    t = pd.crosstab(ev["Ferramenta"], ev["Risco"]).reindex(columns=RISK_ORDER, fill_value=0)
    t["Total"] = t.sum(axis=1)
    t["% alto/crítico"] = (t["Alto"] + t["Crítico"]) / t["Total"]
    return t.sort_values("% alto/crítico", ascending=False)


def monthly_critical(base: StarkBase | None = None) -> pd.DataFrame:
    ev = (base or load_base()).eventos.copy()
    ev["Mês"] = ev["Data/hora"].dt.to_period("M").astype(str)
    g = ev.groupby("Mês").agg(Eventos=("ID Evento", "count"), Críticos=("Risco", lambda s: (s == "Crítico").sum()))
    g["% crítico"] = g["Críticos"] / g["Eventos"]
    return g.reset_index()


def info_heatmap(base: StarkBase | None = None) -> pd.DataFrame:
    al = (base or load_base()).alertas
    return pd.crosstab(al["Área"], al["Informação"])


def replay(base: StarkBase | None = None) -> pd.DataFrame:
    """Reprocessa os 650 eventos históricos pelo motor de política do gateway.

    Responde: 'se o gateway estivesse ativo, o que teria acontecido com cada evento?'.
    Usa o tipo de informação registrado (não há texto na base).
    """
    b = base or load_base()
    rows = []
    for _, e in b.eventos.iterrows():
        insp = inspect_declared(e["Tipo informação"], int(e["Qtd. itens"]))
        dec = decide(Context(user_id=e["ID Usuário"], area=e["Área"], tool=e["Ferramenta"], purpose=e["Finalidade"]), insp)
        rows.append({"ID Evento": e["ID Evento"], "Área": e["Área"], "Ferramenta": e["Ferramenta"],
                     "Risco original": e["Risco"], "Regra original": e["Regra acionada"],
                     "Decisão do gateway": dec.action, "Regra do gateway": dec.rule_id})
    return pd.DataFrame(rows)


def replay_summary(rp: pd.DataFrame) -> dict:
    crit = rp[rp["Risco original"] == "Crítico"]
    high = rp[rp["Risco original"] == "Alto"]
    return {
        "criticos": len(crit),
        "criticos_bloqueados": int((crit["Decisão do gateway"] == "BLOCK").sum()),
        "altos": len(high),
        "altos_retidos": int(high["Decisão do gateway"].isin(["APPROVAL", "REVIEW", "BLOCK", "MASK"]).sum()),
        "liberados_sem_atrito": int(rp["Decisão do gateway"].isin(["ALLOW", "ALLOW_REGISTER"]).sum()),
        "total": len(rp),
    }


def indicators(base: StarkBase | None = None) -> pd.DataFrame:
    return (base or load_base()).indicadores
