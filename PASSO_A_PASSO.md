# Passo a passo — Protótipo Stark AI Gateway (ITA Challenge Sprint)

Registro de tudo o que foi feito para construir o protótipo, na ordem em que aconteceu.

---

## Etapa 1 — Leitura e análise dos arquivos da pasta

### 1.1 `Diagnostico_Governanca_Rastreabilidade_IA_Starkbank.pdf` (10 páginas)
- Escopo: 01/06 a 08/09/2026 · 650 eventos · 72 usuários · 12 áreas · 8 ferramentas.
- 160 alertas alto/crítico (24,6%), 74 eventos críticos (11,4% vs meta < 1%), 113 alertas pendentes (70,6%).
- Pareto das causas: finalidade incompatível (30%), IA não aprovada (24,4%), volume elevado (23,8%), credenciais/secrets (21,9%).
- Lacunas: rastreabilidade completa 84% (meta ≥ 98%), SLA crítico 24h em 72% (meta ≥ 95%),
  148 registros manuais (22,8%), 2 ferramentas públicas sem log, sem hash do artefato e sem data de fechamento do alerta.
- Recomendação 0–30 dias: **bloquear/intermediar IA pública não aprovada (proxy + DLP)**.

### 1.2 `Hipotese_de_Solucao_V10.pdf` (16 páginas)
- Conceito "vacina": prevenir **antes** do envio ao modelo.
- Fluxo: identidade → canal controlado → inspeção (DLP + IA) → motor de política → modelo aprovado → visualização segura.
- 4 decisões: **Permitir · Sanitizar · Aprovar · Bloquear** (+ revisão humana quando a confiança é baixa).
- Separação de papéis: **IA analisa e educa · regras decidem · pessoas aprovam exceções**.
- Agente educativo: explica o bloqueio, recomenda a ferramenta aprovada, ensina anonimização — **sem receber o conteúdo sensível original**.
- Métrica principal: taxa de bloqueio de exposições críticas, meta 100%.

### 1.3 `Base de Dados - Starkbank.xlsx` (11 abas, cabeçalho na linha 3)
| Aba | Conteúdo | Uso no protótipo |
|---|---|---|
| Eventos_Uso_IA | 650 eventos | Painel de insights |
| Alertas | 160 alertas (Aberto/Em análise/Tratado) | Fila de incidentes |
| Ferramentas_IA | 8 ferramentas (IA-01…IA-08) e status de aprovação | Catálogo do motor de política |
| Tipos_Informacao | 20 tipos (INF-01…INF-20) e classificação padrão | Classificação do conteúdo |
| Regras_Risco | R01…R14 | Regras citadas em cada decisão |
| Usuarios_Areas | 72 usuários, 12 áreas, cargos | Perfis do simulador |
| Casos_Validacao | CV01…CV15 com resultado esperado | Bateria de testes automática |
| Indicadores_Atuais | 10 KPIs e metas | Comparação atual × meta |
| Fontes_Logs, Classificacao_Informacao, Dicionario_Dados | Referência | Arquitetura / documentação |

### 1.4 `stark-ai-gateway-v2.html` (mockup visual)
- Paleta navy `#1B2B4C` + dourado `#C19A4F`, fontes Playfair Display + Albert Sans.
- Abas: Simulador, Insights, Arquitetura, Auditoria e validação, Matriz de regras.
- Motor de decisão em JavaScript (regex) com 6 ações e baterias CV01–CV15 + adversarial CV16–CV21.
- **Pontos a ajustar para a competição:**
  1. Tudo roda no navegador — não há backend real fazendo o bloqueio.
  2. Insights usam dados **aleatórios simulados**, não a base da Stark.
  3. Agente educativo é só uma caixa de texto — não há avatar nem conversa.
  4. Não há foco nos **profissionais administrativos** e em *como* usar as IAs aprovadas para acelerar entregas.
  5. Regras do HTML não citam os IDs R01–R14 da base.

---

## Etapa 2 — Desenho da solução (decisões de arquitetura)

```
ITA_Sprint/
├── app.py                  ← tela Streamlit (frontend)
├── backend/
│   ├── data_loader.py      ← lê a planilha da Stark
│   ├── detector.py         ← inspeção do conteúdo (segredos, CPF, dados pessoais...)
│   ├── policy_engine.py    ← motor determinístico: BLOQUEAR / MASCARAR / APROVAR / REVISAR / PERMITIR
│   ├── audit.py            ← trilha de auditoria com hash SHA-256 (sem guardar o texto)
│   ├── education_agent.py  ← agente educativo (avatar) + guias por área administrativa
│   ├── analytics.py        ← KPIs reais da base
│   └── validation.py       ← baterias CV01–CV21
├── assets/                 ← avatar do agente
├── tests/                  ← testes automáticos
└── .streamlit/config.toml  ← tema visual navy/dourado
```

