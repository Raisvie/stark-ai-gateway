# Stark AI Gateway — protótipo (ITA Challenge Sprint)

Gateway que **inspeciona e decide antes do envio** de conteúdo para ferramentas de IA, e **Íris**, um agente
educativo que mostra aos profissionais administrativos como usar as IAs aprovadas da Stark para entregar mais rápido.
Construído sobre `Base de Dados - Starkbank.xlsx` (dados fictícios do desafio).

## Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py                 # tela da apresentação → http://localhost:8501
uvicorn api:app --port 8000          # (opcional) API REST do gateway → http://localhost:8000/docs
python -m pytest -q tests            # testes automatizados
```

**Conversa com Claude (opcional):** defina `ANTHROPIC_API_KEY` antes de iniciar. Sem ela, a Íris responde pela base
de conhecimento local — a demonstração funciona offline. A Íris usa o modelo `claude-opus-5-5` e só recebe texto já
filtrado pelo gateway.

## Estrutura

| Arquivo | Papel |
|---|---|
| `app.py` | Tela Streamlit: Gateway, Íris, Insights, Validação & auditoria, Como funciona |
| `api.py` | API REST (`/v1/inspect`, `/v1/agent/chat`, `/v1/audit/verify`) |
| `backend/detector.py` | Inspeção: credenciais, CPF, cartão, base64, vocabulário PT/EN, volume; sanitização |
| `backend/policy_engine.py` | Decisão determinística com as regras R01–R14 da base |
| `backend/audit.py` | Trilha com SHA-256 do conteúdo, versão da política, SLA e cadeia de hashes |
| `backend/education_agent.py` | Íris: explicação de cada decisão, guias por área, chat, quiz |
| `backend/analytics.py` | KPIs da base e reprocessamento dos 650 eventos pelo motor |
| `backend/validation.py` | Baterias CV01–CV15 (base) e CV16–CV21 (adversarial) |
| `PASSO_A_PASSO.md` | Registro de tudo o que foi feito |

## Resultados

- 21/21 casos de validação corretos, 0 exposições.
- Reprocessando os 650 eventos históricos: **74/74 críticos bloqueados**, 86/86 altos retidos, 384 usos sem atrito.
