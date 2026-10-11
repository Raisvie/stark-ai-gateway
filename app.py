"""Stark AI Gateway — protótipo para o ITA Challenge Sprint.

Rodar:  streamlit run app.py
"""
from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from backend import analytics, audit
from backend.data_loader import load_base
from backend.detector import inspect, sanitize
from backend.education_agent import (AGENT_NAME, PLAYBOOKS, PROMPT_RECIPE, QUIZ, chat, explain, llm_available)
from backend.policy_engine import (ACTIONS, POLICY_VERSION, PURPOSES, TOOL_PURPOSES, TOOLS, Context, decide,
                                   resend_safely)
from backend.validation import ADVERSARIAL, base_cases, run_suite
from ui.avatar import avatar_svg
from ui.style import CSS

st.set_page_config(page_title="Stark AI Gateway", page_icon="🛡️", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

INK, GOLD, MUTED, LINE, CRIT = "#1B2B4C", "#C19A4F", "#5C6A84", "#E5E3DA", "#A8434B"
esc = html.escape


# ---------------------------------------------------------------------------
# dados (cache)
# ---------------------------------------------------------------------------
@st.cache_data
def cached_base():
    b = load_base()
    return b


@st.cache_data
def cached_replay():
    return analytics.replay()


@st.cache_data
def cached_suites():
    return run_suite(base_cases()), run_suite(ADVERSARIAL)


base = cached_base()
users = base.usuarios.copy()
users["label"] = users["ID Usuário"] + " · " + users["Cargo"] + " · " + users["Área"]
USER_LABELS = users["label"].tolist()
USER_BY_LABEL = users.set_index("label").to_dict("index")


def first_user(area: str, cargo: str | None = None) -> str:
    sub = users[users["Área"] == area]
    if cargo is not None and (sub["Cargo"] == cargo).any():
        sub = sub[sub["Cargo"] == cargo]
    return sub.iloc[0]["label"]


# cenários prontos para a demonstração — foco no administrativo
SCENARIOS = {
    "— escolha um cenário —": None,
    "Pessoas · folha de pagamento na IA pública": (first_user("Pessoas", "Comp & Ben"), "IA Pública A", "Analisar dados", 1,
        "Analise a folha de pagamento de setembro e aponte desvios: Ana Souza, salário R$ 9.200, CPF 529.982.247-25; "
        "Bruno Lima, salário R$ 12.400."),
    "Pessoas · mesma tarefa no Assistente Corporativo": (first_user("Pessoas", "Comp & Ben"), "Assistente Corporativo A", "Analisar dados", 1,
        "Analise a folha de pagamento de setembro e aponte desvios: Ana Souza, salário R$ 9.200, CPF 529.982.247-25; "
        "Bruno Lima, salário R$ 12.400."),
    "Financeiro · resultado não divulgado na IA pública": (first_user("Financeiro", "Controller"), "IA Pública B", "Apoiar decisão", 1,
        "Resultado financeiro ainda não divulgado: receita de R$ 248 milhões e margem de 31%. Monte um resumo para a diretoria."),
    "Comercial · lote de 10 propostas": (first_user("Comercial", "Sales Manager"), "Assistente Corporativo A", "Revisar texto", 10,
        "Lote com 10 arquivos de propostas comerciais confidenciais para revisão em massa."),
    "Atendimento · resposta a cliente com dados pessoais": (first_user("Atendimento"), "Copiloto de Produtividade", "Responder cliente", 1,
        "Responda ao cliente João Pereira (joao.p@email.com, (11) 98765-4321) pedindo desculpas pelo atraso no PIX de ontem."),
    "Jurídico · parecer no Assistente Jurídico": (first_user("Jurídico"), "Assistente Jurídico", "Revisar texto", 1,
        "Parecer jurídico confidencial sobre cláusula contratual do Fornecedor Exemplo: revise a redação."),
    "Operações · ata de reunião (uso livre)": (first_user("Operações"), "Copiloto de Produtividade", "Resumir documento", 1,
        "Resuma a ata de reunião interna sobre o novo fluxo de conciliação: decisões, pendências e responsáveis."),
    "Engenharia · chave de API (CV12)": (first_user("Engenharia"), "Assistente de Código", "Gerar código", 1,
        "Configure o exemplo: API_KEY=demo_secret_stark_12345."),
    "Shadow AI · ferramenta fora do catálogo (CV13)": (first_user("Operações"), "Ferramenta desconhecida", "Classificar conteúdo", 1,
        "Informação sem classificação conhecida para análise."),
    "Adversarial · segredo escondido em base64 (CV16)": (first_user("Engenharia"), "IA Pública A", "Gerar código", 1,
        "Segue o valor codificado: ZGVtb19zZWNyZXRfc3RhcmtfMTIzNDU="),
}

ss = st.session_state
ss.setdefault("f_user", first_user("Financeiro", "FP&A"))
ss.setdefault("f_tool", "Assistente Corporativo A")
ss.setdefault("f_purpose", "Criar rascunho")
ss.setdefault("f_qty", 1)
ss.setdefault("f_text", "")
ss.setdefault("last", None)
ss.setdefault("session", {"tentativas": 0, "criticas": 0, "criticas_bloqueadas": 0, "liberadas": 0})
ss.setdefault("chat", [])
ss.setdefault("chat_api", [])


def load_scenario():
    sc = SCENARIOS.get(ss.scenario)
    if not sc:
        return
    ss.f_user, ss.f_tool, ss.f_purpose, ss.f_qty, ss.f_text = sc
    ss.last = None


def manager_of(area: str) -> str:
    return f"Gestor(a) de {area}"


def current_ctx() -> Context:
    u = USER_BY_LABEL[ss.f_user]
    return Context(user_id=u["ID Usuário"], area=u["Área"], cargo=u["Cargo"], tool=ss.f_tool,
                   purpose=ss.f_purpose, manager=manager_of(u["Área"]))


def run_gateway(ctx: Context, text: str, qty: int, origin: str = "Gateway (automático)"):
    enforce = (ss.get("mode") or "Proteção") == "Proteção"
    insp = inspect(text, declared_items=qty)
    dec = decide(ctx, insp, enforce=enforce)
    rec = audit.record(ctx, insp, dec, text)
    s = ss.session
    s["tentativas"] += 1
    if dec.risk == "Crítico":
        s["criticas"] += 1
        if dec.enforced:
            s["criticas_bloqueadas"] += 1
    if dec.action in ("ALLOW", "ALLOW_REGISTER", "MASK"):
        s["liberadas"] += 1
    ss.last = {"ctx": ctx, "insp": insp, "dec": dec, "text": text, "rec": rec,
               "guide": explain(ctx, insp, dec, text), "origin": origin}


def on_analyze():
    if not ss.f_text.strip():
        ss.form_error = True
        return
    ss.form_error = False
    run_gateway(current_ctx(), ss.f_text.strip(), int(ss.f_qty))


def on_resend():
    last = ss.last
    new_ctx = resend_safely(last["ctx"], last["insp"])
    text = sanitize(last["text"]) if last["insp"].has_personal else last["text"]
    ss.f_tool, ss.f_purpose, ss.f_text = new_ctx.tool, new_ctx.purpose, text
    run_gateway(new_ctx, text, last["insp"].volume_items, origin="Reenvio pela alternativa segura")


def on_use_safe_prompt():
    ss.f_text = ss.last["guide"].safe_prompt
    ss.last = None


# ---------------------------------------------------------------------------
# componentes visuais
# ---------------------------------------------------------------------------
def stat(value, label, detail="", tone=""):
    return (f'<div class="stat"><div class="v {tone}">{value}</div><div class="l">{esc(label)}</div>'
            f'<div class="d">{esc(detail)}</div></div>')


def md_inline(s: str) -> str:
    """**negrito** -> <b> sobre texto já escapado."""
    import re
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc(s))