Princípios mantidos da Hipótese V10:
- O bloqueio é **determinístico** (regras), nunca depende só de um modelo de IA.
- O agente educativo **nunca recebe o texto sensível** — só metadados (categoria, ferramenta, área, regra).
- Falha segura: dúvida → retém para revisão humana.

---

## Etapa 3 — Ambiente

```bash
pip install streamlit anthropic plotly pandas openpyxl pytest
```
Python 3.11. Também foi usado `pypdf` apenas para ler os PDFs nesta análise.

---

## Etapa 4 — Backend (pasta `backend/`)

### 4.1 `data_loader.py`
- Lê as 11 abas da planilha com `header=2` (o cabeçalho está na 3ª linha).
- Converte "Data/hora" para data real.

### 4.2 `detector.py` — inspeção do conteúdo (camada DLP)
Cada achado vira um tipo de informação da base (INF-01…INF-20) com sua classificação.
- **Credenciais:** palavras-chave + padrões (`sk_`, `AKIA`, `ghp_`, `API_KEY=`) + **segredo em base64/alta entropia**.
- **Dados pessoais:** CPF (com validação do dígito), CNPJ, e-mail, telefone, endereço, data de nascimento.
- **Cartão:** número validado pelo algoritmo de Luhn.
- **Vocabulário de negócio em PT e EN:** resultado não divulgado, EBITDA, folha, proposta comercial, parecer jurídico etc.
- **Regra anti-burla:** se houver dado restrito, o marcador "já publicado" é ignorado.
- **Sanitização:** troca CPF, e-mail, telefone, nome, endereço, valores de salário e segredos por `[CPF]`, `[NOME]`…

### 4.3 `policy_engine.py` — decisão determinística (versão `POL-2026.10-v3`)
| Ordem | Regra da base | Situação | Decisão |
|---|---|---|---|
| 1 | R03 | Segredo/credencial (qualquer ferramenta) | BLOQUEAR |
| 2 | R01/R02/R04/R05/R06 | Conteúdo restrito em IA pública | BLOQUEAR |
| 3 | R13/R14 | Ferramenta desconhecida / sem classificação | REVISÃO HUMANA |
| 4 | R11 | 10+ itens restritos de uma vez | PEDIR APROVAÇÃO |
| 5 | R07 + LGPD | Dado pessoal em ferramenta aprovada | MASCARAR |
| 6 | R10 | Crítico em ferramenta aprovada / finalidade incompatível | APROVAÇÃO / REVISÃO |
| 7 | R07 | Confidencial em ferramenta aprovada | PERMITIR COM REGISTRO |
| 8 | R08/R09 | Público, interno, anonimizado | PERMITIR |

Novidade em relação ao HTML: **política por finalidade** (R10 — a causa nº 1 dos alertas, 30%).
Cada ferramenta tem finalidades aprovadas; o motor sugere a ferramenta certa para a tarefa.

### 4.4 `audit.py` — trilha de auditoria
Fecha lacunas do Diagnóstico: grava **SHA-256 do conteúdo** (prova sem guardar o texto), versão da política,
data de abertura/fechamento (SLA recalculável) e **cadeia de hashes** (cada registro aponta para o anterior).
Arquivo: `runtime/audit_log.jsonl`.

### 4.5 `validation.py` — baterias de teste
- Base CV01–CV15 (aba Casos_Validacao) + adversarial CV16–CV21 (base64, texto livre, CPF sem rótulo, inglês, mistura público+segredo).
- **Resultado: 21/21 corretos.**
- Ajuste feito durante o teste: CV04 citava R05 (financeiro) porque "condições ainda não divulgadas" casava com o vocabulário financeiro — padrão restringido.
- Ajuste na máscara: "Salário de Ana Souza R$ 9.200" agora vira "Salário de [NOME] [VALOR]".

### 4.6 `analytics.py` — indicadores reais + reprocessamento histórico
- KPIs batem com o Diagnóstico: 650 eventos, 160 alertas, 74 críticos, 113 pendentes, 148 manuais.
- **Reprocessamento dos 650 eventos pelo motor do gateway:**
  - **74/74 eventos críticos seriam bloqueados antes do envio** (meta da Hipótese: 100%).
  - 86/86 eventos de risco alto ficariam retidos (aprovação, máscara ou bloqueio).
  - 384 eventos seguiriam sem atrito — o gateway não trava o trabalho do dia a dia.

---

## Etapa 5 — Agente educativo "Íris" (`backend/education_agent.py` + `ui/avatar.py`)

- **Avatar em SVG** com 6 expressões ligadas à decisão: olá, aprovado (verde), alerta (vermelho), atenção (dourado),
  máscara (azul) e pensando (modo monitor). Pisca e flutua levemente (respeita "reduzir movimento").
