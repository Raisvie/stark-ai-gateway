"""Inspeção do conteúdo antes do envio (camada DLP do gateway).

Cada achado é ligado a um tipo de informação da base (INF-01…INF-20), que define a
classificação padrão (Pública, Interna, Confidencial, Crítica).

Camadas:
  1. Padrões determinísticos (regex, dígito verificador, Luhn, entropia).
  2. Sinais semânticos por vocabulário (PT e EN) — no produto, substituídos por um
     classificador de IA rodando em ambiente corporativo.
"""
from __future__ import annotations

import base64
import binascii
import math
import re
import unicodedata
from dataclasses import dataclass, field

LEVEL = {"Pública": 0, "Interna": 1, "Confidencial": 2, "Crítica": 3}

# INF id -> (nome, categoria de negócio, classificação padrão)
INFO_TYPES = {
    "INF-00": ("Documento marcado como confidencial", "Não especificada", "Confidencial"),
    "INF-01": ("Código-fonte", "Propriedade intelectual", "Confidencial"),
    "INF-02": ("Chave/API secret", "Credencial", "Crítica"),
    "INF-03": ("Arquitetura técnica", "Propriedade intelectual", "Confidencial"),
    "INF-04": ("Contrato de cliente", "Cliente/Jurídico", "Confidencial"),
    "INF-05": ("Proposta comercial", "Comercial", "Confidencial"),
    "INF-06": ("Pipeline de vendas", "Comercial", "Confidencial"),
    "INF-07": ("Dados cadastrais de cliente", "Dados pessoais", "Confidencial"),
    "INF-08": ("Dados financeiros de cliente", "Cliente/Financeiro", "Crítica"),
    "INF-09": ("Resultado financeiro não divulgado", "Estratégica/Financeira", "Crítica"),
    "INF-10": ("Projeção de receita/EBITDA", "Estratégica/Financeira", "Confidencial"),
    "INF-11": ("Currículo de candidato", "Dados pessoais", "Confidencial"),
    "INF-12": ("Folha/remuneração", "Dados pessoais", "Crítica"),
    "INF-13": ("Avaliação de desempenho", "Dados pessoais", "Confidencial"),
    "INF-14": ("Parecer jurídico", "Jurídico", "Confidencial"),
    "INF-15": ("Ata de reunião interna", "Interna", "Interna"),
    "INF-16": ("Campanha já publicada", "Marketing", "Pública"),
    "INF-17": ("Estratégia de lançamento", "Estratégica", "Confidencial"),
    "INF-18": ("Dados agregados anonimizados", "Analytics", "Interna"),
    "INF-19": ("Ticket de atendimento anonimizado", "Atendimento", "Interna"),
    "INF-20": ("Documento público/regulatório", "Pública", "Pública"),
}
PERSONAL = {"INF-07", "INF-11", "INF-12", "INF-13"}


@dataclass
class Finding:
    info_id: str
    evidence: str          # sinal que disparou (nunca o valor sensível completo)
    count: int = 1
    method: str = "padrão"  # padrão | validação | semântico | declarado

    @property
    def name(self) -> str:
        return INFO_TYPES[self.info_id][0]

    @property
    def category(self) -> str:
        return INFO_TYPES[self.info_id][1]

    @property
    def sensitivity(self) -> str:
        return INFO_TYPES[self.info_id][2]


@dataclass
class Inspection:
    findings: list[Finding] = field(default_factory=list)
    volume_items: int = 1
    unclassified_marker: bool = False

    @property
    def ids(self) -> set[str]:
        return {f.info_id for f in self.findings}

    @property
    def has_secret(self) -> bool:
        return "INF-02" in self.ids

    @property
    def has_personal(self) -> bool:
        return bool(self.ids & PERSONAL)

    @property
    def sensitivity(self) -> str | None:
        """Maior classificação encontrada. Conteúdo restrito anula marcadores de 'público'."""
        if not self.findings:
            return None
        return max((f.sensitivity for f in self.findings), key=LEVEL.get)

    @property
    def restricted(self) -> bool:
        return self.sensitivity in ("Confidencial", "Crítica")

    @property
    def confidence(self) -> str:
        if not self.findings:
            return "Baixa"
        strong = any(f.method in ("validação", "padrão", "declarado") for f in self.findings)
        return "Alta" if strong else "Média"


def norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


