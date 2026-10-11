"""CSS do protótipo — herda a identidade do mockup stark-ai-gateway-v2.html."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Albert+Sans:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');
:root{
  --ink:#1B2B4C; --muted:#5C6A84; --line:#E5E3DA; --bg:#FAFAF7; --surface:#FFFFFF;
  --gold:#C19A4F; --goldink:#8A6B28; --goldsoft:#F6F0E2; --signal:#D8B573;
  --crit:#A8434B; --critsoft:#F7E8E9; --ok:#2F7D5B; --oksoft:#E4F2EB; --mask:#4B5E8E; --masksoft:#E7EBF5;
  --warn:#8A6B28; --warnsoft:#F6F0E2; --mon:#5C6A84; --monsoft:#ECEEF3;
  --serif:"Playfair Display",Georgia,serif; --sans:"Albert Sans","Segoe UI",system-ui,sans-serif;
}
html, body, [class*="css"], .stMarkdown, .stTextInput, .stSelectbox, button, textarea { font-family: var(--sans) !important; }
.block-container{padding-top:1.2rem; max-width:1320px}
h1,h2,h3{font-family:var(--serif) !important; color:var(--ink); letter-spacing:-.01em}
[data-testid="stHeader"]{background:transparent}

/* barra superior */
.topband{background:var(--ink); color:#F5F2EA; border-bottom:3px solid var(--gold); border-radius:8px;
  padding:14px 22px; display:flex; flex-wrap:wrap; gap:12px 24px; align-items:center; justify-content:space-between; margin-bottom:6px}
.topband .brand{display:flex; gap:14px; align-items:center}
.topband b{font-family:var(--serif); font-size:22px; letter-spacing:.2em; display:block; line-height:1.1}
.topband small{display:block; font-size:11px; letter-spacing:.24em; color:#9FACC6}
.topband .badge{font-size:12px; color:#C9D2E4; border:1px solid rgba(255,255,255,.18); border-radius:999px; padding:5px 12px}

/* hero */
.hero{background:var(--ink); color:#F5F2EA; border-radius:8px; padding:28px 30px; height:100%}
.hero .eyebrow{color:var(--signal)}
.hero h1{color:#F5F2EA !important; font-size:clamp(26px,3.2vw,40px); line-height:1.1; margin:.2em 0 .3em}
.hero h1 em{font-style:normal; color:var(--signal)}
.hero p{color:#C9D2E4; font-size:16px; margin:0}
.eyebrow{font-size:12px; font-weight:700; letter-spacing:.16em; text-transform:uppercase; color:var(--goldink)}
.stat{background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:16px 18px; height:100%;
  box-shadow:0 1px 2px rgba(27,43,76,.05),0 10px 28px rgba(27,43,76,.06)}
.stat .v{font-family:var(--serif); font-size:34px; font-weight:700; line-height:1.15; color:var(--ink)}
.stat .v.gold{color:var(--goldink)} .stat .v.ok{color:var(--ok)} .stat .v.crit{color:var(--crit)}
.stat .l{font-size:13.5px; color:var(--ink); font-weight:600}
.stat .d{font-size:12.5px; color:var(--muted)}

/* cartão de decisão */
.dcard{border:1px solid var(--line); border-radius:8px; overflow:hidden; background:var(--surface);
  box-shadow:0 1px 2px rgba(27,43,76,.05),0 10px 28px rgba(27,43,76,.07)}
.dtop{display:flex; gap:16px; align-items:center; padding:18px 22px; background:var(--ink); color:#F5F2EA}
.dicon{width:54px; height:54px; border-radius:50%; display:grid; place-items:center; font-size:26px; font-weight:700; flex:none}
.tone-crit .dicon{background:var(--crit); color:#fff} .tone-ok .dicon{background:var(--ok); color:#fff}
.tone-mask .dicon{background:var(--mask); color:#fff} .tone-warn .dicon{background:var(--signal); color:#1B2B4C}
.tone-mon .dicon{background:var(--mon); color:#fff}
.dtitle{font-family:var(--serif); font-size:26px; font-weight:700; line-height:1.1}
.tone-crit .dtitle{color:#F2B8BD} .tone-ok .dtitle{color:#9FE0BE} .tone-mask .dtitle{color:#C3CFF3}
.tone-warn .dtitle{color:var(--signal)} .tone-mon .dtitle{color:#C9D2E4}
.dsub{font-size:14px; color:#9FACC6}
.dbody{padding:16px 22px 18px}
.pill{display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:700; letter-spacing:.03em;
  margin:0 6px 6px 0; background:var(--monsoft); color:var(--ink)}
.pill.crit{background:var(--critsoft); color:var(--crit)} .pill.ok{background:var(--oksoft); color:var(--ok)}
.pill.warn{background:var(--warnsoft); color:var(--warn)} .pill.mask{background:var(--masksoft); color:var(--mask)}
.tag{display:inline-block; font-size:12.5px; font-weight:600; padding:4px 10px; border-radius:3px; margin:0 6px 6px 0;
  background:var(--goldsoft); color:var(--goldink)}
.sect{font-size:11.5px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); font-weight:700; margin:14px 0 6px}
.payload{padding:12px 14px; border-radius:6px; background:#14203B; color:#DDE3F0; white-space:pre-wrap; word-break:break-word;
  font:12.5px/1.55 ui-monospace,Consolas,monospace; max-height:180px; overflow:auto}
.chip{display:inline-block; font-size:12.5px; padding:4px 11px; border-radius:999px; margin:0 6px 6px 0;
  background:var(--goldsoft); color:var(--goldink); border:1px solid #E6D6B0; font-weight:600}

/* Íris */
.iris{display:flex; gap:16px; align-items:flex-start; margin-top:14px}
.iris .bubble{position:relative; flex:1; background:var(--goldsoft); border:1px solid #E6D6B0; border-radius:12px; padding:14px 16px; color:var(--ink)}
.iris .bubble:before{content:""; position:absolute; left:-9px; top:26px; width:16px; height:16px; background:var(--goldsoft);
  border-left:1px solid #E6D6B0; border-bottom:1px solid #E6D6B0; transform:rotate(45deg)}
.iris .who{font-size:11.5px; letter-spacing:.14em; text-transform:uppercase; color:var(--goldink); font-weight:700}
.iris h4{font-family:var(--serif); font-size:20px; margin:2px 0 6px; color:var(--ink)}
.iris p{margin:0 0 6px; font-size:15px}
.iris ol{margin:6px 0 0 0; padding-left:20px; font-size:14.5px}
.iris-avatar{flex:none; filter:drop-shadow(0 6px 14px rgba(27,43,76,.25)); animation:float 4s ease-in-out infinite}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
@media (prefers-reduced-motion:reduce){.iris-avatar{animation:none}}
.lesson{border-left:4px solid var(--gold); background:var(--surface); border-radius:0 6px 6px 0; padding:10px 14px; margin-top:10px; font-size:14px}
.lesson b{display:block; font-size:11.5px; letter-spacing:.12em; text-transform:uppercase; color:var(--goldink)}

/* fluxo */
.flow{display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:14px}
.node{border:1px solid var(--line); border-radius:8px; padding:16px; background:var(--surface); min-height:150px}
.node.dark{background:var(--ink); color:#F5F2EA; border-color:var(--ink)}
.node .n{display:inline-grid; place-items:center; width:26px; height:26px; border-radius:50%; background:var(--goldsoft); color:var(--goldink); font-weight:700; font-size:13px}
.node.dark .n{background:var(--signal); color:var(--ink)}
.node h4{font-family:var(--serif); margin:8px 0 4px; font-size:18px}
.node p{font-size:13.5px; color:var(--muted); margin:0}
.node.dark p{color:#9FACC6}
.rule{border:1px solid var(--line); border-left:5px solid var(--gold); border-radius:6px; padding:12px 16px; background:var(--surface); margin-bottom:10px}
.rule.crit{border-left-color:var(--crit)} .rule.ok{border-left-color:var(--ok)} .rule.mask{border-left-color:var(--mask)}
.rule code{font-size:12.5px}
@media (max-width:900px){ .flow{grid-template-columns:1fr} }

.stTabs [data-baseweb="tab-list"]{gap:4px; border-bottom:1px solid var(--line)}
.stTabs [data-baseweb="tab"]{font-weight:600; font-size:15px; padding:10px 14px}
.stTabs [aria-selected="true"]{color:var(--ink)}
.stTabs [data-baseweb="tab-highlight"]{background:var(--gold)}
.foot{margin-top:28px; padding:14px 18px; border-radius:8px; background:var(--ink); color:#9FACC6; font-size:13px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px}
</style>
"""