- **Mensagem por decisão:** título, explicação, próximos passos, **versão segura do pedido** e uma **microlição**
  (segredos, LGPD, financeiro, comercial, IA pública, volume, finalidade).
- **Guia por área administrativa** (Financeiro, Pessoas, Jurídico, Comercial, Atendimento, Operações,
  Risco & Compliance, Marketing): 3 usos cada, com ferramenta aprovada, prompt-modelo com [MARCADORES],
  "nunca inclua" e o resultado esperado.
- **Receita de prompt** em 6 partes (papel, contexto, tarefa, formato, critério, revisão) com exemplo antes/depois.
- **Chat:** a própria mensagem passa pelo gateway — credencial é retida, CPF/nome viram [CPF]/[NOME] antes de a
  Íris ler. Com `ANTHROPIC_API_KEY` usa Claude (`claude-opus-5-5`, esforço baixo, fallback automático);
  sem chave, responde pela base local (funciona offline no palco).
- Ajustes durante o teste: o chat passou a casar a tarefa pelo radical da palavra ("resumir contrato" →
  Assistente Jurídico; "ata" → Ata de reunião) e textos como "pelo Plataforma" viraram "via Plataforma".
- **Quiz relâmpago** de 5 perguntas com feedback.

## Etapa 6 — Tela Streamlit (`app.py`, `ui/style.py`, `.streamlit/config.toml`)

Identidade visual herdada do HTML (navy `#1B2B4C`, dourado `#C19A4F`, Playfair Display + Albert Sans).

| Aba | O que mostra |
|---|---|
| 🛡️ Gateway | Hero "IA além do hype", 74/74 críticos bloqueados, simulador com 10 cenários prontos (foco administrativo), cartão de decisão, Íris, botões "Reenviar via ferramenta segura" e "Usar a versão segura", evidência de auditoria |
| 🎓 Íris · Guia de IA | Guia da área, conversa, receita de prompt, quiz |
| 📊 Insights da base | KPIs reais, "se o gateway estivesse ativo", Pareto, risco por ferramenta, % crítico por mês × meta, mapa área × tipo de dado, indicadores, fila de alertas |
| ✅ Validação & auditoria | 21 casos com esperado × obtido, trilha com verificação da cadeia de hashes, exportar CSV |
| 🧭 Como funciona | Fluxo de 5 etapas, papéis (IA · regras · pessoas), matriz de regras, finalidades por ferramenta, lacunas fechadas, caminho 30/60/90, limites |

Controles no topo: **Modo** Proteção/Monitor e **Perfil** Liderança (só agregados) / Segurança (vê IDs).

**O que mudou em relação ao HTML original:**
1. Decisão roda no backend Python (e em API REST), não no navegador.
2. Insights usam a base real, não dados aleatórios.
3. A caixa de texto educativa virou a Íris com avatar, conversa, guia por área e quiz.
4. Foco em profissionais administrativos e em produtividade com as IAs aprovadas.
5. Regras citam os IDs R01–R14; nova regra de finalidade (R10).
6. Auditoria com hash, versão da política e cadeia à prova de adulteração.

## Etapa 7 — API REST (`api.py`)

`POST /v1/inspect` (decisão + conteúdo liberado/mascarado + orientação da Íris), `POST /v1/agent/chat`,
`GET /v1/audit/verify`. É o ponto que uma extensão de navegador ou proxy chamaria em produção.

## Etapa 8 — Testes e verificação

- `tests/test_gateway.py`: 10 testes (baterias, reprocessamento 74/74, segredo em ferramenta aprovada, modo monitor,
  uso comum liberado, CPF/Luhn/máscara, adulteração da trilha, Íris não recebe segredo/CPF, API). **10/10 passando.**
- Teste de fluxo da tela com `streamlit.testing.AppTest`: cenário → bloqueio → reenvio seguro → máscara; chat; monitor. Sem erros.
- App iniciado com `streamlit run app.py` e health check `200 OK`.

## Como apresentar (roteiro sugerido, ~4 min)

1. **Gateway → "Pessoas · folha na IA pública"** → Analisar: bloqueio + Íris explica.
2. Clicar **"Reenviar via …"**: mesma tarefa, agora mascarada e liberada — *a segurança não trava o trabalho*.
3. **"Comercial · lote de 10 propostas"** → aprovação do gestor (R11).
4. **"Adversarial · base64"** → mostra que não depende de palavra-chave.
5. **Íris → Conversar**: "Qual ferramenta uso para resumir um contrato?" e depois colar um CPF.
6. **Insights**: "se o gateway estivesse ativo, 74/74 críticos bloqueados e 384 usos sem atrito".
7. **Validação**: 21/21, 0 exposições, cadeia de auditoria íntegra.
