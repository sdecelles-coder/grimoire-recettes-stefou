"""
MISE EN PLACE — console de recettes
Ajuste les portions, les quantités suivent.

Lancer avec :  streamlit run recettes_console.py
"""

import streamlit as st
import streamlit.components.v1 as components

# ─────────────────────────────────────────────────────────────────────────────
#  DONNÉES — pour ajouter une recette, copie un bloc et modifie-le.
#   qte   : quantité pour la valeur de base (mettre None = « au goût »)
#   palier: arrondi de mesure (0.5 = demi-cuillère, 0.25 = quart, 1 = unité)
# ─────────────────────────────────────────────────────────────────────────────
RECETTES = [
    {
        "titre": "Marinade grecque pour poulet",
        "sous_titre": "Style Casa Grecque",
        "base": {"label": "Poids de poulet", "unite": "g", "valeur": 750,
                 "min": 100, "max": 3000, "pas": 50},
        "ingredients": [
            {"nom": "Mayonnaise (comble)",        "qte": 3, "unite": "c. à table", "palier": 0.5},
            {"nom": "Origan",                      "qte": 2, "unite": "c. à table", "palier": 0.5},
            {"nom": "Huile légère",                "qte": 4, "unite": "c. à table", "palier": 0.5},
            {"nom": "Jus de citron",               "qte": 3, "unite": "c. à table", "palier": 0.5},
            {"nom": "Poudre d'oignon",             "qte": 1, "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Ail haché",                   "qte": 1, "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Moutarde de Dijon",           "qte": 1, "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Base de bouillon de poulet",  "qte": 1, "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Sel et poivre",               "qte": None, "unite": "au goût", "palier": None},
        ],
    },
    {
        "titre": "Vinaigrette balsamique",
        "sous_titre": "Classique 3 pour 1 — à éditer selon ton goût",
        "base": {"label": "Volume", "unite": "ml", "valeur": 250,
                 "min": 60, "max": 1000, "pas": 10},
        "ingredients": [
            {"nom": "Huile d'olive",        "qte": 6, "unite": "c. à table", "palier": 0.5},
            {"nom": "Vinaigre balsamique",  "qte": 2, "unite": "c. à table", "palier": 0.5},
            {"nom": "Moutarde de Dijon",    "qte": 1, "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Miel",                 "qte": 1, "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Ail haché",            "qte": 0.5, "unite": "c. à thé", "palier": 0.25},
            {"nom": "Sel et poivre",        "qte": None, "unite": "au goût", "palier": None},
        ],
    },
    {
        "titre": "Marinade BBQ maison",
        "sous_titre": "Exemple modifiable",
        "base": {"label": "Poids de viande", "unite": "g", "valeur": 1000,
                 "min": 200, "max": 4000, "pas": 100},
        "ingredients": [
            {"nom": "Ketchup",              "qte": 4, "unite": "c. à table", "palier": 0.5},
            {"nom": "Cassonade",            "qte": 2, "unite": "c. à table", "palier": 0.5},
            {"nom": "Sauce Worcestershire", "qte": 2, "unite": "c. à table", "palier": 0.5},
            {"nom": "Vinaigre de cidre",    "qte": 1, "unite": "c. à table", "palier": 0.5},
            {"nom": "Paprika fumé",         "qte": 2, "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Poudre d'ail",         "qte": 1, "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Sel et poivre",        "qte": None, "unite": "au goût", "palier": None},
        ],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
#  LOGIQUE
# ─────────────────────────────────────────────────────────────────────────────
FRACTIONS = {0.0: "", 0.25: "¼", 0.5: "½", 0.75: "¾"}


def echelle(ing, facteur):
    """Quantité mise à l'échelle et arrondie au palier. None => au goût."""
    if ing["qte"] is None:
        return None
    pal = ing.get("palier") or 0.25
    val = round(ing["qte"] * facteur / pal) * pal
    if ing["qte"] > 0 and val == 0:      # jamais tomber à zéro pour un ingrédient réel
        val = pal
    return val


def jolie_qte(x):
    """0.5 -> '½', 3.5 -> '3 ½', 3.0 -> '3'."""
    if x is None:
        return "au goût"
    entier = int(x)
    reste = round(x - entier, 2)
    fr = FRACTIONS.get(reste, "")
    if entier == 0:
        return fr if fr else "0"
    return f"{entier} {fr}".strip()


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Mise en place", page_icon="🍳", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500;700&display=swap');

:root{
  --bg:#0a0e1c; --panel:#131a30; --line:#26304f;
  --amber:#ffb454; --cyan:#3fe0d0; --pink:#ff5c8a;
  --text:#e7ecff; --muted:#7f8bb0;
}
.stApp{
  background:
    radial-gradient(1100px 500px at 12% -10%, rgba(63,224,208,.10), transparent 60%),
    radial-gradient(900px 500px at 100% 0%, rgba(255,180,84,.10), transparent 55%),
    var(--bg);
}
#MainMenu, header, footer{visibility:hidden;}
.block-container{padding-top:2.4rem; max-width:1050px;}

/* En-tête */
.hero{margin-bottom:1.6rem;}
.hero .eyebrow{
  font-family:'JetBrains Mono',monospace; font-size:.72rem; letter-spacing:.42em;
  color:var(--cyan); text-transform:uppercase; margin-bottom:.5rem;
}
.hero h1{
  font-family:'Chakra Petch',sans-serif; font-weight:700; font-size:2.9rem;
  color:var(--text); margin:0; letter-spacing:.02em; line-height:1;
  text-shadow:0 0 26px rgba(255,180,84,.18);
}
.hero p{font-family:'Inter',sans-serif; color:var(--muted); margin:.5rem 0 0; font-size:1rem;}

/* Widgets Streamlit */
.stSelectbox label, [data-testid="stNumberInput"] label{
  font-family:'JetBrains Mono',monospace!important; font-size:.7rem!important;
  letter-spacing:.24em!important; text-transform:uppercase!important; color:var(--muted)!important;
}
.stSelectbox div[data-baseweb="select"] > div, [data-testid="stNumberInput"] input{
  background:var(--panel)!important; border:1px solid var(--line)!important;
  border-radius:12px!important; color:var(--text)!important;
  font-family:'Chakra Petch',sans-serif!important;
}
[data-testid="stNumberInput"] input{font-size:1.15rem!important; font-weight:600!important;}
[data-testid="stNumberInput"] button{background:var(--panel)!important; border-color:var(--line)!important;}
.stSelectbox div[data-baseweb="select"] > div:focus-within,
[data-testid="stNumberInput"] input:focus{
  border-color:var(--cyan)!important; box-shadow:0 0 0 2px rgba(63,224,208,.25)!important;
}

/* Mobile */
@media (max-width:640px){
  .block-container{padding-top:1.6rem; padding-left:.9rem; padding-right:.9rem;}
  .hero h1{font-size:2.05rem;}
  .hero p{font-size:.92rem;}
  .hero .eyebrow{font-size:.66rem; letter-spacing:.34em;}
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <div class="eyebrow">Mise en place</div>
  <h1>Console de recettes</h1>
  <p>Choisis une recette, règle la quantité — les ingrédients s'ajustent en direct.</p>
</div>
""", unsafe_allow_html=True)

# Contrôles
c1, c2 = st.columns([1.4, 1])
with c1:
    titres = [r["titre"] for r in RECETTES]
    choix = st.selectbox("Recette", titres, index=0)
recette = next(r for r in RECETTES if r["titre"] == choix)
base = recette["base"]

with c2:
    cible = st.number_input(
        f"{base['label']} ({base['unite']})",
        min_value=float(base["min"]), max_value=float(base["max"]),
        value=float(base["valeur"]), step=float(base["pas"]),
    )
facteur = cible / base["valeur"] if base["valeur"] else 1.0

# Lignes d'ingrédients
lignes = ""
for ing in recette["ingredients"]:
    q = jolie_qte(echelle(ing, facteur))
    au_gout = ing["qte"] is None
    unite = "" if au_gout else ing["unite"]
    cls_qte = "qte gout" if au_gout else "qte"
    lignes += f"""
    <div class="ing" onclick="toggle(this)">
      <span class="box"></span>
      <span class="nom">{ing['nom']}</span>
      <span class="{cls_qte}"><b>{q}</b> {unite}</span>
    </div>"""

n = len(recette["ingredients"])
calib = f"Calibré pour {jolie_qte(base['valeur']) if base['valeur']%1 else int(base['valeur'])} {base['unite']} · {base['label'].lower()}"
cible_txt = f"{int(cible) if cible%1==0 else cible} {base['unite']}"

TEMPLATE = """
<!doctype html><html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',sans-serif;color:#e7ecff;background:transparent}
.card{
  position:relative;border:1px solid #26304f;border-radius:20px;overflow:hidden;
  background:
    linear-gradient(180deg, rgba(19,26,48,.92), rgba(11,15,28,.92));
  box-shadow:0 24px 60px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.04);
}
.card::before{content:"";position:absolute;inset:0;pointer-events:none;
  background-image:linear-gradient(rgba(63,224,208,.05) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(63,224,208,.05) 1px,transparent 1px);
  background-size:34px 34px;mask:linear-gradient(180deg,#000,transparent 70%);opacity:.5}
.head{padding:22px 26px 16px;border-bottom:1px solid #26304f;position:relative}
.rtitle{font-family:'Chakra Petch',sans-serif;font-weight:700;font-size:1.5rem;letter-spacing:.01em}
.rsub{color:#7f8bb0;font-size:.92rem;margin-top:2px}
.meta{display:flex;gap:18px;margin-top:14px;flex-wrap:wrap}
.chip{font-family:'JetBrains Mono',monospace;font-size:.74rem;color:#9fb0d8;
  border:1px solid #26304f;border-radius:999px;padding:5px 12px;background:rgba(63,224,208,.05)}
.chip b{color:#ffb454}
.prog{height:4px;background:#1c2440;border-radius:999px;margin-top:16px;overflow:hidden}
.progfill{height:100%;width:0;background:linear-gradient(90deg,#3fe0d0,#ffb454);
  box-shadow:0 0 14px rgba(63,224,208,.6);transition:width .35s ease}
.count{font-family:'JetBrains Mono',monospace;font-size:.72rem;color:#7f8bb0;margin-top:8px;letter-spacing:.1em}

.list{padding:8px 12px 16px}
.ing{display:flex;align-items:center;gap:14px;padding:14px 14px;border-radius:12px;
  cursor:pointer;transition:background .18s, opacity .18s;border:1px solid transparent}
.ing:hover{background:rgba(63,224,208,.06);border-color:#26304f}
.box{width:20px;height:20px;flex:0 0 20px;border-radius:6px;
  border:2px solid #3a4a75;position:relative;transition:all .18s}
.ing.done .box{background:#3fe0d0;border-color:#3fe0d0;box-shadow:0 0 12px rgba(63,224,208,.7)}
.ing.done .box::after{content:"";position:absolute;left:6px;top:2px;width:5px;height:10px;
  border:solid #0a0e1c;border-width:0 2.5px 2.5px 0;transform:rotate(45deg)}
.nom{flex:1;font-size:1.02rem;font-weight:500;transition:all .18s}
.ing.done .nom{color:#5a688f;text-decoration:line-through}
.qte{font-family:'JetBrains Mono',monospace;font-size:1.05rem;color:#9fb0d8;white-space:nowrap;
  padding:4px 12px;border-radius:8px;border:1px solid #2a355c;background:rgba(255,180,84,.06)}
.qte b{color:#ffb454;text-shadow:0 0 12px rgba(255,180,84,.45);font-weight:700}
.qte.gout{color:#7f8bb0;background:transparent;border-color:transparent}
.qte.gout b{color:#7f8bb0;text-shadow:none;font-weight:500}
.ing.done .qte{opacity:.35}
@media (max-width:640px){
  .head{padding:18px 16px 14px}
  .rtitle{font-size:1.25rem}
  .rsub{font-size:.84rem}
  .chip{font-size:.68rem;padding:4px 10px}
  .list{padding:6px 6px 12px}
  .ing{gap:10px;padding:12px 10px}
  .nom{font-size:.95rem}
  .qte{font-size:.95rem;padding:3px 9px}
  .box{width:18px;height:18px;flex:0 0 18px}
}
</style></head><body>
<div class="card">
  <div class="head">
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
</div>
<script>
function toggle(el){el.classList.toggle('done');maj();}
function maj(){
  var items=Array.prototype.slice.call(document.querySelectorAll('.ing'));
  var d=items.filter(function(i){return i.classList.contains('done')}).length;
  document.getElementById('cnt').textContent=d+' / '+items.length+' ingrédients cochés';
  document.getElementById('fill').style.width=(items.length?d/items.length*100:0)+'%';
}
</script></body></html>
"""

html = (TEMPLATE
        .replace("__TITRE__", recette["titre"])
        .replace("__SOUS__", recette["sous_titre"])
        .replace("__CALIB__", calib)
        .replace("__CIBLE__", cible_txt)
        .replace("__FACT__", f"{facteur:.2f}")
        .replace("__N__", str(n))
        .replace("__ROWS__", lignes))

components.html(html, height=340 + n * 64, scrolling=False)

st.markdown(
    "<p style='font-family:JetBrains Mono,monospace;font-size:.7rem;color:#5a688f;"
    "letter-spacing:.2em;text-align:center;margin-top:18px'>"
    "TOUCHE UN INGRÉDIENT POUR LE COCHER</p>",
    unsafe_allow_html=True,
)
