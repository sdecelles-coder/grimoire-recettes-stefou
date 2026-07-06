"""
Grimoire de recettes techno-futuriste
────────────────────────────────────────────────────────
• Onglet CUISINE : ajuste les portions, coche les ingrédients ET les
  étapes de préparation ; les quantités (y compris dans les étapes)
  s'ajustent automatiquement.
• Onglet ÉDITION : sommaire (temps de préparation, cuisson, portions),
  édition des ingrédients et des étapes, création / suppression de recettes.
  C'est aussi ici qu'on applique des TAGS aux recettes et qu'on gère le
  catalogue partagé de tags (renommer, recolorer, supprimer).
• TAGS : catalogue global partagé par tous les utilisateurs (enregistré avec
  les recettes). Chaque tag a une couleur. Recherche par tags (ET), et affichage
  des tags dans les sommaires de cuisine et d'édition.
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
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode

# ─────────────────────────────────────────────────────────────────────────────
#  PERSISTANCE — recettes.json à côté du script
# ─────────────────────────────────────────────────────────────────────────────
FICHIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recettes.json")

# ─────────────────────────────────────────────────────────────────────────────
#  GIFS DE VICTOIRE — fichiers stockés dans le repo (dossier images/).
#
#  La carte cuisine est rendue dans une iframe (srcdoc) : un chemin relatif n'y
#  résout pas. Deux modes de service :
#    • "local"  : le GIF est intégré en base64 dans le HTML → marche tout de
#                 suite, sans push, sans dépendance externe. Plus lourd (le HTML
#                 est renvoyé à chaque ajustement de portions).
#    • "github" : le GIF est servi depuis raw.githubusercontent (repo public) →
#                 léger et mis en cache par le navigateur, MAIS il faut d'abord
#                 pousser les fichiers sur la branche ci-dessous.
#  Pour basculer une fois les images poussées : GIF_MODE = "github".
# ─────────────────────────────────────────────────────────────────────────────
DOSSIER_IMAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
GIF_MODE = "local"                                     # "local" ou "github"
GIF_REPO = "sdecelles-coder/grimoire-recettes-stefou"
GIF_BRANCH = "main"
GIF_BASE = f"https://raw.githubusercontent.com/{GIF_REPO}/{GIF_BRANCH}/images"
GIF_INGREDIENTS_FICHIER = "ingredients.gif"            # mise en place terminée
GIF_PREPARATION_FICHIER = "cat_eat.gif"               # préparation terminée


@st.cache_data(show_spinner=False)
def gif_src(nom_fichier):
    """URL utilisable dans l'iframe pour un GIF de images/. En mode "local",
    renvoie un data-URI base64 (lu depuis le disque) ; en mode "github", l'URL
    raw. Repli sur l'URL raw si le fichier local est introuvable."""
    if GIF_MODE == "local":
        try:
            with open(os.path.join(DOSSIER_IMAGES, nom_fichier), "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            return f"data:image/gif;base64,{b64}"
        except OSError:
            pass
    return f"{GIF_BASE}/{nom_fichier}"

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


# ─────────────────────────────────────────────────────────────────────────────
#  TAGS — catalogue global partagé (enregistré avec les recettes)
# ─────────────────────────────────────────────────────────────────────────────
# Palette de couleurs proposée par défaut aux nouveaux tags (cyclée selon le
# nombre de tags déjà présents). L'utilisateur peut changer la couleur ensuite
# dans le panneau « Gérer les tags ».
PALETTE_TAGS = [
    "#4df3e3", "#ffb454", "#ff7a9c", "#a78bfa", "#7ee787",
    "#63b3ff", "#f4d35e", "#ff8f5e", "#5eead4", "#c084fc",
]

# Tags proposés au tout premier démarrage (aucun fichier encore enregistré).
TAGS_DEFAUT = [
    {"nom": "déjeuner",       "couleur": "#f4d35e"},
    {"nom": "Félix",          "couleur": "#63b3ff"},
    {"nom": "Juju",           "couleur": "#a78bfa"},
    {"nom": "lunch",          "couleur": "#7ee787"},
    {"nom": "Mélo",           "couleur": "#ff7a9c"},
    {"nom": "dessert",        "couleur": "#ff8f5e"},
    {"nom": "plat principal", "couleur": "#4df3e3"},
    {"nom": "Stefou",         "couleur": "#ffb454"},
]

COULEUR_TAG_DEFAUT = "#7d8cb5"      # gris : tag sans couleur connue


def _norm_tag(nom):
    """Clé de comparaison d'un tag (insensible à la casse et aux espaces)."""
    return (nom or "").strip().casefold()


def trier_tags(tags):
    """Trie une liste de tags (dicts {nom, couleur}) par nom, insensible à la
    casse. Retourne une nouvelle liste."""
    return sorted(tags, key=lambda t: _norm_tag(t.get("nom")))


def normaliser_tags(tags):
    """Nettoie le catalogue global : chaque entrée devient {nom, couleur},
    doublons (même nom insensible à la casse) fusionnés, tri alphabétique."""
    vus = {}
    for t in tags or []:
        if isinstance(t, str):                      # ancien format éventuel
            t = {"nom": t}
        nom = (t.get("nom") or "").strip()
        if not nom:
            continue
        cle = _norm_tag(nom)
        if cle in vus:
            continue
        couleur = t.get("couleur") or PALETTE_TAGS[len(vus) % len(PALETTE_TAGS)]
        vus[cle] = {"nom": nom, "couleur": couleur}
    return trier_tags(list(vus.values()))


def index_couleurs(tags):
    """Dict {clé normalisée -> couleur} pour retrouver vite la couleur d'un tag."""
    return {_norm_tag(t["nom"]): t.get("couleur") or COULEUR_TAG_DEFAUT
            for t in tags}


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


def _defaut():
    """Copie fraîche des recettes et tags par défaut."""
    return (json.loads(json.dumps(RECETTES_DEFAUT)),
            json.loads(json.dumps(TAGS_DEFAUT)))


def _extraire(data):
    """Décompose le contenu JSON chargé en (recettes, tags).

    Deux formats acceptés :
      • ancien : une simple liste de recettes → les tags sont ceux par défaut ;
      • nouveau : {"recettes": [...], "tags": [...]}."""
    if isinstance(data, list):
        return data, json.loads(json.dumps(TAGS_DEFAUT))
    if isinstance(data, dict) and isinstance(data.get("recettes"), list):
        return data["recettes"], data.get("tags") or []
    return None


def charger_recettes():
    """Charge recettes + tags depuis GitHub si configuré, sinon depuis le
    fichier local ; retourne (recettes, tags, mode, erreur)."""
    cfg = _github_cfg()
    if cfg:
        try:
            r = requests.get(_gh_url(cfg), headers=_gh_headers(cfg),
                             params={"ref": cfg["branch"]}, timeout=10)
            if r.status_code == 200:
                data = json.loads(base64.b64decode(r.json()["content"]))
                extrait = _extraire(data)
                if extrait:
                    return extrait[0], extrait[1], "github", None
            if r.status_code == 404:   # pas encore de fichier dans le repo
                rec, tags = _defaut()
                return rec, tags, "github", None
            rec, tags = _defaut()
            return (rec, tags, "github",
                    f"Lecture GitHub impossible (code {r.status_code}) — "
                    "vérifie le token et le nom du repo dans les secrets.")
        except requests.RequestException as e:
            rec, tags = _defaut()
            return (rec, tags, "github",
                    f"Connexion à GitHub impossible : {e}")
    # Mode local
    if os.path.exists(FICHIER):
        try:
            with open(FICHIER, encoding="utf-8") as f:
                data = json.load(f)
            extrait = _extraire(data)
            if extrait:
                return extrait[0], extrait[1], "local", None
        except (json.JSONDecodeError, OSError):
            pass
    rec, tags = _defaut()
    return rec, tags, "local", None


def sauvegarder_recettes(recettes, tags):
    """Écrit recettes + catalogue de tags (GitHub si configuré, sinon local).
    Retourne (ok, message_erreur)."""
    cfg = _github_cfg()
    contenu = json.dumps({"recettes": recettes, "tags": tags},
                         ensure_ascii=False, indent=2)
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
    r.setdefault("tags", [])
    # Tags : liste de noms (chaînes), nettoyée et sans doublons.
    vus, propres = set(), []
    for t in r.get("tags", []):
        nom = (t or "").strip() if isinstance(t, str) else ""
        if nom and _norm_tag(nom) not in vus:
            vus.add(_norm_tag(nom))
            propres.append(nom)
    r["tags"] = propres
    r.setdefault("base", {})
    b = r["base"]
    b.setdefault("label", "Rendement")
    b.setdefault("unite", "")
    b.setdefault("valeur", 0)
    b.setdefault("personnes", 4)          # personnes servies par la valeur de réf.
    b.setdefault("max_personnes", 20)     # borne haute du curseur en cuisine
    b.setdefault("multiples", False)      # ajuster seulement par multiples entiers
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
    recettes, tags, mode, erreur = charger_recettes()
    for r in recettes:
        normaliser_recette(r)
    st.session_state.recettes = recettes
    st.session_state.tags = normaliser_tags(tags)   # catalogue global
    st.session_state.stockage = mode          # "github" ou "local"
    st.session_state.erreur_chargement = erreur
if "sel" not in st.session_state:
    # Au démarrage, aucune recette n'est sélectionnée (« Choisis ta recette »).
    st.session_state.sel = None
if "recette_select" not in st.session_state:
    # Valeur du sélecteur de recette (index dans RECETTES, ou None = aucune).
    st.session_state.recette_select = None
if "confirmer_suppr" not in st.session_state:
    st.session_state.confirmer_suppr = False

RECETTES = st.session_state.recettes


def persister(recettes, tags=None):
    """Sauvegarde recettes + tags et affiche l'erreur au besoin. Retourne True
    si OK. Sans `tags`, on réutilise le catalogue courant de la session."""
    if tags is None:
        tags = st.session_state.tags
    ok, err = sauvegarder_recettes(recettes, tags)
    if not ok:
        st.error(f"⚠ Sauvegarde échouée — {err}")
    return ok


def _ingredients_depuis_editeur(df):
    """Convertit le tableau édité (data_editor) en liste d'ingrédients propre,
    en ignorant les lignes sans nom. Sert à l'enregistrement ET au
    réordonnancement, pour ne pas perdre les éditions en cours."""
    nouveaux = []
    for ligne in df.to_dict("records"):
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
            "palier": None if (palier is None or palier == "" or pd.isna(palier)) else float(palier),
        })
    return nouveaux