def iris_block(guide, size=118):
    steps = "".join(f"<li>{md_inline(s)}</li>" for s in guide.next_steps)
    lesson = ""
    if guide.lesson:
        title, bullets = guide.lesson
        lesson = (f'<div class="lesson"><b>Microlição · {esc(title)}</b>'
                  + "".join(f"<div>• {esc(b)}</div>" for b in bullets) + "</div>")
    st.markdown(
        f'<div class="iris">{avatar_svg(guide.mood, size)}<div class="bubble"><div class="who">{AGENT_NAME} · agente educativo</div>'
        f'<h4>{esc(guide.headline)}</h4><p>{md_inline(guide.message)}</p>'
        f'{"<ol>" + steps + "</ol>" if steps else ""}{lesson}</div></div>',
        unsafe_allow_html=True)


def decision_card(last):
    dec, insp, ctx, text = last["dec"], last["insp"], last["ctx"], last["text"]
    meta = dict(dec.meta)
    tone = meta["tom"]
    if not dec.enforced and dec.stops_content:
        meta = {"titulo": "REGISTRADO EM MONITOR", "sub": f"Em modo proteção: {dec.meta['titulo'].lower()}.", "icone": "◉"}
        tone = "mon"
    risk_cls = {"Crítico": "crit", "Alto": "warn", "Revisar": "warn", "Médio": "mask", "Baixo": "ok"}[dec.risk]
    tags = "".join(f'<span class="tag">{esc(f.name)}{" ×" + str(f.count) if f.count > 1 else ""}</span>'
                   for f in insp.findings) or '<span class="tag">Nenhum dado sensível identificado</span>'
    if dec.action == "BLOCK" and dec.enforced:
        payload = "ENVIO INTERROMPIDO ANTES DO CONECTOR\nNenhum byte foi transmitido para " + ctx.tool + "."
    elif dec.action in ("REVIEW", "APPROVAL") and dec.enforced:
        payload = "CONTEÚDO RETIDO NO GATEWAY\nAguardando " + ("revisão da governança." if dec.action == "REVIEW" else f"aprovação de {ctx.manager}.")
    elif dec.action == "MASK":
        payload = "VERSÃO SANITIZADA QUE SEGUE PARA A IA:\n\n" + sanitize(text)
    else:
        payload = "CONTEÚDO AUTORIZADO QUE SEGUE PARA A IA:\n\n" + text
    chips = "".join(f'<span class="chip">{esc(n)}</span>' for n in dec.notify)
    origin = f'<span class="pill">{esc(last["origin"])}</span>' if last["origin"] != "Gateway (automático)" else ""
    st.markdown(f"""
<div class="dcard tone-{tone}">
  <div class="dtop"><div class="dicon">{meta['icone']}</div>
    <div><div class="dtitle">{meta['titulo']}</div><div class="dsub">{esc(meta['sub'])}</div></div></div>
  <div class="dbody">
    <span class="pill {risk_cls}">RISCO {dec.risk.upper()}</span><span class="pill">REGRA {dec.rule_id}</span>
    <span class="pill">CONFIANÇA {insp.confidence.upper()}</span>{origin}
    <div class="sect">O que o gateway encontrou</div>{tags}
    <div class="sect">Regra aplicada · {dec.rule_id}</div><div>{esc(dec.rule_text)}.<br><span style="color:var(--muted)">{esc(dec.reason)}</span></div>
    <div class="sect">Destino do conteúdo</div><div class="payload">{esc(payload)}</div>
    <div class="sect">Quem foi avisado</div>{chips}
  </div>
</div>""", unsafe_allow_html=True)


