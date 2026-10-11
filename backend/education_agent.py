"""Íris — agente educativo do Stark AI Gateway.

Dois papéis (Hipótese V10, seção 03):
  1. Explicar cada decisão do gateway no momento do uso e indicar a alternativa segura.
  2. Ensinar os profissionais administrativos a usar as IAs aprovadas para acelerar entregas.

Regra de ouro: a Íris nunca recebe o conteúdo sensível original. Ela trabalha com metadados
(área, ferramenta, finalidade, categoria, regra) e com texto já sanitizado pelo gateway.
O modo conversa usa Claude quando há credencial configurada; sem ela, usa a base de
conhecimento local — a demonstração funciona offline.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .detector import Inspection, inspect, norm, sanitize
from .policy_engine import TOOL_PURPOSES, TOOLS, Context, Decision, decide

AGENT_NAME = "Íris"
MODEL = "claude-opus-5-5"


# ---------------------------------------------------------------------------
# 1. Mensagem contextual para cada decisão
# ---------------------------------------------------------------------------
@dataclass
class Guidance:
    mood: str              # alerta | atencao | aprovado | mascara | pensando
    headline: str
    message: str
    next_steps: list[str] = field(default_factory=list)
    safe_prompt: str | None = None
    lesson: tuple[str, list[str]] | None = None


LESSONS = {
    "INF-02": ("Segredos não são contexto", [
        "A IA não precisa da chave para revisar o código — use um valor fictício como API_KEY=<SUA_CHAVE>.",
        "Chave colada em prompt deve ser tratada como vazada: peça a rotação.",
        "Guarde credenciais no cofre de segredos, nunca em arquivos de texto ou planilhas.",
    ]),
    "pessoal": ("Minimização de dados (LGPD)", [
        "Pergunte-se: a IA precisa saber QUEM é a pessoa para fazer a tarefa? Quase nunca.",
        "Troque nome, CPF e contato por rótulos: [CLIENTE], [COLABORADOR_A].",
        "Depois, recoloque os dados reais no texto final — fora da IA.",
    ]),
    "financeiro": ("Informação financeira não divulgada", [
        "Resultado antes da divulgação oficial é informação privilegiada.",
        "Para estruturar a análise, use números fictícios ou variações percentuais.",
        "A Plataforma de Dados IA tem acesso por perfil e trilha de auditoria.",
    ]),
    "comercial": ("Propostas e contratos", [
        "Condições comerciais pertencem ao cliente e à Stark — não a um provedor externo.",
        "Use o Assistente Corporativo A ou o Assistente Jurídico (ambiente segregado).",
        "Para benchmark de mercado, descreva o cenário sem nomes e sem valores.",
    ]),
    "publica": ("Por que a IA pública é diferente", [
        "Sem contrato corporativo, não há garantia de retenção nem de não-treinamento com seus dados.",
        "Sem logs corporativos, a Stark não consegue provar o que foi compartilhado.",
        "As ferramentas aprovadas fazem as mesmas tarefas — com proteção.",
    ]),
    "volume": ("Envio em lote", [
        "Muitos arquivos de uma vez aumentam a exposição sem aumentar a qualidade da resposta.",
        "Envie só os trechos necessários — a IA trabalha melhor com contexto focado.",
        "Se o lote for realmente necessário, a aprovação do gestor fica registrada.",
    ]),
    "finalidade": ("A ferramenta certa para cada tarefa", [
        "Cada IA aprovada tem uma finalidade: código, dados, jurídico, produtividade.",
        "Usar a ferramenta certa melhora o resultado e mantém o uso rastreável.",
        "Na dúvida, pergunte para mim qual ferramenta usar.",
    ]),
}


def _lesson_for(insp: Inspection, dec: Decision):
    ids = insp.ids
    if "INF-02" in ids:
        return LESSONS["INF-02"]
    if insp.has_personal:
        return LESSONS["pessoal"]
    if ids & {"INF-08", "INF-09", "INF-10"}:
        return LESSONS["financeiro"]
    if dec.rule_id == "R11":
        return LESSONS["volume"]
    if dec.rule_id == "R10":
        return LESSONS["finalidade"]
    if ids & {"INF-04", "INF-05", "INF-06", "INF-14"}:
        return LESSONS["comercial"]
    if dec.tool_class == "publica":
        return LESSONS["publica"]
    return None


def _safe_prompt(ctx: Context, insp: Inspection, text: str) -> str:
    """Reescreve o pedido sem dados sensíveis, mantendo a intenção."""
    if insp.has_secret:
        clean = sanitize(text)
        return clean + "\n\n(Use um valor fictício no lugar da credencial. A chave real fica no cofre de segredos.)"
    if insp.has_personal:
        return sanitize(text)
    if insp.restricted:
        return (f"Atue como apoio para {ctx.purpose.lower()} na área de {ctx.area}. "
                "Considere um cenário hipotético com valores fictícios: [descreva a situação sem nomes de clientes, "
                "sem números reais e sem condições comerciais]. Entregue: 1) estrutura, 2) pontos de atenção, 3) próximo passo.")
    return text


def explain(ctx: Context, insp: Inspection, dec: Decision, text: str = "") -> Guidance:
    kinds = ", ".join(sorted({f.name.lower() for f in insp.findings})) or "nenhum dado sensível"
    alt = dec.suggested_tool
    lesson = _lesson_for(insp, dec)
    act = dec.action

    if not dec.enforced and dec.stops_content:
        return Guidance("pensando", "Modo monitor: registrei, mas não interrompi",
                        f"Em modo proteção, esta tentativa seria: **{dec.meta['titulo'].lower()}** (regra {dec.rule_id}). "
                        "O modo monitor serve para medir o risco real antes de ativar o bloqueio.",
                        ["Revise o conteúdo antes de enviar", "Use a ferramenta corporativa aprovada"],
                        _safe_prompt(ctx, insp, text), lesson)

    if act == "BLOCK":
        if insp.has_secret:
            steps = ["Remova a credencial do texto", "Peça a rotação da chave à Segurança (já avisada)",
                     f"Reenvie o pedido via {alt or 'Assistente de Código'} com um valor fictício"]
            head = "Segurei aqui: encontrei uma credencial"
        else:
            steps = [f"Use **{alt}** — mesma tarefa, ambiente protegido",
                     "Ou anonimize o conteúdo com a sugestão abaixo", "Se precisar de exceção, peça ao gestor"]
            head = f"Essa informação não pode ir para a {ctx.tool}"
        msg = (f"Encontrei **{kinds}**. {dec.reason} Nada foi enviado — a proteção agiu antes da conexão. "
               "Não é uma punição: é a vacina funcionando.")
        return Guidance("alerta", head, msg, steps, _safe_prompt(ctx, insp, text), lesson)

    if act == "REVIEW":
        return Guidance("atencao", "Preciso de uma segunda opinião humana",
                        f"{dec.reason} Seu pedido ficou retido e a governança foi acionada.",
                        [f"Prefira {alt or 'Assistente Corporativo A'}, que já está no catálogo",
                         "Informe a finalidade com clareza", "Peça a inclusão da ferramenta no catálogo, se ela for útil para o time"],
                        _safe_prompt(ctx, insp, text), lesson)

    if act == "APPROVAL":
        return Guidance("atencao", f"Isso precisa do OK de {ctx.manager}",
                        f"Encontrei **{kinds}**. {dec.reason} Enviei o pedido de aprovação; você recebe a resposta aqui.",
                        ["Reduza o volume ou envie só os trechos necessários", "Explique a finalidade na justificativa",
                         "Enquanto isso, trabalhe com um exemplo fictício"],
                        _safe_prompt(ctx, insp, text), lesson)

    if act == "MASK":
        return Guidance("mascara", "Pode seguir — removi os dados pessoais",
                        f"A ferramenta é aprovada, mas a tarefa não precisa de **{kinds}**. "
                        "Só a versão mascarada vai para a IA; depois você recoloca os dados no texto final.",
                        ["Confira se a versão mascarada ainda atende ao pedido", "Recoloque os dados reais fora da IA"],
                        sanitize(text) if text else None, lesson)

    tip = None
    if alt and not dec.purpose_ok:
        tip = f"Para '{ctx.purpose.lower()}', **{alt}** costuma entregar melhor."
    elif dec.tool_class == "publica":
        tip = "Liberado porque não há dado restrito — mas o Assistente Corporativo A guarda seu histórico e não treina com seus dados."
    head = "Tudo certo, pode seguir!" if act == "ALLOW" else "Liberado — e registrado"
    msg = ("Uso compatível com a política. " if act == "ALLOW" else
           f"Ferramenta aprovada para **{kinds}**. O uso fica rastreável para sua proteção. ")
    msg += tip or "Dica: dê contexto, formato e critério de qualidade — veja os modelos no Guia."
    return Guidance("aprovado", head, msg, [], None, lesson if tip else None)


# ---------------------------------------------------------------------------
# 2. Guia de produtividade por área administrativa
# ---------------------------------------------------------------------------
@dataclass
class UseCase:
    tarefa: str
    ferramenta: str
    finalidade: str
    prompt: str
    nunca: str
    ganho: str


PLAYBOOKS: dict[str, list[UseCase]] = {
    "Financeiro": [
        UseCase("Comentário de variação orçamentária", "Plataforma de Dados IA", "Analisar dados",
                "Você é analista de FP&A. Com base na tabela anexa (valores em % de variação, sem nomes de clientes), "
                "explique as 3 maiores variações orçado × realizado, possíveis causas e perguntas para os donos dos centros de custo. "
                "Formato: tabela + 5 bullets executivos.",
                "Resultado ainda não divulgado ao mercado; dados de clientes individuais.",
                "Rascunho do comentário mensal pronto para revisão."),
        UseCase("Resumo de política ou norma", "Assistente Corporativo A", "Resumir documento",
                "Resuma a norma anexa em linguagem simples para o time. Liste: o que muda, quem é afetado, prazos e "
                "3 perguntas frequentes com respostas.",
                "Planilhas com dados de clientes junto com o documento.",
                "Leitura de normas longas em minutos."),
        UseCase("E-mail de cobrança de documentos", "Copiloto de Produtividade", "Criar rascunho",
                "Escreva um e-mail cordial para [ÁREA] solicitando os comprovantes pendentes do fechamento de [MÊS], "
                "com prazo [DATA] e lista em bullets. Tom: objetivo e colaborativo.",
                "Valores de remuneração ou dados bancários.",
                "Comunicações padronizadas sem retrabalho."),
    ],
    "Pessoas": [
        UseCase("Descrição de vaga", "Copiloto de Produtividade", "Criar rascunho",
                "Crie uma descrição de vaga para [CARGO] na área de [ÁREA]: missão, responsabilidades, requisitos "
                "obrigatórios e desejáveis, linguagem inclusiva e sem jargões.",
                "Currículos de candidatos e faixas salariais individuais.",
                "Vaga publicada mais rápido e com linguagem consistente."),
        UseCase("Roteiro de onboarding", "Assistente Corporativo A", "Criar apresentação",
                "Monte um roteiro de onboarding de 2 semanas para [CARGO]: objetivos por dia, materiais, quem apresenta e "
                "checkpoints. Formato: tabela.",
                "Nome, CPF ou avaliação de desempenho da pessoa contratada.",
                "Primeiro dia organizado para todo novo colaborador."),
        UseCase("Estruturar feedback", "Assistente Corporativo A", "Revisar texto",
                "Reescreva este feedback no modelo Situação-Comportamento-Impacto, tom respeitoso e acionável: "
                "[descreva a situação sem o nome da pessoa].",
                "Nome da pessoa, notas de avaliação, dados de saúde.",
                "Conversas difíceis mais claras e justas."),
    ],
    "Jurídico": [
        UseCase("Resumo de contrato", "Assistente Jurídico", "Resumir documento",
                "Resuma o contrato anexo: partes, objeto, prazo, multas, rescisão, obrigações da Stark e cláusulas fora do padrão. "
                "Sinalize riscos em vermelho/amarelo/verde.",
                "Usar IA pública para qualquer contrato — o Assistente Jurídico roda em ambiente segregado.",
                "Triagem de contratos em minutos, não horas."),
        UseCase("Comparar versões de minuta", "Assistente Jurídico", "Revisar texto",
                "Compare a versão A e a versão B da minuta e liste todas as alterações materiais, com impacto para a Stark.",
                "Pareceres de outros casos sem relação com a tarefa.",
                "Revisão de redlines mais segura."),
        UseCase("Pesquisa de tema regulatório", "Assistente Corporativo A", "Pesquisar hipóteses",
                "Liste os principais pontos da regulamentação pública sobre [TEMA] e as perguntas que devemos responder internamente.",
                "Fatos de processos em andamento.",
                "Ponto de partida estruturado para o parecer."),
    ],
    "Comercial": [
        UseCase("Estrutura de proposta", "Assistente Corporativo A", "Criar rascunho",
                "Crie a estrutura de uma proposta para um cliente do segmento [SEGMENTO] interessado em [PRODUTO]: "
                "contexto, dor, solução, benefícios, próximos passos. Use [CLIENTE] como marcador.",
                "Nome real do cliente, descontos e condições — inclua depois, fora da IA.",
                "Propostas novas a partir de um esqueleto pronto."),
        UseCase("Preparação de reunião", "Copiloto de Produtividade", "Criar apresentação",
                "Prepare uma pauta de 30 min para reunião de descoberta com um cliente de [SEGMENTO]: objetivos, "
                "10 perguntas abertas e possíveis objeções com respostas.",
                "Pipeline de vendas e dados de outros clientes.",
                "Reuniões mais produtivas."),
        UseCase("Follow-up pós-reunião", "Copiloto de Produtividade", "Criar rascunho",
                "Com base nestas anotações [sem dados pessoais], escreva um e-mail de follow-up com resumo, "
                "próximos passos, responsáveis e datas.",
                "Contatos pessoais do cliente.",
                "Follow-up enviado no mesmo dia."),
    ],
    "Atendimento": [
        UseCase("Resposta empática padrão", "Copiloto de Produtividade", "Responder cliente",
                "Escreva uma resposta para um cliente que relata [PROBLEMA], com empatia, explicação simples, "
                "prazo e próximo passo. Use [CLIENTE] no lugar do nome.",
                "CPF, saldo, extrato, dados cadastrais.",
                "Respostas consistentes e mais rápidas."),
        UseCase("Classificar tickets", "Assistente Corporativo A", "Classificar conteúdo",
                "Classifique os tickets anonimizados abaixo por tema, urgência e área responsável. Formato: tabela.",
                "Tickets sem anonimização.",
                "Fila organizada no início do turno."),
        UseCase("Base de conhecimento", "Assistente Corporativo A", "Criar rascunho",
                "Transforme este procedimento interno em um artigo de ajuda para clientes: passo a passo, linguagem simples, "
                "perguntas frequentes.",
                "Dados de clientes usados como exemplo.",
                "Menos tickets repetidos."),
    ],
    "Operações": [
        UseCase("Documentar processo (POP)", "Assistente Corporativo A", "Criar rascunho",
                "Transforme estas anotações em um procedimento operacional: objetivo, papéis, passo a passo numerado, "
                "controles e exceções.",
                "Dados de clientes ou transações reais.",
                "Processos documentados e auditáveis."),
        UseCase("Análise de indicadores operacionais", "Plataforma de Dados IA", "Analisar dados",
                "Analise a série de volumes agregados por dia e identifique tendências, picos e possíveis causas. "
                "Sugira 3 ações.",
                "Base com identificação individual.",
                "Leitura rápida dos números da semana."),
        UseCase("Ata de reunião", "Copiloto de Produtividade", "Resumir documento",
                "Resuma estas anotações em ata: decisões, pendências com responsável e prazo, riscos.",
                "Credenciais ou dados de clientes citados na reunião.",
                "Ata pronta ao sair da reunião."),
    ],
    "Risco & Compliance": [
        UseCase("Checklist de controle", "Assistente Corporativo A", "Criar rascunho",
                "Crie um checklist de verificação para o processo [PROCESSO] com base nesta política interna: "
                "item, evidência esperada, frequência, responsável.",
                "Achados de investigação com nomes.",
                "Testes de controle padronizados."),
        UseCase("Mapear riscos de um processo", "Assistente Corporativo A", "Apoiar decisão",
                "Liste os riscos operacionais, de fraude e de privacidade do processo descrito, com probabilidade, impacto e controle sugerido.",
                "Casos reais em investigação.",
                "Matriz de risco inicial em minutos."),
        UseCase("Resumo regulatório", "Assistente Jurídico", "Resumir documento",
                "Resuma a norma pública anexa: o que muda, prazos, impactos para a Stark e plano de adequação sugerido.",
                "Pareceres internos sigilosos sem relação com a tarefa.",
                "Adequação regulatória mais ágil."),
    ],
    "Marketing": [
        UseCase("Variações de texto de campanha", "Copiloto de Produtividade", "Criar rascunho",
                "Crie 5 variações de título e subtítulo para a campanha pública [CAMPANHA], público [PÚBLICO], tom [TOM].",
                "Estratégia de lançamento ainda não anunciada (use o Assistente Corporativo A).",
                "Mais opções para testar em menos tempo."),
        UseCase("Peça visual de campanha publicada", "Gerador de Imagens", "Criar conteúdo de campanha",
                "Gere uma imagem para a campanha já publicada [CAMPANHA], estilo [ESTILO], sem logos de terceiros.",
                "Qualquer material confidencial — o gerador é aprovado só para conteúdo público.",
                "Peças de apoio sem depender de fila de design."),
        UseCase("Plano de conteúdo", "Assistente Corporativo A", "Apoiar decisão",
                "Monte um calendário editorial de 4 semanas para [TEMA], com formato, canal, objetivo e métrica de cada peça.",
                "Dados de clientes de campanhas anteriores.",
                "Planejamento mensal estruturado."),
    ],
}

PROMPT_RECIPE = [
    ("Papel", "Diga quem a IA deve ser: “Você é analista de FP&A…”"),
    ("Contexto", "Explique a situação — sem dados pessoais nem segredos; use [MARCADORES]."),
    ("Tarefa", "Peça uma coisa por vez, com verbo claro: resuma, compare, classifique."),
    ("Formato", "Defina a entrega: tabela, 5 bullets, e-mail de 120 palavras."),
    ("Critério", "Diga como é um bom resultado: tom, público, o que evitar."),
    ("Revisão", "Você é o responsável final: confira números, fatos e tom antes de usar."),
]


# ---------------------------------------------------------------------------
# 3. Conversa
# ---------------------------------------------------------------------------
def _catalog_text() -> str:
    lines = []
    for name, t in TOOLS.items():
        if t["classe"] == "desconhecida":
            continue
        purposes = ", ".join(sorted(TOOL_PURPOSES.get(name, []))) or "nenhuma (não aprovada)"
        lines.append(f"- {name} ({t['status']}): {purposes}")
    return "\n".join(lines)


SYSTEM_PROMPT = f"""Você é a {AGENT_NAME}, agente educativa do Stark AI Gateway, no Stark Bank.
Seu público são profissionais administrativos (Financeiro, Pessoas, Jurídico, Comercial, Atendimento,
Operações, Risco & Compliance, Marketing). Seu objetivo é que eles usem as IAs aprovadas pela empresa para
entregar mais rápido e melhor, sem expor dados.