def _etapes_depuis_editeur(df):
    """Convertit le tableau des étapes édité en liste de chaînes propre."""
    return [str(v).strip() for v in df["Étape"].tolist()
            if pd.notna(v) and str(v).strip()]


def _bloc_reordonner(recette, champ, items, labels, k):
    """Liste compacte pour réordonner `recette[champ]` : chaque ligne porte ses
    propres flèches ▲/▼ (manipulation directe, sans étape de sélection).

    `items` est la liste reconstruite depuis l'éditeur (elle contient donc les
    éditions non encore enregistrées) et `labels` les libellés parallèles.

    Un déplacement s'applique EN MÉMOIRE (instantané, aucune écriture réseau) et
    est conservé jusqu'au bouton « 💾 Enregistrer », exactement comme les
    éditions de cellules. On réinitialise l'éditeur concerné (nonce dans sa clé)
    pour resynchroniser le data_editor sur le nouvel ordre sans décaler ses
    modifications internes."""
    n = len(items)
    if n < 2:
        return
    nonce_key = f"ord_nonce_{champ}_{k}"

    def _echanger(i, j):
        items[i], items[j] = items[j], items[i]
        recette[champ] = items
        # Pas de persist ici : l'ordre est gardé en session et écrit au 💾.
        st.session_state[nonce_key] = st.session_state.get(nonce_key, 0) + 1
        st.rerun()

    st.caption("Ordre des lignes — ▲ / ▼ pour déplacer "
               "(pris en compte à l'enregistrement 💾).")
    for i in range(n):
        c_txt, c_up, c_down = st.columns([8, 1, 1])
        c_txt.markdown(
            "<div style=\"font-family:'JetBrains Mono',monospace;font-size:.8rem;"
            "color:#9aa8cf;padding-top:.5rem;white-space:nowrap;overflow:hidden;"
            f"text-overflow:ellipsis;\">{i + 1}. {html_escape(labels[i])}</div>",
            unsafe_allow_html=True)
        if c_up.button("▲", key=f"ord_up_{champ}_{k}_{i}", disabled=(i == 0),
                       use_container_width=True, help="Monter cette ligne"):
            _echanger(i, i - 1)
        if c_down.button("▼", key=f"ord_down_{champ}_{k}_{i}", disabled=(i == n - 1),
                         use_container_width=True, help="Descendre cette ligne"):
            _echanger(i, i + 1)


def _grille_aggrid(df_init, ss_key, configurer):
    """PROTOTYPE — Option B : une seule grille AgGrid qui édite les cellules ET
    réordonne les lignes par glisser (poignée ⠿ sur la 1ʳᵉ colonne).

    L'état de travail (éditions + ordre) vit en session sous `ss_key`, appliqué
    en mémoire jusqu'au bouton « 💾 Enregistrer ». `configurer(gb)` applique les
    réglages de colonnes propres à chaque tableau. Retourne l'objet AgGrid (dont
    `["data"]` = DataFrame courant, `["selected_rows"]` = lignes cochées)."""
    if ss_key not in st.session_state:
        st.session_state[ss_key] = df_init.reset_index(drop=True)
    travail = st.session_state[ss_key]
    # _rowid toujours en dernier : la 1re colonne (visible) garde la case à cocher.
    if "_rowid" in travail.columns:
        travail = travail[[c for c in travail.columns if c != "_rowid"] + ["_rowid"]]

    gb = GridOptionsBuilder.from_dataframe(travail)
    gb.configure_default_column(editable=True, resizable=True, sortable=False,
                                filter=False)
    gb.configure_selection("multiple", use_checkbox=True,
                           header_checkbox=False)
    configurer(gb)
    options = gb.build()
    options["rowDragManaged"] = True      # AgGrid réordonne rowData au glisser
    options["animateRows"] = True
    options["suppressMoveWhenRowDragging"] = False
    options["domLayout"] = "autoHeight"   # la grille s'adapte au nombre de lignes

    # Le nonce force un remontage propre après ajout/suppression (AgGrid recharge
    # alors les données serveur, sans conserver un état client périmé).
    nonce = st.session_state.get(f"{ss_key}_nonce", 0)
    grille = AgGrid(
        travail,
        gridOptions=options,
        key=f"aggrid_{ss_key}_{nonce}",
        update_on=["cellValueChanged", "rowDragEnd", "selectionChanged"],
        data_return_mode=DataReturnMode.AS_INPUT,
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=True,
        theme="streamlit",
    )
    # Persiste l'état courant (ordre glissé + éditions) pour les reruns suivants.
    st.session_state[ss_key] = pd.DataFrame(grille["data"])
    return grille


def _lignes_selectionnees_ids(grille, colonne_id):
    """Renvoie l'ensemble des identifiants de lignes cochées dans une grille
    AgGrid, en tolérant les deux formats de retour (DataFrame ou liste)."""
    sel = grille["selected_rows"]
    if sel is None:
        return set()
    if isinstance(sel, pd.DataFrame):
        return set(sel.get(colonne_id, [])) if not sel.empty else set()
    return {ligne.get(colonne_id) for ligne in sel}


def couleur_de(nom):
    """Couleur associée à un nom de tag (gris par défaut si inconnu)."""
    return index_couleurs(st.session_state.tags).get(_norm_tag(nom),
                                                     COULEUR_TAG_DEFAUT)


def noms_tags():
    """Liste triée des noms de tags du catalogue global."""
    return [t["nom"] for t in st.session_state.tags]


def enregistrer_tags(noms):
    """Convertit une liste de noms saisis (existants ou nouveaux) en noms
    canoniques, en ajoutant au catalogue global tout tag inédit (couleur
    attribuée depuis la palette). Retourne la liste des noms canoniques, sans
    doublon. Met à jour st.session_state.tags (trié)."""
    catalogue = st.session_state.tags
    par_cle = {_norm_tag(t["nom"]): t for t in catalogue}
    canon, vus = [], set()
    for nom in noms:
        nom = (nom or "").strip()
        if not nom:
            continue
        cle = _norm_tag(nom)
        if cle in vus:
            continue
        vus.add(cle)
        if cle in par_cle:
            canon.append(par_cle[cle]["nom"])          # nom canonique existant
        else:
            couleur = PALETTE_TAGS[len(catalogue) % len(PALETTE_TAGS)]
            nouveau = {"nom": nom, "couleur": couleur}
            catalogue.append(nouveau)
            par_cle[cle] = nouveau
            canon.append(nom)
    st.session_state.tags = trier_tags(catalogue)
    return canon


def _renommer_tag_partout(ancien, nouveau):
    """Applique un renommage de tag à toutes les recettes (par clé normalisée)."""
    cle = _norm_tag(ancien)
    for r in st.session_state.recettes:
        r["tags"] = [nouveau if _norm_tag(x) == cle else x
                     for x in r.get("tags", [])]


def _supprimer_tag_partout(nom):
    """Retire un tag du catalogue global ET de toutes les recettes."""
    cle = _norm_tag(nom)
    st.session_state.tags = [t for t in st.session_state.tags
                             if _norm_tag(t["nom"]) != cle]
    for r in st.session_state.recettes:
        r["tags"] = [x for x in r.get("tags", []) if _norm_tag(x) != cle]