def fig_style(fig, height=320):
    fig.update_layout(height=height, margin=dict(l=8, r=16, t=10, b=8), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Albert Sans, Segoe UI, sans-serif", color=INK, size=13),
                      hoverlabel=dict(bgcolor="white", font_color=INK, bordercolor=LINE), showlegend=False)
    fig.update_xaxes(gridcolor="#EFEDE6", zeroline=False, linecolor=LINE)
    fig.update_yaxes(gridcolor="#EFEDE6", zeroline=False, linecolor=LINE)
    return fig


PLOT_CFG = {"displayModeBar": False}

# ---------------------------------------------------------------------------
# cabeçalho
# ---------------------------------------------------------------------------
st.markdown("""
<div class="topband"><div class="brand">
<svg width="34" height="38" viewBox="0 0 34 38" aria-hidden="true"><path d="M17 2 31 7v11c0 9-6 15-14 18C9 33 3 27 3 18V7z" fill="none" stroke="#D8B573" stroke-width="2.2"/><path d="m10.5 18.5 5 5 8.5-10" fill="none" stroke="#D8B573" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
<div><b>STARK</b><small>AI GATEWAY</small></div></div>
<span class="badge">ITA Challenge Sprint · Protótipo · dados fictícios</span></div>""", unsafe_allow_html=True)

c1, c2, c3 = st.columns([1.2, 1.2, 3])
with c1:
    st.segmented_control("Modo do gateway", ["Proteção", "Monitor"], key="mode", default="Proteção",
                         help="Monitor registra a decisão sem bloquear — serve para medir o risco antes de ativar a proteção.")
with c2:
    st.segmented_control("Perfil de visão", ["Liderança", "Segurança"], key="role", default="Liderança",
                         help="Liderança vê só dados agregados. Segurança vê IDs de usuário (acesso registrado).")
if ss.get("mode") == "Monitor":
    st.warning("**Modo monitor ativo:** as decisões são registradas, mas nenhum envio é interrompido.", icon="📡")

tab_gw, tab_iris, tab_ins, tab_val, tab_how = st.tabs(
    ["🛡️ Gateway", f"🎓 {AGENT_NAME} · Guia de IA", "📊 Insights da base", "✅ Validação & auditoria", "🧭 Como funciona"])

# ---------------------------------------------------------------------------
# TAB 1 — GATEWAY
# ---------------------------------------------------------------------------
with tab_gw:
    rp = cached_replay()
    rs = analytics.replay_summary(rp)
    suite_b, suite_a = cached_suites()
    exposures = sum(r.status == "EXPOSIÇÃO" for r in suite_b + suite_a)

    h1, h2 = st.columns([1.7, 1])
    with h1:
        st.markdown("""<div class="hero"><div class="eyebrow">IA além do hype</div>
<h1>Uma vacina operacional para o <em>uso seguro de IA</em></h1>
<p>O gateway lê identidade, finalidade e conteúdo <b>antes</b> do envio, aplica uma política determinística e a
Íris orienta o colaborador na hora — mostrando o caminho seguro para entregar mais rápido.</p></div>""",
                    unsafe_allow_html=True)
    with h2:
        st.markdown(stat(f"{rs['criticos_bloqueados']}/{rs['criticos']}", "eventos críticos da base seriam bloqueados",
                         "650 eventos reais reprocessados pelo motor", "ok"), unsafe_allow_html=True)
        st.write("")
        st.markdown(stat(f"{rs['liberados_sem_atrito']}", "usos seguiriam sem atrito",
                         f"{rs['liberados_sem_atrito'] / rs['total']:.0%} do total — o trabalho não para", "gold"),
                    unsafe_allow_html=True)

    st.write("")
    s = ss.session
    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(stat(s["tentativas"], "Tentativas nesta sessão", "cada uma vira registro auditável"), unsafe_allow_html=True)
    m2.markdown(stat(f"{s['criticas_bloqueadas']}/{s['criticas']}" if s["criticas"] else "—",
                     "Críticas bloqueadas", "meta: 100%", "ok" if s["criticas"] == s["criticas_bloqueadas"] else "crit"),
                unsafe_allow_html=True)
    m3.markdown(stat(s["criticas"] - s["criticas_bloqueadas"], "Exposições críticas liberadas",
                     "só ocorre em modo monitor", "crit" if s["criticas"] > s["criticas_bloqueadas"] else "ok"),
                unsafe_allow_html=True)
    m4.markdown(stat(f"{exposures}", "Exposições nos 21 testes", "baterias base + adversarial", "ok" if not exposures else "crit"),
                unsafe_allow_html=True)

    st.write("")
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        st.subheader("Simular uma tentativa de uso")
        st.selectbox("Cenário pronto", list(SCENARIOS), key="scenario", on_change=load_scenario,
                     help="Carrega um caso da base ou um cenário administrativo típico.")
        a, b = st.columns(2)
        a.selectbox("Colaborador (aba Usuarios_Areas)", USER_LABELS, key="f_user")
        b.selectbox("Ferramenta de IA", list(TOOLS), key="f_tool",
                    format_func=lambda t: f"{t} — {TOOLS[t]['status']}")
        a2, b2 = st.columns([2, 1])
        a2.selectbox("Finalidade declarada", PURPOSES, key="f_purpose")
        b2.number_input("Qtd. de arquivos/itens", min_value=1, max_value=500, key="f_qty")
        st.text_area("Conteúdo do prompt ou descrição do arquivo", key="f_text", height=150,
                     placeholder="Cole aqui o que seria enviado para a IA…")
        if ss.get("form_error"):
            st.error("Escreva o conteúdo que seria enviado para a IA.")
        st.button("Analisar antes do envio", type="primary", on_click=on_analyze, width="stretch")
        u = USER_BY_LABEL[ss.f_user]
        st.caption(f"Identidade (SSO simulado): **{u['ID Usuário']}** · {u['Cargo']} · {u['Área']} · "
                   f"{u['Modelo trabalho']} · gestor: {manager_of(u['Área'])}. O texto não sai desta máquina.")

    with right:
        st.subheader("Decisão preventiva")
        last = ss.last
        if not last:
            st.markdown(
                f'<div class="iris">{avatar_svg("ola", 118)}<div class="bubble"><div class="who">{AGENT_NAME} · agente educativo</div>'
                '<h4>Oi! Eu fico entre você e a IA.</h4><p>Escolha um cenário ou escreva um pedido. Eu verifico antes do envio '
                'e, se algo não puder seguir, mostro o caminho seguro para você entregar do mesmo jeito.</p></div></div>',
                unsafe_allow_html=True)
        else:
            decision_card(last)
            iris_block(last["guide"])
            g = last["guide"]
            bcols = st.columns(2)
            if last["dec"].action in ("BLOCK", "REVIEW") and last["dec"].suggested_tool and last["dec"].enforced \
                    and not last["insp"].has_secret:
                bcols[0].button(f"↪ Reenviar via {last['dec'].suggested_tool}", on_click=on_resend, width="stretch")
            if g.safe_prompt and g.safe_prompt != last["text"] and last["dec"].action != "MASK":
                bcols[1].button("✎ Usar a versão segura do pedido", on_click=on_use_safe_prompt, width="stretch")
            if g.safe_prompt and last["dec"].action != "MASK" and g.safe_prompt != last["text"]:
                with st.expander("Versão segura sugerida pela Íris"):
                    st.code(g.safe_prompt, language=None, wrap_lines=True)
            with st.expander("Evidência de auditoria deste evento"):
                r = last["rec"]
                st.markdown(
                    f"- **ID:** `{r.id_evento}` · **aberto em:** {r.aberto_em} · **fechado em:** {r.fechado_em or 'pendente (caso aberto)'}\n"
                    f"- **Política:** `{r.versao_politica}` · **regra:** {r.regra} · **decisão aplicada:** {'sim' if r.aplicada else 'não (monitor)'}\n"
                    f"- **SHA-256 do conteúdo:** `{r.hash_conteudo[:32]}…` ({r.tamanho_conteudo} caracteres — o texto não é gravado)\n"
                    f"- **Encadeamento:** registro `{r.hash_registro[:16]}…` aponta para `{r.hash_anterior[:16]}…`")
                st.markdown("**Sinais detectados:**")
                for f in last["insp"].findings:
                    st.markdown(f"- {f.name} ({f.sensitivity}) — {f.evidence} · método: {f.method}")