Catálogo de ferramentas e finalidades aprovadas:
{_catalog_text()}

Política (resumo): segredos e credenciais nunca vão para nenhuma IA; conteúdo confidencial ou crítico
nunca vai para IA pública; dados pessoais são mascarados; envio de 10+ arquivos restritos precisa de
aprovação do gestor; ferramenta fora do catálogo vai para revisão humana.

Como responder:
- Português do Brasil, tom acolhedor e direto, no máximo ~150 palavras.
- Quando a pessoa descrever uma tarefa, indique a ferramenta aprovada e entregue um prompt-modelo
  com [MARCADORES] no lugar de dados reais (papel, contexto, tarefa, formato, critério).
- Nunca peça nem repita dados pessoais, valores financeiros reais, credenciais ou nomes de clientes.
- As mensagens chegam já filtradas pelo gateway; marcadores como [CPF] ou [NOME] indicam que algo foi removido.
- Se não souber uma regra interna específica, diga isso e sugira consultar a Governança de IA."""


INTENTS = [
    (r"qual (ferramenta|ia)|que (ferramenta|ia)|onde (uso|faco|posso)|ferramenta (certa|ideal)",
     "tool"),
    (r"anonimiz|mascar|tirar (os )?dados|lgpd|dado pessoal|cpf",
     "anon"),
    (r"chatgpt|gemini|ia publica|publica|externa|gratuita",
     "public"),
    (r"prompt|como (pedir|perguntar|escrever)|melhor resultado|instrucao",
     "prompt"),
    (r"bloque|por que (fui|foi)|barrad|negad",
     "blocked"),
    (r"senha|chave|token|credencial|api",
     "secret"),
    (r"resum|e-?mail|apresenta|planilha|contrato|proposta|vaga|ata|relatorio",
     "task"),
]


STOP = {"para", "como", "qual", "uma", "que", "com", "sem", "fazer", "preciso", "quero", "posso", "usar", "ferramenta"}


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z]{3,}", norm(text)) if w not in STOP}


def _match_use_case(t: str, area: str) -> UseCase | None:
    """Caso de uso com maior sobreposição de radicais; empate favorece a área de quem pergunta."""
    q = _stems(t)
    best, best_score = None, 0
    for a, ucs in PLAYBOOKS.items():
        for uc in ucs:
            score = len(q & _stems(uc.tarefa)) * 2 + len(q & _stems(uc.prompt)) * 0.2 + (0.5 if a == area else 0)
            if score > best_score:
                best, best_score = uc, score
    return best if best_score >= 2 else None


def _local_answer(msg: str, ctx: Context) -> str:
    t = norm(msg)
    intent = next((name for rx, name in INTENTS if re.search(rx, t)), None)
    cases = PLAYBOOKS.get(ctx.area, PLAYBOOKS["Operações"])

    if intent in (None, "tool", "task"):
        uc = _match_use_case(t, ctx.area)
        if uc:
            return (f"Boa! Para **{uc.tarefa.lower()}**, use **{uc.ferramenta}** (finalidade: {uc.finalidade.lower()}).\n\n"
                    f"Prompt-modelo:\n> {uc.prompt}\n\n⚠️ Nunca inclua: {uc.nunca}")
        if intent == "task":
            intent = "tool"
    if intent == "tool":
        rows = "\n".join(f"- **{uc.tarefa}** → {uc.ferramenta}" for uc in cases)
        return (f"Para a área de **{ctx.area}**, estes são os usos que mais aceleram entregas:\n{rows}\n\n"
                "Regra rápida: texto e e-mail → Copiloto de Produtividade · documentos e análises gerais → Assistente Corporativo A · "
                "contratos → Assistente Jurídico · números → Plataforma de Dados IA · código → Assistente de Código.")
    if intent == "anon":
        return ("Anonimizar em 3 passos:\n1. Troque nomes por papéis: [CLIENTE], [COLABORADOR_A].\n"
                "2. Remova identificadores: CPF, e-mail, telefone, conta, endereço.\n"
                "3. Troque valores reais por fictícios ou por variação %.\n\n"
                "A IA entrega o mesmo resultado — e você recoloca os dados no texto final, fora dela. "
                "Em ferramenta aprovada, o gateway já mascara o que eu encontrar.")
    if intent == "public":
        return ("IA pública (A e B) não tem contrato corporativo nem logs: não dá para saber onde o conteúdo fica nem provar o que foi enviado. "
                "Ela só é liberada para conteúdo **público** (ex.: campanha já publicada). Para todo o resto, o **Assistente Corporativo A** "
                "faz a mesma coisa com proteção.")
    if intent == "prompt":
        recipe = "\n".join(f"{i+1}. **{a}** — {b}" for i, (a, b) in enumerate(PROMPT_RECIPE))
        return f"Um bom prompt tem 6 partes:\n{recipe}"
    if intent == "blocked":
        return ("O bloqueio acontece antes do envio, quando encontro segredo, dado pessoal em IA pública ou informação "
                "confidencial fora do ambiente aprovado. Não é punição: nada vazou. No painel do Gateway eu mostro a "
                "alternativa segura e uma versão do pedido sem os dados sensíveis.")
    if intent == "secret":
        return ("Credenciais (senhas, tokens, chaves de API) **nunca** vão para nenhuma IA — nem as aprovadas. "
                "Use um valor fictício (API_KEY=<SUA_CHAVE>). Se uma chave já foi colada em algum lugar, peça a rotação à Segurança.")
    return ("Posso ajudar com: **qual ferramenta usar** para uma tarefa, **como montar um bom prompt**, **como anonimizar** "
            "um documento, ou **por que um envio foi bloqueado**. Me conte o que você precisa entregar hoje.")


def llm_available() -> bool:
    if os.environ.get("IRIS_OFFLINE") == "1":
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _llm_answer(history: list[dict], ctx: Context) -> str | None:
    import anthropic

    client = anthropic.Anthropic()
    system = SYSTEM_PROMPT + f"\n\nPerfil de quem pergunta: área {ctx.area}, cargo {ctx.cargo or 'não informado'}."
    try:
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=system,
            messages=history[-12:],
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except (anthropic.APIStatusError, anthropic.APIConnectionError):
        return None
    if resp.stop_reason == "refusal":
        return None
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text or None


@dataclass
class ChatTurn:
    reply: str
    decision: Decision | None
    sanitized: str
    used_llm: bool


def chat(message: str, ctx: Context, history: list[dict]) -> ChatTurn:
    """A própria conversa com a Íris passa pelo gateway: ela também não recebe dado sensível."""
    insp = inspect(message)
    gw_ctx = Context(ctx.user_id, ctx.area, ctx.cargo, "Assistente Corporativo A", "Pesquisar hipóteses", ctx.manager)
    dec = decide(gw_ctx, insp)
    if insp.has_secret:
        return ChatTurn("🔒 Sua mensagem tinha uma **credencial** e eu não a recebi. Apague-a e, se ela é real, "
                        "peça a rotação à Segurança. Pode refazer a pergunta usando um valor fictício.", dec, "", False)
    safe = sanitize(message) if insp.findings else message
    prefix = ""
    if safe != message:
        prefix = "🛡️ Removi dados pessoais da sua mensagem antes de ler. Eu não preciso deles para ajudar.\n\n"

    msgs = history + [{"role": "user", "content": safe}]
    if llm_available():
        answer = _llm_answer(msgs, ctx)
        if answer:
            return ChatTurn(prefix + answer, dec, safe, True)
    return ChatTurn(prefix + _local_answer(safe, ctx), dec, safe, False)


# ---------------------------------------------------------------------------
# 4. Quiz relâmpago
# ---------------------------------------------------------------------------
QUIZ = [
    ("Você quer que a IA revise um script que contém API_KEY=… Qual o caminho?",
     ["Colar no Assistente de Código, ele é aprovado", "Trocar a chave por um valor fictício e usar o Assistente de Código",
      "Usar a IA Pública A, que é mais rápida"], 1,
     "Credenciais são bloqueadas em qualquer ferramenta, inclusive nas aprovadas (R03)."),
    ("Precisa resumir um contrato de cliente. Onde?",
     ["Assistente Jurídico", "IA Pública B", "Gerador de Imagens"], 0,
     "O Assistente Jurídico roda em ambiente segregado e é a ferramenta aprovada para contratos."),
    ("Uma campanha já publicada no site pode ir para a IA Pública B?",
     ["Sim, é conteúdo público", "Não, nunca", "Só com aprovação do diretor"], 0,
     "Conteúdo público sem dado restrito junto é permitido (R08) — mas cuidado para não misturar."),
    ("Você vai enviar 12 propostas comerciais de uma vez para o Assistente Corporativo A. O que acontece?",
     ["Envio liberado", "Pede aprovação do gestor", "Bloqueio definitivo"], 1,
     "Volume elevado de conteúdo confidencial exige aprovação (R11)."),
    ("Qual é o jeito certo de pedir ajuda para responder um cliente?",
     ["Colar o cadastro completo para dar contexto", "Descrever o problema usando [CLIENTE] no lugar dos dados",
      "Enviar print da tela do sistema"], 1,
     "Minimização: a IA não precisa saber quem é o cliente para escrever uma boa resposta."),
]