@st.dialog("Supprimer le tag")
def _dialog_suppr_tag(nom):
    """Fenêtre de confirmation avant suppression d'un tag partout."""
    st.warning(f"Le tag « {nom} » sera retiré de **toutes les recettes** qui le "
               "portent, et du catalogue partagé. Cette action est définitive.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Oui, supprimer partout", type="primary",
                     use_container_width=True, key="confirm_suppr_tag"):
            _supprimer_tag_partout(nom)
            ok, err = sauvegarder_recettes(st.session_state.recettes,
                                           st.session_state.tags)
            st.session_state.err_save = None if ok else err
            st.rerun()
    with c2:
        if st.button("Annuler", use_container_width=True, key="annuler_suppr_tag"):
            st.rerun()


def chips_tags_html(noms, taille="normal"):
    """Rend une rangée de puces de tags colorées (HTML). `noms` = liste de
    noms de tags de la recette."""
    if not noms:
        return ""
    pad = "3px 10px" if taille == "normal" else "2px 8px"
    fs = ".72rem" if taille == "normal" else ".66rem"
    puces = []
    for nom in sorted(noms, key=_norm_tag):
        c = couleur_de(nom)
        puces.append(
            f'<span style="display:inline-block;font-family:\'JetBrains Mono\','
            f'monospace;font-size:{fs};font-weight:700;letter-spacing:.04em;'
            f'padding:{pad};margin:3px 6px 3px 0;border-radius:999px;'
            f'color:{c};border:1px solid {c};background:{c}1f;">'
            f'{html_escape(nom)}</span>')
    return ('<div style="display:flex;flex-wrap:wrap;align-items:center;'
            'margin-top:4px;">' + "".join(puces) + "</div>")


def recette_vierge(n_total):
    return {
        "titre": f"Nouvelle recette {n_total}" if n_total > 1 else "Nouvelle recette",
        "sous_titre": "À personnaliser",
        "temps_prep": 0,
        "temps_cuisson": 0,
        "base": {"label": "Portions", "unite": "portions", "valeur": 4,
                 "personnes": 4, "max_personnes": 20, "multiples": False},
        "ingredients": [{"nom": "Premier ingrédient", "qte": 1,
                         "unite": "c. à table", "palier": 0.5}],
        "preparation": ["Première étape — écris [Premier ingrédient] pour insérer sa quantité."],
        "tags": [],
    }


CHOIX_RECETTE = (
    '<div class="choix"><div class="t">CHOISIS TA RECETTE</div>'
    '<div class="s">Utilise le sélecteur ci-dessus pour afficher une recette</div></div>'
)


def _creer_recette():
    """Callback : ajoute une recette vierge, l'affiche et efface les filtres.
    Exécuté avant l'instanciation des widgets, donc peut écrire leurs clés."""
    recettes = st.session_state.recettes
    recettes.append(recette_vierge(len(recettes) + 1))
    st.session_state.recherche_titre = ""
    st.session_state.recherche_ingredient = ""
    st.session_state.recette_select = len(recettes) - 1
    st.session_state.confirmer_suppr = False
    ok, err = sauvegarder_recettes(recettes, st.session_state.tags)
    st.session_state.err_save = None if ok else err


def _supprimer_recette():
    """Callback : retire la recette sélectionnée ; plus rien n'est sélectionné."""
    recettes = st.session_state.recettes
    i = st.session_state.sel
    if i is not None and 0 <= i < len(recettes):
        recettes.pop(i)
    st.session_state.recette_select = None
    st.session_state.confirmer_suppr = False
    ok, err = sauvegarder_recettes(recettes, st.session_state.tags)
    st.session_state.err_save = None if ok else err


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE + THÈME
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="grimoire de recettes", page_icon="🛰️",
                   layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500;700&display=swap');

:root{
  --bg:#04060d; --panel:#0b1120; --line:#1e2a45;
  --cyan:#4df3e3; --amber:#ffb454;
  --text:#e9efff; --muted:#7d8cb5;
  /* Champs de saisie / sélection : fond navy un peu plus clair que --panel
     (meilleur confort de lecture) + bordure plus lisible + texte d'invite. */
  --field:#152036; --field-line:#31446b; --field-ph:#93a2c6;
}

/* Fond futuriste — uniquement des couches d'arrière-plan (rien ne recouvre le
   contenu) : halos d'ambiance, grille technique + fines scanlines type HUD. */