# ---------------------------------------------------------------------------
# TAB 2 — ÍRIS
# ---------------------------------------------------------------------------
with tab_iris:
    top_l, top_r = st.columns([1, 3])
    with top_l:
        st.markdown(avatar_svg("ola", 170), unsafe_allow_html=True)
    with top_r:
        st.markdown(f'<div class="eyebrow">Agente educativo</div>', unsafe_allow_html=True)
        st.markdown(f"## {AGENT_NAME}: use as IAs da Stark para entregar mais — com segurança")
        st.markdown("Feita para quem está no **administrativo**: Financeiro, Pessoas, Jurídico, Comercial, Atendimento, "
                    "Operações, Risco & Compliance e Marketing. A Íris não recebe dados sensíveis: tudo o que você "
                    "escreve passa antes pelo gateway.")
        st.caption("Conversa com Claude (" + ("ativa" if llm_available() else
                   "offline — defina ANTHROPIC_API_KEY para ativar; a base de conhecimento local responde enquanto isso") + ").")

    area_list = list(PLAYBOOKS)
    me = USER_BY_LABEL[ss.f_user]
    default_area = me["Área"] if me["Área"] in area_list else "Financeiro"
    area = st.selectbox("Sua área", area_list, index=area_list.index(default_area), key="iris_area")

    t_guide, t_chat, t_recipe, t_quiz = st.tabs(["📘 Guia da área", "💬 Conversar", "🧪 Receita de prompt", "⚡ Quiz relâmpago"])

    with t_guide:
        st.markdown(f"#### Onde a IA acelera o time de {area}")
        for uc in PLAYBOOKS[area]:
            with st.container(border=True):
                c_a, c_b = st.columns([3, 1.3])
                c_a.markdown(f"**{uc.tarefa}**  \n<span style='color:#5C6A84'>Resultado: {uc.ganho}</span>",
                             unsafe_allow_html=True)
                c_b.markdown(f"<span class='pill ok'>{esc(uc.ferramenta)}</span><span class='pill'>{esc(uc.finalidade)}</span>",
                             unsafe_allow_html=True)
                st.code(uc.prompt, language=None, wrap_lines=True)
                st.markdown(f"<span class='pill crit'>NUNCA INCLUA</span> {esc(uc.nunca)}", unsafe_allow_html=True)
        st.info("Os prompts usam [MARCADORES] no lugar de dados reais. Preencha os dados no documento final, fora da IA.", icon="💡")

    with t_chat:
        for m in ss.chat:
            with st.chat_message(m["role"], avatar="🧑‍💼" if m["role"] == "user" else "🛡️"):
                st.markdown(m["content"])
        if not ss.chat:
            st.caption("Experimente: “Qual ferramenta uso para resumir um contrato?” · “Como anonimizar uma planilha?” · "
                       "“Posso usar IA pública?” · ou cole um texto com CPF para ver o filtro agir.")
        q = st.chat_input(f"Pergunte para a {AGENT_NAME}…")
        if q:
            ctx = Context(user_id=me["ID Usuário"], area=area, cargo=me["Cargo"], manager=manager_of(area))
            turn = chat(q, ctx, ss.chat_api)
            shown_q = turn.sanitized or "🔒 [mensagem retida pelo gateway: continha credencial]"
            ss.chat.append({"role": "user", "content": shown_q})
            ss.chat.append({"role": "assistant", "content": turn.reply})
            if turn.sanitized:
                ss.chat_api += [{"role": "user", "content": turn.sanitized}, {"role": "assistant", "content": turn.reply}]
            st.rerun()
        if ss.chat and st.button("Limpar conversa"):
            ss.chat, ss.chat_api = [], []
            st.rerun()

    with t_recipe:
        st.markdown("#### As 6 partes de um prompt que traz resultado")
        cols = st.columns(3)
        for i, (part, desc) in enumerate(PROMPT_RECIPE):
            cols[i % 3].markdown(stat(f"{i + 1}", part, desc, "gold"), unsafe_allow_html=True)
            if i == 2:
                cols = st.columns(3)
        st.write("")
        bad, good = st.columns(2)
        with bad:
            st.markdown("**❌ Antes**")
            st.code("Faz um resumo desse contrato do cliente Acme, CNPJ 12.345.678/0001-90, "
                    "valor R$ 2,3 mi, e me diz se tá ok.", language=None, wrap_lines=True)
            st.caption("Dados do cliente, valor real, pedido vago, sem formato. Seria bloqueado na IA pública.")
        with good:
            st.markdown("**✅ Depois**")
            st.code("Você é advogado(a) corporativo(a). Resuma o contrato anexo de [CLIENTE]: partes, objeto, prazo, "
                    "multas, rescisão e cláusulas fora do padrão. Classifique cada risco em alto/médio/baixo. "
                    "Formato: tabela + 3 bullets de recomendação.", language=None, wrap_lines=True)
            st.caption("No Assistente Jurídico: papel, contexto sem dados, tarefa, formato e critério.")

    with t_quiz:
        st.markdown("#### 5 perguntas, 1 minuto")
        score = 0
        answered = 0
        for i, (qtxt, opts, correct, why) in enumerate(QUIZ):
            ans = st.radio(f"**{i + 1}. {qtxt}**", opts, index=None, key=f"quiz_{i}")
            if ans is not None:
                answered += 1
                if opts.index(ans) == correct:
                    score += 1
                    st.success(f"Isso! {why}", icon="✅")
                else:
                    st.error(f"Quase. {why}", icon="↩️")
        if answered == len(QUIZ):
            mood = "aprovado" if score >= 4 else "atencao"
            st.markdown(f'<div class="iris">{avatar_svg(mood, 100)}<div class="bubble"><div class="who">{AGENT_NAME}</div>'
                        f'<h4>Você fez {score}/{len(QUIZ)}</h4><p>'
                        + ("Mandou bem! Você está pronto(a) para usar IA com segurança." if score >= 4
                           else "Vale revisar o Guia da área — e pode contar comigo no dia a dia.")
                        + "</p></div></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# TAB 3 — INSIGHTS
# ---------------------------------------------------------------------------
with tab_ins:
    k = analytics.kpis(base)
    p0, p1 = k["periodo"]
    st.markdown(f'<div class="eyebrow">Base de Dados - Starkbank.xlsx · {p0:%d/%m} a {p1:%d/%m/%Y}</div>', unsafe_allow_html=True)
    st.markdown("## O que a liderança precisa saber")
    cols = st.columns(5)
    tiles = [
        (k["eventos"], "eventos de uso de IA", f"{k['usuarios']} usuários · {k['areas']} áreas", ""),
        (k["alertas"], "alertas alto/crítico", f"{k['alertas_pct']:.1%} dos eventos", "gold"),
        (k["criticos"], "eventos críticos", f"{k['criticos_pct']:.1%} vs meta < 1%", "crit"),
        (k["pendentes"], "alertas pendentes", f"{k['pendentes_pct']:.1%} abertos ou em análise", "crit"),
        (k["manuais"], "registros manuais", f"{k['manuais_pct']:.1%} — evidência mais fraca", "gold"),
    ]
    for c, t in zip(cols, tiles):
        c.markdown(stat(*t), unsafe_allow_html=True)

    st.write("")
    st.markdown("### Se o gateway estivesse ativo desde junho")
    rcols = st.columns(3)
    rcols[0].markdown(stat(f"{rs['criticos_bloqueados']}/{rs['criticos']}", "críticos bloqueados antes do envio",
                           "R01, R02 e R03 → bloqueio", "ok"), unsafe_allow_html=True)
    rcols[1].markdown(stat(f"{rs['altos_retidos']}/{rs['altos']}", "altos retidos", "aprovação, máscara ou revisão", "ok"),
                      unsafe_allow_html=True)
    rcols[2].markdown(stat(rs["liberados_sem_atrito"], "liberados sem atrito", "público, interno, confidencial aprovado", "gold"),
                      unsafe_allow_html=True)
    short = {"BLOCK": "Bloqueado", "REVIEW": "Revisão", "APPROVAL": "Aprovação", "MASK": "Mascarado",
             "ALLOW_REGISTER": "Com registro", "ALLOW": "Permitido"}
    ct = (pd.crosstab(rp["Risco original"], rp["Decisão do gateway"])
          .reindex(index=["Crítico", "Alto", "Médio", "Baixo"], columns=list(short), fill_value=0).rename(columns=short))
    ct.index.name = "Risco original → decisão do gateway"
    st.dataframe(ct, width="stretch")

    st.write("")
    g1, g2 = st.columns(2, gap="large")
    with g1:
        st.markdown("**1 · Por que os alertas acontecem?** — Pareto das causas imediatas")
        pa = analytics.pareto(base).iloc[::-1]
        fig = go.Figure(go.Bar(x=pa["Alertas"], y=pa["Causa"], orientation="h", marker_color=GOLD,
                               text=[f"{a} · {p:.0%}" for a, p in zip(pa["Alertas"], pa["%"])], textposition="outside",
                               hovertemplate="%{y}: %{x} alertas<extra></extra>", cliponaxis=False))
        fig.update_traces(marker_line_width=0)
        fig.update_xaxes(range=[0, pa["Alertas"].max() * 1.25])
        st.plotly_chart(fig_style(fig, 260), width="stretch", config=PLOT_CFG)
        st.caption("Finalidade incompatível lidera (30%): aprovar a ferramenta não basta — o gateway checa a finalidade.")
    with g2:
        st.markdown("**2 · Onde está o risco?** — % de eventos alto/crítico por ferramenta")
        rt = analytics.risk_by_tool(base).iloc[::-1]
        is_pub = [TOOLS.get(t, {}).get("classe") in ("publica", "publica_restrita") for t in rt.index]
        fig = go.Figure(go.Bar(x=rt["% alto/crítico"], y=rt.index, orientation="h",
                               marker_color=[GOLD if p else INK for p in is_pub],
                               text=[f"{v:.0%}" + (" · pública" if p else "") for v, p in zip(rt["% alto/crítico"], is_pub)],
                               textposition="outside", cliponaxis=False,
                               customdata=rt["Total"], hovertemplate="%{y}: %{x:.0%} de %{customdata} eventos<extra></extra>"))
        fig.update_xaxes(tickformat=".0%", range=[0, 1])
        st.plotly_chart(fig_style(fig, 260), width="stretch", config=PLOT_CFG)
        st.caption("Navy = corporativa · dourado = pública. IA Pública A e B passam de 50% — e as corporativas também geram risco.")

    g3, g4 = st.columns(2, gap="large")
    with g3:
        st.markdown("**3 · O risco está caindo?** — % de eventos críticos por mês")
        mc = analytics.monthly_critical(base)
        meses = {"06": "Jun", "07": "Jul", "08": "Ago", "09": "Set (parcial)"}
        mc["Mês"] = [meses.get(m[-2:], m) for m in mc["Mês"]]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=mc["Mês"], y=mc["% crítico"], mode="lines+markers+text", line=dict(color=INK, width=2),
                                 marker=dict(size=9, color=INK, line=dict(color="white", width=2)),
                                 text=[f"{v:.1%}" for v in mc["% crítico"]], textposition="top center",
                                 customdata=mc["Eventos"], hovertemplate="%{x}: %{y:.1%} de %{customdata} eventos<extra></extra>"))
        fig.add_hline(y=0.01, line=dict(color=CRIT, dash="dash", width=1.5), annotation_text="meta < 1%",
                      annotation_position="bottom right", annotation_font_color=CRIT)
        fig.update_yaxes(tickformat=".0%", range=[0, max(mc["% crítico"]) * 1.35])
        fig.update_xaxes(type="category")
        st.plotly_chart(fig_style(fig, 260), width="stretch", config=PLOT_CFG)
        st.caption("Sem tendência sustentada de queda. Setembro é parcial (até 08/09).")
    with g4:
        st.markdown("**4 · Quais áreas concentram risco?** — % de eventos alto/crítico por área")
        ra = analytics.risk_by_area(base).iloc[::-1]
        fig = go.Figure(go.Bar(x=ra["% alto/crítico"], y=ra.index, orientation="h", marker_color=INK,
                               text=[f"{v:.0%} · {n}" for v, n in zip(ra["% alto/crítico"], ra["Alto"] + ra["Crítico"])],
                               textposition="outside", cliponaxis=False, customdata=ra["Total"],
                               hovertemplate="%{y}: %{x:.0%} de %{customdata} eventos<extra></extra>"))
        fig.update_xaxes(tickformat=".0%", range=[0, ra["% alto/crítico"].max() * 1.3])
        st.plotly_chart(fig_style(fig, 300), width="stretch", config=PLOT_CFG)
        st.caption("Rótulo: % e nº de eventos alto/crítico. Segurança tem a maior taxa; Financeiro, o maior volume de alertas.")

    st.markdown("**5 · Que dado está exposto, e por quem?** — alertas por tipo de informação × área")
    hm = analytics.info_heatmap(base).T
    hm = hm.loc[hm.sum(axis=1).sort_values(ascending=False).index, hm.sum().sort_values(ascending=False).index]
    fig = go.Figure(go.Heatmap(z=hm.values, x=hm.columns, y=hm.index, colorscale=[[0, "#FBF7EE"], [1, "#8A6B28"]],
                               xgap=2, ygap=2, showscale=False,
                               text=[[str(v) if v else "" for v in row] for row in hm.values], texttemplate="%{text}",
                               hovertemplate="%{y} · %{x}: %{z} alertas<extra></extra>"))
    fig.update_xaxes(side="top", gridcolor="rgba(0,0,0,0)")
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)", autorange="reversed")
    st.plotly_chart(fig_style(fig, 470), width="stretch", config=PLOT_CFG)

    st.markdown("**6 · Indicadores atuais × meta** (aba Indicadores_Atuais)")
    st.dataframe(analytics.indicators(base), width="stretch", hide_index=True)

    st.markdown("**7 · Fila de alertas**")
    al = base.alertas.copy()
    if ss.get("role") == "Segurança":
        st.caption("🔓 Perfil Segurança: IDs de usuário visíveis. Este acesso seria registrado na trilha de auditoria.")
        st.dataframe(al[["ID Alerta", "Data/hora", "ID Usuário", "Área", "Ferramenta", "Informação", "Risco", "Regra", "Status",
                         "Responsável"]], width="stretch", hide_index=True, height=280)
    else:
        st.caption("🔒 Perfil Liderança: só dados agregados por área (privacidade por padrão). Troque para Segurança no topo.")
        agg = pd.crosstab(al["Área"], al["Status"])
        agg["Total"] = agg.sum(axis=1)
        st.dataframe(agg.sort_values("Total", ascending=False), width="stretch")

