"""Avatar da Íris em SVG, com expressão por estado da decisão."""
from __future__ import annotations

MOODS = {
    # anel, olhos, boca, sobrancelha, extra
    "aprovado": {"ring": "#2F7D5B", "label": "Tudo certo"},
    "alerta": {"ring": "#A8434B", "label": "Bloqueio preventivo"},
    "atencao": {"ring": "#C19A4F", "label": "Atenção"},
    "mascara": {"ring": "#4B5E8E", "label": "Dados protegidos"},
    "pensando": {"ring": "#5C6A84", "label": "Observando"},
    "ola": {"ring": "#C19A4F", "label": "Olá!"},
}


def avatar_svg(mood: str = "ola", size: int = 132) -> str:
    m = MOODS.get(mood, MOODS["ola"])
    ring = m["ring"]

    # olhos
    if mood == "alerta":
        eyes = ('<rect x="47" y="60" width="16" height="5" rx="2.5" fill="#F5E6C4"/>'
                '<rect x="77" y="60" width="16" height="5" rx="2.5" fill="#F5E6C4"/>')
    elif mood == "aprovado" or mood == "ola":
        eyes = ('<path d="M47 64 q8 -9 16 0" stroke="#F5E6C4" stroke-width="4" fill="none" stroke-linecap="round"/>'
                '<path d="M77 64 q8 -9 16 0" stroke="#F5E6C4" stroke-width="4" fill="none" stroke-linecap="round"/>')
    else:
        eyes = ('<circle cx="55" cy="62" r="6" fill="#F5E6C4"><animate attributeName="r" values="6;6;0.8;6" '
                'keyTimes="0;0.92;0.96;1" dur="4s" repeatCount="indefinite"/></circle>'
                '<circle cx="85" cy="62" r="6" fill="#F5E6C4"><animate attributeName="r" values="6;6;0.8;6" '
                'keyTimes="0;0.92;0.96;1" dur="4s" repeatCount="indefinite"/></circle>')

    # boca / extras
    if mood == "alerta":
        mouth = '<path d="M58 88 h24" stroke="#F5E6C4" stroke-width="4" stroke-linecap="round"/>'
        brows = ('<path d="M45 50 l18 5" stroke="#D8B573" stroke-width="3.5" stroke-linecap="round"/>'
                 '<path d="M95 50 l-18 5" stroke="#D8B573" stroke-width="3.5" stroke-linecap="round"/>')
    elif mood == "atencao":
        mouth = '<path d="M60 89 q10 -5 20 0" stroke="#F5E6C4" stroke-width="4" fill="none" stroke-linecap="round"/>'
        brows = '<path d="M77 47 q8 -6 16 0" stroke="#D8B573" stroke-width="3.5" fill="none" stroke-linecap="round"/>'
    elif mood == "mascara":
        mouth = ('<rect x="40" y="78" width="60" height="20" rx="8" fill="#4B5E8E"/>'
                 '<path d="M44 84 h52 M44 90 h52" stroke="#A5B6EA" stroke-width="1.5"/>')
        brows = ""
    elif mood == "pensando":
        mouth = ('<circle cx="62" cy="88" r="2.6" fill="#F5E6C4"/><circle cx="70" cy="88" r="2.6" fill="#F5E6C4"/>'
                 '<circle cx="78" cy="88" r="2.6" fill="#F5E6C4"/>')
        brows = ""
    else:
        mouth = '<path d="M56 84 q14 13 28 0" stroke="#F5E6C4" stroke-width="4" fill="none" stroke-linecap="round"/>'
        brows = ""

    badge = {
        "alerta": '<path d="M112 98 l12 4.5v8c0 6.5-4.5 11-12 13.5c-7.5-2.5-12-7-12-13.5v-8z" fill="#A8434B" stroke="#fff" stroke-width="2"/>'
                  '<path d="M107 108 l10 8 M117 108 l-10 8" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/>',
        "aprovado": '<circle cx="113" cy="110" r="12" fill="#2F7D5B" stroke="#fff" stroke-width="2"/>'
                    '<path d="M107 110 l4.5 4.5 l8 -9" stroke="#fff" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
        "atencao": '<circle cx="113" cy="110" r="12" fill="#C19A4F" stroke="#fff" stroke-width="2"/>'
                   '<path d="M113 103 v8" stroke="#1B2B4C" stroke-width="3" stroke-linecap="round"/><circle cx="113" cy="116" r="1.8" fill="#1B2B4C"/>',
        "mascara": '<circle cx="113" cy="110" r="12" fill="#4B5E8E" stroke="#fff" stroke-width="2"/>'
                   '<path d="M106 110 h14" stroke="#fff" stroke-width="3" stroke-linecap="round"/>',
    }.get(mood, "")

    return f"""<svg class="iris-avatar" width="{size}" height="{size}" viewBox="0 0 140 140" role="img" aria-label="Íris — {m['label']}">
  <circle cx="70" cy="70" r="66" fill="none" stroke="{ring}" stroke-width="5" opacity=".9"/>
  <circle cx="70" cy="70" r="59" fill="#1B2B4C"/>
  <path d="M70 14 l3 7 l-3 4 l-3 -4z" fill="#D8B573"/>
  <rect x="34" y="40" width="72" height="66" rx="28" fill="#24375E"/>
  <rect x="38" y="48" width="64" height="26" rx="13" fill="#14203B"/>
  {brows}{eyes}{mouth}
  <circle cx="34" cy="73" r="5" fill="#D8B573"/><circle cx="106" cy="73" r="5" fill="#D8B573"/>
  {badge}
</svg>"""
