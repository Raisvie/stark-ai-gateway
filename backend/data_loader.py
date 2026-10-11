"""Leitura da base fictícia da Stark (Base de Dados - Starkbank.xlsx).

Todas as abas têm um título na linha 1, uma linha vazia e o cabeçalho na linha 3.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "Base de Dados - Starkbank.xlsx"

SHEETS = [
    "Eventos_Uso_IA", "Alertas", "Ferramentas_IA", "Tipos_Informacao", "Regras_Risco",
    "Usuarios_Areas", "Casos_Validacao", "Indicadores_Atuais", "Fontes_Logs",
    "Classificacao_Informacao", "Dicionario_Dados",
]


@dataclass(frozen=True)
class StarkBase:
    eventos: pd.DataFrame
    alertas: pd.DataFrame
    ferramentas: pd.DataFrame
    tipos: pd.DataFrame
    regras: pd.DataFrame
    usuarios: pd.DataFrame
    casos: pd.DataFrame
    indicadores: pd.DataFrame
    fontes: pd.DataFrame
    classificacao: pd.DataFrame
    dicionario: pd.DataFrame


@lru_cache(maxsize=1)
def load_base(path: str | Path = XLSX) -> StarkBase:
    raw = pd.read_excel(path, sheet_name=SHEETS, header=2)
    frames = {name: df.dropna(how="all").reset_index(drop=True) for name, df in raw.items()}

    ev = frames["Eventos_Uso_IA"]
    ev["Data/hora"] = pd.to_datetime(ev["Data/hora"], format="%d/%m/%Y %H:%M")
    al = frames["Alertas"]
    al["Data/hora"] = pd.to_datetime(al["Data/hora"], format="%d/%m/%Y %H:%M")

    return StarkBase(
        eventos=ev,
        alertas=al,
        ferramentas=frames["Ferramentas_IA"].rename(columns={"Ferramenta fictícia": "Ferramenta"}),
        tipos=frames["Tipos_Informacao"],
        regras=frames["Regras_Risco"],
        usuarios=frames["Usuarios_Areas"],
        casos=frames["Casos_Validacao"],
        indicadores=frames["Indicadores_Atuais"],
        fontes=frames["Fontes_Logs"],
        classificacao=frames["Classificacao_Informacao"],
        dicionario=frames["Dicionario_Dados"],
    )


def tool_catalog(base: StarkBase | None = None) -> dict[str, dict]:
    """Ferramenta -> {id, tipo, status, uso, logs, controles, finalidade}."""
    base = base or load_base()
    out = {}
    for _, r in base.ferramentas.iterrows():
        out[r["Ferramenta"]] = {
            "id": r["ID"],
            "tipo": r["Tipo"],
            "status": r["Status"],
            "uso": r["Uso principal"],
            "logs": r["Logs disponíveis"],
            "controles": r["Controles fictícios"],
            "finalidade": r["Finalidade aprovada"],
        }
    return out


def rule_table(base: StarkBase | None = None) -> dict[str, dict]:
    base = base or load_base()
    return {
        r["ID"]: {"tema": r["Tema"], "regra": r["Regra fictícia"], "nivel": r["Nível esperado"], "acao": r["Ação esperada"]}
        for _, r in base.regras.iterrows()
    }