# ---------------------------------------------------------------------------
# TAB 4 — VALIDAÇÃO & AUDITORIA
# ---------------------------------------------------------------------------
with tab_val:
    st.markdown("## Evidências: o protótipo faz o que promete?")
    st.markdown("Bateria **base** (CV01–CV15, aba Casos_Validacao) e bateria **adversarial** (CV16–CV21: casos feitos "
                "para enganar o detector). A pergunta é: quando erra, erra para o lado seguro?")
    allr = suite_b + suite_a
    v = st.columns(4)
    v[0].markdown(stat(f"{sum(r.status == 'Correto' for r in allr)}/{len(allr)}", "decisões iguais às esperadas", "", "ok"),
                  unsafe_allow_html=True)
    crit_cases = [r for r in allr if r.esperado == "BLOCK"]
    v[1].markdown(stat(f"{sum(r.obtido == 'BLOCK' for r in crit_cases)}/{len(crit_cases)}", "casos críticos contidos",
                       "métrica principal da Hipótese V10", "ok"), unsafe_allow_html=True)
    v[2].markdown(stat(sum(r.status == "Desvio seguro" for r in allr), "desvios seguros", "mais restritivo que o esperado", "gold"),
                  unsafe_allow_html=True)
    v[3].markdown(stat(sum(r.status == "EXPOSIÇÃO" for r in allr), "exposições", "liberado sem o controle esperado",
                       "ok" if not exposures else "crit"), unsafe_allow_html=True)
    df = pd.DataFrame([r.__dict__ for r in allr]).rename(columns={
        "caso": "Caso", "area": "Área", "ferramenta": "Ferramenta", "o_que_testa": "O que testa", "esperado": "Esperado",
        "obtido": "Obtido", "regra": "Regra", "status": "Status"})
    st.dataframe(df, width="stretch", hide_index=True, height=420)

    st.markdown("### Trilha de auditoria")
    st.markdown("Cada decisão grava: quem, área, cargo, ferramenta, finalidade, tipo de dado, regra, versão da política, "
                "**hash SHA-256 do conteúdo** e horários de abertura/fechamento. O texto nunca é gravado. "
                "Cada registro carrega o hash do anterior — qualquer adulteração quebra a cadeia.")
    logs = audit.read_all()
    ok, n = audit.verify_chain()
    a1, a2, a3 = st.columns([1, 1, 2])
    a1.markdown(stat(n, "registros na trilha", "arquivo runtime/audit_log.jsonl"), unsafe_allow_html=True)
    a2.markdown(stat("Íntegra" if ok else "Violada", "cadeia de hashes", "verificada agora", "ok" if ok else "crit"),
                unsafe_allow_html=True)
    if logs:
        ldf = pd.DataFrame(logs)
        show = ["id_evento", "aberto_em", "fechado_em", "id_usuario", "area", "ferramenta", "finalidade", "sensibilidade",
                "decisao", "aplicada", "regra", "versao_politica", "hash_conteudo"]
        if ss.get("role") != "Segurança":
            ldf["id_usuario"] = "oculto (Liderança)"
        st.dataframe(ldf[show].iloc[::-1], width="stretch", hide_index=True, height=260)
        d1, d2 = st.columns([1, 4])
        d1.download_button("Exportar CSV", ldf[show].to_csv(index=False).encode("utf-8-sig"), "auditoria_gateway.csv",
                           "text/csv")
        if d2.button("Limpar trilha (demonstração)"):
            audit.clear()
            st.rerun()
    else:
        st.info("Nenhum registro ainda. Faça uma simulação na aba Gateway.")

