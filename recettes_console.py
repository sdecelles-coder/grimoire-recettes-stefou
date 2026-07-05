"""
MISE EN PLACE v2 — console de recettes techno-futuriste
────────────────────────────────────────────────────────
• Onglet CUISINE : ajuste les portions, coche les ingrédients ET les
  étapes de préparation ; les quantités (y compris dans les étapes)
  s'ajustent automatiquement.
• Onglet ÉDITION : sommaire (temps de préparation, cuisson, portions),
  édition des ingrédients et des étapes, création / suppression de recettes.
• Dans une étape, écris [nom d'ingrédient] entre crochets pour insérer
  sa quantité mise à l'échelle.
• Sauvegarde vers GitHub (si secrets configurés) ou en local.

Lancer avec :  streamlit run recettes_console.py
"""

import base64
import json
import os
import re

import pandas as pd
import requests
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
        "temps_prep": 10,
        "temps_cuisson": 0,
        "base": {"label": "Poids de poulet", "unite": "g", "valeur": 750,
                 "personnes": 4, "max_personnes": 20},
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
        "preparation": [
            "Dans un bol, fouetter [Mayonnaise (comble)], [Origan], [Huile légère] et [Jus de citron].",
            "Ajouter [Poudre d'oignon], [Ail haché], [Moutarde de Dijon] et [Base de bouillon de poulet]. Bien mélanger.",
            "Enrober le poulet de marinade, couvrir et réfrigérer au moins 2 heures.",
            "Saler et poivrer au goût juste avant la cuisson.",
        ],
    },
    {
        "titre": "Vinaigrette balsamique",
        "sous_titre": "Classique 3 pour 1 — à éditer selon ton goût",
        "temps_prep": 5,
        "temps_cuisson": 0,
        "base": {"label": "Volume", "unite": "ml", "valeur": 250,
                 "personnes": 4, "max_personnes": 20},
        "ingredients": [
            {"nom": "Huile d'olive",        "qte": 6,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Vinaigre balsamique",  "qte": 2,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Moutarde de Dijon",    "qte": 1,    "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Miel",                 "qte": 1,    "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Ail haché",            "qte": 0.5,  "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Sel et poivre",        "qte": None, "unite": "au goût",    "palier": None},
        ],
        "preparation": [
            "Fouetter [Moutarde de Dijon] et [Miel] avec [Vinaigre balsamique].",
            "Ajouter [Ail haché], puis verser [Huile d'olive] en filet en fouettant sans arrêt.",
            "Saler et poivrer au goût. Bien secouer avant chaque service.",
        ],
    },
    {
        "titre": "Marinade BBQ maison",
        "sous_titre": "Exemple modifiable",
        "temps_prep": 10,
        "temps_cuisson": 20,
        "base": {"label": "Poids de viande", "unite": "g", "valeur": 1000,
                 "personnes": 4, "max_personnes": 20},
        "ingredients": [
            {"nom": "Ketchup",              "qte": 4,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Cassonade",            "qte": 2,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Sauce Worcestershire", "qte": 2,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Vinaigre de cidre",    "qte": 1,    "unite": "c. à table", "palier": 0.5},
            {"nom": "Paprika fumé",         "qte": 2,    "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Poudre d'ail",         "qte": 1,    "unite": "c. à thé",   "palier": 0.25},
            {"nom": "Sel et poivre",        "qte": None, "unite": "au goût",    "palier": None},
        ],
        "preparation": [
            "Dans une casserole, mélanger [Ketchup], [Cassonade] et [Sauce Worcestershire].",
            "Ajouter [Vinaigre de cidre], [Paprika fumé] et [Poudre d'ail].",
            "Porter à faible ébullition, puis laisser mijoter 15 à 20 minutes en remuant.",
            "Saler et poivrer au goût. Badigeonner sur la viande en fin de cuisson.",
        ],
    },
]


