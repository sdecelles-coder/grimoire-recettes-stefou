"""
MISE EN PLACE v2 — console de recettes techno-futuriste
────────────────────────────────────────────────────────
• Onglet CUISINE : ajuste les portions, coche les ingrédients.
• Onglet ÉDITION : modifie les quantités, ajoute / retire des
  ingrédients, crée ou supprime des recettes.
• Les recettes sont sauvegardées dans recettes.json (créé
  automatiquement à côté de ce script).

Lancer avec :  streamlit run recettes_console.py
"""

import json
import os

import streamlit as st
import streamlit.components.v1 as components

# ─────────────────────────────────────────────────────────────────────────────
#  PERSISTANCE — recettes.json à côté du script
# ─────────────────────────────────────────────────────────────────────────────
FICHIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recettes.json")

RECETTES_DEFAUT = [
    {
        "titre": "Marinade grecque pour poulet",
        "sous_titre": "Style Casa Grecque",
        "base": {"label": "Poids de poulet", "unite": "g", "valeur": 750,
                 "min": 100, "max": 3000, "pas": 50},
        "ingredients": [
            {"nom": "Mayonnaise (comble)",        "qte": 3,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Origan",                      "qte": 2,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Huile légère",                "qte": 4,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Jus de citron",               "qte": 3,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Poudre d'oignon",             "qte": 1,    "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Ail haché",                   "qte": 1,    "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Moutarde de Dijon",           "qte": 1,    "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Base de bouillon de poulet",  "qte": 1,    "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Sel et poivre",               "qte": None, "unite": "au goût",    "palier": None},
        ],
    },
    {
        "titre": "Vinaigrette balsamique",
        "sous_titre": "Classique 3 pour 1 — à éditer selon ton goût",
        "base": {"label": "Volume", "unite": "ml", "valeur": 250,
                 "min": 60, "max": 1000, "pas": 10},
        "ingredients": [
            {"nom": "Huile d'olive",        "qte": 6,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Vinaigre balsamique",  "qte": 2,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Moutarde de Dijon",    "qte": 1,    "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Miel",                 "qte": 1,    "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Ail haché",            "qte": 0.5,  "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Sel et poivre",        "qte": None, "unite": "au goût",    "palier": None},
        ],
    },
    {
        "titre": "Marinade BBQ maison",
        "sous_titre": "Exemple modifiable",
        "base": {"label": "Poids de viande", "unite": "g", "valeur": 1000,
                 "min": 200, "max": 4000, "pas": 100},
        "ingredients": [
            {"nom": "Ketchup",              "qte": 4,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Cassonade",            "qte": 2,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Sauce Worcestershire", "qte": 2,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Vinaigre de cidre",    "qte": 1,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Paprika fumé",         "qte": 2,    "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Poudre d'ail",         "qte": 1,    "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Sel et poivre",        "qte": None, "unite": "au goût",    "palier": None},
        ],
    },
]


