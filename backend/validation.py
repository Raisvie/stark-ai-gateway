"""Baterias de validação.

Base (CV01–CV15): casos da aba Casos_Validacao, com um texto de exemplo fictício para cada um.
Adversarial (CV16–CV21): casos difíceis para mostrar onde o detector ainda pode falhar — e se
ele falha para o lado seguro.
"""
from __future__ import annotations

from dataclasses import dataclass

from .data_loader import load_base
from .detector import inspect
from .policy_engine import EXPECTED_TO_ACTION, RANK, Context, decide

# texto fictício + finalidade usados para executar cada caso da base
CASE_INPUTS = {
    "CV01": ("Apoio ao desenvolvimento: revise este código. Chave de API fictícia: sk_demo_stark_4f9a_secret", "Gerar código"),
    "CV02": ("Resultado financeiro ainda não divulgado: receita fictícia de R$ 248 milhões e margem de 31%.", "Analisar dados"),
    "CV03": ("Folha e remuneração fictícia: Colaborador Exemplo, salário R$ 18.500 e CPF 000.000.000-00.", "Revisar texto"),
    "CV04": ("Proposta comercial confidencial para Cliente Exemplo, desconto especial de 18% e condições ainda não divulgadas.", "Criar rascunho"),
    "CV05": ("Código-fonte fictício para revisão: function calculateFee(value) { return value * 0.012; }", "Explicar código"),
    "CV06": ("Campanha já publicada: Stark Week, conteúdo público disponível no site institucional.", "Criar conteúdo de campanha"),
    "CV07": ("Dados agregados e anonimizados: 42% das interações ocorreram pelo canal web, sem identificação individual.", "Analisar dados"),
    "CV08": ("Parecer jurídico confidencial fictício sobre cláusula contratual do Fornecedor Exemplo.", "Revisar texto"),
    "CV09": ("Estratégia confidencial de lançamento do Produto Exemplo para o próximo trimestre.", "Apoiar decisão"),
    "CV10": ("Dados cadastrais do Cliente Fictício: CPF 000.000.000-00, e-mail cliente@exemplo.invalid.", "Responder cliente"),
    "CV11": ("Projeção confidencial de receita e EBITDA fictícios para o próximo exercício.", "Analisar dados"),
    "CV12": ("Configure o exemplo: API_KEY=demo_secret_stark_12345.", "Gerar código"),
    "CV13": ("Informação sem classificação conhecida para análise.", "Classificar conteúdo"),
    "CV14": ("Campanha já publicada e conteúdo público: texto institucional do Produto Exemplo.", "Criar conteúdo de campanha"),
    "CV15": ("Lote com 10 arquivos de propostas comerciais confidenciais para revisão em massa.", "Revisar texto"),
}

ADVERSARIAL = [
    ("CV16", "Engenharia", "IA Pública A", "Gerar código", "Segue o valor codificado: ZGVtb19zZWNyZXRfc3RhcmtfMTIzNDU=", "CRÍTICO", "Segredo em base64, sem palavra-chave"),
    ("CV17", "Atendimento", "IA Pública B", "Responder cliente", "Maria da Silva, nascida em 12/03/1985, mora na Rua das Flores, 120, apto 4.", "CRÍTICO", "Dado pessoal em texto livre"),
    ("CV18", "Atendimento", "IA Pública A", "Responder cliente", "Documento do cliente: 000.000.000-00.", "CRÍTICO", "CPF sem a palavra “CPF”"),
    ("CV19", "Marketing", "Assistente Corporativo A", "Criar rascunho", "Campanha já publicada. Anexo: API_KEY=demo_secret_stark_999.", "CRÍTICO", "Conteúdo público misturado com segredo"),
    ("CV20", "Comercial", "IA Pública B", "Criar rascunho", "Confidential commercial proposal for Example Client, special discount of 20%.", "CRÍTICO", "Informação comercial em inglês"),
    ("CV21", "Produto", "Assistente Corporativo A", "Apoiar decisão", "Campanha já publicada. Estratégia confidencial de lançamento do Produto Exemplo para o próximo trimestre.", "MÉDIO", "Marcador “público” junto com dado restrito"),
]


@dataclass
class CaseResult:
    caso: str
    area: str
    ferramenta: str
    o_que_testa: str
    esperado: str
    obtido: str
    regra: str
    status: str  # Correto | Desvio seguro | EXPOSIÇÃO


def _status(obtained: str, expected: str) -> str:
    if obtained == expected:
        return "Correto"
    return "Desvio seguro" if RANK[obtained] > RANK[expected] else "EXPOSIÇÃO"


def base_cases() -> list[tuple]:
    rows = []
    for _, r in load_base().casos.iterrows():
        text, purpose = CASE_INPUTS[r["Caso"]]
        rows.append((r["Caso"], r["Área"], r["Ferramenta"], purpose, text, r["Resultado esperado"], r["Justificativa"]))
    return rows


def run_suite(cases: list[tuple]) -> list[CaseResult]:
    out = []
    for caso, area, tool, purpose, text, expected_label, what in cases:
        insp = inspect(text)
        dec = decide(Context(area=area, tool=tool, purpose=purpose), insp)
        expected = EXPECTED_TO_ACTION[expected_label]
        out.append(CaseResult(caso, area, tool, what, expected, dec.action, dec.rule_id, _status(dec.action, expected)))
    return out


def run_all() -> dict[str, list[CaseResult]]:
    return {"base": run_suite(base_cases()), "adversarial": run_suite(ADVERSARIAL)}