.stApp{
  background:
    radial-gradient(1200px 620px at 6% -16%, rgba(77,243,227,.16), transparent 60%),
    radial-gradient(1100px 580px at 110% -8%, rgba(255,180,84,.12), transparent 55%),
    radial-gradient(1100px 900px at 50% 124%, var(--accent-glow,rgba(77,243,227,.10)), transparent 62%),
    repeating-linear-gradient(0deg, rgba(255,255,255,.022) 0 1px, transparent 1px 3px),
    linear-gradient(rgba(77,243,227,.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(77,243,227,.055) 1px, transparent 1px),
    var(--bg);
  background-size:auto,auto,auto,100% 3px,40px 40px,40px 40px,auto;
  background-attachment:fixed,fixed,fixed,fixed,fixed,fixed,fixed;
}
#MainMenu, header, footer{visibility:hidden;}
.block-container{padding-top:2.2rem; padding-bottom:3rem; max-width:980px;}

/* ── En-tête ─────────────────────────────────────────── */
.hero{margin-bottom:1.3rem; position:relative;}
.hero .eyebrow{
  font-family:'JetBrains Mono',monospace; font-size:.8rem; letter-spacing:.46em;
  color:#7af6e9; text-transform:uppercase; margin-bottom:.45rem;
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
.stSelectbox label, [data-testid="stNumberInput"] label, .stTextInput label,
[data-testid="stMultiSelect"] label{
  font-family:'JetBrains Mono',monospace!important; font-size:.68rem!important;
  letter-spacing:.24em!important; text-transform:uppercase!important; color:var(--muted)!important;
}
/* Boîte de saisie / sélection — même fond, bordure, rayon et texte PARTOUT
   (texte, nombre, selectbox ET multiselect). */
.stSelectbox div[data-baseweb="select"] > div,
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
[data-testid="stNumberInput"] input,
.stTextInput input{
  background:var(--field)!important; border:1px solid var(--field-line)!important;
  border-radius:10px!important; color:var(--text)!important;
  font-family:'Inter',sans-serif!important;
}
[data-testid="stNumberInput"] input{font-family:'JetBrains Mono',monospace!important;
  font-size:1.1rem!important; font-weight:700!important;}
[data-testid="stNumberInput"] button{background:var(--field)!important; border-color:var(--field-line)!important; color:var(--text)!important;}

/* Selectbox : texte de la valeur sélectionnée bien lisible (clair) */
.stSelectbox [data-baseweb="select"] > div > div{color:var(--text)!important;}
/* Zone de frappe (texte tapé) des sélecteurs : clair */
.stSelectbox [data-baseweb="select"] input{color:var(--text)!important;}
/* Multiselect : quand il est vide, l'invite « Écris pour voir les tags… » est
   un <div> BaseWeb (pas un input) — ::placeholder ne l'atteint pas. On colore
   donc TOUT le texte de sa zone en gris clair lisible (comme le placeholder de
   « ex. citron, ail… »). Les tags sélectionnés sont des puces stylées à part. */
[data-testid="stMultiSelect"] [data-baseweb="select"] > div *{
  color:var(--field-ph)!important;
}
/* Invites (placeholders) des champs input : même gris clair lisible */
.stTextInput input::placeholder,
[data-testid="stNumberInput"] input::placeholder,
[data-baseweb="select"] input::placeholder{color:var(--field-ph)!important; opacity:1!important;}
/* Icônes (chevron, croix) : teinte discrète mais visible */
[data-baseweb="select"] svg{fill:var(--muted)!important;}

/* Focus : liseré cyan cohérent sur tous les champs */
.stSelectbox div[data-baseweb="select"] > div:focus-within,
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div:focus-within,
[data-testid="stNumberInput"] input:focus, .stTextInput input:focus{
  border-color:var(--cyan)!important; box-shadow:0 0 0 2px rgba(77,243,227,.22)!important;
}

/* Puces de tags sélectionnées dans un multiselect — teinte cyan du thème.
   On force aussi le texte des enfants (span interne) pour qu'il ne soit pas
   grisé par la règle générale d'invite ci-dessus. */
[data-testid="stMultiSelect"] span[data-baseweb="tag"],
[data-testid="stMultiSelect"] span[data-baseweb="tag"] *{
  color:#cfe9ff!important; font-family:'JetBrains Mono',monospace!important;
}
[data-testid="stMultiSelect"] span[data-baseweb="tag"]{
  background:rgba(77,243,227,.14)!important; border:1px solid rgba(77,243,227,.5)!important;
}
[data-testid="stMultiSelect"] span[data-baseweb="tag"] svg{fill:#cfe9ff!important;}

/* Menu déroulant (selectbox & multiselect) — fond sombre, texte clair contrasté.
   Le conteneur du menu ET la liste sont assombris (sélecteurs agnostiques du tag)
   pour être sûr de couvrir le fond blanc par défaut de BaseWeb. Le :has() limite
   l'effet aux popovers qui contiennent une liste (épargne les infobulles « ? » et
   le sélecteur de couleur des tags). */
div[data-baseweb="popover"]:has([role="listbox"]) > div,
[role="listbox"], [data-baseweb="menu"]{
  background:var(--field)!important; border:1px solid var(--field-line)!important;
  border-radius:10px!important; box-shadow:0 12px 34px rgba(0,0,0,.5)!important;
}
/* Filet de sécurité : aucun sous-conteneur blanc ne subsiste dans le menu. */
div[data-baseweb="popover"]:has([role="listbox"]) div{
  background-color:var(--field)!important;
}
/* Les options laissent voir le fond sombre du menu ; texte clair = bon contraste */
[role="listbox"] [role="option"], [data-baseweb="menu"] li{
  background-color:transparent!important; color:var(--text)!important;
  font-family:'Inter',sans-serif!important;
}
[role="listbox"] [role="option"]:hover,
[role="listbox"] [role="option"][aria-selected="true"],
[data-baseweb="menu"] li:hover,
[data-baseweb="menu"] li[aria-selected="true"]{
  background-color:rgba(77,243,227,.20)!important; color:#eaffff!important;
}

/* Onglets — pilules futuristes, une couleur par mode */
/* overflow:visible + padding : la pastille surélevée au survol n'est pas rognée */
.stTabs [data-baseweb="tab-list"]{
  gap:14px; border-bottom:none; margin-bottom:.5rem;
  padding:6px 2px 4px!important; overflow:visible!important;
}
.stTabs [data-baseweb="tab"]{overflow:visible!important;}
.stTabs [data-baseweb="tab"]{
  font-family:'Orbitron',sans-serif!important; font-size:1rem!important;
  font-weight:700!important; letter-spacing:.16em!important;
  border-radius:12px!important; padding:14px 32px!important;
  border:1px solid var(--line)!important; background:var(--panel)!important;
  transition:all .2s!important;
}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"]{
  display:none!important;
}

/* Onglet CUISINE — cyan.
   Au repos : pastille remplie et en relief (look bouton) sans en être une. */
.stTabs button[id$="-tab-0"]{
  color:var(--cyan)!important; border:1px solid rgba(77,243,227,.6)!important;
  background:linear-gradient(135deg, rgba(77,243,227,.16), rgba(77,243,227,.05))!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.07),
             0 0 0 1px rgba(77,243,227,.10),
             0 6px 16px rgba(0,0,0,.4)!important;
  text-shadow:0 0 12px rgba(77,243,227,.4)!important;
}
.stTabs button[id$="-tab-0"]:hover{
  border-color:var(--cyan)!important; transform:translateY(-1px)!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.10),
             0 0 20px rgba(77,243,227,.45), 0 8px 20px rgba(0,0,0,.45)!important;
}
.stTabs button[id$="-tab-0"][aria-selected="true"]{
  color:#04060d!important; border-color:var(--cyan)!important; transform:none!important;
  background:linear-gradient(135deg,#4df3e3,#2bd3c4)!important;
  box-shadow:0 0 28px rgba(77,243,227,.7)!important; text-shadow:none!important;
}

/* Onglet ÉDITION — ambre. */
.stTabs button[id$="-tab-1"]{
  color:var(--amber)!important; border:1px solid rgba(255,180,84,.6)!important;
  background:linear-gradient(135deg, rgba(255,180,84,.16), rgba(255,180,84,.05))!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.07),
             0 0 0 1px rgba(255,180,84,.10),
             0 6px 16px rgba(0,0,0,.4)!important;
  text-shadow:0 0 12px rgba(255,180,84,.4)!important;
}
.stTabs button[id$="-tab-1"]:hover{
  border-color:var(--amber)!important; transform:translateY(-1px)!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.10),
             0 0 20px rgba(255,180,84,.45), 0 8px 20px rgba(0,0,0,.45)!important;
}
.stTabs button[id$="-tab-1"][aria-selected="true"]{
  color:#04060d!important; border-color:var(--amber)!important; transform:none!important;
  background:linear-gradient(135deg,#ffb454,#ff9d2e)!important;
  box-shadow:0 0 28px rgba(255,180,84,.65)!important; text-shadow:none!important;
}

/* Fond teinté selon le mode actif — repère cuisine / édition bien marqué.
   Teal profond en cuisine, ambre profond en édition (dégradé + halo interne). */
.stApp:has(button[id$="-tab-0"][aria-selected="true"]){
  --bg:#03181a;
  --accent-glow:rgba(77,243,227,.14);
  box-shadow:inset 0 0 320px rgba(77,243,227,.20),
             inset 0 140px 260px -160px rgba(77,243,227,.28)!important;
}
.stApp:has(button[id$="-tab-1"][aria-selected="true"]){
  --bg:#1a1204;
  --accent-glow:rgba(255,180,84,.12);
  box-shadow:inset 0 0 320px rgba(255,180,84,.18),
             inset 0 140px 260px -160px rgba(255,180,84,.24)!important;
}

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
  font-family:'JetBrains Mono',monospace!important; font-size:.8rem!important;
  color:#9aa8cf!important; letter-spacing:.06em;
}
div[data-testid="stAlert"]{
  background:var(--panel)!important; border:1px solid var(--line)!important;
  border-radius:12px!important; color:var(--text)!important;
}

/* Case à cocher (ex. « ajuster par multiples ») — libellé bien lisible :
   plus grand, plus clair, et case cyan un peu plus visible. */
[data-testid="stCheckbox"] label{
  font-size:1rem!important; color:var(--text)!important; font-weight:600!important;
}
[data-testid="stCheckbox"] label p,
[data-testid="stCheckbox"] label div{
  font-size:1rem!important; color:var(--text)!important; font-weight:600!important;
}
[data-testid="stCheckbox"] [data-baseweb="checkbox"] > span:first-child,
[data-testid="stCheckbox"] [role="checkbox"]{
  border-color:var(--cyan)!important;
}

/* Message « choisis ta recette » lorsqu'aucune recette n'est sélectionnée */
.choix{text-align:center;padding:2.8rem 1rem;border:1px dashed #26355c;border-radius:16px;
  background:rgba(77,243,227,.03);margin-top:1rem;}
.choix .t{font-family:'Orbitron',sans-serif;font-weight:900;font-size:1.4rem;color:var(--cyan);
  letter-spacing:.12em;text-shadow:0 0 18px rgba(77,243,227,.5);}
.choix .s{font-family:'JetBrains Mono',monospace;font-size:.72rem;color:var(--muted);
  letter-spacing:.16em;margin-top:.6rem;text-transform:uppercase;}

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
  <h1>GRIMOIRE DE RECETTES</h1>
  <p>Ajuste les portions en cuisine, ou passe en mode édition pour modifier tes recettes.
     <span style="font-family:'JetBrains Mono',monospace;font-size:.68rem;color:#4df3e3;
     letter-spacing:.1em;white-space:nowrap;">{badge}</span></p>
</div>
""", unsafe_allow_html=True)

# ── Toggle « écran toujours allumé » (Wake Lock API — mobile / tablette) ───────
components.html(
    """
<div id="wl-wrap">
  <button id="wl-btn" type="button" aria-pressed="false">
    <span class="wl-dot"></span>
    <span class="wl-label">Écran toujours allumé</span>
    <span class="wl-state">OFF</span>
  </button>
  <p id="wl-note">Empêche la mise en veille de l'écran pendant que tu cuisines.</p>
</div>
<style>
  *{box-sizing:border-box;}
  body{margin:0;background:transparent;font-family:'JetBrains Mono',ui-monospace,monospace;}
  #wl-wrap{display:flex;flex-direction:column;gap:.35rem;align-items:flex-start;}
  #wl-btn{
    display:inline-flex;align-items:center;gap:.6rem;cursor:pointer;
    padding:.5rem .9rem;border-radius:999px;
    background:#12161c;border:1px solid #263038;color:#c9d4d6;
    font-family:inherit;font-size:.74rem;letter-spacing:.08em;
    transition:border-color .2s,color .2s,box-shadow .2s;
  }
  #wl-btn:hover{border-color:#4df3e3;}
  #wl-btn .wl-dot{
    width:9px;height:9px;border-radius:50%;background:#3a464e;
    transition:background .2s,box-shadow .2s;flex:0 0 auto;
  }
  #wl-btn .wl-state{
    font-size:.66rem;padding:.1rem .45rem;border-radius:999px;
    background:#1c232a;color:#7c8b90;letter-spacing:.1em;
  }
  #wl-btn.on{border-color:#4df3e3;color:#e6fffb;box-shadow:0 0 0 1px rgba(77,243,227,.25);}
  #wl-btn.on .wl-dot{background:#4df3e3;box-shadow:0 0 10px 2px rgba(77,243,227,.6);}
  #wl-btn.on .wl-state{background:rgba(77,243,227,.15);color:#4df3e3;}
  #wl-btn:disabled{opacity:.5;cursor:not-allowed;}
  #wl-note{margin:0;font-size:.62rem;color:#6b7a80;letter-spacing:.04em;}