# ---------------------------------------------------------------------------
# TAB 5 — COMO FUNCIONA
# ---------------------------------------------------------------------------
with tab_how:
    st.markdown("## Arquitetura funcional")
    st.markdown("O conteúdo só chega à IA depois que identidade, contexto e política são avaliados.")
    st.markdown("""
<div class="flow">
 <div class="node"><span class="n">1</span><h4>Identidade e contexto</h4><p>SSO: usuário, área, cargo, gestor, ferramenta e finalidade declarada.</p></div>
 <div class="node"><span class="n">2</span><h4>Inspeção (IA + padrões)</h4><p>Credenciais, CPF validado, cartão (Luhn), base64, vocabulário PT/EN, volume.</p></div>
 <div class="node dark"><span class="n">3</span><h4>Motor de política</h4><p>Regras R01–R14 da base, em ordem fixa, reproduzível e versionada.</p></div>
 <div class="node"><span class="n">4</span><h4>Ação</h4><p>Bloquear, revisar, pedir aprovação, mascarar, permitir com registro ou permitir.</p></div>
 <div class="node"><span class="n">5</span><h4>Íris + auditoria</h4><p>Orientação na hora; registro com hash, política e SLA.</p></div>
</div>""", unsafe_allow_html=True)

    st.write("")
    r1, r2, r3 = st.columns(3)
    r1.markdown(stat("IA", "analisa e educa", "classifica conteúdo, detecta entidades, explica o risco, ensina", "gold"),
                unsafe_allow_html=True)
    r2.markdown(stat("Regras", "decidem", "bloqueio determinístico — nunca depende só de um modelo"), unsafe_allow_html=True)
    r3.markdown(stat("Pessoas", "aprovam exceções", "gestor, Segurança, DPO e Compliance", "ok"), unsafe_allow_html=True)

    st.markdown(f"### Matriz de regras · `{POLICY_VERSION}`")
    rules = [
        ("crit", "1 · Segredo ou credencial — R03", "Bloqueio em qualquer ferramenta, inclusive nas aprovadas.", "SE segredo → BLOQUEAR + avisar Segurança"),
        ("crit", "2 · Restrito em IA pública — R01, R02, R04, R05, R06", "Confidencial ou crítico não sai do ambiente controlado.", "SE restrito E IA pública → BLOQUEAR"),
        ("", "3 · Ferramenta ou conteúdo desconhecido — R13, R14", "Falha segura: o sistema não inventa classificação.", "SE fora do catálogo OU sem classificação → REVISÃO HUMANA"),
        ("", "4 · Volume elevado — R11", "Lote de 10+ itens restritos.", "SE volume ≥ 10 → PEDIR APROVAÇÃO DO GESTOR"),
        ("mask", "5 · Dado pessoal em ferramenta aprovada — R07 + LGPD", "Minimização: identificadores saem antes do envio.", "SE dado pessoal E aprovada → MASCARAR"),
        ("", "6 · Finalidade — R10", "Crítico em ambiente aprovado ou finalidade fora do aprovado para a ferramenta.", "SE crítico OU finalidade incompatível → APROVAÇÃO / REVISÃO"),
        ("ok", "7 · Confidencial em ferramenta aprovada — R07", "Segue com rastreabilidade.", "→ PERMITIR E REGISTRAR"),
        ("ok", "8 · Público, interno ou anonimizado — R08, R09", "Uso livre, com dica da melhor ferramenta.", "→ PERMITIR"),
    ]
    rc = st.columns(2)
    for i, (cls, t, d, code) in enumerate(rules):
        rc[i % 2].markdown(f'<div class="rule {cls}"><b>{esc(t)}</b><div style="color:#5C6A84;font-size:14px">{esc(d)}</div>'
                           f'<code>{esc(code)}</code></div>', unsafe_allow_html=True)

    st.markdown("### Finalidades aprovadas por ferramenta")
    tp = pd.DataFrame([(t, TOOLS[t]["status"], ", ".join(sorted(TOOL_PURPOSES.get(t, []))) or "—") for t in TOOLS],
                      columns=["Ferramenta", "Status", "Finalidades aprovadas"])
    st.dataframe(tp, width="stretch", hide_index=True)

    st.markdown("### Lacunas do diagnóstico que o protótipo fecha")
    st.dataframe(pd.DataFrame([
        ("Sem vínculo ao artefato original", "Hash SHA-256 do conteúdo em cada evento"),
        ("Sem versão da política", f"Cada decisão carrega `{POLICY_VERSION}`"),
        ("Alertas sem data de fechamento (SLA não recalculável)", "aberto_em / fechado_em em cada registro"),
        ("148 registros manuais (22,8%)", "Captura automática no ponto de uso"),
        ("2 ferramentas públicas sem log", "Gateway registra antes da ferramenta — com ou sem log do provedor"),
        ("Finalidade incompatível lidera os alertas", "Política por finalidade + Íris indica a ferramenta certa"),
        ("Detecção sem prevenção (113 alertas pendentes)", "Bloqueio antes do envio: o alerta nem chega a nascer"),
    ], columns=["Lacuna (Diagnóstico)", "Como o protótipo responde"]), width="stretch", hide_index=True)

    st.markdown("### Caminho de implantação")
    road = st.columns(4)
    for c, (n, t, d) in zip(road, [
        ("0–30 dias", "Modo monitor", "Medir 2–4 semanas sem bloquear para formar a linha de base."),
        ("0–30 dias", "Bloquear o crítico", "Secrets e dado restrito em IA pública — a métrica de 100%."),
        ("31–60 dias", "Canal único + logs", "Extensão de navegador/proxy com SSO; ID único de evento."),
        ("61–90 dias", "Escalar com a Íris", "Trilhas por área, quiz, indicadores de reincidência."),
    ]):
        c.markdown(stat(t, n, d, "gold"), unsafe_allow_html=True)

    st.markdown("### Limites honestos")
    st.markdown("- Detecção por padrões e vocabulário: no produto, somar classificador semântico em ambiente corporativo e NER (ex.: Presidio).\n"
                "- Bloqueio de USB/HDMI e anti-captura dependem de gestão do endpoint (MDM/EDR/DLP), não do navegador.\n"
                "- A base não tem hierarquia/gestor: o protótipo usa “Gestor(a) da área” até integrar IAM/RH.\n"
                "- Dados 100% fictícios; alertas não comprovam fraude nem vazamento.")

st.markdown(f'<div class="foot"><span>Stark AI Gateway · protótipo ITA Challenge Sprint · política {POLICY_VERSION}</span>'
            '<span>Dados fictícios — não use dados reais</span></div>', unsafe_allow_html=True)