def _github_cfg():
    """Retourne la config GitHub depuis st.secrets, ou None si absente (mode local)."""
    try:
        gh = st.secrets["github"]
        return {
            "token":  gh["token"],
            "repo":   gh["repo"],                       # ex: "sdecelles-coder/grimoire-recettes-stefou"
            "branch": gh.get("branch", "main"),
            "chemin": gh.get("chemin", "recettes.json"),
        }
    except (KeyError, FileNotFoundError):
        return None


def _gh_url(cfg):
    return f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['chemin']}"


def _gh_headers(cfg):
    return {
        "Authorization": f"Bearer {cfg['token']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def charger_recettes():
    """Charge les recettes depuis GitHub si configuré, sinon depuis le fichier
    local ; retourne (recettes, mode, erreur)."""
    cfg = _github_cfg()
    if cfg:
        try:
            r = requests.get(_gh_url(cfg), headers=_gh_headers(cfg),
                             params={"ref": cfg["branch"]}, timeout=10)
            if r.status_code == 200:
                data = json.loads(base64.b64decode(r.json()["content"]))
                if isinstance(data, list):
                    return data, "github", None
            if r.status_code == 404:   # pas encore de fichier dans le repo
                return json.loads(json.dumps(RECETTES_DEFAUT)), "github", None
            return (json.loads(json.dumps(RECETTES_DEFAUT)), "github",
                    f"Lecture GitHub impossible (code {r.status_code}) — "
                    "vérifie le token et le nom du repo dans les secrets.")
        except requests.RequestException as e:
            return (json.loads(json.dumps(RECETTES_DEFAUT)), "github",
                    f"Connexion à GitHub impossible : {e}")
    # Mode local
    if os.path.exists(FICHIER):
        try:
            with open(FICHIER, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data, "local", None
        except (json.JSONDecodeError, OSError):
            pass
    return json.loads(json.dumps(RECETTES_DEFAUT)), "local", None


def sauvegarder_recettes(recettes):
    """Écrit les recettes (GitHub si configuré, sinon local).
    Retourne (ok, message_erreur)."""
    cfg = _github_cfg()
    contenu = json.dumps(recettes, ensure_ascii=False, indent=2)
    if cfg:
        try:
            # SHA actuel du fichier (obligatoire pour mettre à jour un fichier existant)
            sha = None
            r = requests.get(_gh_url(cfg), headers=_gh_headers(cfg),
                             params={"ref": cfg["branch"]}, timeout=10)
            if r.status_code == 200:
                sha = r.json().get("sha")
            payload = {
                "message": "Mise à jour des recettes via la console",
                "content": base64.b64encode(contenu.encode("utf-8")).decode("ascii"),
                "branch": cfg["branch"],
            }
            if sha:
                payload["sha"] = sha
            r2 = requests.put(_gh_url(cfg), headers=_gh_headers(cfg),
                              json=payload, timeout=15)
            if r2.status_code in (200, 201):
                return True, None
            detail = ""
            try:
                detail = r2.json().get("message", "")
            except ValueError:
                pass
            return False, f"GitHub a refusé l'écriture (code {r2.status_code}) : {detail}"
        except requests.RequestException as e:
            return False, f"Connexion à GitHub impossible : {e}"
    # Mode local
    try:
        with open(FICHIER, "w", encoding="utf-8") as f:
            f.write(contenu)
        return True, None
    except OSError as e:
        return False, f"Écriture locale impossible : {e}"


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


def normaliser_recette(r):
    """Garantit que chaque recette possède tous les champs attendus
    (migration des anciennes recettes sans temps ni préparation)."""
    r.setdefault("titre", "Sans titre")
    r.setdefault("sous_titre", "")
    r.setdefault("temps_prep", 0)
    r.setdefault("temps_cuisson", 0)
    r.setdefault("preparation", [])
    r.setdefault("ingredients", [])
    r.setdefault("base", {})
    b = r["base"]
    b.setdefault("label", "Rendement")
    b.setdefault("unite", "")
    b.setdefault("valeur", 0)
    b.setdefault("personnes", 4)          # personnes servies par la valeur de réf.
    b.setdefault("max_personnes", 20)     # borne haute du curseur en cuisine
    return r


def injecter_quantites(texte, index_ing, facteur):
    """Remplace les [nom d'ingrédient] d'une étape par la quantité mise à
    l'échelle. Le texte est déjà échappé HTML ; les crochets survivent."""
    def repl(m):
        cle = m.group(1).strip().lower()
        ing = index_ing.get(cle)
        if not ing:
            return m.group(1)                      # nom seul si non trouvé
        q = echelle(ing, facteur)
        if q is None:
            val = "au goût"
        else:
            unite = html_escape(ing.get("unite") or "")
            val = f"{jolie_qte(q)} {unite}".strip()
        return f'<span class="inq">{val}</span>'
    return re.sub(r"\[([^\[\]]+)\]", repl, texte)


# ─────────────────────────────────────────────────────────────────────────────
#  ÉTAT
# ─────────────────────────────────────────────────────────────────────────────
if "recettes" not in st.session_state:
    recettes, mode, erreur = charger_recettes()
    for r in recettes:
        normaliser_recette(r)
    st.session_state.recettes = recettes
    st.session_state.stockage = mode          # "github" ou "local"
    st.session_state.erreur_chargement = erreur
if "sel" not in st.session_state:
    st.session_state.sel = 0
if "confirmer_suppr" not in st.session_state:
    st.session_state.confirmer_suppr = False

RECETTES = st.session_state.recettes


def persister(recettes):
    """Sauvegarde et affiche l'erreur au besoin. Retourne True si OK."""
    ok, err = sauvegarder_recettes(recettes)
    if not ok:
        st.error(f"⚠ Sauvegarde échouée — {err}")
    return ok


def recette_vierge(n_total):
    return {
        "titre": f"Nouvelle recette {n_total}" if n_total > 1 else "Nouvelle recette",
        "sous_titre": "À personnaliser",
        "temps_prep": 0,
        "temps_cuisson": 0,
        "base": {"label": "Portions", "unite": "portions", "valeur": 4,
                 "personnes": 4, "max_personnes": 20},
        "ingredients": [{"nom": "Premier ingrédient", "qte": 1,
                         "unite": "c. à table", "palier": 0.5}],
        "preparation": ["Première étape — écris [Premier ingrédient] pour insérer sa quantité."],
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

badge = ("☁ Sauvegarde · GitHub" if st.session_state.stockage == "github"
         else "💾 Sauvegarde · locale")
st.markdown(f"""
<div class="hero">
  <div class="eyebrow">Mise en place · v2.1</div>
  <h1>CONSOLE DE RECETTES</h1>
  <p>Ajuste les portions en cuisine, ou passe en mode édition pour modifier tes recettes.
     <span style="font-family:'JetBrains Mono',monospace;font-size:.68rem;color:#4df3e3;
     letter-spacing:.1em;white-space:nowrap;">{badge}</span></p>
</div>
""", unsafe_allow_html=True)

if st.session_state.erreur_chargement:
    st.error(f"⚠ {st.session_state.erreur_chargement} Les recettes affichées sont "
             "les valeurs par défaut ; les sauvegardes échoueront tant que le "
             "problème n'est pas réglé.")

# ─────────────────────────────────────────────────────────────────────────────
#  SÉLECTION DE RECETTE + NOUVELLE RECETTE
# ─────────────────────────────────────────────────────────────────────────────
if not RECETTES:
    st.info("Aucune recette au menu. Crée ta première recette ci-dessous.")
    if st.button("＋ Nouvelle recette", type="primary", use_container_width=True):
        RECETTES.append(recette_vierge(1))
        st.session_state.sel = 0
        if persister(RECETTES):
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
        if persister(RECETTES):
            st.rerun()

recette = RECETTES[st.session_state.sel]
base = recette["base"]

onglet_cuisine, onglet_edition = st.tabs(["◈  CUISINE", "⚙  ÉDITION"])

# ═════════════════════════════════════════════════════════════════════════════
#  ONGLET CUISINE — mise à l'échelle + checklist
# ═════════════════════════════════════════════════════════════════════════════
with onglet_cuisine:
    # Le curseur = NOMBRE DE PERSONNES. La « valeur de référence » (rendement)
    # correspond au nombre de personnes de référence ; tout est mis à l'échelle
    # proportionnellement au nombre de personnes choisi.
    personnes_ref = int(base.get("personnes", 4) or 4)
    if personnes_ref < 1:
        personnes_ref = 1
    max_pers = int(base.get("max_personnes", 20) or 20)
    if max_pers < personnes_ref:
        max_pers = max(personnes_ref, 20)

    cible_pers = st.number_input(
        "Nombre de personnes",
        min_value=1, max_value=max_pers,
        value=min(personnes_ref, max_pers), step=1,
        key=f"cible_{st.session_state.sel}",
        help=f"Recette de référence pour {personnes_ref} personne"
             f"{'s' if personnes_ref > 1 else ''}.",
    )
    facteur = cible_pers / personnes_ref if personnes_ref else 1.0

    rendement_ref = float(base.get("valeur") or 0)      # pour personnes_ref pers.
    rendement = rendement_ref * facteur                 # pour cible_pers pers.
    portion = rendement_ref / personnes_ref if personnes_ref else 0

    # Index des ingrédients pour l'auto-ajustement dans les étapes
    index_ing = {ing["nom"].strip().lower(): ing
                 for ing in recette["ingredients"] if ing.get("nom")}

    # Section INGRÉDIENTS
    lignes_ing = ""
    for ing in recette["ingredients"]:
        q = jolie_qte(echelle(ing, facteur))
        au_gout = ing.get("qte") is None
        unite = "" if au_gout else html_escape(ing.get("unite") or "")
        cls_qte = "qte gout" if au_gout else "qte"
        lignes_ing += f"""
        <div class="ing" onclick="toggle(this)">
          <span class="box"></span>
          <span class="nom">{html_escape(ing['nom'])}</span>
          <span class="{cls_qte}"><b>{q}</b> {unite}</span>
        </div>"""

    # Section PRÉPARATION (étapes numérotées, quantités auto-ajustées)
    lignes_prep = ""
    for i, etape in enumerate(recette.get("preparation", []), start=1):
        texte = injecter_quantites(html_escape(etape), index_ing, facteur)
        lignes_prep += f"""
        <div class="ing step" onclick="toggle(this)">
          <span class="box"></span>
          <span class="num">{i}.</span>
          <span class="nom">{texte}</span>
        </div>"""

    n_ing = len(recette["ingredients"])
    n_prep = len(recette.get("preparation", []))
    n = n_ing + n_prep

    # ── Sommaire : personnes ↔ rendement, temps, facteur ─────────────────
    tp = int(recette.get("temps_prep", 0) or 0)
    tc = int(recette.get("temps_cuisson", 0) or 0)
    unite = html_escape(base.get("unite") or "")
    label = html_escape(base.get("label") or "Rendement")
    chips = [f'<span class="chip chip-ref">Personnes · <b>{cible_pers:g}</b></span>']
    if rendement_ref > 0:
        chips.append(f'<span class="chip">{label} · <b>{rendement:g} {unite}</b></span>')
        chips.append(f'<span class="chip">Portion/pers · <b>{portion:g} {unite}</b></span>')
    if tp:
        chips.append(f'<span class="chip">Prép · <b>{tp} min</b></span>')
    if tc:
        chips.append(f'<span class="chip">Cuisson · <b>{tc} min</b></span>')
    if tp or tc:
        chips.append(f'<span class="chip">Temps total · <b>{tp + tc} min</b></span>')
    chips.append(f'<span class="chip">Facteur · <b>×{facteur:.2f}</b></span>')
    meta_html = "".join(chips)

    sommaire_body = f'<div class="meta">{meta_html}</div>'
    if rendement_ref > 0:
        sommaire_body += (
            f'<div class="sommaire-rel">Référence : '
            f'<b>{rendement_ref:g} {unite}</b> pour '
            f'<b>{personnes_ref} personne{"s" if personnes_ref > 1 else ""}</b>'
            f' · soit <b>{portion:g} {unite}</b> par personne</div>')

    # ── Sections repliables (Sommaire, Ingrédients, Préparation) ─────────
    def section_block(cls, ico, titre, count_txt, body):
        return (f'<div class="section {cls}" onclick="toggleSec(this)">'
                f'<span class="sec-ico">{ico}</span>'
                f'<span class="sec-txt">{titre}</span>'
                f'<span class="sec-count">{count_txt}</span>'
                f'<span class="sec-chevron">▾</span></div>'
                f'<div class="sec-body">{body}</div>')

    rows = section_block("sec-som", "◈", "Sommaire",
                         f"{cible_pers:g} pers", sommaire_body)
    if lignes_ing:
        rows += section_block("sec-ing", "🧺", "Ingrédients",
                              str(n_ing), lignes_ing)
    if lignes_prep:
        rows += section_block("sec-prep", "🍳", "Préparation",
                              f'{n_prep} étape{"s" if n_prep > 1 else ""}',
                              lignes_prep)

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
.meta{display:flex;gap:10px;flex-wrap:wrap}
.chip{font-family:'JetBrains Mono',monospace;font-size:.72rem;color:#9fb0d8;
  border:1px solid #1e2a45;border-radius:999px;padding:5px 12px;background:rgba(77,243,227,.05)}
.chip b{color:#ffb454}
.chip-ref{border-color:#4df3e3;background:rgba(77,243,227,.12);color:#cfe9ff;
  box-shadow:0 0 14px rgba(77,243,227,.25)}
.chip-ref b{color:#4df3e3;text-shadow:0 0 12px rgba(77,243,227,.6)}
.sommaire-rel{font-family:'Inter',sans-serif;font-size:.82rem;color:#9fb0d8;
  margin-top:11px;padding:9px 12px;border-radius:10px;border:1px dashed #26355c;
  background:rgba(77,243,227,.04)}
.sommaire-rel b{color:#ffb454;font-weight:700}
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

/* Sections repliables (Sommaire, Ingrédients, Préparation) */
.section{font-family:'Orbitron',sans-serif;font-weight:900;font-size:.98rem;
  letter-spacing:.14em;text-transform:uppercase;display:flex;align-items:center;
  gap:12px;margin:18px 8px 8px;padding:12px 16px;border-radius:12px;cursor:pointer;
  -webkit-tap-highlight-color:transparent;user-select:none;
  border:1px solid #26355c;background:linear-gradient(90deg,rgba(77,243,227,.14),rgba(77,243,227,.02));
  border-left:4px solid #4df3e3;box-shadow:0 4px 18px rgba(0,0,0,.3),inset 0 1px 0 rgba(255,255,255,.05);
  transition:box-shadow .18s,border-color .18s}
.section:hover{box-shadow:0 4px 22px rgba(77,243,227,.28),inset 0 1px 0 rgba(255,255,255,.05)}
.section .sec-ico{font-size:1.15rem;line-height:1;filter:drop-shadow(0 0 8px rgba(77,243,227,.5))}
.section .sec-txt{color:#e9efff;text-shadow:0 0 16px rgba(77,243,227,.4)}
.section .sec-count{margin-left:auto;font-family:'JetBrains Mono',monospace;
  font-weight:700;font-size:.66rem;letter-spacing:.08em;color:#04060d;background:#4df3e3;
  padding:4px 10px;border-radius:999px;box-shadow:0 0 12px rgba(77,243,227,.5)}
.section .sec-chevron{font-size:.9rem;color:#4df3e3;transition:transform .22s ease;line-height:1}
.section.collapsed .sec-chevron{transform:rotate(-90deg)}
.sec-body{overflow:hidden;padding:4px 6px 6px}
.sec-body.hidden{display:none}
.sec-som .sec-count{background:#9fb0d8;box-shadow:0 0 12px rgba(159,176,216,.5)}
.sec-prep{border-left-color:#ffb454;
  background:linear-gradient(90deg,rgba(255,180,84,.14),rgba(255,180,84,.02))}
.sec-prep:hover{box-shadow:0 4px 22px rgba(255,180,84,.28),inset 0 1px 0 rgba(255,255,255,.05)}
.sec-prep .sec-ico{filter:drop-shadow(0 0 8px rgba(255,180,84,.5))}
.sec-prep .sec-txt{text-shadow:0 0 16px rgba(255,180,84,.4)}
.sec-prep .sec-count{background:#ffb454;box-shadow:0 0 12px rgba(255,180,84,.5)}
.sec-prep .sec-chevron{color:#ffb454}
.ing.step{align-items:flex-start}
.ing.step .box{margin-top:2px}
.step .num{font-family:'JetBrains Mono',monospace;font-weight:700;color:#ffb454;
  flex:0 0 auto;font-size:.95rem;line-height:1.5}
.step .nom{font-weight:400;line-height:1.5}
.inq{font-family:'JetBrains Mono',monospace;color:#ffb454;font-weight:700;
  background:rgba(255,180,84,.1);padding:1px 6px;border-radius:5px;white-space:nowrap;
  text-shadow:0 0 10px rgba(255,180,84,.35)}
.ing.done .inq{opacity:.4;text-shadow:none}

/* Overlay de victoire — apparaît quand tout est coché */
.victoire{
  position:absolute;inset:0;z-index:10;display:flex;align-items:center;justify-content:center;
  background:rgba(4,6,13,.86);backdrop-filter:blur(3px);border-radius:16px;
  opacity:0;visibility:hidden;transition:opacity .35s ease, visibility .35s;cursor:pointer;
}
.victoire.visible{opacity:1;visibility:visible;}
.v-cadre{text-align:center;padding:18px;animation:pop .45s cubic-bezier(.2,1.4,.4,1)}
@keyframes pop{from{transform:scale(.7);opacity:0}to{transform:scale(1);opacity:1}}
@media (prefers-reduced-motion: reduce){.v-cadre{animation:none}}
.v-cadre img{
  max-width:min(280px,70vw);max-height:44vh;border-radius:14px;
  border:2px solid #4df3e3;box-shadow:0 0 34px rgba(77,243,227,.55);
}
.v-titre{font-family:'Orbitron',sans-serif;font-weight:900;font-size:1.05rem;
  color:#4df3e3;letter-spacing:.16em;margin-top:14px;
  text-shadow:0 0 18px rgba(77,243,227,.7)}
.v-sous{font-family:'JetBrains Mono',monospace;font-size:.66rem;color:#7d8cb5;
  letter-spacing:.22em;margin-top:6px;text-transform:uppercase}
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
  .section{font-size:.82rem;padding:10px 12px;margin:14px 5px 8px}
  .section .sec-ico{font-size:1rem}
}
</style></head><body>
<div class="card">
  <span class="corner c-tl"></span><span class="corner c-tr"></span>
  <span class="corner c-bl"></span><span class="corner c-br"></span>
  <div class="head">
    <div class="scan"></div>
    <div class="rtitle">__TITRE__</div>
    <div class="rsub">__SOUS__</div>
    <div class="prog"><div class="progfill" id="fill"></div></div>
    <div class="count" id="cnt">0 / __N__ éléments cochés</div>
  </div>
  <div class="list">__ROWS__</div>
  <div class="hint">Touche un ingrédient ou une étape pour le cocher</div>
  <div class="victoire" id="victoire" onclick="fermerVictoire()">
    <div class="v-cadre">
      <img src="https://i.pinimg.com/originals/fc/6e/a2/fc6ea2c2a09d097a22efca53e3780843.gif" alt="Mise en place complète !">
      <div class="v-titre">MISE EN PLACE COMPLÈTE</div>
      <div class="v-sous">Touche pour fermer</div>
    </div>
  </div>
</div>
<script>
var victoireFermee=false;
function toggle(el){el.classList.toggle('done');maj();}
function toggleSec(el){
  el.classList.toggle('collapsed');
  var body=el.nextElementSibling;
  if(body && body.classList.contains('sec-body')){body.classList.toggle('hidden');}
}
function maj(){
  var items=Array.prototype.slice.call(document.querySelectorAll('.ing'));
  var d=items.filter(function(i){return i.classList.contains('done')}).length;
  document.getElementById('cnt').textContent=d+' / '+items.length+' \\u00e9l\\u00e9ments coch\\u00e9s';
  document.getElementById('fill').style.width=(items.length?d/items.length*100:0)+'%';
  var complet=items.length>0 && d===items.length;
  if(!complet){victoireFermee=false;}
  document.getElementById('victoire').classList.toggle('visible', complet && !victoireFermee);
}
function fermerVictoire(){
  victoireFermee=true;
  document.getElementById('victoire').classList.remove('visible');
}
</script></body></html>
"""

    html = (TEMPLATE
            .replace("__TITRE__", html_escape(recette["titre"]))
            .replace("__SOUS__", html_escape(recette.get("sous_titre", "")))
            .replace("__N__", str(n))
            .replace("__ROWS__", rows))

    # Hauteur : en-tête + section Sommaire + sections Ingrédients / Préparation
    hauteur = (290 + 210
               + (66 + n_ing * 60 if n_ing else 0)
               + (66 + n_prep * 92 if n_prep else 0))
    components.html(html, height=hauteur, scrolling=True)

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

    with st.expander("Sommaire — personnes, temps & rendement", expanded=True):
        st.caption("En cuisine, le curseur correspond au NOMBRE DE PERSONNES. "
                   "La « valeur de référence » est le rendement obtenu pour le "
                   "nombre de personnes de référence ; ingrédients et quantités "
                   "s'ajustent proportionnellement.")
        s1, s2 = st.columns(2)
        with s1:
            temps_prep = st.number_input("Temps de préparation (min)", min_value=0,
                                         value=int(recette.get("temps_prep", 0) or 0),
                                         step=5, key=f"tp_{k}")
        with s2:
            temps_cuisson = st.number_input("Temps de cuisson (min)", min_value=0,
                                            value=int(recette.get("temps_cuisson", 0) or 0),
                                            step=5, key=f"tc_{k}")
        st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
        p1, p2 = st.columns(2)
        with p1:
            b_personnes = st.number_input(
                "Nombre de personnes (référence)", min_value=1, step=1,
                value=int(base.get("personnes", 4) or 4), key=f"bpe_{k}",
                help="Nombre de personnes servi par la valeur de référence.")
        with p2:
            b_maxpers = st.number_input(
                "Personnes maximum (curseur cuisine)", min_value=1, step=1,
                value=int(base.get("max_personnes", 20) or 20), key=f"bmp_{k}",
                help="Borne haute du curseur « Nombre de personnes » en cuisine.")
        b1, b2, b3 = st.columns([1.4, 1, 0.9])
        with b1:
            b_label = st.text_input("Étiquette du rendement (ex. Poids de poulet)",
                                    value=base.get("label", ""), key=f"bl_{k}")
        with b2:
            b_val = st.number_input(
                "Valeur de référence", min_value=0.0, step=1.0,
                value=float(base.get("valeur") or 0), key=f"bv_{k}",
                help="Rendement total pour le nombre de personnes de référence "
                     "(mettre 0 si non pertinent).")
        with b3:
            b_unite = st.text_input("Unité", value=base.get("unite", ""), key=f"bu_{k}")
        if b_personnes and b_val:
            st.caption(f"→ soit {b_val / b_personnes:g} {b_unite or ''}".rstrip()
                       + " par personne.")

    with st.expander(f"🧺  Ingrédients ({len(recette['ingredients'])})",
                     expanded=True):
        st.caption("Modifie les cellules · la ligne vide du bas ajoute un "
                   "ingrédient · coche une ligne puis 🗑 pour la retirer · "
                   "quantité vide = « au goût »")

        df_ing = pd.DataFrame(
            [
                {
                    "Ingrédient": ing.get("nom", ""),
                    "Quantité": ing.get("qte"),
                    "Unité": ing.get("unite", ""),
                    "Palier": ing.get("palier"),
                }
                for ing in recette["ingredients"]
            ],
            columns=["Ingrédient", "Quantité", "Unité", "Palier"],
        )

        edite = st.data_editor(
            df_ing,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
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

    with st.expander(f"🍳  Préparation ({len(recette.get('preparation', []))} étape"
                     f"{'s' if len(recette.get('preparation', [])) > 1 else ''})",
                     expanded=True):
        st.caption("Une étape par ligne (dans l'ordre) · clique la ligne vide du bas "
                   "pour ajouter une étape · écris [nom d'ingrédient] entre crochets "
                   "pour insérer sa quantité, qui s'ajustera automatiquement en cuisine.")

        df_prep = pd.DataFrame(
            {"Étape": list(recette.get("preparation", []))},
            columns=["Étape"],
        ).astype({"Étape": "string"})
        edite_prep = st.data_editor(
            df_prep,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key=f"prep_editeur_{k}",
            column_config={
                "Étape": st.column_config.TextColumn(
                    "Étape", required=True, width="large",
                    help="Ex. : Fouetter [Huile d'olive] avec [Miel]."),
            },
        )

    if st.button("💾 Enregistrer les modifications", type="primary",
                 use_container_width=True, key=f"save_{k}"):
        nouveaux = []
        for ligne in edite.to_dict("records"):
            nom = str(ligne.get("Ingrédient") or "").strip()
            if not nom or nom.lower() == "nan":
                continue
            qte = ligne.get("Quantité")
            au_gout = qte is None or qte == "" or pd.isna(qte)
            palier = ligne.get("Palier")
            unite_raw = ligne.get("Unité")
            unite = "" if (unite_raw is None or pd.isna(unite_raw)) else str(unite_raw).strip()
            nouveaux.append({
                "nom": nom,
                "qte": None if au_gout else float(qte),
                "unite": unite or ("au goût" if au_gout else ""),
                "palier": None if (palier is None or pd.isna(palier)) else float(palier),
            })
        etapes = [str(v).strip() for v in edite_prep["Étape"].tolist()
                  if pd.notna(v) and str(v).strip()]
        if not nouveaux:
            st.error("Il faut au moins un ingrédient avec un nom.")
        else:
            recette["titre"] = titre.strip() or "Sans titre"
            recette["sous_titre"] = sous_titre.strip()
            recette["temps_prep"] = int(temps_prep)
            recette["temps_cuisson"] = int(temps_cuisson)
            recette["base"] = {"label": b_label.strip() or "Rendement",
                               "unite": b_unite.strip(),
                               "valeur": float(b_val),
                               "personnes": int(b_personnes),
                               "max_personnes": max(int(b_maxpers), int(b_personnes))}
            recette["ingredients"] = nouveaux
            recette["preparation"] = etapes
            if persister(RECETTES):
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
                persister(RECETTES)
                st.rerun()
        with d2:
            if st.button("Annuler", use_container_width=True, key=f"delno_{k}"):
                st.session_state.confirmer_suppr = False
                st.rerun()