</style>
<script>
  const btn   = document.getElementById('wl-btn');
  const state = btn.querySelector('.wl-state');
  const note  = document.getElementById('wl-note');
  let sentinel = null;
  let wanted   = false;

  if (!('wakeLock' in navigator)) {
    btn.disabled = true;
    state.textContent = 'N/D';
    note.textContent = "Fonction non supportée par ce navigateur (essaie Chrome/Safari sur mobile).";
  }

  async function acquire() {
    try {
      sentinel = await navigator.wakeLock.request('screen');
      sentinel.addEventListener('release', () => {
        // Relâché par le système (ex : onglet masqué) — on note l'état off visuel.
        if (!document.hidden) return;
      });
      setUI(true);
    } catch (err) {
      wanted = false;
      setUI(false);
      note.textContent = "Impossible d'activer : " + err.message;
    }
  }

  async function release() {
    try { if (sentinel) { await sentinel.release(); } } catch (e) {}
    sentinel = null;
    setUI(false);
  }

  function setUI(on) {
    btn.classList.toggle('on', on);
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    state.textContent = on ? 'ON' : 'OFF';
  }

  btn.addEventListener('click', async () => {
    if (btn.disabled) return;
    wanted = !wanted;
    if (wanted) { await acquire(); } else { await release(); }
  });

  // Réacquiert le verrou quand l'onglet redevient visible (le système le relâche
  // automatiquement lorsqu'on quitte l'app puis qu'on y revient).
  document.addEventListener('visibilitychange', async () => {
    if (wanted && sentinel === null && document.visibilityState === 'visible') {
      await acquire();
    }
  });