# ---------- validadores ----------
def cpf_valid(digits: str) -> bool:
    d = re.sub(r"\D", "", digits)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        s = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (s * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def luhn_valid(number: str) -> bool:
    d = [int(c) for c in re.sub(r"\D", "", number)][::-1]
    if not 13 <= len(d) <= 19:
        return False
    total = sum(x if i % 2 == 0 else (x * 2 - 9 if x * 2 > 9 else x * 2) for i, x in enumerate(d))
    return total % 10 == 0


def shannon(s: str) -> float:
    if not s:
        return 0.0
    freq = {c: s.count(c) / len(s) for c in set(s)}
    return -sum(p * math.log2(p) for p in freq.values())


# ---------- padrões ----------
RX_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
RX_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
RX_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RX_PHONE = re.compile(r"(?:\+?55\s?)?\(?\b\d{2}\)?\s?9\d{4}-?\d{4}\b")
RX_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
RX_DATE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
RX_ADDRESS = re.compile(r"\b(rua|avenida|av\.|alameda|travessa|rodovia|estrada)\s+[a-zÀ-ÿ ]{3,40},?\s*\d+", re.I)
RX_SECRET = re.compile(
    r"(api[_\s-]?key|chave.{0,12}api|secret|\bsk[_-][a-z0-9_]{6,}|\btoken\b|senha\s*[:=]|password\s*[:=]|"
    r"credencia|akia[0-9a-z]{12,}|ghp_[a-z0-9]{20,}|xox[bp]-[a-z0-9-]{10,}|begin [a-z ]*private key)"
)
RX_B64 = re.compile(r"\b[A-Za-z0-9+/]{16,}={0,2}")
RX_VOLUME = re.compile(r"\b(\d{1,4})\s+(arquivos|documentos|planilhas|contratos|propostas|files|documents)\b")

# vocabulário semântico (normalizado, sem acento) -> INF
VOCAB: list[tuple[str, str]] = [
    ("INF-09", r"resultado financeiro|(resultado|receita|lucro|balanco|margem).{0,40}nao divulgad|antes da divulgacao|balanco nao publicado|receita ficticia|unreleased (results|earnings)"),
    ("INF-10", r"ebitda|projecao.{0,20}receita|forecast|orcamento confidencial|budget"),
    ("INF-08", r"saldo|extrato|limite de credito|dados financeiros de cliente|conta corrente|transacoes do cliente|account balance"),
    ("INF-12", r"folha( de pagamento)?|remuneracao|salario|bonus individual|payroll|salary"),
    ("INF-11", r"curriculo|candidat[oa]|resume\b|\bcv do"),
    ("INF-13", r"avaliacao de desempenho|feedback individual|performance review|plano de desenvolvimento individual"),
    ("INF-07", r"dados cadastrais|cadastro do cliente|nascid[oa] em|data de nascimento|\brg\b|endereco residencial|customer data"),
    ("INF-04", r"contrato (de|do) cliente|clausula contratual|minuta de contrato|aditivo contratual|customer contract"),
    ("INF-05", r"proposta comercial|propostas comerciais|desconto especial|condicoes (comerciais|ainda nao divulgadas)|commercial proposal|special discount"),
    ("INF-06", r"pipeline de vendas|funil de vendas|forecast de vendas|sales pipeline"),
    ("INF-14", r"parecer juridico|opiniao legal|legal opinion|estrategia processual"),
    ("INF-17", r"estrategia.{0,25}lancamento|roadmap confidencial|planejamento confidencial|launch strategy"),
    ("INF-03", r"arquitetura (tecnica|do sistema)|diagrama de infraestrutura|topologia de rede"),
    ("INF-01", r"codigo-fonte|codigo fonte|\bfunction\s|\bdef\s+\w+\(|\bclass\s+\w+|\breturn\s|import\s+\w+|source code"),
    ("INF-15", r"ata de reuniao|pauta interna|reuniao interna"),
    ("INF-19", r"ticket.{0,20}anonimizad"),
    ("INF-18", r"anonimizad|dados agregados|sem identificacao individual"),
    ("INF-16", r"ja publicad|conteudo publico|site institucional|campanha publicada"),
    ("INF-20", r"documento publico|regulatorio publico|resolucao do banco central|lei geral de protecao"),
]
CONFIDENTIAL_WORDS = re.compile(r"\b(confidencial|confidential|sigilos[oa]|restrito|uso interno apenas)\b")


def inspect(text: str, declared_items: int = 1) -> Inspection:
    raw = text or ""
    t = norm(raw)
    found: dict[str, Finding] = {}

    def add(info_id: str, evidence: str, n: int = 1, method: str = "padrão"):
        if info_id in found:
            found[info_id].count += n
        else:
            found[info_id] = Finding(info_id, evidence, n, method)

    # 1. credenciais
    secrets = RX_SECRET.findall(t)
    if secrets:
        add("INF-02", "padrão de credencial/secret", len(secrets))
    for tok in RX_B64.findall(raw):
        if len(tok) < 20 or tok.isalpha() or tok.isdigit():
            continue
        try:
            decoded = base64.b64decode(tok + "=" * (-len(tok) % 4), validate=True).decode("utf-8", "ignore")
        except (binascii.Error, ValueError):
            decoded = ""
        if RX_SECRET.search(norm(decoded)) or (shannon(tok) > 4.0 and len(tok) >= 32):
            add("INF-02", "segredo codificado (base64/alta entropia)", 1, "validação")

    # 2. identificadores pessoais
    cpfs = RX_CPF.findall(raw)
    if cpfs:
        valid = sum(cpf_valid(c) for c in cpfs)
        add("INF-07", f"CPF ({valid} com dígito válido)" if valid else "número no formato de CPF", len(cpfs),
            "validação" if valid else "padrão")
    if RX_CNPJ.search(raw):
        add("INF-07", "CNPJ", len(RX_CNPJ.findall(raw)))
    if RX_EMAIL.search(raw):
        add("INF-07", "e-mail", len(RX_EMAIL.findall(raw)))
    if RX_PHONE.search(raw):
        add("INF-07", "telefone", len(RX_PHONE.findall(raw)))
    if RX_ADDRESS.search(raw) or (RX_DATE.search(raw) and re.search(r"nascid|nasceu|born", t)):
        add("INF-07", "endereço ou data de nascimento em texto livre", 1, "semântico")
    cards = [c for c in RX_CARD.findall(raw) if luhn_valid(c) and not RX_CPF.fullmatch(c.strip())]
    if cards:
        add("INF-08", "número de cartão (Luhn válido)", len(cards), "validação")

    # 3. vocabulário semântico
    for info_id, pattern in VOCAB:
        hits = re.findall(pattern, t)
        if hits:
            add(info_id, "vocabulário de " + INFO_TYPES[info_id][0].lower(), len(hits), "semântico")

    # 4. marcador genérico "confidencial" sem tipo específico
    if CONFIDENTIAL_WORDS.search(t) and not any(LEVEL[f.sensitivity] >= 2 for f in found.values()):
        add("INF-00", "documento marcado como confidencial", 1, "semântico")

    # público só vale quando não há nada restrito junto
    insp = Inspection(list(found.values()))
    if insp.restricted:
        insp.findings = [f for f in insp.findings if f.sensitivity != "Pública"]

    vol = [int(m.group(1)) for m in RX_VOLUME.finditer(t)]
    if re.search(r"lote|em massa|bulk|todos os arquivos", t) and not vol:
        vol = [10]
    insp.volume_items = max([declared_items, *vol])
    insp.unclassified_marker = bool(re.search(r"sem classificacao|nao classificad", t))
    return insp


def inspect_declared(info_name: str, items: int = 1) -> Inspection:
    """Inspeção a partir do tipo de informação já registrado (eventos históricos da base)."""
    for info_id, (name, _, _) in INFO_TYPES.items():
        if name == info_name:
            return Inspection([Finding(info_id, "tipo declarado no registro", 1, "declarado")], volume_items=items)
    return Inspection([], volume_items=items, unclassified_marker=True)


# ---------- sanitização ----------
def sanitize(text: str) -> str:
    out = RX_CPF.sub("[CPF]", text)
    out = RX_CNPJ.sub("[CNPJ]", out)
    out = RX_EMAIL.sub("[E-MAIL]", out)
    out = RX_PHONE.sub("[TELEFONE]", out)
    out = RX_CARD.sub(lambda m: "[CARTÃO]" if luhn_valid(m.group()) else m.group(), out)
    out = RX_ADDRESS.sub("[ENDEREÇO]", out)
    out = re.sub(r"(nascid[oa] em\s*)\d{2}/\d{2}/\d{4}", r"\1[DATA]", out, flags=re.I)
    if re.search(r"salari|remunerac|folha|bonus|payroll|salary", norm(text)):
        out = re.sub(r"R\$\s*[\d.,]+", "[VALOR]", out)
    out = re.sub(r"((?:api[_\s-]?key|token|senha|password|secret)\s*[:=]\s*)\S+", r"\1[SEGREDO]", out, flags=re.I)
    out = re.sub(r"\bsk[_-][A-Za-z0-9_]{6,}", "[SEGREDO]", out)
    out = RX_NAME.sub(_mask_name, out)
    return out


def _mask_name(m: re.Match) -> str:
    words = m.group().split()
    i = 0
    while i < len(words) and (words[i] in NOT_NAMES or words[i] in CONNECTORS):
        i += 1
    rest = words[i:]
    if sum(w[0].isupper() for w in rest) < 2:
        return m.group()
    return " ".join(words[:i] + ["[NOME]"])


CONNECTORS = {"da", "de", "do", "dos", "das", "e"}


# Nome próprio (2+ palavras capitalizadas). Heurística de protótipo; em produção, NER (ex.: Presidio).
RX_NAME = re.compile(r"\b([A-ZÀ-Ý][a-zà-ÿ]+)(?:\s+(?:da|de|do|dos|das|e)?\s*[A-ZÀ-Ý][a-zà-ÿ]+)+\b")
NOT_NAMES = {
    "Analise", "Responda", "Crie", "Escreva", "Resuma", "Revise", "Monte", "Produto", "Cliente", "Campanha",
    "Stark", "Assistente", "Copiloto", "Plataforma", "Gerador", "Ferramenta", "Fornecedor", "Colaborador",
    "Banco", "Central", "Open", "Segue", "Projeção", "Estratégia", "Parecer", "Proposta", "Dados", "Documento",
    "Salário", "Folha", "Contrato", "Relatório", "Equipe", "Time", "Prezado", "Prezada", "Olá", "Oi", "Caro", "Cara",
}