def charger_recettes():
    """Charge recettes.json ; sinon retourne une copie des recettes par défaut."""
    if os.path.exists(FICHIER):
        try:
            with open(FICHIER, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return json.loads(json.dumps(RECETTES_DEFAUT))


def sauvegarder_recettes(recettes):
    with open(FICHIER, "w", encoding="utf-8") as f:
        json.dump(recettes, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
#  LOGIQUE DE MISE À L'ÉCHELLE
# ─────────────────────────────────────────────────────────────────────────────
FRACTIONS = {0.0: "", 0.25: "¼", 0.5: "½", 0.75: "¾"}


def echelle(ing, facteur):
    """Quantité mise à l'échelle, arrondie au palier. None => au goût."""
    if ing.get("qte") is None:
        return None
    pal = ing.get("palier") or 0.25
    val = round(ing["qte"] * facteur / pal) * pal
    if ing["qte"] > 0 and val == 0:
        val = pal
    return val


def jolie_qte(x):
    """0.5 -> '½', 3.5 -> '3 ½', 3.0 -> '3'."""
    if x is None:
        return "au goût"
    entier = int(x)
    reste = round(x - entier, 2)
    fr = FRACTIONS.get(reste, "")
    if fr == "" and reste:                       # palier inhabituel (ex. 0.1)
        return f"{x:g}"
    if entier == 0:
        return fr if fr else "0"
    return f"{entier} {fr}".strip()


def html_escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ─────────────────────────────────────────────────────────────────────────────
#  ÉTAT
# ─────────────────────────────────────────────────────────────────────────────
if "recettes" not in st.session_state:
    st.session_state.recettes = charger_recettes()
if "sel" not in st.session_state:
    st.session_state.sel = 0
if "confirmer_suppr" not in st.session_state:
    st.session_state.confirmer_suppr = False

RECETTES = st.session_state.recettes


def recette_vierge(n_total):
    return {
        "titre": f"Nouvelle recette {n_total}" if n_total > 1 else "Nouvelle recette",
        "sous_titre": "À personnaliser",
        "base": {"label": "Portions", "unite": "u", "valeur": 4,
                 "min": 1, "max": 20, "pas": 1},
        "ingredients": [{"nom": "Premier ingrédient", "qte": 1,
                         "unite": "c. à table", "palier": 0.5}],
    }


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE + THÈME
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Mise en place", page_icon="🛰️",
                   layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500;700&display=swap');

:root{
  --bg:#04060d; --panel:#0b1120; --line:#1e2a45;
  --cyan:#4df3e3; --amber:#ffb454;
  --text:#e9efff; --muted:#7d8cb5;
}

.stApp{
  background:
    radial-gradient(1200px 560px at 10% -12%, rgba(77,243,227,.09), transparent 60%),
    radial-gradient(1000px 520px at 105% -5%, rgba(255,180,84,.08), transparent 55%),
    linear-gradient(rgba(77,243,227,.028) 1px, transparent 1px),
    linear-gradient(90deg, rgba(77,243,227,.028) 1px, transparent 1px),
    var(--bg);
  background-size:auto,auto,44px 44px,44px 44px,auto;
}
#MainMenu, header, footer{visibility:hidden;}
.block-container{padding-top:2.2rem; padding-bottom:3rem; max-width:980px;}

/* ── En-tête ─────────────────────────────────────────── */
.hero{margin-bottom:1.3rem; position:relative;}
.hero .eyebrow{
  font-family:'JetBrains Mono',monospace; font-size:.7rem; letter-spacing:.46em;
  color:var(--cyan); text-transform:uppercase; margin-bottom:.45rem;
}
.hero .eyebrow::before{content:"▮ "; animation:blink 1.4s steps(1) infinite;}
@keyframes blink{50%{opacity:0}}
.hero h1{
  font-family:'Orbitron',sans-serif; font-weight:900; font-size:2.5rem;
  color:var(--text); margin:0; letter-spacing:.04em; line-height:1.05;
  text-shadow:0 0 30px rgba(77,243,227,.25);
}
.hero p{font-family:'Inter',sans-serif; color:var(--muted); margin:.5rem 0 0; font-size:.98rem;}

/* ── Widgets Streamlit ───────────────────────────────── */
.stSelectbox label, [data-testid="stNumberInput"] label, .stTextInput label{
  font-family:'JetBrains Mono',monospace!important; font-size:.68rem!important;
  letter-spacing:.24em!important; text-transform:uppercase!important; color:var(--muted)!important;
}
.stSelectbox div[data-baseweb="select"] > div,
[data-testid="stNumberInput"] input,
.stTextInput input{
  background:var(--panel)!important; border:1px solid var(--line)!important;
  border-radius:10px!important; color:var(--text)!important;
  font-family:'Inter',sans-serif!important;
}
[data-testid="stNumberInput"] input{font-family:'JetBrains Mono',monospace!important;
  font-size:1.1rem!important; font-weight:700!important;}
[data-testid="stNumberInput"] button{background:var(--panel)!important; border-color:var(--line)!important; color:var(--text)!important;}
.stSelectbox div[data-baseweb="select"] > div:focus-within,
[data-testid="stNumberInput"] input:focus, .stTextInput input:focus{
  border-color:var(--cyan)!important; box-shadow:0 0 0 2px rgba(77,243,227,.22)!important;
}

/* Onglets */
.stTabs [data-baseweb="tab-list"]{gap:6px; border-bottom:1px solid var(--line);}
.stTabs [data-baseweb="tab"]{
  font-family:'Orbitron',sans-serif!important; font-size:.82rem!important;
  letter-spacing:.14em!important; color:var(--muted)!important;
  background:transparent!important; padding:10px 18px!important;
}
.stTabs [aria-selected="true"]{
  color:var(--cyan)!important; text-shadow:0 0 14px rgba(77,243,227,.5);
}
.stTabs [data-baseweb="tab-highlight"]{background:var(--cyan)!important;
  box-shadow:0 0 12px rgba(77,243,227,.8);}

/* Boutons */
.stButton button{
  font-family:'Orbitron',sans-serif!important; font-size:.78rem!important;
  letter-spacing:.12em!important; text-transform:uppercase!important;
  background:var(--panel)!important; color:var(--cyan)!important;
  border:1px solid var(--line)!important; border-radius:10px!important;
  transition:all .18s!important;
}
.stButton button:hover{border-color:var(--cyan)!important;
  box-shadow:0 0 16px rgba(77,243,227,.35)!important;}
.stButton button[kind="primary"]{
  background:linear-gradient(135deg, rgba(77,243,227,.16), rgba(77,243,227,.05))!important;
  border-color:var(--cyan)!important;
}
.stButton button:disabled{opacity:.35!important;}

/* Éditeur de données + expanders */
[data-testid="stDataFrame"]{
  border:1px solid var(--line)!important; border-radius:12px!important; overflow:hidden;
}
[data-testid="stExpander"]{
  background:var(--panel)!important; border:1px solid var(--line)!important;
  border-radius:12px!important;
}
[data-testid="stExpander"] summary{
  font-family:'JetBrains Mono',monospace!important; font-size:.74rem!important;
  letter-spacing:.18em!important; text-transform:uppercase!important; color:var(--muted)!important;
}
[data-testid="stCaptionContainer"] p{
  font-family:'JetBrains Mono',monospace!important; font-size:.7rem!important;
  color:var(--muted)!important; letter-spacing:.06em;
}
div[data-testid="stAlert"]{
  background:var(--panel)!important; border:1px solid var(--line)!important;
  border-radius:12px!important; color:var(--text)!important;
}

/* ── Mobile ──────────────────────────────────────────── */
@media (max-width:640px){
  .block-container{padding-top:1.3rem; padding-left:.85rem; padding-right:.85rem;}
  .hero h1{font-size:1.7rem;}
  .hero p{font-size:.88rem;}
  .hero .eyebrow{font-size:.62rem; letter-spacing:.34em;}
  .stTabs [data-baseweb="tab"]{padding:9px 12px!important; font-size:.74rem!important;}
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <div class="eyebrow">Mise en place · v2.0</div>
  <h1>CONSOLE DE RECETTES</h1>
  <p>Ajuste les portions en cuisine, ou passe en mode édition pour modifier tes recettes.</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  SÉLECTION DE RECETTE + NOUVELLE RECETTE
# ─────────────────────────────────────────────────────────────────────────────
if not RECETTES:
    st.info("Aucune recette au menu. Crée ta première recette ci-dessous.")
    if st.button("＋ Nouvelle recette", type="primary", use_container_width=True):
        RECETTES.append(recette_vierge(1))
        st.session_state.sel = 0
        sauvegarder_recettes(RECETTES)
        st.rerun()
    st.stop()

st.session_state.sel = min(st.session_state.sel, len(RECETTES) - 1)

c_sel, c_new = st.columns([2.6, 1])
with c_sel:
    idx = st.selectbox(
        "Recette", options=list(range(len(RECETTES))),
        format_func=lambda i: RECETTES[i]["titre"],
        index=st.session_state.sel,
    )
    if idx != st.session_state.sel:
        st.session_state.sel = idx
        st.session_state.confirmer_suppr = False
with c_new:
    st.markdown("<div style='height:1.72rem'></div>", unsafe_allow_html=True)
    if st.button("＋ Nouvelle", use_container_width=True,
                 help="Ajouter une recette vierge au menu"):
        RECETTES.append(recette_vierge(len(RECETTES) + 1))
        st.session_state.sel = len(RECETTES) - 1
        st.session_state.confirmer_suppr = False
        sauvegarder_recettes(RECETTES)
        st.rerun()

recette = RECETTES[st.session_state.sel]
base = recette["base"]

onglet_cuisine, onglet_edition = st.tabs(["◈  CUISINE", "⚙  ÉDITION"])

# ═════════════════════════════════════════════════════════════════════════════
#  ONGLET CUISINE — mise à l'échelle + checklist
# ═════════════════════════════════════════════════════════════════════════════
with onglet_cuisine:
    cible = st.number_input(
        f"{base['label']} ({base['unite']})",
        min_value=float(base["min"]), max_value=float(base["max"]),
        value=float(base["valeur"]), step=float(base["pas"]),
        key=f"cible_{st.session_state.sel}",
    )
    facteur = cible / base["valeur"] if base["valeur"] else 1.0

    lignes = ""
    for ing in recette["ingredients"]:
        q = jolie_qte(echelle(ing, facteur))
        au_gout = ing.get("qte") is None
        unite = "" if au_gout else html_escape(ing.get("unite") or "")
        cls_qte = "qte gout" if au_gout else "qte"
        lignes += f"""
        <div class="ing" onclick="toggle(this)">
          <span class="box"></span>
          <span class="nom">{html_escape(ing['nom'])}</span>
          <span class="{cls_qte}"><b>{q}</b> {unite}</span>
        </div>"""

    n = len(recette["ingredients"])
    calib = f"Calibré · {base['valeur']:g} {base['unite']}"
    cible_txt = f"{cible:g} {base['unite']}"

    TEMPLATE = """
<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',sans-serif;color:#e9efff;background:transparent;padding:4px}
.card{
  position:relative;border:1px solid #1e2a45;border-radius:16px;
  background:linear-gradient(180deg, rgba(14,22,40,.95), rgba(6,10,20,.95));
  box-shadow:0 24px 60px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.04);
}
/* coins HUD */
.corner{position:absolute;width:16px;height:16px;border:2px solid #4df3e3;opacity:.85;pointer-events:none}
.c-tl{top:-2px;left:-2px;border-right:none;border-bottom:none;border-radius:14px 0 0 0}
.c-tr{top:-2px;right:-2px;border-left:none;border-bottom:none;border-radius:0 14px 0 0}
.c-bl{bottom:-2px;left:-2px;border-right:none;border-top:none;border-radius:0 0 0 14px}
.c-br{bottom:-2px;right:-2px;border-left:none;border-top:none;border-radius:0 0 14px 0}

.head{padding:20px 22px 15px;border-bottom:1px solid #1e2a45;position:relative;overflow:hidden}
.scan{position:absolute;top:0;left:0;height:2px;width:40%;
  background:linear-gradient(90deg,transparent,#4df3e3,transparent);
  animation:scan 3.4s linear infinite;opacity:.7}
@keyframes scan{from{left:-40%}to{left:100%}}
@media (prefers-reduced-motion: reduce){.scan{animation:none;display:none}}
.rtitle{font-family:'Orbitron',sans-serif;font-weight:900;font-size:1.32rem;letter-spacing:.03em}
.rsub{color:#7d8cb5;font-size:.9rem;margin-top:3px}
.meta{display:flex;gap:10px;margin-top:13px;flex-wrap:wrap}
.chip{font-family:'JetBrains Mono',monospace;font-size:.72rem;color:#9fb0d8;
  border:1px solid #1e2a45;border-radius:999px;padding:5px 12px;background:rgba(77,243,227,.05)}
.chip b{color:#ffb454}
.prog{height:4px;background:#141d34;border-radius:999px;margin-top:15px;overflow:hidden}
.progfill{height:100%;width:0;background:linear-gradient(90deg,#4df3e3,#ffb454);
  box-shadow:0 0 14px rgba(77,243,227,.6);transition:width .35s ease}
.count{font-family:'JetBrains Mono',monospace;font-size:.7rem;color:#7d8cb5;margin-top:7px;letter-spacing:.12em}

.list{padding:8px 10px 4px}
.ing{display:flex;align-items:center;gap:12px;padding:13px 12px;border-radius:11px;
  cursor:pointer;transition:background .18s;border:1px solid transparent;
  -webkit-tap-highlight-color:transparent}
.ing:hover{background:rgba(77,243,227,.06);border-color:#1e2a45}
.box{width:20px;height:20px;flex:0 0 20px;border-radius:6px;
  border:2px solid #3a4a75;position:relative;transition:all .18s}
.ing.done .box{background:#4df3e3;border-color:#4df3e3;box-shadow:0 0 12px rgba(77,243,227,.7)}
.ing.done .box::after{content:"";position:absolute;left:5px;top:1px;width:5px;height:10px;
  border:solid #04060d;border-width:0 2.5px 2.5px 0;transform:rotate(45deg)}
.nom{flex:1;font-size:1rem;font-weight:500;transition:all .18s;min-width:0;overflow-wrap:break-word}
.ing.done .nom{color:#5a688f;text-decoration:line-through}
.qte{font-family:'JetBrains Mono',monospace;font-size:1rem;color:#9fb0d8;white-space:nowrap;
  padding:4px 11px;border-radius:8px;border:1px solid #26355c;background:rgba(255,180,84,.06)}
.qte b{color:#ffb454;text-shadow:0 0 12px rgba(255,180,84,.45);font-weight:700}
.qte.gout{color:#7d8cb5;background:transparent;border-color:transparent}
.qte.gout b{color:#7d8cb5;text-shadow:none;font-weight:500}
.ing.done .qte{opacity:.35}
.hint{font-family:'JetBrains Mono',monospace;font-size:.66rem;color:#5a688f;
  letter-spacing:.22em;text-align:center;padding:8px 0 14px;text-transform:uppercase}
@media (max-width:640px){
  .head{padding:16px 14px 13px}
  .rtitle{font-size:1.08rem}
  .rsub{font-size:.82rem}
  .chip{font-size:.64rem;padding:4px 9px}
  .list{padding:6px 5px 2px}
  .ing{gap:9px;padding:11px 8px}
  .nom{font-size:.92rem}
  .qte{font-size:.88rem;padding:3px 8px}
  .box{width:18px;height:18px;flex:0 0 18px}
}
</style></head><body>
<div class="card">
  <span class="corner c-tl"></span><span class="corner c-tr"></span>
  <span class="corner c-bl"></span><span class="corner c-br"></span>
  <div class="head">
    <div class="scan"></div>
    <div class="rtitle">__TITRE__</div>
    <div class="rsub">__SOUS__</div>
    <div class="meta">
      <span class="chip">__CALIB__</span>
      <span class="chip">Cible · <b>__CIBLE__</b></span>
      <span class="chip">Facteur · <b>×__FACT__</b></span>
    </div>
    <div class="prog"><div class="progfill" id="fill"></div></div>
    <div class="count" id="cnt">0 / __N__ ingrédients cochés</div>
  </div>
  <div class="list">__ROWS__</div>
  <div class="hint">Touche un ingrédient pour le cocher</div>
</div>
<script>
function toggle(el){el.classList.toggle('done');maj();}
function maj(){
  var items=Array.prototype.slice.call(document.querySelectorAll('.ing'));
  var d=items.filter(function(i){return i.classList.contains('done')}).length;
  document.getElementById('cnt').textContent=d+' / '+items.length+' ingr\\u00e9dients coch\\u00e9s';
  document.getElementById('fill').style.width=(items.length?d/items.length*100:0)+'%';
}
</script></body></html>
"""

    html = (TEMPLATE
            .replace("__TITRE__", html_escape(recette["titre"]))
            .replace("__SOUS__", html_escape(recette.get("sous_titre", "")))
            .replace("__CALIB__", html_escape(calib))
            .replace("__CIBLE__", html_escape(cible_txt))
            .replace("__FACT__", f"{facteur:.2f}")
            .replace("__N__", str(n))
            .replace("__ROWS__", lignes))

    components.html(html, height=320 + max(n, 1) * 62, scrolling=True)

# ═════════════════════════════════════════════════════════════════════════════
#  ONGLET ÉDITION — modifier / ajouter / retirer / supprimer
# ═════════════════════════════════════════════════════════════════════════════
with onglet_edition:
    k = st.session_state.sel  # clés uniques par recette sélectionnée

    e1, e2 = st.columns(2)
    with e1:
        titre = st.text_input("Titre", value=recette["titre"], key=f"t_{k}")
    with e2:
        sous_titre = st.text_input("Sous-titre", value=recette.get("sous_titre", ""),
                                   key=f"s_{k}")

    with st.expander("Référence de base (mise à l'échelle)"):
        b1, b2, b3 = st.columns(3)
        with b1:
            b_label = st.text_input("Étiquette", value=base["label"], key=f"bl_{k}")
            b_val = st.number_input("Valeur de référence", min_value=0.01,
                                    value=float(base["valeur"]), key=f"bv_{k}")
        with b2:
            b_unite = st.text_input("Unité", value=base["unite"], key=f"bu_{k}")
            b_min = st.number_input("Minimum", min_value=0.0,
                                    value=float(base["min"]), key=f"bm_{k}")
        with b3:
            b_pas = st.number_input("Pas", min_value=0.01,
                                    value=float(base["pas"]), key=f"bp_{k}")
            b_max = st.number_input("Maximum", min_value=0.01,
                                    value=float(base["max"]), key=f"bx_{k}")

    st.caption("INGRÉDIENTS — modifie les cellules · la ligne vide du bas ajoute un "
               "ingrédient · coche une ligne puis 🗑 pour la retirer · "
               "quantité vide = « au goût »")

    lignes_edit = [
        {
            "Ingrédient": ing.get("nom", ""),
            "Quantité": ing.get("qte"),
            "Unité": ing.get("unite", ""),
            "Palier": ing.get("palier"),
        }
        for ing in recette["ingredients"]
    ]

    edite = st.data_editor(
        lignes_edit,
        num_rows="dynamic",
        use_container_width=True,
        key=f"editeur_{k}",
        column_config={
            "Ingrédient": st.column_config.TextColumn("Ingrédient", required=True,
                                                      width="large"),
            "Quantité": st.column_config.NumberColumn(
                "Quantité", min_value=0.0, step=0.25,
                help="Laisser vide pour « au goût »"),
            "Unité": st.column_config.TextColumn("Unité", width="medium"),
            "Palier": st.column_config.SelectboxColumn(
                "Palier", options=[0.25, 0.5, 1.0],
                help="Arrondi lors de la mise à l'échelle"),
        },
    )

    if st.button("💾 Enregistrer les modifications", type="primary",
                 use_container_width=True, key=f"save_{k}"):
        nouveaux = []
        for ligne in edite:
            nom = (ligne.get("Ingrédient") or "").strip()
            if not nom:
                continue
            qte = ligne.get("Quantité")
            au_gout = qte in (None, "")
            nouveaux.append({
                "nom": nom,
                "qte": None if au_gout else float(qte),
                "unite": (ligne.get("Unité") or "").strip() or
                         ("au goût" if au_gout else ""),
                "palier": float(ligne["Palier"]) if ligne.get("Palier") else None,
            })
        if not nouveaux:
            st.error("Il faut au moins un ingrédient avec un nom.")
        elif b_min >= b_max:
            st.error("Le minimum de la référence doit être inférieur au maximum.")
        else:
            recette["titre"] = titre.strip() or "Sans titre"
            recette["sous_titre"] = sous_titre.strip()
            recette["base"] = {"label": b_label.strip() or "Base",
                               "unite": b_unite.strip() or "u",
                               "valeur": b_val, "min": b_min,
                               "max": b_max, "pas": b_pas}
            recette["ingredients"] = nouveaux
            sauvegarder_recettes(RECETTES)
            st.success("Recette enregistrée ✓")
            st.rerun()

    st.divider()

    # Retrait de la recette, avec confirmation
    if not st.session_state.confirmer_suppr:
        if st.button("🗑 Retirer cette recette du menu", use_container_width=True,
                     key=f"del_{k}"):
            st.session_state.confirmer_suppr = True
            st.rerun()
    else:
        st.warning(f"Retirer « {recette['titre']} » du menu ? Cette action est définitive.")
        d1, d2 = st.columns(2)
        with d1:
            if st.button("Oui, retirer", type="primary", use_container_width=True,
                         key=f"delok_{k}"):
                RECETTES.pop(st.session_state.sel)
                st.session_state.sel = max(0, st.session_state.sel - 1)
                st.session_state.confirmer_suppr = False
                sauvegarder_recettes(RECETTES)
                st.rerun()
        with d2:
            if st.button("Annuler", use_container_width=True, key=f"delno_{k}"):
                st.session_state.confirmer_suppr = False
                st.rerun()