</script>
""",
    height=78,
)

if st.session_state.erreur_chargement:
    st.error(f"⚠ {st.session_state.erreur_chargement} Les recettes affichées sont "
             "les valeurs par défaut ; les sauvegardes échoueront tant que le "
             "problème n'est pas réglé.")

# ─────────────────────────────────────────────────────────────────────────────
#  SÉLECTION DE RECETTE + NOUVELLE RECETTE
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.get("err_save"):
    st.error(f"⚠ Sauvegarde échouée — {st.session_state.err_save}")
    st.session_state.err_save = None

if not RECETTES:
    st.info("Aucune recette au menu. Crée ta première recette ci-dessous.")
    st.button("＋ Nouvelle recette", type="primary", use_container_width=True,
              on_click=_creer_recette)
    st.stop()

if st.session_state.sel is not None:
    st.session_state.sel = min(st.session_state.sel, len(RECETTES) - 1)

def _reset_filtres():
    st.session_state.recherche_titre = ""
    st.session_state.recherche_ingredient = ""
    st.session_state.recherche_tags = []
    st.session_state.recette_select = None      # aucune recette sélectionnée
    st.session_state.confirmer_suppr = False


with st.expander("🔍  Choisir ou rechercher une recette (mode cuisine ou édition)",
                 expanded=True):
    f1, f2 = st.columns(2)
    with f1:
        recherche = st.text_input(
            "Rechercher une recette", key="recherche_titre",
            placeholder="Nom ou sous-titre…",
            help="Filtre les recettes dont le titre ou le sous-titre contient ce texte.")
    with f2:
        filtre_ing = st.text_input(
            "Contient l'ingrédient", key="recherche_ingredient",
            placeholder="ex. citron, ail…",
            help="N'affiche que les recettes qui contiennent cet ingrédient.")

    filtre_tags = st.multiselect(
        "Filtrer par tags", options=noms_tags(), key="recherche_tags",
        placeholder="Écris pour voir les tags…",
        help="N'affiche que les recettes portant TOUS les tags choisis. "
             "Tape du texte pour retrouver un tag existant.")

    q_titre = recherche.strip().lower()
    q_ing = filtre_ing.strip().lower()
    q_tags = {_norm_tag(t) for t in filtre_tags}

    st.button("↺ Réinitialiser les filtres", key="reset_filtres",
              on_click=_reset_filtres, disabled=not (q_titre or q_ing or q_tags),
              help="Efface la recherche, l'ingrédient et les tags.")

    def _correspond(r):
        if q_titre and (q_titre not in r.get("titre", "").lower()
                        and q_titre not in r.get("sous_titre", "").lower()):
            return False
        if q_ing and not any(q_ing in (ing.get("nom") or "").lower()
                             for ing in r.get("ingredients", [])):
            return False
        if q_tags:                                   # ET : tous les tags requis
            tags_r = {_norm_tag(t) for t in r.get("tags", [])}
            if not q_tags.issubset(tags_r):
                return False
        return True

    # Recettes triées automatiquement par ordre alphabétique de titre.
    indices = sorted((i for i, r in enumerate(RECETTES) if _correspond(r)),
                     key=lambda i: (RECETTES[i].get("titre") or "").casefold())

    if not indices:
        st.info("Aucune recette ne correspond à ta recherche.")
        st.session_state.sel = None
    else:
        # VIDE = première option « ligne vide » (chaîne vide, distincte des index
        # entiers). C'est un vrai choix sélectionnable — contrairement à None que
        # Streamlit interprète comme « aucune sélection » (placeholder).
        VIDE = ""
        # None hérité (reset/suppression) ou sélection hors résultats -> ligne vide.
        if (st.session_state.recette_select is None
                or (st.session_state.recette_select != VIDE
                    and st.session_state.recette_select not in indices)):
            st.session_state.recette_select = VIDE
        idx = st.selectbox(
            "Recettes disponibles", options=[VIDE] + indices,
            format_func=lambda i: "" if i == VIDE else RECETTES[i]["titre"],
            key="recette_select",
        )
        sel = None if idx == VIDE else idx
        if sel != st.session_state.sel:
            st.session_state.sel = sel
            st.session_state.confirmer_suppr = False
        if len(indices) < len(RECETTES):
            st.markdown(
                f"<p style=\"font-family:'JetBrains Mono',monospace;font-size:.8rem;"
                f"color:#7d8cb5;letter-spacing:.06em;margin:.35rem 0 0;\">"
                f"{len(indices)} recette{'s' if len(indices) > 1 else ''} "
                f"sur {len(RECETTES)} affichée"
                f"{'s' if len(indices) > 1 else ''}.</p>",
                unsafe_allow_html=True)

recette = RECETTES[st.session_state.sel] if st.session_state.sel is not None else None
base = recette["base"] if recette else None

onglet_cuisine, onglet_edition = st.tabs(["◈  CUISINE", "⚙  ÉDITION"])

# ═════════════════════════════════════════════════════════════════════════════
#  ONGLET CUISINE — mise à l'échelle + checklist
# ═════════════════════════════════════════════════════════════════════════════
with onglet_cuisine:
  if recette is None:
    st.markdown(CHOIX_RECETTE, unsafe_allow_html=True)
  else:
    # Le curseur = NOMBRE DE PERSONNES. La « valeur de référence » (rendement)
    # correspond au nombre de personnes de référence ; tout est mis à l'échelle
    # proportionnellement au nombre de personnes choisi.
    personnes_ref = int(base.get("personnes", 4) or 4)
    if personnes_ref < 1:
        personnes_ref = 1
    max_pers = int(base.get("max_personnes", 20) or 20)
    if max_pers < personnes_ref:
        max_pers = max(personnes_ref, 20)
    par_multiples = bool(base.get("multiples", False))

    rendement_ref = float(base.get("valeur") or 0)      # pour personnes_ref pers.
    tp = int(recette.get("temps_prep", 0) or 0)
    tc = int(recette.get("temps_cuisson", 0) or 0)
    unite = html_escape(base.get("unite") or "")
    label = html_escape(base.get("label") or "Rendement")

    # ── Réglage du nombre de personnes : widget Streamlit interactif, placé
    #    juste au-dessus de la carte. Le récapitulatif (« sommaire »), lui, est
    #    intégré DANS la carte comme première section (voir plus bas).
    c_pers, _ = st.columns([1, 1.3])
    with c_pers:
        if par_multiples:
            # Ajustement par multiples entiers : le champ ne saute que par
            # paliers de personnes_ref (ex. 4 → 8 → 12), jamais 5 ou 6.
            max_mult_pers = (max_pers // personnes_ref) * personnes_ref
            if max_mult_pers < personnes_ref:
                max_mult_pers = personnes_ref
            cible_pers = st.number_input(
                "🍽️  Nombre de personnes",
                min_value=personnes_ref, max_value=max_mult_pers,
                value=personnes_ref, step=personnes_ref,
                key=f"cible_{st.session_state.sel}",
                help=f"Recette ajustée par multiples : par paliers de "
                     f"{personnes_ref} personne{'s' if personnes_ref > 1 else ''} "
                     f"(×1, ×2, ×3…).")
            # On garantit un multiple exact même si une valeur est saisie à la main.
            cible_pers = int(round(cible_pers / personnes_ref)) * personnes_ref
            cible_pers = max(personnes_ref, min(cible_pers, max_mult_pers))
            # Note à .8rem, bien claire (couleur --text plutôt que muted).
            st.markdown(
                f"<div style=\"font-family:'JetBrains Mono',monospace;"
                f"font-size:.8rem;font-weight:600;color:var(--text);"
                f"letter-spacing:.06em;margin-top:-.35rem;\">"
                f"⏫ Ajusté par paliers de {personnes_ref} "
                f"personne{'s' if personnes_ref > 1 else ''} "
                f"(×{cible_pers // personnes_ref}).</div>",
                unsafe_allow_html=True)
        else:
            cible_pers = st.number_input(
                "🍽️  Nombre de personnes",
                min_value=1, max_value=max_pers,
                value=min(personnes_ref, max_pers), step=1,
                key=f"cible_{st.session_state.sel}",
                help=f"Recette de référence pour {personnes_ref} personne"
                     f"{'s' if personnes_ref > 1 else ''}.")

    facteur = cible_pers / personnes_ref if personnes_ref else 1.0
    rendement = rendement_ref * facteur                 # pour cible_pers pers.
    portion = rendement_ref / personnes_ref if personnes_ref else 0

    # Récapitulatif « sommaire » — rendu DANS la carte (classes .meta / .chip).
    chips = [f'<span class="chip chip-ref">Personnes · <b>{cible_pers:g}</b></span>']
    if par_multiples:
        chips.append(f'<span class="chip">Multiple · '
                     f'<b>×{cible_pers // personnes_ref}</b></span>')
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
    somm_body = f'<div class="meta">{"".join(chips)}</div>'
    if rendement_ref > 0:
        somm_body += (
            f'<div class="sommaire-rel">Référence : '
            f'<b>{rendement_ref:g} {unite}</b> pour '
            f'<b>{personnes_ref} personne{"s" if personnes_ref > 1 else ""}</b>'
            f' · soit <b>{portion:g} {unite}</b> par personne</div>')
    # Tags de la recette (puces colorées), affichés dans le sommaire.
    if recette.get("tags"):
        somm_body += (
            '<div class="tags-titre">Tags</div>'
            + chips_tags_html(recette["tags"]))

    # Index des ingrédients pour l'auto-ajustement dans les étapes
    index_ing = {ing["nom"].strip().lower(): ing
                 for ing in recette["ingredients"] if ing.get("nom")}

    # Section INGRÉDIENTS — on ouvre par une ligne « rendement » : l'étiquette
    # de base et sa valeur de référence, mise à l'échelle comme les ingrédients
    # (générée automatiquement, non cochable).
    lignes_ing = ""
    if rendement_ref > 0:
        lignes_ing += f"""
        <div class="rendement">
          <span class="r-ico">◈</span>
          <span class="nom">{label}</span>
          <span class="qte"><b>{rendement:g}</b> {unite}</span>
        </div>"""
    for ing in recette["ingredients"]:
        q = jolie_qte(echelle(ing, facteur))
        au_gout = ing.get("qte") is None
        unite_ing = "" if au_gout else html_escape(ing.get("unite") or "")
        cls_qte = "qte gout" if au_gout else "qte"
        lignes_ing += f"""
        <div class="ing" onclick="toggle(this)">
          <span class="box"></span>
          <span class="nom">{html_escape(ing['nom'])}</span>
          <span class="{cls_qte}"><b>{q}</b> {unite_ing}</span>
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

    # ── Sections repliables du bloc interactif. Le Sommaire est ouvert par
    #    défaut (collapsed=False) pour être immédiatement visible ; les autres
    #    sont fermées.
    def section_block(cls, ico, titre, count_txt, body, collapsed=True):
        etat = " collapsed" if collapsed else ""
        cache = " hidden" if collapsed else ""
        return (f'<div class="section {cls}{etat}" onclick="toggleSec(this)">'
                f'<span class="sec-ico">{ico}</span>'
                f'<span class="sec-txt">{titre}</span>'
                f'<span class="sec-count">{count_txt}</span>'
                f'<span class="sec-chevron">▾</span></div>'
                f'<div class="sec-body{cache}">{body}</div>')

    somm_count = (f'×{cible_pers // personnes_ref}' if par_multiples
                  else f'{cible_pers:g} pers.')
    rows = section_block("sec-som", "◈", "Sommaire et configuration de la recette",
                         somm_count, somm_body, collapsed=False)
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
.chip{font-family:'JetBrains Mono',monospace;font-size:.82rem;color:#9fb0d8;
  border:1px solid #1e2a45;border-radius:999px;padding:5px 12px;background:rgba(77,243,227,.05)}
.chip b{color:#ffb454}
.chip-ref{border-color:#4df3e3;background:rgba(77,243,227,.12);color:#cfe9ff;
  box-shadow:0 0 14px rgba(77,243,227,.25)}
.chip-ref b{color:#4df3e3;text-shadow:0 0 12px rgba(77,243,227,.6)}
.sommaire-rel{font-family:'Inter',sans-serif;font-size:.82rem;color:#9fb0d8;
  margin-top:11px;padding:9px 12px;border-radius:10px;border:1px dashed #26355c;
  background:rgba(77,243,227,.04)}
.sommaire-rel b{color:#ffb454;font-weight:700}
.tags-titre{font-family:'JetBrains Mono',monospace;font-size:.64rem;letter-spacing:.2em;
  text-transform:uppercase;color:#7d8cb5;margin:12px 0 2px}
.prog{height:4px;background:#141d34;border-radius:999px;margin-top:15px;overflow:hidden}
.progfill{height:100%;width:0;background:linear-gradient(90deg,#4df3e3,#ffb454);
  box-shadow:0 0 14px rgba(77,243,227,.6);transition:width .35s ease}
.count{font-family:'JetBrains Mono',monospace;font-size:.8rem;color:#9aa8cf;margin-top:7px;letter-spacing:.12em}

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
/* Ligne « aliment principal » (étiquette de base + valeur de référence mise à
   l'échelle, non cochable). Rendu à plat, exactement comme un ingrédient — pas
   d'encadré ni de fond — mais en doré. */
.rendement{display:flex;align-items:center;gap:12px;padding:13px 12px;
  border-radius:11px;border:1px solid transparent}
.rendement .r-ico{width:20px;flex:0 0 20px;text-align:center;color:#ffb454;
  font-size:1.05rem;line-height:1}
/* Font strictement identique aux ingrédients de base (.nom), seule la couleur
   change : doré. */
.rendement .nom{flex:1;font-family:'Inter',sans-serif;font-size:1rem;font-weight:500;
  color:#ffb454;transition:all .18s;min-width:0;overflow-wrap:break-word}
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
.sec-som .sec-txt{letter-spacing:.05em}   /* titre long : moins d'interlettrage */
.sec-som .meta{padding-top:2px}
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
/* Variante « préparation terminée » — teinte ambre (comme la section Préparation) */
.victoire.prep .v-cadre img{border-color:#ffb454;box-shadow:0 0 34px rgba(255,180,84,.55)}
.victoire.prep .v-titre{color:#ffb454;text-shadow:0 0 18px rgba(255,180,84,.7)}
@media (max-width:640px){
  .head{padding:16px 14px 13px}
  .rtitle{font-size:1.08rem}
  .rsub{font-size:.82rem}
  .chip{font-size:.74rem;padding:4px 9px}
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
  <div class="victoire" id="victoire-ing" onclick="fermer('ing')">
    <div class="v-cadre">
      <img src="__GIF_ING__" alt="Mise en place complète !">
      <div class="v-titre">MISE EN PLACE COMPLÈTE</div>
      <div class="v-sous">Tous les ingrédients sont prêts · touche pour fermer</div>
    </div>
  </div>
  <div class="victoire prep" id="victoire-prep" onclick="fermer('prep')">
    <div class="v-cadre">
      <img src="__GIF_PREP__" alt="Préparation terminée !">
      <div class="v-titre">BON APPÉTIT !</div>
      <div class="v-sous">Toutes les étapes sont faites · touche pour fermer</div>
    </div>
  </div>
</div>
<script>
var fermeIng=false, fermePrep=false;
// Ajuste la hauteur de l'iframe au contenu réellement visible (sections repliées
// ou dépliées) pour éviter tout espace vide. Sans effet si l'accès à l'iframe
// parente est refusé : la hauteur de repli sert alors de valeur fixe.
function resizeFrame(){
  try{
    if(window.frameElement){
      window.frameElement.style.height=document.documentElement.scrollHeight+'px';
    }
  }catch(e){}
}
function toggle(el){el.classList.toggle('done');maj();}
// Clé stable par section (sec-som / sec-ing / sec-prep) pour mémoriser son état.
function cleSection(el){
  var m=(el.className||'').match(/sec-[a-z]+/);
  return m ? 'grimoire_sec_'+m[0] : null;
}
function memoriser(el){
  var cle=cleSection(el);
  if(!cle) return;
  try{ sessionStorage.setItem(cle, el.classList.contains('collapsed')?'0':'1'); }catch(e){}
}
function toggleSec(el){
  el.classList.toggle('collapsed');
  var body=el.nextElementSibling;
  if(body && body.classList.contains('sec-body')){body.classList.toggle('hidden');}
  memoriser(el);
  resizeFrame();
}
// Restaure l'état déplié/replié mémorisé : l'iframe étant régénérée à chaque
// rerun Streamlit (ex. clic sur +/- du « nombre de personnes »), sans cela les
// sections ingrédients / préparation se refermeraient à chaque ajustement.
function restaurerSections(){
  var secs=document.querySelectorAll('.section');
  for(var i=0;i<secs.length;i++){
    var cle=cleSection(secs[i]);
    if(!cle) continue;
    var v=null;
    try{ v=sessionStorage.getItem(cle); }catch(e){}
    if(v===null) continue;                       // pas d'état mémorisé -> défaut
    var ouvrir=(v==='1');
    var body=secs[i].nextElementSibling;
    secs[i].classList.toggle('collapsed', !ouvrir);
    if(body && body.classList.contains('sec-body')){ body.classList.toggle('hidden', !ouvrir); }
  }
  resizeFrame();
}
function estFait(el){return el.classList.contains('done');}
function maj(){
  // Progression globale (barre + compteur) sur ingrédients ET étapes.
  var items=Array.prototype.slice.call(document.querySelectorAll('.ing'));
  var d=items.filter(estFait).length;
  document.getElementById('cnt').textContent=d+' / '+items.length+' \\u00e9l\\u00e9ments coch\\u00e9s';
  document.getElementById('fill').style.width=(items.length?d/items.length*100:0)+'%';

  // Victoires par section : ingrédients (.ing sans .step) et préparation (.step).
  var ings=Array.prototype.slice.call(document.querySelectorAll('.ing:not(.step)'));
  var steps=Array.prototype.slice.call(document.querySelectorAll('.ing.step'));
  var ingComplet=ings.length>0 && ings.every(estFait);
  var prepComplet=steps.length>0 && steps.every(estFait);
  if(!ingComplet){fermeIng=false;}
  if(!prepComplet){fermePrep=false;}
  // La préparation (fin de recette) a priorité si les deux sont complètes.
  var montrePrep=prepComplet && !fermePrep;
  var montreIng=ingComplet && !fermeIng && !montrePrep;
  document.getElementById('victoire-prep').classList.toggle('visible', montrePrep);
  document.getElementById('victoire-ing').classList.toggle('visible', montreIng);
}
function fermer(quoi){
  if(quoi==='prep'){fermePrep=true;}else{fermeIng=true;}
  maj();
}
window.addEventListener('load', restaurerSections);
window.addEventListener('load', resizeFrame);
window.addEventListener('resize', resizeFrame);
restaurerSections();
resizeFrame();
</script></body></html>
"""

    html = (TEMPLATE
            .replace("__TITRE__", html_escape(recette["titre"]))
            .replace("__SOUS__", html_escape(recette.get("sous_titre", "")))
            .replace("__N__", str(n))
            .replace("__GIF_ING__", gif_src(GIF_INGREDIENTS_FICHIER))
            .replace("__GIF_PREP__", gif_src(GIF_PREPARATION_FICHIER))
            .replace("__ROWS__", rows))

    # Hauteur de repli (les sections sont fermées par défaut). Si le
    # redimensionnement auto de l'iframe fonctionne, elle grandit à l'ouverture
    # d'une section ; sinon cette valeur (contenu déplié) évite toute coupure.
    hauteur = (290
               + 210                                    # section Sommaire (dépliée)
               + (48 if recette.get("tags") else 0)     # puces de tags
               + (60 if rendement_ref > 0 else 0)       # ligne « rendement »
               + (66 + n_ing * 60 if n_ing else 0)
               + (66 + n_prep * 92 if n_prep else 0))
    components.html(html, height=hauteur, scrolling=True)

# ═════════════════════════════════════════════════════════════════════════════
#  ONGLET ÉDITION — modifier / ajouter / retirer / supprimer
# ═════════════════════════════════════════════════════════════════════════════
with onglet_edition:
    st.button("＋ Nouvelle recette", use_container_width=True,
              key="nouvelle_edition", on_click=_creer_recette,
              help="Ajouter une recette vierge au menu")

    # ── Panneau de gestion des tags (catalogue partagé) ──────────────────────
    # Toujours accessible en édition, même sans recette sélectionnée.
    with st.expander(f"🏷️  Gérer les tags partagés ({len(st.session_state.tags)})",
                     expanded=False):
        st.caption("Ces tags sont communs à tout le monde. Renomme un tag ou "
                   "change sa couleur, puis enregistre : le changement se "
                   "propage à toutes les recettes. Pour créer un tag, écris-le "
                   "directement sur une recette (champ « Tags de cette recette »).")
        if not st.session_state.tags:
            st.info("Aucun tag pour l'instant. Ajoute-en un depuis une recette.")
        else:
            noms_saisis, cols_saisies, cles = [], [], []
            for t in st.session_state.tags:
                cle = _norm_tag(t["nom"])
                cles.append(cle)
                gc, gn, gd = st.columns([0.7, 3, 1])
                with gc:
                    couleur = st.color_picker(
                        "Couleur", value=t.get("couleur") or COULEUR_TAG_DEFAUT,
                        key=f"tagcol_{cle}", label_visibility="collapsed")
                with gn:
                    nom_saisi = st.text_input(
                        "Nom du tag", value=t["nom"], key=f"tagname_{cle}",
                        label_visibility="collapsed")
                with gd:
                    if st.button("🗑", key=f"deltag_{cle}",
                                 help=f"Supprimer « {t['nom']} » partout",
                                 use_container_width=True):
                        _dialog_suppr_tag(t["nom"])
                noms_saisis.append(nom_saisi)
                cols_saisies.append(couleur)

            if st.button("💾 Enregistrer les tags", type="primary",
                         use_container_width=True, key="save_tags"):
                anciens = [t["nom"] for t in st.session_state.tags]
                nouveau_cat, renommages, vus, err_tag = [], [], set(), None
                for ancien, nom_saisi, couleur in zip(anciens, noms_saisis,
                                                      cols_saisies):
                    nv = (nom_saisi or "").strip()
                    if not nv:
                        err_tag = "Un tag ne peut pas avoir un nom vide."
                        break
                    if _norm_tag(nv) in vus:
                        err_tag = f"Deux tags portent le même nom « {nv} »."
                        break
                    vus.add(_norm_tag(nv))
                    nouveau_cat.append({"nom": nv, "couleur": couleur})
                    if nv != ancien:
                        renommages.append((ancien, nv))
                if err_tag:
                    st.error(err_tag)
                else:
                    for ancien, nv in renommages:            # propage aux recettes
                        _renommer_tag_partout(ancien, nv)
                    st.session_state.tags = trier_tags(nouveau_cat)
                    if persister(RECETTES):
                        st.success("Tags enregistrés ✓")
                        st.rerun()

    if recette is None:
        st.markdown(CHOIX_RECETTE, unsafe_allow_html=True)
        st.stop()

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
        b_multiples = st.checkbox(
            "Ajuster uniquement par multiples de la recette",
            value=bool(base.get("multiples", False)), key=f"bmul_{k}",
            help="Utile en pâtisserie : en cuisine, le nombre de personnes ne "
                 "saute que par paliers de la valeur de référence (ex. 4 → 8 → 12), "
                 "jamais 5 ou 6, pour garder des proportions exactes.")
        st.caption("L'élément de base ci-dessous est obligatoire : chaque recette "
                   "doit avoir une étiquette de rendement, une valeur de référence "
                   "(> 0) et une unité — c'est ce qui s'ajuste avec le nombre de "
                   "personnes en cuisine.")
        b1, b2, b3 = st.columns([1.4, 1, 0.9])
        with b1:
            b_label = st.text_input("Étiquette du rendement * (ex. Poids de poulet)",
                                    value=base.get("label", ""), key=f"bl_{k}",
                                    help="Obligatoire. Ce que produit la recette "
                                         "(ex. « Poids de viande », « Volume », "
                                         "« Rendement »).")
        with b2:
            b_val = st.number_input(
                "Valeur de référence *", min_value=0.0, step=1.0,
                value=float(base.get("valeur") or 0), key=f"bv_{k}",
                help="Obligatoire (> 0). Rendement total pour le nombre de "
                     "personnes de référence ; s'ajuste avec le nombre de personnes.")
        with b3:
            b_unite = st.text_input("Unité *", value=base.get("unite", ""),
                                    key=f"bu_{k}",
                                    help="Obligatoire (ex. g, ml, biscuits, portions).")
        if b_personnes and b_val:
            st.caption(f"→ soit {b_val / b_personnes:g} {b_unite or ''}".rstrip()
                       + " par personne.")

        st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
        # Défaut = tags déjà appliqués ; on complète les options avec ces valeurs
        # au cas (rare) où l'une ne serait pas dans le catalogue courant.
        opts_tags = noms_tags()
        for t in recette.get("tags", []):
            if _norm_tag(t) not in {_norm_tag(o) for o in opts_tags}:
                opts_tags.append(t)
        tags_appliques = st.multiselect(
            "Tags de cette recette",
            options=sorted(opts_tags, key=_norm_tag),
            default=list(recette.get("tags", [])),
            key=f"rtags_{k}", accept_new_options=True,
            placeholder="Écris un tag existant ou un nouveau…",
            help="Choisis des tags existants ou écris-en un nouveau (il sera "
                 "ajouté au catalogue partagé lors de l'enregistrement). "
                 "Une couleur lui est attribuée automatiquement ; tu peux la "
                 "changer dans « Gérer les tags ».")
        if tags_appliques:
            st.markdown(chips_tags_html(tags_appliques), unsafe_allow_html=True)

    with st.expander(f"🧺  Ingrédients ({len(recette['ingredients'])})",
                     expanded=True):
        st.caption("PROTOTYPE AgGrid — double-clique une cellule pour l'éditer · "
                   "glisse la poignée ⠿ (à gauche du nom) pour changer l'ordre · "
                   "coche des lignes puis 🗑 pour les retirer · quantité vide = "
                   "« au goût ». Pris en compte à l'enregistrement 💾.")

        ss_ing = f"agg_ing_{k}"
        df_ing = pd.DataFrame(
            [
                {
                    "Ingrédient": ing.get("nom", ""),
                    "Quantité": ing.get("qte"),
                    "Unité": ing.get("unite", ""),
                    "Palier": ing.get("palier"),
                    "_rowid": str(i),
                }
                for i, ing in enumerate(recette["ingredients"])
            ],
            # _rowid en dernier : la 1re colonne (visible) porte la case à cocher.
            columns=["Ingrédient", "Quantité", "Unité", "Palier", "_rowid"],
        )

        def _cfg_ing(gb):
            gb.configure_column("_rowid", hide=True, editable=False)
            gb.configure_column("Ingrédient", rowDrag=True, editable=True, flex=3)
            gb.configure_column("Quantité", editable=True, flex=1,
                                type=["numericColumn"])
            gb.configure_column("Unité", editable=True, flex=1)
            gb.configure_column("Palier", editable=True, flex=1,
                                cellEditor="agSelectCellEditor",
                                cellEditorParams={"values": ["", "0.25", "0.5", "1.0"]})

        grille_ing = _grille_aggrid(df_ing, ss_ing, _cfg_ing)
        edite = pd.DataFrame(grille_ing["data"])

        ca, cb = st.columns(2)
        if ca.button("＋ Ajouter un ingrédient", key=f"add_ing_{k}",
                     use_container_width=True):
            seq = st.session_state.get(f"{ss_ing}_seq", 0) + 1
            st.session_state[f"{ss_ing}_seq"] = seq
            st.session_state[ss_ing] = pd.concat(
                [edite, pd.DataFrame([{"Ingrédient": "", "Quantité": None,
                                       "Unité": "", "Palier": None,
                                       "_rowid": f"n{seq}"}])],
                ignore_index=True)
            st.session_state[f"{ss_ing}_nonce"] = \
                st.session_state.get(f"{ss_ing}_nonce", 0) + 1
            st.rerun()
        if cb.button("🗑 Retirer les lignes cochées", key=f"del_ing_{k}",
                     use_container_width=True):
            ids = _lignes_selectionnees_ids(grille_ing, "_rowid")
            if ids:
                st.session_state[ss_ing] = edite[~edite["_rowid"].isin(ids)] \
                    .reset_index(drop=True)
                st.session_state[f"{ss_ing}_nonce"] = \
                    st.session_state.get(f"{ss_ing}_nonce", 0) + 1
                st.rerun()
            else:
                st.info("Coche d'abord au moins une ligne (case à gauche), "
                        "puis clique 🗑.")

    with st.expander(f"🍳  Préparation ({len(recette.get('preparation', []))} étape"
                     f"{'s' if len(recette.get('preparation', [])) > 1 else ''})",
                     expanded=True):
        st.caption("PROTOTYPE AgGrid — double-clique pour éditer l'étape · glisse "
                   "la poignée ⠿ pour réordonner · coche + 🗑 pour retirer · écris "
                   "[nom d'ingrédient] entre crochets pour insérer sa quantité.")

        ss_prep = f"agg_prep_{k}"
        df_prep = pd.DataFrame(
            [{"Étape": e, "_rowid": str(i)}
             for i, e in enumerate(recette.get("preparation", []))],
            # _rowid en dernier : la 1re colonne (visible) porte la case à cocher.
            columns=["Étape", "_rowid"],
        )

        def _cfg_prep(gb):
            gb.configure_column("_rowid", hide=True, editable=False)
            gb.configure_column("Étape", rowDrag=True, editable=True, flex=1,
                                wrapText=True, autoHeight=True,
                                cellEditor="agLargeTextCellEditor",
                                cellEditorPopup=True)

        grille_prep = _grille_aggrid(df_prep, ss_prep, _cfg_prep)
        edite_prep = pd.DataFrame(grille_prep["data"])

        cc, cd = st.columns(2)
        if cc.button("＋ Ajouter une étape", key=f"add_prep_{k}",
                     use_container_width=True):
            seq = st.session_state.get(f"{ss_prep}_seq", 0) + 1
            st.session_state[f"{ss_prep}_seq"] = seq
            st.session_state[ss_prep] = pd.concat(
                [edite_prep, pd.DataFrame([{"Étape": "", "_rowid": f"n{seq}"}])],
                ignore_index=True)
            st.session_state[f"{ss_prep}_nonce"] = \
                st.session_state.get(f"{ss_prep}_nonce", 0) + 1
            st.rerun()
        if cd.button("🗑 Retirer les étapes cochées", key=f"del_prep_{k}",
                     use_container_width=True):
            ids = _lignes_selectionnees_ids(grille_prep, "_rowid")
            if ids:
                st.session_state[ss_prep] = edite_prep[~edite_prep["_rowid"].isin(ids)] \
                    .reset_index(drop=True)
                st.session_state[f"{ss_prep}_nonce"] = \
                    st.session_state.get(f"{ss_prep}_nonce", 0) + 1
                st.rerun()
            else:
                st.info("Coche d'abord au moins une étape (case à gauche), "
                        "puis clique 🗑.")

    if st.button("💾 Enregistrer les modifications", type="primary",
                 use_container_width=True, key=f"save_{k}"):
        nouveaux = _ingredients_depuis_editeur(edite)
        etapes = _etapes_depuis_editeur(edite_prep)

        # L'élément de base (étiquette + valeur de référence + unité) est
        # obligatoire pour chaque recette : c'est ce qui s'ajuste avec le nombre
        # de personnes en cuisine.
        erreurs = []
        if not nouveaux:
            erreurs.append("Il faut au moins un ingrédient avec un nom.")
        if not b_label.strip():
            erreurs.append("L'étiquette du rendement est obligatoire.")
        if float(b_val) <= 0:
            erreurs.append("La valeur de référence est obligatoire et doit être "
                           "supérieure à 0.")
        if not b_unite.strip():
            erreurs.append("L'unité de la valeur de référence est obligatoire.")

        if erreurs:
            for msg in erreurs:
                st.error(msg)
        else:
            recette["titre"] = titre.strip() or "Sans titre"
            recette["sous_titre"] = sous_titre.strip()
            recette["temps_prep"] = int(temps_prep)
            recette["temps_cuisson"] = int(temps_cuisson)
            recette["base"] = {"label": b_label.strip(),
                               "unite": b_unite.strip(),
                               "valeur": float(b_val),
                               "personnes": int(b_personnes),
                               "max_personnes": max(int(b_maxpers), int(b_personnes)),
                               "multiples": bool(b_multiples)}
            recette["ingredients"] = nouveaux
            recette["preparation"] = etapes
            # Tags : enregistre les nouveaux au catalogue global, applique les
            # noms canoniques à la recette.
            recette["tags"] = enregistrer_tags(tags_appliques)
            if persister(RECETTES):
                # Repart des données sauvées : on vide les tables de travail
                # (et leurs nonces/compteurs de remontage).
                for base in (f"agg_ing_{k}", f"agg_prep_{k}"):
                    for cle in (base, f"{base}_nonce", f"{base}_seq"):
                        st.session_state.pop(cle, None)
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
            st.button("Oui, retirer", type="primary", use_container_width=True,
                      key=f"delok_{k}", on_click=_supprimer_recette)
        with d2:
            if st.button("Annuler", use_container_width=True, key=f"delno_{k}"):
                st.session_state.confirmer_suppr = False
                st.rerun()