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
• Dans une étape, les ingrédients cités deviennent DYNAMIQUES quand ils sont
  marqués [ainsi] : leur quantité mise à l'échelle s'affiche « nom (qté) ».
  Le marquage se fait à la demande via « 🔍 Rescanner » (qui relance un scan à
  neuf à chaque appui, sur les grilles EN COURS d'édition) : l'éditeur surligne
  chaque occurrence citée et on bascule dynamique/non d'un clic, PAR OCCURRENCE
  (un ingrédient cité plusieurs fois peut n'être dynamique qu'une seule fois).
  La détection est EXACTE (« filet » → « Filet mignon ») mais aussi APPROCHÉE
  (≈) : pluriel/singulier (« crevette » → « Crevettes ») et troncatures
  (« choco » → « Chocolat noir ») ; les cas ambigus sont écartés. On peut aussi
  éditer les crochets à la main. Aucun marquage automatique à l'enregistrement.
• Pour un ingrédient fractionné, une PORTION explicite : [beurre: 15 ml]
  (le 15 s'échelonne) ou [beurre: reste] (le solde). Le rescan ne touche jamais
  aux portions (« 15 ml … du beurre », « le reste du beurre »).
• Sauvegarde vers GitHub (si secrets configurés) ou en local.

Lancer avec :  streamlit run recettes_console.py
"""

import base64
import json
import os
import re
import unicodedata
from contextlib import nullcontext

import pandas as pd
import requests
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode

import conversion_web as cw          # module local : import d'une recette web

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


# ─────────────────────────────────────────────────────────────────────────────
#  ANIMATION — onglet CONVERSION WEB (GIF animé, dans images/) :
#    • conversion.gif  — marmite qui mijote, jouée en boucle pendant l'appel IA.
#  L'ajout et l'annulation utilisent, eux, le toast `_toast` (comme un « 💾 »).
#  Si le fichier manque, l'app se rabat sans erreur sur le spinner texte.
# ─────────────────────────────────────────────────────────────────────────────
ANIM_FICHIERS = {
    "conversion": "conversion.gif",
}


def _jouer_anim(nom, *, width=170, overlay=False, legende=None):
    """Affiche le GIF animé `nom` (centré). Renvoie True si joué, False si le
    fichier manque — l'appelant peut alors se rabattre sur un texte.

    On l'injecte en <img> base64 (via gif_src) plutôt qu'avec st.image : ça
    garantit l'animation (st.image peut ré-encoder le GIF en image fixe).

    Si `overlay` est vrai, le GIF est posé en surimpression `position:fixed` au
    centre de la fenêtre visible (quel que soit le défilement), sur un voile
    semi-transparent. `legende` s'affiche alors sous le GIF, dans le voile."""
    fichier = ANIM_FICHIERS.get(nom)
    if not fichier:
        return False
    if not os.path.exists(os.path.join(DOSSIER_IMAGES, fichier)):
        return False
    if overlay:
        # Surimpression plein écran : le GIF reste au milieu de ce qu'on regarde
        # même si la page est scrollée (position:fixed rapportée au viewport).
        texte = (
            f'<div style="margin-top:16px;color:#e6edf3;font-size:.95rem;'
            f'text-align:center;text-shadow:0 1px 3px rgba(0,0,0,.6)">{legende}</div>'
            if legende else "")
        st.markdown(
            '<div style="position:fixed;inset:0;z-index:9999;display:flex;'
            'flex-direction:column;align-items:center;justify-content:center;'
            'background:rgba(11,15,20,.55);backdrop-filter:blur(3px);'
            '-webkit-backdrop-filter:blur(3px)">'
            f'<img src="{gif_src(fichier)}" '
            f'style="width:80%;max-width:{width}px;border-radius:12px;'
            'box-shadow:0 12px 40px rgba(0,0,0,.5)">'
            f'{texte}</div>',
            unsafe_allow_html=True)
        return True
    # Centrage fiable : colonnes [1,2,1] → le GIF est au milieu de la page,
    # juste sous le bouton « Convertir ».
    _, milieu, _ = st.columns([1, 2, 1])
    with milieu:
        st.markdown(
            f'<img src="{gif_src(fichier)}" '
            f'style="display:block;margin:0 auto;width:100%;max-width:{width}px;'
            'border-radius:12px">',
            unsafe_allow_html=True)
    return True


RECETTES_DEFAUT = [
    {
        "titre": "Marinade grecque pour poulet",
        "sous_titre": "Style Casa Grecque",
        "temps_prep": 10,
        "temps_cuisson": 0,
        "base": {"label": "Poids de poulet", "unite": "g", "valeur": 750,
                 "personnes": 4, "max_personnes": 20},
        "ingredients": [
            {"nom": "Mayonnaise (comble)",        "qte": 3,    "unite": "c. à soupe", "palier": 0.5},
            {"nom": "Origan",                      "qte": 2,    "unite": "c. à soupe", "palier": 0.5},
            {"nom": "Huile légère",                "qte": 4,    "unite": "c. à soupe", "palier": 0.5},
            {"nom": "Jus de citron",               "qte": 3,    "unite": "c. à soupe", "palier": 0.5},
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
            {"nom": "Huile d'olive",        "qte": 6,    "unite": "c. à soupe", "palier": 0.5},
            {"nom": "Vinaigre balsamique",  "qte": 2,    "unite": "c. à soupe", "palier": 0.5},
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
            {"nom": "Ketchup",              "qte": 4,    "unite": "c. à soupe", "palier": 0.5},
            {"nom": "Cassonade",            "qte": 2,    "unite": "c. à soupe", "palier": 0.5},
            {"nom": "Sauce Worcestershire", "qte": 2,    "unite": "c. à soupe", "palier": 0.5},
            {"nom": "Vinaigre de cidre",    "qte": 1,    "unite": "c. à soupe", "palier": 0.5},
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

COULEUR_TAG_DEFAUT = "#d6ddf4"      # gris : tag sans couleur connue


def _norm_tag(nom):
    """Clé de comparaison d'un tag (insensible à la casse et aux espaces)."""
    return (nom or "").strip().casefold()


_DELIGATURE = {"œ": "oe", "Œ": "Oe", "æ": "ae", "Æ": "Ae"}


def _deligature(s):
    """Remplace les ligatures œ/æ par « oe »/« ae » pour le STOCKAGE et
    l'affichage (« bœuf » → « boeuf », « œuf » → « oeuf »). Sans effet sur le
    matching interne, qui passe par _plier (lequel replie œ→o pour préserver les
    positions). Renvoie la valeur telle quelle si ce n'est pas une chaîne."""
    if not isinstance(s, str):
        return s
    for lig, rem in _DELIGATURE.items():
        if lig in s:
            s = s.replace(lig, rem)
    return s


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
        nom = _deligature((t.get("nom") or "").strip())   # « bœuf » → « boeuf »
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


def _anthropic_cfg():
    """Retourne {api_key, model} depuis st.secrets["anthropic"], ou None si absent.
    Sert à la fonctionnalité « Conversion recette web »."""
    try:
        an = st.secrets["anthropic"]
        api_key = an["api_key"]
    except (KeyError, FileNotFoundError):
        return None
    if not api_key:
        return None
    return {"api_key": api_key, "model": an.get("model", "claude-sonnet-4-6")}


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
    """Décompose le contenu JSON chargé en (recettes, tags, prochain_id).

    Deux formats acceptés :
      • ancien : une simple liste de recettes → les tags sont ceux par défaut ;
      • nouveau : {"recettes": [...], "tags": [...], "prochain_id": N}.
    `prochain_id` peut être absent (None) : il sera recalé à la migration."""
    if isinstance(data, list):
        return data, json.loads(json.dumps(TAGS_DEFAUT)), None
    if isinstance(data, dict) and isinstance(data.get("recettes"), list):
        pid = data.get("prochain_id")
        return data["recettes"], data.get("tags") or [], pid if isinstance(pid, int) else None
    return None


def charger_recettes():
    """Charge recettes + tags depuis GitHub si configuré, sinon depuis le
    fichier local ; retourne (recettes, tags, prochain_id, mode, erreur).
    `prochain_id` vaut None si le fichier ne le stocke pas encore (ancien
    format) : l'appelant le recale alors à la migration des ids."""
    cfg = _github_cfg()
    if cfg:
        try:
            r = requests.get(_gh_url(cfg), headers=_gh_headers(cfg),
                             params={"ref": cfg["branch"]}, timeout=10)
            if r.status_code == 200:
                data = json.loads(base64.b64decode(r.json()["content"]))
                extrait = _extraire(data)
                if extrait:
                    return extrait[0], extrait[1], extrait[2], "github", None
            if r.status_code == 404:   # pas encore de fichier dans le repo
                rec, tags = _defaut()
                return rec, tags, None, "github", None
            rec, tags = _defaut()
            return (rec, tags, None, "github",
                    f"Lecture GitHub impossible (code {r.status_code}) — "
                    "vérifie le token et le nom du repo dans les secrets.")
        except requests.RequestException as e:
            rec, tags = _defaut()
            return (rec, tags, None, "github",
                    f"Connexion à GitHub impossible : {e}")
    # Mode local
    if os.path.exists(FICHIER):
        try:
            with open(FICHIER, encoding="utf-8") as f:
                data = json.load(f)
            extrait = _extraire(data)
            if extrait:
                return extrait[0], extrait[1], extrait[2], "local", None
        except (json.JSONDecodeError, OSError):
            pass
    rec, tags = _defaut()
    return rec, tags, None, "local", None


def sauvegarder_recettes(recettes, tags, prochain_id=None):
    """Écrit recettes + catalogue de tags + compteur d'ids (GitHub si configuré,
    sinon local). `prochain_id` par défaut = celui de la session. Retourne
    (ok, message_erreur)."""
    if prochain_id is None:
        prochain_id = st.session_state.get("prochain_id")
    cfg = _github_cfg()
    # SÉCURITÉ — protection de la référence git : si la lecture initiale de
    # GitHub a échoué (ex. 502 transitoire), les recettes en session sont les
    # VALEURS PAR DÉFAUT, pas le contenu du repo. Écrire ici écraserait la
    # référence git avec ces défauts. On refuse donc toute écriture tant que la
    # lecture n'a pas réussi (recharge la page une fois GitHub de nouveau joignable).
    if cfg and st.session_state.get("erreur_chargement"):
        return (False,
                "sauvegarde bloquée — la lecture initiale de GitHub a échoué, "
                "les recettes affichées sont les valeurs par défaut. Écrire "
                "maintenant écraserait la référence git. Recharge la page une "
                "fois GitHub de nouveau accessible.")
    corps = {"recettes": recettes, "tags": tags}
    if prochain_id is not None:
        corps["prochain_id"] = prochain_id
    contenu = json.dumps(corps, ensure_ascii=False, indent=2)
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
#  FICHIERS ANNEXES — notes (★) et commentaires, stockés à part de recettes.json
#
#  Choix d'architecture (léger pour Streamlit Cloud) :
#    • Fichiers SÉPARÉS : ajouter une note/un commentaire ne réécrit jamais les
#      recettes ; la surface de conflit git est minuscule.
#    • Écriture UNIQUEMENT à la soumission (jamais à chaque rerun).
#    • Les notes et commentaires référencent la recette par son `id` STABLE
#      (survit à un renommage), jamais par son titre.
#  Lecture/écriture calquées sur recettes.json (GitHub si secrets, sinon local).
# ─────────────────────────────────────────────────────────────────────────────
NOTES_FICHIER = "notes.json"
COMMENTAIRES_FICHIER = "commentaires.json"
NOTES_DEFAUT = {"notes": [], "prochain_id": 1}
COMMENTAIRES_DEFAUT = {"commentaires": [], "prochain_id": 1}


def _gh_url_fichier(cfg, chemin):
    return f"https://api.github.com/repos/{cfg['repo']}/contents/{chemin}"


def _chemin_local(nom_fichier):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), nom_fichier)


def charger_json_annexe(nom_fichier, defaut):
    """Lecture seule d'un fichier annexe (notes/commentaires). Retourne
    (data, erreur). En cas d'échec de lecture, renvoie une copie de `defaut`."""
    cfg = _github_cfg()
    if cfg:
        try:
            r = requests.get(_gh_url_fichier(cfg, nom_fichier),
                             headers=_gh_headers(cfg),
                             params={"ref": cfg["branch"]}, timeout=10)
            if r.status_code == 200:
                return json.loads(base64.b64decode(r.json()["content"])), None
            if r.status_code == 404:            # fichier pas encore créé
                return json.loads(json.dumps(defaut)), None
            return (json.loads(json.dumps(defaut)),
                    f"Lecture GitHub de {nom_fichier} impossible (code {r.status_code}).")
        except requests.RequestException as e:
            return json.loads(json.dumps(defaut)), f"Connexion à GitHub impossible : {e}"
    chemin = _chemin_local(nom_fichier)
    if os.path.exists(chemin):
        try:
            with open(chemin, encoding="utf-8") as f:
                return json.load(f), None
        except (json.JSONDecodeError, OSError):
            pass
    return json.loads(json.dumps(defaut)), None


def muter_json_annexe(nom_fichier, defaut, mutation):
    """Charge la version LA PLUS À JOUR du fichier annexe, applique
    `mutation(data)` (qui modifie data sur place), puis l'écrit. En cas de
    conflit de SHA (écriture concurrente d'un autre visiteur), recharge et
    RÉAPPLIQUE la mutation : aucune contribution concurrente n'est perdue.
    Retourne (data_final, ok, erreur)."""
    cfg = _github_cfg()
    if cfg:
        url = _gh_url_fichier(cfg, nom_fichier)
        for tentative in range(4):
            try:
                r = requests.get(url, headers=_gh_headers(cfg),
                                 params={"ref": cfg["branch"]}, timeout=10)
                sha = None
                if r.status_code == 200:
                    data = json.loads(base64.b64decode(r.json()["content"]))
                    sha = r.json().get("sha")
                elif r.status_code == 404:
                    data = json.loads(json.dumps(defaut))
                else:
                    return (None, False,
                            f"Lecture GitHub de {nom_fichier} impossible "
                            f"(code {r.status_code}).")
                mutation(data)
                contenu = json.dumps(data, ensure_ascii=False, indent=2)
                payload = {
                    "message": f"Mise à jour {nom_fichier} via la console",
                    "content": base64.b64encode(contenu.encode("utf-8")).decode("ascii"),
                    "branch": cfg["branch"],
                }
                if sha:
                    payload["sha"] = sha
                r2 = requests.put(url, headers=_gh_headers(cfg), json=payload, timeout=15)
                if r2.status_code in (200, 201):
                    return data, True, None
                if r2.status_code == 409 and tentative < 3:
                    continue                    # SHA périmé : recharge + réapplique
                detail = ""
                try:
                    detail = r2.json().get("message", "")
                except ValueError:
                    pass
                return (None, False,
                        f"GitHub a refusé l'écriture (code {r2.status_code}) : {detail}")
            except requests.RequestException as e:
                if tentative < 3:
                    continue
                return None, False, f"Connexion à GitHub impossible : {e}"
        return None, False, "Conflit persistant lors de l'écriture GitHub (réessaie)."
    # Mode local
    chemin = _chemin_local(nom_fichier)
    data = json.loads(json.dumps(defaut))
    if os.path.exists(chemin):
        try:
            with open(chemin, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    mutation(data)
    try:
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, indent=2))
        return data, True, None
    except OSError as e:
        return None, False, f"Écriture locale impossible : {e}"


def _maintenant_iso():
    """Horodatage local « AAAA-MM-JJ HH:MM » pour marquer créations et modifs."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def moyenne_notes(notes_data, recette_id):
    """(moyenne, nombre) des étoiles pour une recette. (None, 0) si aucune note."""
    valeurs = [n["etoiles"] for n in notes_data.get("notes", [])
               if n.get("recette_id") == recette_id
               and isinstance(n.get("etoiles"), (int, float))]
    if not valeurs:
        return None, 0
    return sum(valeurs) / len(valeurs), len(valeurs)


# ─────────────────────────────────────────────────────────────────────────────
#  LOGIQUE DE MISE À L'ÉCHELLE
# ─────────────────────────────────────────────────────────────────────────────
FRACTIONS = {0.0: "", 0.25: "1/4", 0.5: "1/2", 0.75: "3/4", 0.33: "1/3", 0.67: "2/3"}


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
    """0.5 -> '1/2', 3.5 -> '3 1/2', 3.0 -> '3', 0.6667 -> '2/3' (palier 1/3)."""
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
    # Ligatures œ/æ → « oe »/« ae » partout dans le texte visible de la recette.
    r["titre"] = _deligature(r["titre"])
    r["sous_titre"] = _deligature(r["sous_titre"])
    # Préparation : liste d'objets {texte, section} (comme les ingrédients).
    # Migration des anciennes recettes où chaque étape était une simple chaîne.
    etapes = []
    for e in r.get("preparation", []):
        if isinstance(e, dict):
            e.setdefault("texte", "")
            e.setdefault("section", "")
            e["texte"] = _deligature(e["texte"]) if isinstance(e["texte"], str) else ""
            e["section"] = _deligature(e["section"]) if isinstance(e["section"], str) else ""
            etapes.append(e)
        else:                                     # ancien format : chaîne nue
            etapes.append({"texte": _deligature(str(e or "")), "section": ""})
    r["preparation"] = etapes
    # Tags : liste de noms (chaînes), nettoyée, sans ligature et sans doublons.
    vus, propres = set(), []
    for t in r.get("tags", []):
        nom = _deligature((t or "").strip()) if isinstance(t, str) else ""
        if nom and _norm_tag(nom) not in vus:
            vus.add(_norm_tag(nom))
            propres.append(nom)
    r["tags"] = propres
    for _ing in r.get("ingredients", []):         # section : groupe d'ingrédients
        if isinstance(_ing, dict):                # (« Garniture », « Bouillon »…)
            _ing.setdefault("section", "")
            for champ in ("nom", "unite", "section"):   # « bœuf » → « boeuf »
                if isinstance(_ing.get(champ), str):
                    _ing[champ] = _deligature(_ing[champ])
            # qte reste un float ou None : nettoie les quantités « texte libre »
            # des recettes importées (conversion web) — « 1/2 » → 0.5, etc.
            if "qte" in _ing:
                _ing["qte"] = parse_qte(_ing["qte"])
    r.setdefault("base", {})
    b = r["base"]
    b.setdefault("label", "Rendement")
    b.setdefault("unite", "")
    b.setdefault("valeur", 0)
    b.setdefault("personnes", 4)          # personnes servies par la valeur de réf.
    b.setdefault("max_personnes", 20)     # borne haute du curseur en cuisine
    b.setdefault("multiples", False)      # ajuster seulement par paliers fixes
    b.setdefault("pas_personnes", b.get("personnes") or 4)  # taille du palier
    return r


# ─────────────────────────────────────────────────────────────────────────────
#  MATCHING DES INGRÉDIENTS DANS LES ÉTAPES
#
#  Une « variable » d'étape est un ingrédient mentionné dans le texte, marqué
#  par des crochets [ainsi]. Les fonctions ci-dessous servent à la fois à
#  DÉTECTER ces mentions (auto-marquage à l'enregistrement) et à RÉSOUDRE un
#  marqueur vers le bon ingrédient (au rendu). Elles partagent la même
#  normalisation pour rester cohérentes.
# ─────────────────────────────────────────────────────────────────────────────
_LIGATURES = {"œ": "o", "æ": "a"}   # 1 caractère → longueur préservée (cf. ci-dessous)


def _plier(s):
    """Minuscule + sans accents, longueur préservée (é→e). Permet de repérer une
    sous-chaîne dans un texte tout en gardant les positions d'origine.
    Les ligatures œ/æ sont repliées sur un SEUL caractère (o/a) — pas « oe/ae » —
    justement pour préserver les positions ; l'important est que texte et noms
    d'ingrédients subissent la même transformation (« œufs » ↔ « oufs »)."""
    out = []
    for ch in str(s or ""):
        c = ch.lower()
        if c in _LIGATURES:
            out.append(_LIGATURES[c])
            continue
        d = unicodedata.normalize("NFD", c)
        out.append(d[0] if d else c)
    return "".join(out)


def _norm_titre(titre):
    """Clé de comparaison d'un titre de recette : sans casse ni accents, espaces
    condensés. « Crème brûlée » et « creme  brulee » donnent la même clé."""
    return re.sub(r"\s+", " ", _plier(titre)).strip()


def _titre_duplique(titre, recettes, sauf=None):
    """Vrai si `titre` (comparé sans casse ni accents) coïncide avec une AUTRE
    recette du menu. `sauf` = index de la recette en cours d'édition à ignorer."""
    cle = _norm_titre(titre)
    if not cle:
        return False
    for i, r in enumerate(recettes):
        if i == sauf:
            continue
        if _norm_titre(r.get("titre", "")) == cle:
            return True
    return False


def _ingredients_cle(ingredients):
    """Ensemble des noms d'ingrédients normalisés (sans casse ni accents) d'une
    recette. Sert à repérer deux recettes au contenu identique malgré un titre
    différent. Quantités, unités, paliers et sections sont ignorés."""
    return frozenset(
        cle for ing in (ingredients or [])
        if (cle := _norm_titre(ing.get("nom", "")))
    )


def _recette_jumelle_ingredients(ingredients, recettes, sauf=None):
    """Titre d'une AUTRE recette dont l'ensemble des noms d'ingrédients coïncide
    exactement, ou None. `sauf` = index de la recette éditée à ignorer."""
    cle = _ingredients_cle(ingredients)
    if not cle:
        return None
    for i, r in enumerate(recettes):
        if i == sauf:
            continue
        if _ingredients_cle(r.get("ingredients")) == cle:
            return r.get("titre", "")
    return None


def _mots_ing(nom):
    """Mots significatifs d'un nom d'ingrédient : sans accents ni casse, les
    qualificatifs entre parenthèses et la ponctuation retirés.
    « Beurre non salé (fondu) » → ['beurre', 'non', 'sale']."""
    s = re.sub(r"\([^)]*\)", " ", _plier(nom))     # retire « (fondu) » etc.
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.split()


def _phrases_ing(nom):
    """Sous-suites de mots d'un ingrédient — préfixes ET suffixes — du plus long
    au plus court, sans doublon.
    « Beurre non salé (fondu) » → ['beurre non sale', 'beurre non', 'sale',
    'beurre', 'non']. Le préfixe court capte les mentions abrégées (« beurre »)
    et le suffixe capte les citations par le nom-clé final (« œufs » pour « Gros
    œufs », « vanille » pour « Extrait de vanille »)."""
    mots = _mots_ing(nom)
    phrases = [" ".join(mots[:n]) for n in range(len(mots), 0, -1)]   # préfixes
    phrases += [" ".join(mots[i:]) for i in range(1, len(mots))]      # suffixes
    vus, uniques = set(), []
    for ph in phrases:
        if ph and ph not in vus:
            vus.add(ph)
            uniques.append(ph)
    uniques.sort(key=lambda p: -len(p.split()))     # plus long d'abord
    return uniques


# ── Correspondance APPROCHÉE : pluriel + troncature ───────────────────────────
#  La détection exacte capte déjà les abréviations qui sont un mot ENTIER de
#  l'ingrédient (« filet » pour « Filet mignon », via les préfixes de
#  `_phrases_ing`). En plus, on tolère :
#    • le pluriel/singulier      (« crevette » ↔ « Crevettes ») ;
#    • une troncature en préfixe  (« choco » pour « Chocolat noir »),
#  d'au moins _MIN_TRUNC lettres pour éviter le bruit. Détection ET résolution
#  des marqueurs partagent ces règles pour rester cohérentes (sinon un marqueur
#  accepté s'afficherait « introuvable » en cuisine).
_MIN_TRUNC = 4


def _racine(mot):
    """Racine grossière d'un mot plié : ôte un « s »/« x » final de pluriel
    (mot d'au moins 4 lettres). « crevettes » → « crevette », « choux » → « chou »."""
    return mot[:-1] if len(mot) >= 4 and mot[-1] in "sx" else mot


def _mots_similaires(a, b):
    """Deux mots pliés se correspondent-ils au pluriel près ou par troncature
    (le plus court, d'au moins _MIN_TRUNC lettres, préfixe de l'autre) ?"""
    if a == b or _racine(a) == _racine(b):
        return True
    court, long = (a, b) if len(a) <= len(b) else (b, a)
    return len(court) >= _MIN_TRUNC and long.startswith(court)


def _regex_mot_flou(mot):
    """Motif regex d'un mot d'ingrédient tolérant pluriel ET troncature : tout
    préfixe d'au moins _MIN_TRUNC lettres (et sa marque de pluriel) correspond.
    « chocolat » accepte « choc », « choco », …, « chocolat », « chocolats »."""
    base = _racine(mot)
    tete = re.escape(base[:_MIN_TRUNC])
    queue = ""
    for c in reversed(base[_MIN_TRUNC:]):             # lettres au-delà du seuil
        queue = f"(?:{re.escape(c)}{queue})?"         # → chacune optionnelle
    return tete + queue + "[sx]?"


def index_marqueurs(ingredients):
    """Map « phrase-clé → ingrédient », en ne gardant que les clés NON ambiguës
    (une phrase qui désignerait deux ingrédients est écartée). Sert à résoudre
    un marqueur [texte] ou une mention détectée vers le bon ingrédient.
    Priorité au NOM COMPLET : une phrase qui est le nom entier d'un seul
    ingrédient lui revient, même si elle est une sous-partie d'un autre (« œuf »
    → « Oeuf » plutôt qu'ambigu avec « Jaune d'œuf »)."""
    par_phrase, ing_par_id, noms_complets = {}, {}, {}
    for ing in ingredients:
        if not ing.get("nom"):
            continue
        ing_par_id[id(ing)] = ing
        complet = " ".join(_mots_ing(ing["nom"]))
        if complet:
            noms_complets.setdefault(complet, set()).add(id(ing))
        for ph in set(_phrases_ing(ing["nom"])):
            par_phrase.setdefault(ph, set()).add(id(ing))
    idx = {}
    for ph, ids in par_phrase.items():
        if not ph:
            continue
        if ph in noms_complets and len(noms_complets[ph]) == 1:
            idx[ph] = ing_par_id[next(iter(noms_complets[ph]))]
        elif len(ids) == 1:
            idx[ph] = ing_par_id[next(iter(ids))]
    return idx


def resoudre_marqueur(texte, idx):
    """Ingrédient désigné par le contenu d'un marqueur [texte] : on teste les
    préfixes de mots décroissants (pluriel toléré), puis, en dernier recours, une
    correspondance APPROCHÉE (pluriel/troncature) qui n'accepte qu'une cible
    unique. Le repli flou permet à un marqueur accepté depuis le rescan
    « similaire » (ex. [choco]) de retrouver sa quantité en cuisine."""
    mots = _mots_ing(texte)
    for n in range(len(mots), 0, -1):
        cle = " ".join(mots[:n])
        ing = idx.get(cle) or (idx.get(cle[:-1]) if cle.endswith("s") else None)
        if ing:
            return ing
    # Repli flou : le texte du marqueur correspond mot à mot (pluriel/troncature)
    # à une phrase-clé d'un SEUL ingrédient. Ambigu → non résolu (reste rouge).
    for n in range(len(mots), 0, -1):
        cle_mots = mots[:n]
        cibles, trouve = set(), None
        for ph, ing in idx.items():
            ph_mots = ph.split()
            if len(ph_mots) == len(cle_mots) and \
                    all(_mots_similaires(x, y) for x, y in zip(cle_mots, ph_mots)):
                cibles.add(id(ing))
                trouve = ing
        if len(cibles) == 1:
            return trouve
    return None


# ── Portions ────────────────────────────────────────────────────────────────
#  Un marqueur peut préciser une SOUS-quantité au lieu du total :
#    • [beurre: 15 ml]  → « beurre (15 ml) », le 15 s'échelonne avec le facteur.
#    • [beurre: reste]  → « beurre (le reste) » (solde chiffré seulement si des
#      portions de la MÊME unité ont été explicitées ailleurs — sinon texte).
#  Le garde-fou empêche l'auto-marquage d'apposer le TOTAL sur une mention qui
#  est manifestement une portion (quantité chiffrée ou mot de fractionnement
#  juste avant l'ingrédient).
_FRAC_UNI = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3, "⅛": 0.125}
_RESTE = {"reste", "le reste", "restant", "le restant", "restante"}
_AVANT_FRACTION = re.compile(
    r"(?:reste|restant\w*|moiti\w*|quart|une partie)\s+"
    r"(?:du|des|de|d)\s+(?:la\s+|l\s+)?$")
_AVANT_QTE = re.compile(r"\d.*\b(?:du|des|de|d)\s+(?:la\s+|l\s+)?$")


def _lire_nombre(s):
    """Consomme un nombre en tête de `s` et renvoie (valeur, reste). Comprend :
    entier/décimal (« 1 », « 1,5 »), fraction « a/b » (« 1/2 »), fraction unicode
    (« ½ »), et les nombres mixtes (« 1 1/2 », « 1 ½ »). Renvoie None si aucun
    nombre n'ouvre `s`. Logique partagée par `_lire_portion` et `parse_qte`."""
    s = s.lstrip()
    total, trouve = 0.0, False
    # Partie entière/décimale — sauf si la chaîne commence par une fraction pure
    # « a/b » (« 1/2 » : le « 1 » n'est pas un entier autonome).
    m = re.match(r"\d+(?:[.,]\d+)?", s)
    if m and not re.match(r"\d+\s*/\s*\d+", s):
        total += float(m.group(0).replace(",", "."))
        s, trouve = s[m.end():], True
    # Fraction « a/b », éventuellement après un entier (nombre mixte « 1 1/2 »).
    m = re.match(r"\s*(\d+)\s*/\s*(\d+)", s)
    if m:
        total += int(m.group(1)) / int(m.group(2))
        s, trouve = s[m.end():], True
    else:                                                 # ou fraction unicode
        m = re.match(r"\s*([½¼¾⅓⅔⅛])", s)                 # (« ½ », « 1 ½ »)
        if m:
            total += _FRAC_UNI.get(m.group(1), 0.0)
            s, trouve = s[m.end():], True
    return (total, s.lstrip()) if trouve else None


def _lire_portion(spec):
    """(nombre, unité) depuis « 15 ml », « 1/2 tasse », « ½ c. à thé »,
    « 1 ½ tasse ». Renvoie None si aucun nombre n'ouvre la chaîne."""
    r = _lire_nombre(spec.strip())
    return (r[0], r[1].strip()) if r else None


def parse_qte(valeur):
    """Convertit une quantité saisie/importée en float, ou None (« au goût »).
    Tolérante : ne lève JAMAIS d'exception. Comprend :
      - un nombre déjà numérique (int/float) → tel quel ;
      - une fraction texte « 1/2 », « 3/4 » → 0.5, 0.75 ;
      - un nombre mixte « 1 1/2 » → 1.5 ;
      - les fractions unicode « ½ ¼ ¾ ⅓ ⅔ ⅛ » (seules ou après un entier) ;
      - la virgule décimale « 1,5 » → 1.5 ;
      - les espaces superflus ;
      - une plage « 3 à 4 » ou « 3-4 » → MOYENNE des bornes (3.5). Pour prendre
        plutôt la borne inférieure, renvoyer `bas[0]` au lieu de la moyenne.
    Vide, None, ou texte non chiffré (« au goût », « une pincée ») → None."""
    if valeur is None or isinstance(valeur, bool):        # bool avant int !
        return None
    if isinstance(valeur, (int, float)):
        return None if pd.isna(valeur) else float(valeur)
    s = str(valeur).strip()
    if not s:
        return None
    # Plage « 3 à 4 » / « 3-4 » / « 3–4 » : moyenne des deux bornes lisibles.
    m = re.match(r"(.+?)\s*(?:à|-|–|—)\s*(.+)", s)
    if m:
        bas, haut = _lire_nombre(m.group(1).strip()), _lire_nombre(m.group(2).strip())
        if bas and haut:
            return (bas[0] + haut[0]) / 2
        if bas or haut:                                   # une seule borne lisible
            return (bas or haut)[0]
        return None
    r = _lire_nombre(s)
    return r[0] if r else None


def _echelle_portion(nombre, facteur):
    """Met à l'échelle une portion (qui n'a pas de palier propre) en gardant des
    fractions lisibles : arrondi au quart."""
    return round(nombre * facteur / 0.25) * 0.25


def _etape_texte(e):
    """Texte d'une étape de préparation, tolérant aux deux formes : ancien
    format (chaîne) et nouveau format (dict {texte, section})."""
    return e.get("texte", "") if isinstance(e, dict) else str(e or "")


def _etape_section(e):
    """Section (groupe) d'une étape ; « » pour l'ancien format en chaîne."""
    return e.get("section", "") if isinstance(e, dict) else ""


def calc_allocations(etapes, idx):
    """Somme, par ingrédient (clé id()), des portions explicites [ing: N unité]
    dont l'unité correspond à l'unité TOTALE de l'ingrédient — à l'échelle de
    référence. Sert au calcul fiable du « reste »."""
    sommes = {}
    for etape in etapes:
        for m in re.finditer(r"\[([^\[\]]+)\]", etape):
            nom, sep, spec = m.group(1).partition(":")
            if not sep:
                continue
            ing = resoudre_marqueur(nom.strip(), idx)
            p = _lire_portion(spec.strip()) if ing else None
            if p and _plier(p[1]) == _plier(ing.get("unite") or ""):
                sommes[id(ing)] = sommes.get(id(ing), 0.0) + p[0]
    return sommes


def _mention_est_portion(prefix):
    """Vrai si le texte qui précède immédiatement une mention en fait une portion
    (quantité chiffrée « 15 ml … du » ou mot de fractionnement « le reste du »)."""
    return bool(_AVANT_FRACTION.search(prefix) or _AVANT_QTE.search(prefix))


def detecter_mentions(texte, ingredients, idx):
    """Repère dans `texte` les mentions d'ingrédients pas encore entre crochets.
    Renvoie une liste (start, end, ingrédient) non chevauchante : une seule
    occurrence par ingrédient (la 1re), phrase la plus longue prioritaire."""
    folded = _plier(texte)
    exclus = [(m.start(), m.end()) for m in re.finditer(r"\[[^\[\]]*\]", texte)]

    def chevauche(a, b, spans):
        return any(a < j and i < b for i, j in spans)

    trouves = []
    for ing in ingredients:
        if not ing.get("nom") or ing.get("qte") is None:   # ignore « au goût »
            continue
        for ph in _phrases_ing(ing["nom"]):
            if idx.get(ph) is not ing:            # phrase ambiguë ou d'un autre
                continue
            motif = (r"(?<![a-z0-9])"
                     + r"[^a-z0-9]+".join(map(re.escape, ph.split()))
                     + r"(?![a-z0-9])")
            # 1re occurrence « propre » : ni déjà marquée, ni une portion
            # (« 15 ml … du beurre », « le reste du beurre » → laissées à l'auteur).
            for m in re.finditer(motif, folded):
                if chevauche(m.start(), m.end(), exclus):
                    continue
                if _mention_est_portion(folded[max(0, m.start() - 40):m.start()]):
                    continue
                trouves.append((m.start(), m.end(), ing))
                break
            else:
                continue                          # aucune occurrence propre
            break                                 # ingrédient traité
    # Chevauchements entre ingrédients : garder la plus longue puis la 1re.
    trouves.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    retenus, occup = [], []
    for a, b, ing in trouves:
        if not chevauche(a, b, occup):
            occup.append((a, b))
            retenus.append((a, b, ing))
    retenus.sort()
    return retenus


# ── Rescan à la demande : marquage DYNAMIQUE par OCCURRENCE ───────────────────
#  Plutôt qu'un marquage automatique à l'enregistrement (imprévisible), l'auteur
#  déclenche un « rescan » puis bascule dynamique/non CHAQUE occurrence d'un clic.
#  C'est par occurrence : un ingrédient cité plusieurs fois peut n'être dynamique
#  que là où c'est utile (souvent une seule fois), le reste restant du texte nu.
def ingredients_deja_dynamiques(etapes, ingredients):
    """Noms des ingrédients DÉJÀ entre crochets dans les étapes (ordre
    d'apparition, sans doublon). Sert au rappel « pas encore dynamique »."""
    idx = index_marqueurs(ingredients)
    vus, noms = set(), []
    for e in etapes:
        for m in re.finditer(r"\[([^\[\]]+)\]", e):
            nom = m.group(1).partition(":")[0].strip()
            ing = resoudre_marqueur(nom, idx)
            if ing and id(ing) not in vus:
                vus.add(id(ing))
                noms.append(ing["nom"])
    return noms


def candidats_dynamiques(etapes, ingredients):
    """Noms des ingrédients cités dans les étapes (mention EXACTE ou APPROCHÉE)
    mais dont AUCUNE occurrence n'est encore entre crochets. Ordre d'apparition,
    sans doublon. Sert au rappel qui incite à rendre ces ingrédients dynamiques."""
    idx = index_marqueurs(ingredients)
    vus, noms = set(), []
    for e in etapes:
        mentions = (detecter_mentions(e, ingredients, idx)
                    + detecter_similaires(e, ingredients, idx))
        mentions.sort(key=lambda t: t[0])
        for _a, _b, ing in mentions:
            if id(ing) in vus:
                continue
            vus.add(id(ing))
            noms.append(ing["nom"])
    return noms


def detecter_mentions_toutes(texte, ingredients, idx):
    """Comme `detecter_mentions`, mais renvoie TOUTES les occurrences propres de
    chaque ingrédient (pas seulement la 1re) — (start, end, ingrédient), non
    chevauchantes. Sert au marquage par occurrence."""
    folded = _plier(texte)
    exclus = [(m.start(), m.end()) for m in re.finditer(r"\[[^\[\]]*\]", texte)]

    def chevauche(a, b, spans):
        return any(a < j and i < b for i, j in spans)

    trouves = []
    for ing in ingredients:
        if not ing.get("nom") or ing.get("qte") is None:   # ignore « au goût »
            continue
        for ph in _phrases_ing(ing["nom"]):
            if idx.get(ph) is not ing:            # phrase ambiguë ou d'un autre
                continue
            motif = (r"(?<![a-z0-9])"
                     + r"[^a-z0-9]+".join(map(re.escape, ph.split()))
                     + r"(?![a-z0-9])")
            trouve_ici = False
            for m in re.finditer(motif, folded):
                if chevauche(m.start(), m.end(), exclus):
                    continue
                if _mention_est_portion(folded[max(0, m.start() - 40):m.start()]):
                    continue
                trouves.append((m.start(), m.end(), ing))
                trouve_ici = True
            if trouve_ici:
                break                             # 1re phrase (la + longue) présente
    trouves.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    retenus, occup = [], []
    for a, b, ing in trouves:
        if not chevauche(a, b, occup):
            occup.append((a, b))
            retenus.append((a, b, ing))
    retenus.sort()
    return retenus


def detecter_similaires(texte, ingredients, idx):
    """Mentions APPROCHÉES d'une étape : pluriel/singulier (« crevette » pour
    « Crevettes ») et troncatures (« choco » pour « Chocolat noir »). Complète
    `detecter_mentions_toutes` (exact) sans jamais recouvrir ses occurrences ni
    les marqueurs déjà posés. Ne renvoie que les occurrences NON AMBIGUËS (une
    seule cible possible) — (start, end, ingrédient) triés, non chevauchants."""
    folded = _plier(texte)
    # Zones interdites : marqueurs existants + occurrences déjà captées EXACTEMENT
    # (celles-ci restent des candidats « exacts », pas « similaires »).
    exclus = [(m.start(), m.end()) for m in re.finditer(r"\[[^\[\]]*\]", texte)]
    exclus += [(a, b) for a, b, _ing in
               detecter_mentions_toutes(texte, ingredients, idx)]

    def chevauche(a, b, spans):
        return any(a < j and i < b for i, j in spans)

    trouves = []
    for ing in ingredients:
        if not ing.get("nom") or ing.get("qte") is None:   # ignore « au goût »
            continue
        for ph in _phrases_ing(ing["nom"]):
            if idx.get(ph) is not ing:            # phrase ambiguë ou d'un autre
                continue
            motif = (r"(?<![a-z0-9])"
                     + r"[^a-z0-9]+".join(map(_regex_mot_flou, ph.split()))
                     + r"(?![a-z0-9])")
            for m in re.finditer(motif, folded):
                if chevauche(m.start(), m.end(), exclus):
                    continue
                if _mention_est_portion(folded[max(0, m.start() - 40):m.start()]):
                    continue
                trouves.append((m.start(), m.end(), ing))

    # Un même span réclamé par ≥2 ingrédients distincts est ambigu : on l'écarte
    # (on ne saurait pas lequel proposer). Puis chevauchements : plus long d'abord.
    par_span = {}
    for a, b, ing in trouves:
        par_span.setdefault((a, b), (set(), ing))[0].add(id(ing))
    candidats = [(a, b, ing) for (a, b), (ids, ing) in par_span.items()
                 if len(ids) == 1]
    candidats.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    retenus, occup = [], []
    for a, b, ing in candidats:
        conflit_autre = any(a < j and i < b and id(g) != id(ing)
                            for i, j, g in retenus)
        if conflit_autre or chevauche(a, b, occup):
            continue
        occup.append((a, b))
        retenus.append((a, b, ing))
    retenus.sort()
    return retenus


def occurrences_dynamiques(texte, ingredients, idx):
    """Occurrences « basculables » d'une étape, pour le panneau interactif.
    Renvoie une liste triée de tuples (a, b, etat, nom) où [a, b) est le span
    dans `texte` :
      • etat 'dyn'  → un marqueur simple [nom] (cliquer RETIRE les crochets) ;
      • etat 'cand' → une mention exacte non marquée (cliquer AJOUTE) ;
      • etat 'sim'  → une mention APPROCHÉE (pluriel/troncature) à confirmer.
    Les marqueurs de PORTION [nom: 15 ml] sont ignorés (édition manuelle)."""
    occ = []
    bornes_marqueurs = []
    for m in re.finditer(r"\[([^\[\]]+)\]", texte):
        bornes_marqueurs.append((m.start(), m.end()))
        contenu = m.group(1)
        nom, sep, _spec = contenu.partition(":")
        if sep:                                    # portion → non basculable
            continue
        ing = resoudre_marqueur(nom.strip(), idx)
        if ing:
            occ.append((m.start(), m.end(), "dyn", ing["nom"]))
    for a, b, ing in detecter_mentions_toutes(texte, ingredients, idx):
        occ.append((a, b, "cand", ing["nom"]))
    for a, b, ing in detecter_similaires(texte, ingredients, idx):
        occ.append((a, b, "sim", ing["nom"]))
    occ.sort()
    return occ


def basculer_marqueur(texte, a, b, etat):
    """Ajoute ('cand'/'sim') ou retire ('dyn') les crochets sur le span [a, b)
    d'une étape. Pour 'dyn', [a, b) englobe les crochets. Renvoie le nouveau
    texte. Un candidat approché ('sim') s'insère tel quel — le résolveur flou
    retrouvera l'ingrédient en cuisine."""
    if etat in ("cand", "sim"):
        return texte[:a] + "[" + texte[a:b] + "]" + texte[b:]
    return texte[:a] + texte[a + 1:b - 1] + texte[b:]   # 'dyn' : ôte [ et ]


def _valeur_reste(ing, facteur, allocations):
    """« le reste » : chiffre exact uniquement si des portions de la MÊME unité
    ont été explicitées ailleurs (sinon on ne peut pas soustraire fiablement,
    ex. total en g et portion en ml)."""
    total_ref, somme_ref = ing.get("qte"), allocations.get(id(ing))
    if total_ref is not None and somme_ref:
        diff = total_ref - somme_ref
        if diff > 0:
            reste = echelle({"qte": diff, "palier": ing.get("palier")}, facteur)
            return f"{jolie_qte(reste)} {html_escape(ing.get('unite') or '')}".strip()
    return "le reste"


def injecter_quantites(texte, idx, facteur, allocations=None):
    """Remplace les [ingrédient] d'une étape par « nom (quantité) », la quantité
    étant mise à l'échelle et surlignée. Gère aussi les portions :
    [ing: 15 ml] (nombre échelonné) et [ing: reste] (solde). Le texte est déjà
    échappé HTML ; les crochets survivent. `idx` provient de index_marqueurs()."""
    allocations = allocations or {}

    def repl(m):
        nom, sep, spec = m.group(1).partition(":")
        nom, spec = nom.strip(), spec.strip()
        ing = resoudre_marqueur(nom, idx)
        if not ing:
            return m.group(1)                      # texte seul si non résolu
        if sep and spec:                           # marqueur de portion
            if _plier(spec) in _RESTE:
                val = _valeur_reste(ing, facteur, allocations)
            else:
                p = _lire_portion(spec)
                if p:
                    val = (f"{jolie_qte(_echelle_portion(p[0], facteur))} "
                           f"{html_escape(p[1])}").strip()
                else:
                    val = html_escape(spec)        # portion libre, non chiffrée
        else:                                      # quantité totale
            q = echelle(ing, facteur)
            val = ("au goût" if q is None else
                   f"{jolie_qte(q)} {html_escape(ing.get('unite') or '')}".strip())
        return (f'<span class="inqnom">{nom}</span>'
                f' <span class="inq">({val})</span>')
    return re.sub(r"\[([^\[\]]+)\]", repl, texte)


_MK_OK = ("background:rgba(74,222,128,.15);color:#7ee787;"
          "border:1px solid rgba(74,222,128,.45);border-radius:4px;padding:0 4px")
_MK_KO = ("background:rgba(248,81,73,.15);color:#ff7b72;"
          "border:1px solid rgba(248,81,73,.45);border-radius:4px;padding:0 4px")


def apercu_marqueurs(texte, idx):
    """HTML d'une étape pour l'aperçu de l'éditeur : chaque [marqueur] est
    surligné en vert s'il désigne un ingrédient connu, en rouge sinon. Styles
    inline (la feuille de style .inq ne vit que dans l'iframe de cuisine). Le
    reste du texte est échappé."""
    morceaux, prev = [], 0
    for m in re.finditer(r"\[([^\[\]]+)\]", texte):
        morceaux.append(html_escape(texte[prev:m.start()]))
        contenu = m.group(1)
        nom = contenu.partition(":")[0].strip()    # ignore la portion éventuelle
        style = _MK_OK if resoudre_marqueur(nom, idx) else _MK_KO
        morceaux.append(f'<span style="{style}">[{html_escape(contenu)}]</span>')
        prev = m.end()
    morceaux.append(html_escape(texte[prev:]))
    return "".join(morceaux)


# Panneau interactif de marquage : styles des occurrences (vert = dynamique,
# ambre pointillé = candidat) et pastilles ①..⑨ pour numéroter les répétitions.
_OCC_DYN = ("background:rgba(74,222,128,.15);color:#7ee787;"
            "border-bottom:2px solid rgba(74,222,128,.6);border-radius:3px;padding:0 2px")
_OCC_CAND = ("background:rgba(255,180,84,.13);color:#ffd9a6;"
             "border-bottom:2px dashed rgba(255,180,84,.6);border-radius:3px;padding:0 2px")
# 'sim' (approché) : bleu pointillé, pour le distinguer d'un candidat exact.
_OCC_SIM = ("background:rgba(88,166,255,.13);color:#bcd6ff;"
            "border-bottom:2px dotted rgba(88,166,255,.7);border-radius:3px;padding:0 2px")
_CERCLES = {1: "①", 2: "②", 3: "③", 4: "④", 5: "⑤",
            6: "⑥", 7: "⑦", 8: "⑧", 9: "⑨"}


def apercu_occurrences(texte, occ):
    """HTML d'une étape pour le panneau interactif : 'dyn' surligné vert, 'cand'
    ambre pointillé, 'sim' (approché) bleu pointillé. Le contenu d'un marqueur
    [..] est montré SANS les crochets (pour voir le rendu final). `occ` provient
    d'occurrences_dynamiques() ; le reste du texte est échappé."""
    morceaux, prev = [], 0
    for a, b, etat, _nom in occ:
        morceaux.append(html_escape(texte[prev:a]))
        brut = texte[a:b]
        interne = brut[1:-1] if (etat == "dyn" and brut.startswith("[")) else brut
        style = {"dyn": _OCC_DYN, "sim": _OCC_SIM}.get(etat, _OCC_CAND)
        morceaux.append(f'<span style="{style}">{html_escape(interne)}</span>')
        prev = b
    morceaux.append(html_escape(texte[prev:]))
    return "".join(morceaux)


# ─────────────────────────────────────────────────────────────────────────────
#  ÉTAT
# ─────────────────────────────────────────────────────────────────────────────
if "recettes" not in st.session_state:
    recettes, tags, prochain_id, mode, erreur = charger_recettes()
    for r in recettes:
        normaliser_recette(r)
    # ── MIGRATION : id unique incrémental par recette (lien stable pour les
    #    notes et commentaires). On cale d'abord le compteur au-dessus des ids
    #    déjà présents, puis on attribue un id aux recettes qui n'en ont pas.
    compteur_absent = not isinstance(prochain_id, int) or prochain_id < 1
    if compteur_absent:
        prochain_id = 1
    for r in recettes:
        if isinstance(r.get("id"), int):
            prochain_id = max(prochain_id, r["id"] + 1)
    ids_attribues = False
    for r in recettes:
        if not isinstance(r.get("id"), int):
            r["id"] = prochain_id
            prochain_id += 1
            ids_attribues = True
    st.session_state.recettes = recettes
    st.session_state.tags = normaliser_tags(tags)   # catalogue global
    st.session_state.prochain_id = prochain_id
    st.session_state.stockage = mode          # "github" ou "local"
    st.session_state.erreur_chargement = erreur
    # Persistance UNIQUE de la migration — seulement si quelque chose a changé
    # (ids nouveaux ou compteur absent) et si la lecture initiale a réussi (sans
    # quoi on écraserait le dépôt avec les valeurs par défaut). Aucune écriture
    # aux sessions suivantes une fois la migration faite.
    if (ids_attribues or compteur_absent) and not erreur:
        sauvegarder_recettes(recettes, st.session_state.tags, prochain_id)
if "notes_data" not in st.session_state:
    notes_data, err_notes = charger_json_annexe(NOTES_FICHIER, NOTES_DEFAUT)
    st.session_state.notes_data = notes_data
    st.session_state.erreur_notes = err_notes
if "commentaires_data" not in st.session_state:
    comm_data, err_comm = charger_json_annexe(COMMENTAIRES_FICHIER, COMMENTAIRES_DEFAUT)
    st.session_state.commentaires_data = comm_data
    st.session_state.erreur_commentaires = err_comm
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


def _palier_txt(p):
    """Rend un palier sous forme de chaîne pour l'éditeur (menu déroulant). La
    colonne Palier reste ainsi textuelle : sans ça, streamlit-aggrid l'infère
    numérique et affiche « Invalid Number » sur une valeur de menu ou une ligne
    neuve. Le float est reconstruit à l'enregistrement.
    Le tiers (1/3) n'est pas représentable exactement en décimal : on le
    reconnaît explicitement pour l'afficher « 1/3 » plutôt que « 0.333333 »."""
    if p is None or p == "" or (isinstance(p, float) and pd.isna(p)):
        return ""
    p = float(p)
    for v in ("0.25", "0.5", "1.0"):
        if abs(p - float(v)) < 1e-9:
            return v
    if abs(p - 1 / 3) < 1e-9:
        return "1/3"
    return f"{p:g}"


def _palier_val(txt):
    """Convertit le texte d'un palier (« 0.5 », « 1/3 ») en float ; None si vide.
    Symétrique de _palier_txt — accepte en plus la notation fractionnaire pour
    que les paliers comme 1/3 survivent à l'aller-retour éditeur ↔ données.
    Depuis que le palier se saisit en texte libre (plus de menu déroulant), on
    tolère la virgule décimale française (« 0,5 ») et on retombe sur None — donc
    sur le palier par défaut appliqué à l'échelle — plutôt que de planter sur une
    saisie illisible (« abc », « 0.5.5 »…)."""
    txt = (txt or "").strip().replace(",", ".")
    if not txt:
        return None
    try:
        if "/" in txt:
            n, d = txt.split("/", 1)
            return float(n) / float(d)
        return float(txt)
    except (ValueError, ZeroDivisionError):
        return None


def _ingredients_depuis_editeur(df):
    """Convertit le tableau édité (data_editor) en liste d'ingrédients propre,
    en ignorant les lignes sans nom. Sert à l'enregistrement ET au
    réordonnancement, pour ne pas perdre les éditions en cours."""
    nouveaux = []
    for ligne in df.to_dict("records"):
        nom = str(ligne.get("Ingrédient") or "").strip()
        if not nom or nom.lower() == "nan":
            continue
        qte = parse_qte(ligne.get("Quantité"))   # tolérant : « 1/2 », « ½ »… → float
        au_gout = qte is None
        palier = ligne.get("Palier")
        unite_raw = ligne.get("Unité")
        unite = "" if (unite_raw is None or pd.isna(unite_raw)) else str(unite_raw).strip()
        section_raw = ligne.get("Section")
        section = "" if (section_raw is None or pd.isna(section_raw)) else str(section_raw).strip()
        nouveaux.append({
            "nom": nom,
            "qte": qte,                           # déjà float ou None (parse_qte)
            "unite": unite or ("au goût" if au_gout else ""),
            "palier": _palier_val(None if (palier is None or pd.isna(palier)) else str(palier)),
            "section": section,
        })
    return nouveaux


def _etapes_depuis_editeur(df):
    """Convertit le tableau des étapes édité en liste d'objets {texte, section}
    propre, en ignorant les lignes sans texte. Miroir de
    `_ingredients_depuis_editeur` pour la préparation."""
    a_section = "Section" in df.columns
    etapes = []
    for ligne in df.to_dict("records"):
        texte = str(ligne.get("Étape") or "").strip()
        if not texte or texte.lower() == "nan":
            continue
        sec_raw = ligne.get("Section") if a_section else ""
        sec = "" if (sec_raw is None or pd.isna(sec_raw)) else str(sec_raw).strip()
        etapes.append({"texte": texte, "section": sec})
    return etapes


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
            "color:#d6ddf4;padding-top:.5rem;white-space:nowrap;overflow:hidden;"
            f"text-overflow:ellipsis;\">{i + 1}. {html_escape(labels[i])}</div>",
            unsafe_allow_html=True)
        if c_up.button("▲", key=f"ord_up_{champ}_{k}_{i}", disabled=(i == 0),
                       use_container_width=True, help="Monter cette ligne"):
            _echanger(i, i - 1)
        if c_down.button("▼", key=f"ord_down_{champ}_{k}_{i}", disabled=(i == n - 1),
                         use_container_width=True, help="Descendre cette ligne"):
            _echanger(i, i + 1)


def _df_retour_grille(grille, gabarit):
    """Normalise le retour d'AgGrid en DataFrame, quel que soit le mode de
    sérialisation.

    Avec `use_json_serialization=True` (forcé pour éviter un segfault pyarrow),
    `grille["data"]` n'est PLUS un DataFrame : c'est None (aucune édition depuis
    le rendu → on garde l'état courant) ou une CHAÎNE JSON de records après
    édition (« [] » si toutes les lignes ont été retirées). On reconstruit un
    DataFrame en préservant TOUJOURS les colonnes de `gabarit` (sans quoi une
    grille vide/inchangée perdrait ses colonnes → `configure_selection` planterait
    au rerun suivant) et en gardant `_rowid` en texte pour les correspondances de
    lignes (ajout / retrait)."""
    d = grille["data"]
    if isinstance(d, pd.DataFrame):
        df = d.copy()
    elif isinstance(d, str):
        lignes = json.loads(d) if d.strip() else []
        if not lignes:                       # grille vidée : vide MAIS colonné
            return gabarit.iloc[0:0].copy()
        df = pd.DataFrame(lignes)
    else:                                    # None : rien de neuf, on conserve
        return gabarit.copy()
    for c in gabarit.columns:                # complète d'éventuelles colonnes absentes
        if c not in df.columns:
            df[c] = ""
    df = df[list(gabarit.columns)]
    if "_rowid" in df.columns:
        df["_rowid"] = df["_rowid"].astype(str)
    return df.reset_index(drop=True)


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
    # Valide l'édition en cours dès que la cellule perd le focus (ex. clic sur
    # « 💾 Enregistrer »). Sans cela, une cellule encore en mode édition ne
    # déclenche jamais cellValueChanged : l'ancienne valeur (ex. « tasse » au
    # lieu de « ml ») est renvoyée et enregistrée à sa place.
    options["stopEditingWhenCellsLoseFocus"] = True
    # Info-bulles natives du navigateur (attribut title) : la bulle maison
    # d'AgGrid est tronquée dans l'iframe Streamlit et n'apparaît pas.
    options["enableBrowserTooltips"] = True

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
        # Sérialisation JSON forcée (pas pyarrow). Par défaut streamlit-aggrid
        # sérialise le DataFrame via pyarrow ; avec pandas 3.x / pyarrow récent
        # cette conversion native peut provoquer un SEGMENTATION FAULT côté
        # serveur (Streamlit Cloud), non rattrapable — le repli JSON automatique
        # de la lib ne sert qu'en cas d'EXCEPTION, pas de segfault. On force donc
        # le chemin JSON, robuste aux dtypes mixtes (Quantité None/nombre, etc.).
        use_json_serialization=True,
    )
    # Persiste l'état courant (ordre glissé + éditions) pour les reruns suivants.
    # _df_retour_grille normalise le retour JSON en DataFrame colonné (voir sa
    # docstring) ; les appelants relisent cet état via st.session_state[ss_key].
    st.session_state[ss_key] = _df_retour_grille(grille, travail)
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


def _titre_vierge_unique(recettes):
    """Titre par défaut d'une recette vierge qui ne double aucun titre existant :
    « Nouvelle recette », puis « Nouvelle recette 2 », « … 3 »…"""
    base = "Nouvelle recette"
    if not _titre_duplique(base, recettes):
        return base
    n = 2
    while _titre_duplique(f"{base} {n}", recettes):
        n += 1
    return f"{base} {n}"


def recette_vierge(recettes):
    return {
        "titre": _titre_vierge_unique(recettes),
        "sous_titre": "À personnaliser",
        "temps_prep": 0,
        "temps_cuisson": 0,
        "base": {"label": "Portions", "unite": "portions", "valeur": 4,
                 "personnes": 4, "max_personnes": 20, "multiples": False,
                 "pas_personnes": 4},
        "ingredients": [{"nom": "Premier ingrédient", "qte": 1,
                         "unite": "c. à soupe", "palier": 0.5, "section": ""}],
        "preparation": [{"texte": "Première étape — cite un ingrédient et sa "
                         "quantité s'insérera toute seule à l'enregistrement.",
                         "section": ""}],
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
    nouvelle = recette_vierge(recettes)
    nouvelle["id"] = st.session_state.prochain_id      # id stable pour notes/commentaires
    st.session_state.prochain_id += 1
    recettes.append(nouvelle)
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


def _ajouter_recette_convertie(rec):
    """Callback : ajoute au menu une recette convertie du web, l'affiche et la
    sélectionne. Intègre ses nouveaux tags au catalogue global."""
    normaliser_recette(rec)
    recettes = st.session_state.recettes
    # Anti-doublon : on refuse d'ajouter une recette dont le titre existe déjà
    # (sans casse ni accents). Le message est affiché au rerun.
    if _titre_duplique(rec.get("titre", ""), recettes):
        st.session_state["_conv_doublon"] = rec.get("titre", "")
        return
    jumelle = _recette_jumelle_ingredients(rec.get("ingredients"), recettes)
    if jumelle:
        st.session_state["_conv_doublon_ing"] = (rec.get("titre", ""), jumelle)
        return

    connus = {_norm_tag(t["nom"]) for t in st.session_state.tags}
    for nom in rec.get("tags", []):
        if nom and _norm_tag(nom) not in connus:
            st.session_state.tags.append(
                {"nom": nom, "couleur": COULEUR_TAG_DEFAUT})
            connus.add(_norm_tag(nom))
    st.session_state.tags = trier_tags(st.session_state.tags)

    rec["id"] = st.session_state.prochain_id          # id stable pour notes/commentaires
    st.session_state.prochain_id += 1
    recettes.append(rec)
    st.session_state.recherche_titre = ""
    st.session_state.recherche_ingredient = ""
    st.session_state.recette_select = len(recettes) - 1
    st.session_state.confirmer_suppr = False
    ok, err = sauvegarder_recettes(recettes, st.session_state.tags)
    st.session_state.err_save = None if ok else err

    st.session_state["_conv_ajoutee"] = rec.get("titre", "")   # déclenche le toast
    for cle in ("conv_resultat", "conv_source", "conv_erreur"):
        st.session_state.pop(cle, None)


def _annuler_recette_convertie():
    """Callback : jette l'aperçu de la recette convertie sans l'ajouter au menu.
    Pose un drapeau pour afficher le toast d'annulation au rerun."""
    st.session_state["_conv_annulee"] = True             # déclenche le toast
    for cle in ("conv_resultat", "conv_source", "conv_erreur"):
        st.session_state.pop(cle, None)


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE + THÈME
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="grimoire de recettes", page_icon="🛰️",
                   layout="centered", initial_sidebar_state="collapsed")


def _toast(message="Enregistré", icone="✓"):
    """Petit pop-up (façon « Enregistré ») qui apparaît juste SOUS le bouton
    d'où on l'appelle, tient ~2 s puis se replie et disparaît. Rendu
    inconditionnel : c'est l'appelant qui décide quand l'afficher."""
    st.markdown("""
    <style>
    @keyframes toast-sb{
      0%  {opacity:0;transform:translateY(-8px);max-height:0;padding-top:0;padding-bottom:0}
      12% {opacity:1;transform:translateY(0);max-height:64px;padding-top:10px;padding-bottom:10px}
      70% {opacity:1;transform:translateY(0);max-height:64px}
      100%{opacity:0;transform:translateY(-4px);max-height:0;margin-top:0;
           padding-top:0;padding-bottom:0}
    }
    .toast-sb{
      overflow:hidden;box-sizing:border-box;
      display:flex;align-items:center;justify-content:center;gap:9px;
      width:fit-content;margin:8px auto 0;padding:10px 18px;border-radius:11px;
      background:linear-gradient(135deg,#0b1120,#141a2b);
      border:1px solid rgba(77,243,227,.55);
      color:#7ff5ea;font-family:'JetBrains Mono',monospace;font-weight:700;
      letter-spacing:.04em;box-shadow:0 0 20px rgba(77,243,227,.35);
      animation:toast-sb 2s ease forwards;
    }
    .toast-sb .ts-ico{
      display:inline-flex;align-items:center;justify-content:center;
      width:21px;height:21px;border-radius:50%;
      background:rgba(77,243,227,.18);color:#4df3e3;font-size:.85rem}
    </style>
    """, unsafe_allow_html=True)
    st.markdown(
        f'<div class="toast-sb"><span class="ts-ico">{icone}</span> {message}'
        "</div>", unsafe_allow_html=True)


def toast_enregistre(cle):
    """Affiche le toast « Enregistré » si le drapeau de session `cle` est posé
    (il survit au st.rerun() déclenché par le 💾)."""
    if st.session_state.pop(cle, False):
        _toast()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500;700&display=swap');

:root{
  --bg:#04060d; --panel:#0b1120; --line:#1e2a45;
  --cyan:#4df3e3; --amber:#ffb454;
  --text:#e9efff; --muted:#d6ddf4;
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

/* ── Champ VEDETTE : « Recettes disponibles » ─────────────────────────
   C'est LE point d'entrée du site : on le met très en évidence tout en
   gardant l'esthétique techno-futuriste (néon cyan, coins HUD, halo). */
.st-key-recette_hero{
  position:relative;
  margin:.5rem 0 .3rem;
  padding:1.15rem 1.3rem 1.3rem;
  border:1px solid rgba(77,243,227,.45)!important;
  border-radius:16px;
  background:
    linear-gradient(180deg, rgba(77,243,227,.10), rgba(77,243,227,.02)),
    var(--panel);
  box-shadow:
    0 0 0 1px rgba(77,243,227,.10),
    0 0 30px rgba(77,243,227,.18),
    inset 0 0 36px rgba(77,243,227,.06);
  animation:heroPulse 3.6s ease-in-out infinite;
}
@keyframes heroPulse{
  50%{box-shadow:
    0 0 0 1px rgba(77,243,227,.20),
    0 0 44px rgba(77,243,227,.32),
    inset 0 0 36px rgba(77,243,227,.10);}
}
/* Coins « HUD » (crochets d'angle) */
.st-key-recette_hero::before,
.st-key-recette_hero::after{
  content:""; position:absolute; width:16px; height:16px; pointer-events:none;
  border:2px solid var(--cyan); opacity:.75;
}
.st-key-recette_hero::before{top:9px; left:9px; border-right:0; border-bottom:0;}
.st-key-recette_hero::after{bottom:9px; right:9px; border-left:0; border-top:0;}

/* Étiquette vedette : plus grande, Orbitron, néon cyan */
.st-key-recette_hero .stSelectbox label{
  font-family:'Orbitron',sans-serif!important; font-weight:700!important;
  font-size:1rem!important; letter-spacing:.20em!important;
  color:#8ff9ee!important; text-shadow:0 0 16px rgba(77,243,227,.45);
  margin-bottom:.15rem!important;
}
.st-key-recette_hero .stSelectbox label::before{content:"▸ "; color:var(--cyan);}

/* Boîte de sélection agrandie et lumineuse */
.st-key-recette_hero div[data-baseweb="select"] > div{
  background:var(--field)!important;
  border:1.5px solid rgba(77,243,227,.55)!important;
  border-radius:12px!important;
  min-height:58px!important;
  box-shadow:0 0 18px rgba(77,243,227,.12)!important;
}
.st-key-recette_hero [data-baseweb="select"] > div > div,
.st-key-recette_hero [data-baseweb="select"] input{
  font-family:'Inter',sans-serif!important;
  font-size:1.15rem!important; font-weight:600!important;
  color:#ffffff!important;
}
.st-key-recette_hero div[data-baseweb="select"] > div:focus-within{
  border-color:var(--cyan)!important;
  box-shadow:0 0 0 2px rgba(77,243,227,.30),0 0 26px rgba(77,243,227,.32)!important;
}
.st-key-recette_hero [data-baseweb="select"] svg{fill:var(--cyan)!important;}

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
/* Texte de la liste des recettes agrandi 1,30× (14px → 18,2px). Le menu du
   selectbox est un <li role="option"> dans un stSelectboxVirtualDropdown : les
   sélecteurs [role="listbox"]/[data-baseweb="menu"] ci-dessus ne l'atteignent
   pas, on cible donc directement l'option. */
[data-testid="stSelectboxVirtualDropdown"] li[role="option"],
[role="option"]{
  font-size:18.2px!important;
}
[role="listbox"] [role="option"]:hover,
[role="listbox"] [role="option"][aria-selected="true"],
[data-baseweb="menu"] li:hover,
[data-baseweb="menu"] li[aria-selected="true"]{
  background-color:rgba(77,243,227,.20)!important; color:#eaffff!important;
}

/* ── Barre de modes — pilules futuristes (remplace les onglets) ────────
   st.radio horizontal, scopé au conteneur .st-key-mode_nav pour ne PAS
   toucher au radio « Source » interne de l'onglet Conversion. Avantage clé :
   le serveur connaît le mode actif, donc passer en « Conversion web » peut
   réinitialiser la recette sélectionnée (impossible avec st.tabs). */
.st-key-mode_nav{margin:.2rem 0 .6rem;}
.st-key-mode_nav [role="radiogroup"]{
  gap:14px!important; flex-wrap:wrap!important; align-items:stretch!important;
  padding:6px 2px 4px!important;
}
/* Chaque option = une pilule ; on masque le cercle radio natif */
.st-key-mode_nav [role="radiogroup"] > label{
  margin:0!important; padding:14px 32px!important; border-radius:12px!important;
  border:1px solid var(--line)!important; background:var(--panel)!important;
  cursor:pointer!important; transition:all .2s!important;
  display:flex!important; align-items:center!important;
}
.st-key-mode_nav [role="radiogroup"] > label > div:first-of-type{display:none!important;}
.st-key-mode_nav [role="radiogroup"] > label p,
.st-key-mode_nav [role="radiogroup"] > label div{
  font-family:'Orbitron',sans-serif!important; font-size:1rem!important;
  font-weight:700!important; letter-spacing:.16em!important; margin:0!important;
}

/* Mode CUISINE — cyan (1re pilule) */
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(1){
  border-color:rgba(77,243,227,.6)!important;
  background:linear-gradient(135deg, rgba(77,243,227,.16), rgba(77,243,227,.05))!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.07),
             0 0 0 1px rgba(77,243,227,.10), 0 6px 16px rgba(0,0,0,.4)!important;
}
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(1) p{
  color:var(--cyan)!important; text-shadow:0 0 12px rgba(77,243,227,.4)!important;
}
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(1):hover{
  transform:translateY(-1px)!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.10),
             0 0 20px rgba(77,243,227,.45), 0 8px 20px rgba(0,0,0,.45)!important;
}
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(1):has(input:checked){
  border-color:var(--cyan)!important; transform:none!important;
  background:linear-gradient(135deg,#4df3e3,#2bd3c4)!important;
  box-shadow:0 0 28px rgba(77,243,227,.7)!important;
}
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(1):has(input:checked) p{
  color:#04060d!important; text-shadow:none!important;
}

/* Mode ÉDITION — ambre (2e pilule) */
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(2){
  border-color:rgba(255,180,84,.6)!important;
  background:linear-gradient(135deg, rgba(255,180,84,.16), rgba(255,180,84,.05))!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.07),
             0 0 0 1px rgba(255,180,84,.10), 0 6px 16px rgba(0,0,0,.4)!important;
}
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(2) p{
  color:var(--amber)!important; text-shadow:0 0 12px rgba(255,180,84,.4)!important;
}
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(2):hover{
  transform:translateY(-1px)!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.10),
             0 0 20px rgba(255,180,84,.45), 0 8px 20px rgba(0,0,0,.45)!important;
}
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(2):has(input:checked){
  border-color:var(--amber)!important; transform:none!important;
  background:linear-gradient(135deg,#ffb454,#ff9d2e)!important;
  box-shadow:0 0 28px rgba(255,180,84,.65)!important;
}
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(2):has(input:checked) p{
  color:#04060d!important; text-shadow:none!important;
}

/* Mode CONVERSION WEB — magenta (3e pilule) */
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(3){
  border-color:rgba(255,122,224,.6)!important;
  background:linear-gradient(135deg, rgba(255,122,224,.16), rgba(255,122,224,.05))!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.07),
             0 0 0 1px rgba(255,122,224,.10), 0 6px 16px rgba(0,0,0,.4)!important;
}
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(3) p{
  color:#ff9ee9!important; text-shadow:0 0 12px rgba(255,122,224,.4)!important;
}
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(3):hover{
  transform:translateY(-1px)!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.10),
             0 0 20px rgba(255,122,224,.45), 0 8px 20px rgba(0,0,0,.45)!important;
}
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(3):has(input:checked){
  border-color:#ff7ae0!important; transform:none!important;
  background:linear-gradient(135deg,#ff7ae0,#e24fc0)!important;
  box-shadow:0 0 28px rgba(255,122,224,.7)!important;
}
.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(3):has(input:checked) p{
  color:#1a0a1e!important; text-shadow:none!important;
}

/* Fond teinté selon le mode actif — repère bien marqué (halo + dégradé). */
.stApp:has(.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(1) input:checked){
  --bg:#03181a; --accent-glow:rgba(77,243,227,.14);
  box-shadow:inset 0 0 320px rgba(77,243,227,.20),
             inset 0 140px 260px -160px rgba(77,243,227,.28)!important;
}
.stApp:has(.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(2) input:checked){
  --bg:#1a1204; --accent-glow:rgba(255,180,84,.12);
  box-shadow:inset 0 0 320px rgba(255,180,84,.18),
             inset 0 140px 260px -160px rgba(255,180,84,.24)!important;
}
.stApp:has(.st-key-mode_nav [role="radiogroup"] > label:nth-of-type(3) input:checked){
  --bg:#1a0a1e; --accent-glow:rgba(255,122,224,.12);
  box-shadow:inset 0 0 320px rgba(255,122,224,.16),
             inset 0 140px 260px -160px rgba(255,122,224,.22)!important;
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
/* ── Lisibilité : texte Streamlit « par défaut » ───────────
   Aucun thème [dark] n'est configuré, donc Streamlit applique un
   gris très foncé (#31333F) à TOUT texte sans couleur explicite :
   titres markdown, libellés de widgets, options de radio, listes,
   blocs d'aperçu… illisible sur le fond sombre. On force une
   couleur claire. Les couleurs volontairement atténuées (captions,
   sous-titres) sont réaffirmées juste après avec une spécificité
   supérieure, donc elles restent atténuées mais lisibles. */
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4,
[data-testid="stMarkdownContainer"] h5,
[data-testid="stMarkdownContainer"] h6,
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label,
[data-testid="stRadio"] label,
[role="radiogroup"] label{
  color:var(--text)!important;
}
[data-testid="stCaptionContainer"] [data-testid="stMarkdownContainer"] p,
[data-testid="stCaptionContainer"] p{
  font-family:'JetBrains Mono',monospace!important; font-size:.8rem!important;
  color:#d6ddf4!important; letter-spacing:.06em;
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
# st.iframe : remplaçant de st.components.v1.html (déprécié, retiré après 2026-06).
# Une chaîne HTML brute est auto-détectée et rendue dans un iframe sandboxé.
st.iframe(
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
    background:#1c232a;color:#d6ddf4;letter-spacing:.1em;
  }
  #wl-btn.on{border-color:#4df3e3;color:#e6fffb;box-shadow:0 0 0 1px rgba(77,243,227,.25);}
  #wl-btn.on .wl-dot{background:#4df3e3;box-shadow:0 0 10px 2px rgba(77,243,227,.6);}
  #wl-btn.on .wl-state{background:rgba(77,243,227,.15);color:#4df3e3;}
  #wl-btn:disabled{opacity:.5;cursor:not-allowed;}
  #wl-note{margin:0;font-size:.62rem;color:#93a2c6;letter-spacing:.04em;}
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
             "les valeurs par défaut. Par sécurité, les sauvegardes sont "
             "BLOQUÉES tant que la lecture n'a pas réussi, pour ne pas écraser "
             "la référence git. Recharge la page une fois GitHub de nouveau "
             "accessible.")

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
        # Conteneur « vedette » : ce sélecteur est LE point d'entrée du site,
        # on le met très en évidence via le CSS ciblé sur .st-key-recette_hero.
        with st.container(key="recette_hero"):
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
                f"color:#d6ddf4;letter-spacing:.06em;margin:.35rem 0 0;\">"
                f"{len(indices)} recette{'s' if len(indices) > 1 else ''} "
                f"sur {len(RECETTES)} affichée"
                f"{'s' if len(indices) > 1 else ''}.</p>",
                unsafe_allow_html=True)

recette = RECETTES[st.session_state.sel] if st.session_state.sel is not None else None
base = recette["base"] if recette else None

VUE_CUISINE = "◈  CUISINE"
VUE_EDITION = "⚙  ÉDITION"
VUE_CONVERSION = "🌐  CONVERSION WEB"

def _on_vue_change():
    # « Conversion web » crée une NOUVELLE recette : on repart d'une sélection
    # vide pour éviter toute confusion avec la recette précédemment ouverte.
    # (Ce reset côté serveur est la raison d'être du st.radio ci-dessous : avec
    #  st.tabs, le changement d'onglet est purement côté navigateur, invisible
    #  du serveur, donc impossible à intercepter.)
    if st.session_state.get("vue_active") == VUE_CONVERSION:
        st.session_state.recette_select = ""    # VIDE
        st.session_state.sel = None

with st.container(key="mode_nav"):
    vue = st.radio(
        "Mode", [VUE_CUISINE, VUE_EDITION, VUE_CONVERSION],
        key="vue_active", horizontal=True, label_visibility="collapsed",
        on_change=_on_vue_change,
    )

# ═════════════════════════════════════════════════════════════════════════════
#  NOTES (★) ET COMMENTAIRES — affichés à la FIN d'une recette, en cuisine
#
#  Tout le monde peut ajouter/modifier/supprimer (app familiale, sans compte).
#  Chaque écriture recharge le fichier le plus à jour, applique la mutation et
#  réécrit (muter_json_annexe) : robuste aux contributions concurrentes.
# ═════════════════════════════════════════════════════════════════════════════
def _note_ajouter(recette_id, nom, etoiles):
    def m(data):
        data.setdefault("notes", [])
        pid = data.get("prochain_id", 1)
        now = _maintenant_iso()
        data["notes"].append({"id": pid, "recette_id": recette_id, "nom": nom,
                              "etoiles": etoiles, "cree": now, "modifie": now})
        data["prochain_id"] = pid + 1
    return muter_json_annexe(NOTES_FICHIER, NOTES_DEFAUT, m)


def _note_modifier(note_id, nom, etoiles):
    def m(data):
        for n in data.get("notes", []):
            if n.get("id") == note_id:
                n["nom"], n["etoiles"] = nom, etoiles
                n["modifie"] = _maintenant_iso()
    return muter_json_annexe(NOTES_FICHIER, NOTES_DEFAUT, m)


def _note_supprimer(note_id):
    def m(data):
        data["notes"] = [n for n in data.get("notes", []) if n.get("id") != note_id]
    return muter_json_annexe(NOTES_FICHIER, NOTES_DEFAUT, m)


def _commentaire_ajouter(recette_id, nom, texte):
    def m(data):
        data.setdefault("commentaires", [])
        pid = data.get("prochain_id", 1)
        now = _maintenant_iso()
        data["commentaires"].append({"id": pid, "recette_id": recette_id, "nom": nom,
                                     "texte": texte, "cree": now, "modifie": now,
                                     "reponses": []})
        data["prochain_id"] = pid + 1
    return muter_json_annexe(COMMENTAIRES_FICHIER, COMMENTAIRES_DEFAUT, m)


def _commentaire_modifier(comm_id, nom, texte):
    def m(data):
        for c in data.get("commentaires", []):
            if c.get("id") == comm_id:
                c["nom"], c["texte"] = nom, texte
                c["modifie"] = _maintenant_iso()
    return muter_json_annexe(COMMENTAIRES_FICHIER, COMMENTAIRES_DEFAUT, m)


def _commentaire_supprimer(comm_id):
    def m(data):
        data["commentaires"] = [c for c in data.get("commentaires", [])
                                if c.get("id") != comm_id]
    return muter_json_annexe(COMMENTAIRES_FICHIER, COMMENTAIRES_DEFAUT, m)


def _reponse_ajouter(comm_id, nom, texte):
    def m(data):
        pid = data.get("prochain_id", 1)
        now = _maintenant_iso()
        for c in data.get("commentaires", []):
            if c.get("id") == comm_id:
                c.setdefault("reponses", []).append(
                    {"id": pid, "nom": nom, "texte": texte, "cree": now, "modifie": now})
                data["prochain_id"] = pid + 1
                break
    return muter_json_annexe(COMMENTAIRES_FICHIER, COMMENTAIRES_DEFAUT, m)


def _reponse_modifier(comm_id, rep_id, nom, texte):
    def m(data):
        for c in data.get("commentaires", []):
            if c.get("id") == comm_id:
                for rep in c.get("reponses", []):
                    if rep.get("id") == rep_id:
                        rep["nom"], rep["texte"] = nom, texte
                        rep["modifie"] = _maintenant_iso()
    return muter_json_annexe(COMMENTAIRES_FICHIER, COMMENTAIRES_DEFAUT, m)


def _reponse_supprimer(comm_id, rep_id):
    def m(data):
        for c in data.get("commentaires", []):
            if c.get("id") == comm_id:
                c["reponses"] = [r for r in c.get("reponses", [])
                                 if r.get("id") != rep_id]
    return muter_json_annexe(COMMENTAIRES_FICHIER, COMMENTAIRES_DEFAUT, m)


def _appliquer(resultat, cle_data, cle_erreur):
    """Applique le résultat d'une mutation annexe : met à jour la session et
    relance si OK, affiche l'erreur sinon. `resultat` = (data, ok, err)."""
    data, ok, err = resultat
    if ok:
        st.session_state[cle_data] = data
        st.session_state[cle_erreur] = None
        st.rerun()
    else:
        st.error(f"⚠ Enregistrement échoué — {err}")


def _horodatage(item):
    """« le 2026-07-14 11:30 » + « · modifié le … » si l'item a été édité."""
    cree = item.get("cree", "")
    txt = f"le {cree}" if cree else ""
    if item.get("modifie") and item["modifie"] != cree:
        txt += f" · modifié le {item['modifie']}"
    return txt


def afficher_notes_commentaires(recette):
    """Volet dépliable (replié par défaut) en fin de recette. Son TITRE résume
    déjà la note moyenne et le nombre de commentaires ; le détail (formulaires,
    liste, réponses) est à l'intérieur, ce qui garde la zone compacte et bien
    repérable malgré la hauteur de la carte de recette."""
    rid = recette.get("id")
    notes_data = st.session_state.notes_data
    comm_data = st.session_state.commentaires_data
    moy, nb = moyenne_notes(notes_data, rid)
    nb_comm = sum(1 for c in comm_data.get("commentaires", []) if c.get("recette_id") == rid)
    note_txt = f"⭐ {moy:.1f}/5 ({nb})" if nb else "⭐ Aucune note"
    titre = (f"{note_txt}   ·   💬 {nb_comm} commentaire{'s' if nb_comm > 1 else ''}"
             "     —     Notes & commentaires")
    # Le volet est habillé pour se lire comme une SECTION de la carte (même fond,
    # même bordure/rayon, accent gauche doré comme « Préparation ») et collé sous
    # elle (marge négative) : visuellement, il prolonge le même rectangle.
    st.markdown("""<style>
.st-key-notes_card{margin-top:-14px}
.st-key-notes_card [data-testid="stExpander"]{
  border:1px solid #1e2a45;border-left:3px solid #ffb454;border-radius:14px;
  background:linear-gradient(180deg, rgba(14,22,40,.95), rgba(6,10,20,.95));
  box-shadow:0 18px 44px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.04)}
.st-key-notes_card [data-testid="stExpander"] summary{font-family:'JetBrains Mono',monospace;
  letter-spacing:.05em;text-transform:uppercase;font-size:.82rem;color:#ffe6c2}
.st-key-notes_card [data-testid="stExpander"] summary:hover{color:#fff}
/* Étoiles de notation : contour des étoiles VIDES en blanc (trop sombre par
   défaut sur fond foncé), étoiles CHOISIES en doré. */
[data-testid="stFeedback"] [data-testid="stIconMaterial"]{color:#eef2ff!important}
[data-testid="stFeedback"] [aria-checked="true"] [data-testid="stIconMaterial"]{color:#ffb454!important}
</style>""", unsafe_allow_html=True)
    with st.container(key="notes_card"):
        with st.expander(titre, expanded=False):
            _contenu_notes_commentaires(recette)


def _contenu_notes_commentaires(recette):
    """Détail des notes (★) puis des commentaires (avec réponses), rendu à
    l'intérieur du volet dépliable."""
    rid = recette.get("id")
    notes_data = st.session_state.notes_data
    comm_data = st.session_state.commentaires_data

    if st.session_state.get("erreur_notes") or st.session_state.get("erreur_commentaires"):
        st.warning("Les notes/commentaires n'ont pas pu être lus (mode dégradé). "
                   "Réessaie plus tard ; n'écris pas pour éviter d'écraser des données.")

    # ── NOTES ★ ──────────────────────────────────────────────────────────────
    moy, nb = moyenne_notes(notes_data, rid)
    entete = (f"⭐ Notes — {moy:.1f}/5 sur {nb} note{'s' if nb > 1 else ''}"
              if nb else "⭐ Notes — aucune note pour l'instant")
    st.markdown(f"### {entete}")

    with st.form(key=f"form_note_{rid}", clear_on_submit=True):
        st.markdown("**Laisser une note**")
        nom_n = st.text_input("Ton nom *", key=f"nom_note_{rid}",
                              placeholder="Obligatoire")
        etoiles_n = st.feedback("stars", key=f"etoiles_note_{rid}")
        if st.form_submit_button("Noter", type="primary"):
            if not (nom_n or "").strip():
                st.error("Le nom est obligatoire.")
            elif etoiles_n is None:
                st.error("Choisis une note en étoiles.")
            else:
                _appliquer(_note_ajouter(rid, nom_n.strip(), etoiles_n + 1),
                           "notes_data", "erreur_notes")

    notes_recette = [n for n in notes_data.get("notes", []) if n.get("recette_id") == rid]
    for n in reversed(notes_recette):
        nid = n.get("id")
        if st.session_state.get(f"edit_note_{nid}"):
            with st.form(key=f"form_edit_note_{nid}", clear_on_submit=False):
                nom_e = st.text_input("Nom *", value=n.get("nom", ""),
                                      key=f"nom_edit_note_{nid}")
                st.caption(f"Note actuelle : {n.get('etoiles', 0)}/5 — choisis la nouvelle")
                et_e = st.feedback("stars", key=f"et_edit_note_{nid}")
                c1, c2 = st.columns(2)
                if c1.form_submit_button("Enregistrer", type="primary"):
                    if not (nom_e or "").strip():
                        st.error("Le nom est obligatoire.")
                    elif et_e is None:
                        st.error("Choisis une note en étoiles.")
                    else:
                        st.session_state[f"edit_note_{nid}"] = False
                        _appliquer(_note_modifier(nid, nom_e.strip(), et_e + 1),
                                   "notes_data", "erreur_notes")
                if c2.form_submit_button("Annuler"):
                    st.session_state[f"edit_note_{nid}"] = False
                    st.rerun()
        else:
            etoiles_txt = "★" * int(n.get("etoiles", 0)) + "☆" * (5 - int(n.get("etoiles", 0)))
            c_txt, c_ed, c_sup = st.columns([6, 1, 1])
            c_txt.markdown(
                f"<span style='color:#ffb454'>{etoiles_txt}</span> "
                f"**{html_escape(n.get('nom', ''))}** "
                f"<span style='color:#9fb0d8;font-size:.8rem'>{_horodatage(n)}</span>",
                unsafe_allow_html=True)
            if c_ed.button("✏️", key=f"btn_edit_note_{nid}", help="Modifier"):
                st.session_state[f"edit_note_{nid}"] = True
                st.rerun()
            if c_sup.button("🗑", key=f"btn_sup_note_{nid}", help="Supprimer"):
                _appliquer(_note_supprimer(nid), "notes_data", "erreur_notes")

    # ── COMMENTAIRES ─────────────────────────────────────────────────────────
    commentaires = [c for c in comm_data.get("commentaires", []) if c.get("recette_id") == rid]
    st.markdown(f"### 💬 Commentaires ({len(commentaires)})")

    with st.form(key=f"form_comm_{rid}", clear_on_submit=True):
        st.markdown("**Laisser un commentaire**")
        nom_c = st.text_input("Ton nom *", key=f"nom_comm_{rid}",
                              placeholder="Obligatoire")
        texte_c = st.text_area("Commentaire", key=f"texte_comm_{rid}")
        if st.form_submit_button("Commenter", type="primary"):
            if not (nom_c or "").strip():
                st.error("Le nom est obligatoire.")
            elif not (texte_c or "").strip():
                st.error("Le commentaire ne peut pas être vide.")
            else:
                _appliquer(_commentaire_ajouter(rid, nom_c.strip(), texte_c.strip()),
                           "commentaires_data", "erreur_commentaires")

    for c in reversed(commentaires):
        cid = c.get("id")
        with st.container(border=True):
            if st.session_state.get(f"edit_comm_{cid}"):
                with st.form(key=f"form_edit_comm_{cid}", clear_on_submit=False):
                    nom_ce = st.text_input("Nom *", value=c.get("nom", ""),
                                           key=f"nom_edit_comm_{cid}")
                    txt_ce = st.text_area("Commentaire", value=c.get("texte", ""),
                                          key=f"txt_edit_comm_{cid}")
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Enregistrer", type="primary"):
                        if not (nom_ce or "").strip():
                            st.error("Le nom est obligatoire.")
                        elif not (txt_ce or "").strip():
                            st.error("Le commentaire ne peut pas être vide.")
                        else:
                            st.session_state[f"edit_comm_{cid}"] = False
                            _appliquer(_commentaire_modifier(cid, nom_ce.strip(), txt_ce.strip()),
                                       "commentaires_data", "erreur_commentaires")
                    if c2.form_submit_button("Annuler"):
                        st.session_state[f"edit_comm_{cid}"] = False
                        st.rerun()
            else:
                st.markdown(
                    f"**{html_escape(c.get('nom', ''))}** "
                    f"<span style='color:#9fb0d8;font-size:.8rem'>{_horodatage(c)}</span>",
                    unsafe_allow_html=True)
                st.markdown(html_escape(c.get("texte", "")).replace("\n", "  \n"))
                b1, b2, b3, _ = st.columns([1.3, 1, 1, 4])
                if b1.button("💬 Répondre", key=f"btn_rep_{cid}"):
                    st.session_state[f"rep_comm_{cid}"] = not st.session_state.get(f"rep_comm_{cid}")
                    st.rerun()
                if b2.button("✏️", key=f"btn_edit_comm_{cid}", help="Modifier"):
                    st.session_state[f"edit_comm_{cid}"] = True
                    st.rerun()
                if b3.button("🗑", key=f"btn_sup_comm_{cid}", help="Supprimer"):
                    _appliquer(_commentaire_supprimer(cid),
                               "commentaires_data", "erreur_commentaires")

            # Réponses (un seul niveau), légèrement indentées.
            for rep in c.get("reponses", []):
                repid = rep.get("id")
                with st.container():
                    cg, cd = st.columns([0.4, 9.6])
                    with cd:
                        if st.session_state.get(f"edit_rep_{repid}"):
                            with st.form(key=f"form_edit_rep_{repid}", clear_on_submit=False):
                                nom_re = st.text_input("Nom *", value=rep.get("nom", ""),
                                                       key=f"nom_edit_rep_{repid}")
                                txt_re = st.text_area("Réponse", value=rep.get("texte", ""),
                                                      key=f"txt_edit_rep_{repid}")
                                cc1, cc2 = st.columns(2)
                                if cc1.form_submit_button("Enregistrer", type="primary"):
                                    if not (nom_re or "").strip():
                                        st.error("Le nom est obligatoire.")
                                    elif not (txt_re or "").strip():
                                        st.error("La réponse ne peut pas être vide.")
                                    else:
                                        st.session_state[f"edit_rep_{repid}"] = False
                                        _appliquer(_reponse_modifier(cid, repid, nom_re.strip(), txt_re.strip()),
                                                   "commentaires_data", "erreur_commentaires")
                                if cc2.form_submit_button("Annuler"):
                                    st.session_state[f"edit_rep_{repid}"] = False
                                    st.rerun()
                        else:
                            st.markdown(
                                f"↳ **{html_escape(rep.get('nom', ''))}** "
                                f"<span style='color:#9fb0d8;font-size:.8rem'>{_horodatage(rep)}</span>",
                                unsafe_allow_html=True)
                            st.markdown(html_escape(rep.get("texte", "")).replace("\n", "  \n"))
                            r1, r2, _ = st.columns([1, 1, 6])
                            if r1.button("✏️", key=f"btn_edit_rep_{repid}", help="Modifier"):
                                st.session_state[f"edit_rep_{repid}"] = True
                                st.rerun()
                            if r2.button("🗑", key=f"btn_sup_rep_{repid}", help="Supprimer"):
                                _appliquer(_reponse_supprimer(cid, repid),
                                           "commentaires_data", "erreur_commentaires")

            # Formulaire de réponse (affiché à la demande via « Répondre »).
            if st.session_state.get(f"rep_comm_{cid}"):
                with st.form(key=f"form_rep_{cid}", clear_on_submit=True):
                    nom_r = st.text_input("Ton nom *", key=f"nom_rep_{cid}",
                                          placeholder="Obligatoire")
                    txt_r = st.text_area("Ta réponse", key=f"txt_rep_{cid}")
                    if st.form_submit_button("Répondre", type="primary"):
                        if not (nom_r or "").strip():
                            st.error("Le nom est obligatoire.")
                        elif not (txt_r or "").strip():
                            st.error("La réponse ne peut pas être vide.")
                        else:
                            st.session_state[f"rep_comm_{cid}"] = False
                            _appliquer(_reponse_ajouter(cid, nom_r.strip(), txt_r.strip()),
                                       "commentaires_data", "erreur_commentaires")


# ═════════════════════════════════════════════════════════════════════════════
#  ONGLET CUISINE — mise à l'échelle + checklist
# ═════════════════════════════════════════════════════════════════════════════
if vue == VUE_CUISINE:
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
    pas_pers = int(base.get("pas_personnes") or personnes_ref)
    if pas_pers < 1:
        pas_pers = 1

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
            # Ajustement par paliers fixes : le champ ne saute que par pas de
            # pas_pers (ex. personnes_ref=4, pas_pers=2 → 4 → 6 → 8…), jamais
            # une personne à la fois. pas_pers peut différer de personnes_ref
            # (ex. +2 personnes plutôt que de doubler direct de 4 à 8).
            nb_paliers_max = (max_pers - personnes_ref) // pas_pers
            max_mult_pers = personnes_ref + nb_paliers_max * pas_pers
            if max_mult_pers < personnes_ref:
                max_mult_pers = personnes_ref
            cible_pers = st.number_input(
                "🍽️  Nombre de personnes",
                min_value=personnes_ref, max_value=max_mult_pers,
                value=personnes_ref, step=pas_pers,
                key=f"cible_{st.session_state.sel}",
                help=f"Recette ajustée par paliers de {pas_pers} "
                     f"personne{'s' if pas_pers > 1 else ''} "
                     f"(à partir de {personnes_ref}).")
            # On garantit un palier exact même si une valeur est saisie à la main.
            nb_paliers = int(round((cible_pers - personnes_ref) / pas_pers))
            cible_pers = personnes_ref + nb_paliers * pas_pers
            cible_pers = max(personnes_ref, min(cible_pers, max_mult_pers))
            # Note à .8rem, bien claire (couleur --text plutôt que muted).
            st.markdown(
                f"<div style=\"font-family:'JetBrains Mono',monospace;"
                f"font-size:.8rem;font-weight:600;color:var(--text);"
                f"letter-spacing:.06em;margin-top:-.35rem;\">"
                f"⏫ Ajusté par paliers de {pas_pers} "
                f"personne{'s' if pas_pers > 1 else ''} "
                f"(+{nb_paliers * pas_pers} par rapport à {personnes_ref}).</div>",
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
    # La NOTE moyenne (★) est la toute première puce : c'est ce que l'utilisateur
    # veut voir en premier en ouvrant une recette.
    _moy, _nb = moyenne_notes(st.session_state.notes_data, recette.get("id"))
    if _nb:
        _pleines = int(round(_moy))
        _etoiles = "★" * _pleines + "☆" * (5 - _pleines)
        note_chip = (f'<span class="chip chip-note">{_etoiles} '
                     f'<b>{_moy:.1f}</b>/5 · {_nb} note{"s" if _nb > 1 else ""}</span>')
    else:
        note_chip = '<span class="chip chip-note">☆☆☆☆☆ <b>—</b> · Aucune note</span>'
    chips = [note_chip,
             f'<span class="chip chip-ref">Personnes · <b>{cible_pers:g}</b></span>']
    if par_multiples:
        chips.append(f'<span class="chip">Palier · '
                     f'<b>+{pas_pers}</b></span>')
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
    index_ing = index_marqueurs(recette["ingredients"])

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
    section_courante = None
    for ing in recette["ingredients"]:
        sec = (ing.get("section") or "").strip()
        if sec != section_courante:          # nouveau groupe : sous-titre
            section_courante = sec
            if sec:
                lignes_ing += (f'<div class="ing-groupe">'
                               f'{html_escape(sec)}</div>')
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
    # Les portions explicites [ing: N unité] servent à calculer le « reste ».
    etapes_prep = recette.get("preparation", [])
    allocations = calc_allocations([_etape_texte(e) for e in etapes_prep], index_ing)
    lignes_prep = ""
    section_prep = None
    i = 0
    for etape in etapes_prep:
        sec = _etape_section(etape).strip()
        if sec != section_prep:              # nouveau groupe : sous-titre + reset
            section_prep = sec
            i = 0
            if sec:
                lignes_prep += (f'<div class="step-groupe">'
                                f'{html_escape(sec)}</div>')
        i += 1
        texte = injecter_quantites(html_escape(_etape_texte(etape)), index_ing,
                                   facteur, allocations)
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

    somm_count = (f'+{pas_pers} · {cible_pers:g} pers.' if par_multiples
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
.rsub{color:#d6ddf4;font-size:.9rem;margin-top:3px}
.meta{display:flex;gap:10px;flex-wrap:wrap}
.chip{font-family:'JetBrains Mono',monospace;font-size:.82rem;color:#9fb0d8;
  border:1px solid #1e2a45;border-radius:999px;padding:5px 12px;background:rgba(77,243,227,.05)}
.chip b{color:#ffb454}
.chip-ref{border-color:#4df3e3;background:rgba(77,243,227,.12);color:#cfe9ff;
  box-shadow:0 0 14px rgba(77,243,227,.25)}
.chip-ref b{color:#4df3e3;text-shadow:0 0 12px rgba(77,243,227,.6)}
.chip-note{border-color:#ffb454;background:rgba(255,180,84,.12);color:#ffe6c2;
  box-shadow:0 0 14px rgba(255,180,84,.22);letter-spacing:.04em}
.chip-note b{color:#ffb454;text-shadow:0 0 12px rgba(255,180,84,.55)}
.sommaire-rel{font-family:'Inter',sans-serif;font-size:.82rem;color:#9fb0d8;
  margin-top:11px;padding:9px 12px;border-radius:10px;border:1px dashed #26355c;
  background:rgba(77,243,227,.04)}
.sommaire-rel b{color:#ffb454;font-weight:700}
.tags-titre{font-family:'JetBrains Mono',monospace;font-size:.64rem;letter-spacing:.2em;
  text-transform:uppercase;color:#d6ddf4;margin:12px 0 2px}
.prog{height:4px;background:#141d34;border-radius:999px;margin-top:15px;overflow:hidden}
.progfill{height:100%;width:0;background:linear-gradient(90deg,#4df3e3,#ffb454);
  box-shadow:0 0 14px rgba(77,243,227,.6);transition:width .35s ease}
.count{font-family:'JetBrains Mono',monospace;font-size:.8rem;color:#d6ddf4;margin-top:7px;letter-spacing:.12em}

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
.ing.done .nom{color:#7d8cb5;text-decoration:line-through}
.qte{font-family:'JetBrains Mono',monospace;font-size:1rem;color:#9fb0d8;white-space:nowrap;
  padding:4px 11px;border-radius:8px;border:1px solid #26355c;background:rgba(255,180,84,.06)}
.qte b{color:#ffb454;text-shadow:0 0 12px rgba(255,180,84,.45);font-weight:700}
.qte.gout{color:#d6ddf4;background:transparent;border-color:transparent}
.qte.gout b{color:#d6ddf4;text-shadow:none;font-weight:500}
.ing.done .qte{opacity:.35}
/* Sous-titre de groupe d'ingrédients (« Garniture », « Bouillon »…). */
.ing-groupe{font-family:'Orbitron',sans-serif;font-size:.72rem;font-weight:700;
  letter-spacing:.14em;text-transform:uppercase;color:#4df3e3;
  padding:14px 12px 4px;margin-top:4px;border-top:1px solid #1e2a45}
.ing-groupe:first-child{border-top:none;margin-top:0;padding-top:4px}
/* Sous-titre de groupe d'étapes (variante ambre, cohérente avec la préparation) */
.step-groupe{font-family:'Orbitron',sans-serif;font-size:.72rem;font-weight:700;
  letter-spacing:.14em;text-transform:uppercase;color:#ffb454;
  padding:14px 12px 4px;margin-top:4px;border-top:1px solid #3a2a12}
.step-groupe:first-child{border-top:none;margin-top:0;padding-top:4px}
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
.hint{font-family:'JetBrains Mono',monospace;font-size:.66rem;color:#7d8cb5;
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
/* Nom d'ingrédient « variable » : souligné pointillé discret pour dire
   « ce mot est dynamique », suivi de sa quantité en pastille (.inq). */
.inqnom{border-bottom:1px dotted rgba(255,180,84,.55);color:#ffd9a6}
.inq{font-family:'JetBrains Mono',monospace;color:#ffb454;font-weight:700;
  background:rgba(255,180,84,.1);padding:1px 6px;border-radius:5px;white-space:nowrap;
  text-shadow:0 0 10px rgba(255,180,84,.35)}
.ing.done .inqnom{opacity:.4;border-bottom-color:transparent;color:inherit}
.ing.done .inq{opacity:.4;text-shadow:none}

/* Overlay de victoire — apparaît quand tout est coché */
.victoire{
  position:absolute;inset:0;z-index:10;
  background:rgba(4,6,13,.86);backdrop-filter:blur(3px);border-radius:16px;
  opacity:0;visibility:hidden;transition:opacity .35s ease, visibility .35s;cursor:pointer;
}
.victoire.visible{opacity:1;visibility:visible;}
/* La cadre (gif + textes) est positionnée par JS au centre de la portion
   réellement visible à l'écran (voir positionVictoire), pas au milieu de toute
   la carte : sur mobile/tablette la carte dépasse l'écran et l'animation
   pouvait tomber hors champ. « top » est ajusté dynamiquement. */
.v-cadre{
  position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);
  text-align:center;padding:18px;animation:pop .45s cubic-bezier(.2,1.4,.4,1);
}
@keyframes pop{
  from{transform:translateY(-50%) scale(.7);opacity:0}
  to{transform:translateY(-50%) scale(1);opacity:1}
}
@media (prefers-reduced-motion: reduce){.v-cadre{animation:none}}
.v-cadre img{
  max-width:min(280px,70vw);max-height:44vh;border-radius:14px;
  border:2px solid #4df3e3;box-shadow:0 0 34px rgba(77,243,227,.55);
}
.v-titre{font-family:'Orbitron',sans-serif;font-weight:900;font-size:1.05rem;
  color:#4df3e3;letter-spacing:.16em;margin-top:14px;
  text-shadow:0 0 18px rgba(77,243,227,.7)}
.v-sous{font-family:'JetBrains Mono',monospace;font-size:.66rem;color:#d6ddf4;
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
    var fe=window.frameElement;
    if(fe){
      var h=document.documentElement.scrollHeight;
      fe.style.height=h+'px';
      // Le conteneur Streamlit (stElementContainer) conserve la hauteur RÉSERVÉE
      // (paramètre height=), figée. Si on ne l'ajuste pas, l'iframe agrandie
      // déborde par-dessus le contenu qui suit (les notes). On aligne donc le
      // conteneur sur la hauteur réelle : la carte colle exactement à son
      // contenu (aucun vide) sans jamais chevaucher les notes. Same-origin
      // (srcdoc) → l'accès au parent est autorisé.
      if(fe.parentElement){ fe.parentElement.style.height=h+'px'; }
    }
  }catch(e){}
}
// Centre vertical (en coordonnées internes à l'iframe) de la portion de la carte
// réellement visible dans la fenêtre du navigateur parent. L'iframe fait toute
// la hauteur du contenu et c'est la page Streamlit parente qui défile : on lit
// donc la position de l'iframe dans le viewport parent pour savoir où regarde
// l'utilisateur. Repli : centre du document si l'accès parent est refusé.
function centreVisible(){
  var h=document.documentElement.scrollHeight;
  try{
    var fe=window.frameElement;
    if(fe){
      var r=fe.getBoundingClientRect();
      var vpH=(window.parent&&window.parent.innerHeight)||window.innerHeight;
      var haut=Math.max(0,-r.top);
      var bas=Math.min(h, vpH-r.top);
      if(bas>haut){ return (haut+bas)/2; }
    }
  }catch(e){}
  return h/2;
}
// Place la cadre de chaque overlay au centre de la zone visible. Le « top » est
// relatif à l'overlay (.victoire, inset:0 sur la carte) : on soustrait donc son
// décalage. L'iframe n'ayant pas de défilement interne, getBoundingClientRect
// donne directement le décalage dans le document.
function positionVictoire(){
  var centre=centreVisible();
  var ov=document.querySelectorAll('.victoire');
  for(var i=0;i<ov.length;i++){
    var cadre=ov[i].querySelector('.v-cadre');
    if(!cadre) continue;
    cadre.style.top=(centre-ov[i].getBoundingClientRect().top)+'px';
  }
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
  if(montrePrep || montreIng){ positionVictoire(); }
  document.getElementById('victoire-prep').classList.toggle('visible', montrePrep);
  document.getElementById('victoire-ing').classList.toggle('visible', montreIng);
}
function fermer(quoi){
  if(quoi==='prep'){fermePrep=true;}else{fermeIng=true;}
  maj();
}
window.addEventListener('load', restaurerSections);
window.addEventListener('load', resizeFrame);
window.addEventListener('load', positionVictoire);
window.addEventListener('resize', resizeFrame);
window.addEventListener('resize', positionVictoire);
// Suivre le défilement pour garder l'animation dans le champ de vision. Le
// défilement se produit sur la page parente (l'iframe fait toute la hauteur) ;
// on écoute donc le parent, avec repli sur l'iframe si l'accès est refusé.
window.addEventListener('scroll', positionVictoire, {passive:true});
try{
  if(window.parent && window.parent!==window){
    window.parent.addEventListener('scroll', positionVictoire, {passive:true});
  }
}catch(e){}
restaurerSections();
resizeFrame();
positionVictoire();
</script></body></html>
"""

    html = (TEMPLATE
            .replace("__TITRE__", html_escape(recette["titre"]))
            .replace("__SOUS__", html_escape(recette.get("sous_titre", "")))
            .replace("__N__", str(n))
            .replace("__GIF_ING__", gif_src(GIF_INGREDIENTS_FICHIER))
            .replace("__GIF_PREP__", gif_src(GIF_PREPARATION_FICHIER))
            .replace("__ROWS__", rows))

    # Hauteur INITIALE volontairement PETITE : resizeFrame() (iframe srcdoc,
    # same-origin) agrandit l'iframe pile au contenu réel dès le chargement, puis
    # à chaque section dépliée. Comme il ne peut jamais RÉTRÉCIR sous la valeur
    # passée ici (documentElement remplit le viewport → scrollHeight ≥ hauteur),
    # on sous-estime exprès : ainsi la carte colle exactement à son contenu, sans
    # aucun vide en bas, quelle que soit la recette (avec ou sans ingrédients).
    hauteur = 200
    st.iframe(html, height=hauteur)

    # NOTES (★) et COMMENTAIRES — à la toute fin de la recette.
    afficher_notes_commentaires(recette)


# ═════════════════════════════════════════════════════════════════════════════
#  ONGLET CONVERSION WEB — importer une recette depuis une URL ou du texte collé
# ═════════════════════════════════════════════════════════════════════════════
def _liberer_memoire():
    """Rend au système la mémoire transitoire allouée par le process principal
    (typiquement après une conversion web, qui parse du HTML et a lancé un
    navigateur en sous-processus). `gc.collect()` casse les cycles Python ;
    `malloc_trim(0)` (glibc/Linux) rend au noyau les arènes déjà libérées — sans
    quoi le process conserve son pic mémoire même après coup, ce qui pèse sur un
    conteneur contraint (Streamlit Cloud ≈ 1 Go). Sans effet hors Linux/glibc ;
    n'échoue jamais."""
    import gc
    import sys
    gc.collect()
    if sys.platform.startswith("linux"):
        try:
            import ctypes
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:
            pass


if vue == VUE_CONVERSION:
    st.markdown("#### 🌐 Convertir une recette du web")
    st.caption("Colle l'adresse (URL) d'une recette OU colle directement son "
               "texte. L'IA la convertit au format du grimoire, en français. "
               "Tu pourras la peaufiner ensuite dans l'onglet ⚙ ÉDITION.")

    # Confirmation après un ajout au menu (survit au rerun du callback).
    # Bandeau PERSISTANT (reste jusqu'à la prochaine action) : contrairement à un
    # toast transitoire, impossible à manquer même si la page se raccourcit.
    titre_ajoute = st.session_state.pop("_conv_ajoutee", None)
    if titre_ajoute:
        st.success(f"✅ « {titre_ajoute} » ajoutée au menu ! "
                   "Peaufine-la dans l'onglet ⚙ ÉDITION.")
    # Bandeau d'échec si le titre double une recette existante (anti-doublon).
    titre_doublon = st.session_state.pop("_conv_doublon", None)
    if titre_doublon:
        st.error(f"⛔ « {titre_doublon} » n'a pas été ajoutée : une recette porte "
                 "déjà ce titre (comparaison sans casse ni accents). Renomme la "
                 "recette existante ou modifie le titre avant de l'ajouter.")
    doublon_ing = st.session_state.pop("_conv_doublon_ing", None)
    if doublon_ing:
        titre_conv, jumelle = doublon_ing
        st.error(f"⛔ « {titre_conv} » n'a pas été ajoutée : la recette "
                 f"« {jumelle} » a exactement la même liste d'ingrédients "
                 "(probable doublon). Vérifie avant de l'ajouter.")
    # Aperçu annulé : bandeau persistant, impossible à manquer.
    if st.session_state.pop("_conv_annulee", False):
        st.info("↩️ Aperçu annulé. Tu peux convertir une autre recette.")

    cfg = _anthropic_cfg()
    if cfg is None:
        st.warning("🔑 Clé API Claude absente. Ajoute une section **[anthropic]** "
                   "(api_key) dans les secrets Streamlit pour activer la "
                   "conversion.")
    else:
        entree = st.text_area(
            "Recette à convertir", key="conv_entree", height=220,
            placeholder="Colle une adresse web (https://…) ou le texte complet "
                        "de la recette — la détection est automatique.")

        if st.button("✨ Convertir", type="primary", use_container_width=True,
                     key="conv_go"):
            for cle in ("conv_resultat", "conv_source", "conv_erreur"):
                st.session_state.pop(cle, None)
            try:
                # Marmite qui mijote pendant l'appel IA (animée côté navigateur).
                # Repli sur le spinner texte si le fichier conversion.gif manque.
                anim = st.empty()
                with anim.container():
                    marmite = _jouer_anim(
                        "conversion", width=200, overlay=True,
                        legende="Conversion en cours… (quelques secondes)")
                attente = (nullcontext() if marmite else
                           st.spinner("Conversion en cours… (quelques secondes)"))
                try:
                    with attente:
                        rec, src = cw.convertir(
                            entree, cfg["api_key"], cfg["model"])
                        normaliser_recette(rec)
                        st.session_state.conv_resultat = rec
                        st.session_state.conv_source = src
                finally:
                    anim.empty()
                    # La conversion peut avoir lancé un navigateur (sous-processus
                    # déjà terminé ici) et alloué du HTML : on rend au système la
                    # mémoire transitoire pour ne pas garder le pic sur un
                    # conteneur à 1 Go. Inutile d'attendre — c'est immédiat.
                    _liberer_memoire()
            except cw.CreditEpuise as e:
                st.session_state.conv_erreur = f"🪫 {e}"
            except cw.SiteBloque as e:
                st.session_state.conv_erreur = f"🚫 {e}"
            except cw.RecetteIntrouvable as e:
                st.session_state.conv_erreur = f"🔍 {e}"
            except cw.URLInvalide as e:
                st.session_state.conv_erreur = f"⚠ {e}"
            except cw.ConfigManquante as e:
                st.session_state.conv_erreur = f"🔑 {e}"
            except cw.ConversionError as e:
                st.session_state.conv_erreur = f"⚠ {e}"
            except Exception as e:                       # filet de sécurité
                st.session_state.conv_erreur = f"⚠ Erreur inattendue : {e}"

        if st.session_state.get("conv_erreur"):
            st.error(st.session_state.conv_erreur)

        rec = st.session_state.get("conv_resultat")
        if rec:
            src = st.session_state.get("conv_source", "")
            libelle = {"jsonld": "données structurées du site",
                       "html": "texte de la page",
                       "texte": "texte collé",
                       "ia_fetch": "page récupérée directement par l'IA",
                       "navigateur": "page récupérée via un navigateur automatisé "
                                     "(dernier recours)"}.get(src, src)
            st.success(f"Recette détectée (via {libelle}). Vérifie l'aperçu, "
                       "puis ajoute-la au menu.")

            st.divider()
            st.markdown(f"### {rec.get('titre', '')}")
            if rec.get("sous_titre"):
                st.caption(rec["sous_titre"])
            b = rec.get("base", {})
            meta = []
            if b.get("personnes"):
                meta.append(f"🍽 {b['personnes']} portions")
            if rec.get("temps_prep"):
                meta.append(f"⏱ prép. {rec['temps_prep']} min")
            if rec.get("temps_cuisson"):
                meta.append(f"🔥 cuisson {rec['temps_cuisson']} min")
            if meta:
                st.write(" · ".join(meta))

            st.markdown("**Ingrédients**")
            section_apercu = None
            for ing in rec.get("ingredients", []):
                sec = (ing.get("section") or "").strip()
                if sec != section_apercu:
                    section_apercu = sec
                    if sec:
                        st.markdown(f"*{sec}*")
                q = ing.get("qte")
                u = (ing.get("unite") or "").strip()
                if q in (None, ""):
                    detail = u or "au goût"
                elif isinstance(q, (int, float)):
                    detail = f"{jolie_qte(q)} {u}".strip()
                else:
                    detail = f"{q} {u}".strip()
                st.write(f"- **{ing.get('nom', '')}** — {detail}")

            st.markdown("**Préparation**")
            # Tolérant aux deux formes : aperçu AVANT normalisation (étapes en
            # chaînes) comme après (dicts {texte, section}). Numérotation par
            # section.
            section_prep_ap = None
            i_prep = 0
            for etape in rec.get("preparation", []):
                sec = _etape_section(etape).strip()
                if sec != section_prep_ap:
                    section_prep_ap = sec
                    i_prep = 0
                    if sec:
                        st.markdown(f"*{sec}*")
                i_prep += 1
                st.write(f"{i_prep}. {_etape_texte(etape)}")

            if rec.get("tags"):
                st.write("🏷 " + " · ".join(rec["tags"]))

            st.divider()
            col_add, col_annul = st.columns(2)
            with col_add:
                st.button("➕ Ajouter au menu", type="primary",
                          use_container_width=True, key="conv_add",
                          on_click=_ajouter_recette_convertie, args=(rec,))
            with col_annul:
                st.button("❌ Annuler", use_container_width=True,
                          key="conv_annuler",
                          on_click=_annuler_recette_convertie)


# ═════════════════════════════════════════════════════════════════════════════
#  ONGLET ÉDITION — modifier / ajouter / retirer / supprimer
# ═════════════════════════════════════════════════════════════════════════════
if vue == VUE_EDITION:
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
                        st.session_state["_toast_tags"] = True
                        st.rerun()
            toast_enregistre("_toast_tags")       # pop-up juste sous le bouton

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
            "Ajuster uniquement par paliers fixes",
            value=bool(base.get("multiples", False)), key=f"bmul_{k}",
            help="Utile en pâtisserie : en cuisine, le nombre de personnes ne "
                 "saute que par paliers réguliers, pour garder des proportions "
                 "exactes (ex. 4 → 8 → 12, ou 4 → 6 → 8 si le palier est de 2).")
        if b_multiples:
            b_pas_personnes = st.number_input(
                "Taille du palier (nombre de personnes par saut)",
                min_value=1, step=1,
                value=int(base.get("pas_personnes") or b_personnes),
                key=f"bpas_{k}",
                help="Ex. avec une référence à 4 personnes et un palier de 2 : "
                     "en cuisine on peut choisir 4, 6, 8, 10… (et non doubler "
                     "directement à 8). Laisser égal au nombre de personnes de "
                     "référence pour retrouver l'ancien comportement (×1, ×2, ×3…).")
        else:
            b_pas_personnes = int(base.get("pas_personnes") or b_personnes)
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
        # Défaut = tags déjà appliqués, ramenés à leur forme canonique du
        # catalogue (même casse/accents que les options) — sinon st.multiselect
        # rejette un défaut qui ne correspond pas EXACTEMENT à une option (ex.
        # recette convertie avec « Dessert » alors que le catalogue a « dessert »).
        # On complète les options avec les tags réellement absents du catalogue.
        opts_tags = noms_tags()
        canon = {_norm_tag(o): o for o in opts_tags}
        defauts_tags, vus = [], set()
        for t in recette.get("tags", []):
            n = _norm_tag(t)
            if n not in canon:
                opts_tags.append(t)
                canon[n] = t
            if n not in vus:
                vus.add(n)
                defauts_tags.append(canon[n])
        tags_appliques = st.multiselect(
            "Tags de cette recette",
            options=sorted(opts_tags, key=_norm_tag),
            default=defauts_tags,
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
        st.caption("💡 Astuce : passe la souris sur un titre de colonne "
                   "(Palier, Unité…) et attends une seconde pour voir une "
                   "petite explication.")

        ss_ing = f"agg_ing_{k}"
        df_ing = pd.DataFrame(
            [
                {
                    "Ingrédient": ing.get("nom", ""),
                    "Section": ing.get("section", ""),
                    "Quantité": ing.get("qte"),
                    "Unité": ing.get("unite", ""),
                    "Palier": _palier_txt(ing.get("palier")),
                    "_rowid": str(i),
                }
                for i, ing in enumerate(recette["ingredients"])
            ],
            # _rowid en dernier : la 1re colonne (visible) porte la case à cocher.
            columns=["Ingrédient", "Section", "Quantité", "Unité", "Palier", "_rowid"],
        )

        def _cfg_ing(gb):
            gb.configure_column("_rowid", hide=True, editable=False)
            gb.configure_column("Ingrédient", rowDrag=True, editable=True, flex=3)
            gb.configure_column("Section", editable=True, flex=2,
                                headerTooltip="Groupe d'ingrédients (ex. Garniture, "
                                              "Bouillon). Laisser vide si aucun.")
            gb.configure_column("Quantité", editable=True, flex=1,
                                type=["numericColumn"],
                                headerTooltip="Combien il en faut pour la recette de "
                                              "base, avant d'ajuster le nombre de "
                                              "personnes.")
            gb.configure_column("Unité", editable=True, flex=1,
                                headerTooltip="Dans quoi on mesure : c. à soupe, "
                                              "c. à thé, ml, g, tasse…")
            gb.configure_column("Palier", editable=True, flex=1,
                                headerTooltip="Saisis librement le palier : c'est "
                                              "l'arrondi des quantités quand tu "
                                              "cuisines, pour tomber sur des chiffres "
                                              "faciles à mesurer. Exemple: Palier 25, "
                                              "on incrémente de 25 → 25, 50, 75, 100… "
                                              "Palier 0.5 → des demies (1/2, 1, 1 1/2…). "
                                              "Palier 1/3 → des tiers (1/3, 2/3, 1, "
                                              "1 1/3…), pour ne jamais arrondir un 2/3 "
                                              "à 1. Tu peux écrire « 0,5 » ou « 1/3 ». "
                                              "Laisse vide pour l'arrondi par défaut.")

        grille_ing = _grille_aggrid(df_ing, ss_ing, _cfg_ing)
        # État normalisé (DataFrame colonné) persisté par _grille_aggrid — évite
        # de refaire pd.DataFrame(grille["data"]) qui, en sérialisation JSON,
        # recevrait None ou une chaîne et produirait un DataFrame vide/sans colonnes.
        edite = st.session_state[ss_ing]

        ca, cb = st.columns(2)
        if ca.button("＋ Ajouter un ingrédient", key=f"add_ing_{k}",
                     use_container_width=True):
            seq = st.session_state.get(f"{ss_ing}_seq", 0) + 1
            st.session_state[f"{ss_ing}_seq"] = seq
            st.session_state[ss_ing] = pd.concat(
                [edite, pd.DataFrame([{"Ingrédient": "", "Section": "",
                                       "Quantité": None, "Unité": "",
                                       "Palier": "", "_rowid": f"n{seq}"}])],
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
        st.caption("Double-clique pour éditer l'étape · glisse la poignée ⠿ pour "
                   "réordonner · coche + 🗑 pour retirer. Pour rendre les "
                   "ingrédients cités DYNAMIQUES (quantité insérée et mise à "
                   "l'échelle en cuisine), clique sur « 🔍 Rescanner » ci-dessous "
                   "et confirme-les d'un clic. Pour une PORTION, écris "
                   "[beurre: 15 ml] (s'échelonne) ou [beurre: reste] (le solde).")

        ss_prep = f"agg_prep_{k}"

        df_prep = pd.DataFrame(
            [{"Étape": _etape_texte(e), "Section": _etape_section(e),
              "_rowid": str(i)}
             for i, e in enumerate(recette.get("preparation", []))],
            # _rowid en dernier : la 1re colonne (visible) porte la case à cocher.
            columns=["Étape", "Section", "_rowid"],
        )

        def _cfg_prep(gb):
            gb.configure_column("_rowid", hide=True, editable=False)
            gb.configure_column("Section", editable=True, flex=2,
                                headerTooltip="Groupe d'étapes (ex. Sauce, Montage, "
                                              "Variante). Laisser vide si aucun.")
            gb.configure_column("Étape", rowDrag=True, editable=True, flex=1,
                                wrapText=True, autoHeight=True,
                                cellEditor="agLargeTextCellEditor",
                                cellEditorPopup=True,
                                # agLargeTextCellEditor impose maxLength=200 par
                                # défaut : la textarea (attribut HTML maxlength)
                                # BLOQUE toute frappe dès qu'une étape atteint
                                # 200 caractères. On relève la limite pour que les
                                # longues étapes restent éditables.
                                cellEditorParams={"maxLength": 5000, "rows": 6,
                                                  "cols": 60})

        grille_prep = _grille_aggrid(df_prep, ss_prep, _cfg_prep)
        edite_prep = st.session_state[ss_prep]   # état normalisé (voir _df_retour_grille)

        cc, cd = st.columns(2)
        if cc.button("＋ Ajouter une étape", key=f"add_prep_{k}",
                     use_container_width=True):
            seq = st.session_state.get(f"{ss_prep}_seq", 0) + 1
            st.session_state[f"{ss_prep}_seq"] = seq
            st.session_state[ss_prep] = pd.concat(
                [edite_prep, pd.DataFrame([{"Étape": "", "Section": "",
                                            "_rowid": f"n{seq}"}])],
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

        # ── Ingrédients dynamiques : rescan + marquage PAR OCCURRENCE ─────────
        #  Les quantités ne s'insèrent en cuisine QUE pour les ingrédients entre
        #  [crochets]. On scanne sur demande (grilles EN COURS d'édition) et on
        #  bascule chaque occurrence d'un clic, SANS rechargement (session
        #  préservée). Chaque occurrence est indépendante : un ingrédient cité
        #  plusieurs fois peut n'être dynamique qu'une seule fois.
        etapes_courantes = _etapes_depuis_editeur(edite_prep)
        textes_courants = [e["texte"] for e in etapes_courantes]
        ings_courants = _ingredients_depuis_editeur(edite)
        idx_dyn = index_marqueurs(ings_courants)

        # Rappel « dans l'intérêt de l'auteur » : ingrédients cités dont AUCUNE
        # occurrence n'est dynamique (leur quantité ne s'affichera pas en cuisine).
        deja = {_norm_titre(n)
                for n in ingredients_deja_dynamiques(textes_courants, ings_courants)}
        candidats = [n for n in candidats_dynamiques(textes_courants, ings_courants)
                     if _norm_titre(n) not in deja]
        if candidats:
            st.warning(
                f"🔎 {len(candidats)} ingrédient(s) cité(s) ne sont dynamiques "
                "nulle part : leur quantité ne s'affichera PAS en cuisine. Ouvre "
                "« 🔍 Rescanner » et clique-les pour les rendre dynamiques — "
                + ", ".join(candidats) + ".")

        # Le bouton relance TOUJOURS un scan à neuf (sur les grilles en cours
        # d'édition) : ré-appuyer après avoir modifié les ingrédients ou les
        # étapes ré-affiche des occurrences à jour. Un bouton séparé masque le
        # panneau. Le scan lui-même se recalcule à chaque rerun via
        # occurrences_dynamiques() ci-dessous.
        cle_rescan = f"rescan_actif_{k}"
        actif = st.session_state.get(cle_rescan, False)
        c_scan, c_masq = st.columns([3, 1]) if actif else (st, None)
        if c_scan.button("🔍 Rescanner les ingrédients dynamiques",
                         key=f"rescan_btn_{k}", use_container_width=True):
            st.session_state[cle_rescan] = True
            st.rerun()
        if actif and c_masq.button("Masquer", key=f"rescan_hide_{k}",
                                   use_container_width=True):
            st.session_state[cle_rescan] = False
            st.rerun()

        if actif:
            st.caption("Clique un mot ✅ pour RETIRER sa quantité dynamique, un "
                       "mot ➕ (exact) ou ≈ (approché : pluriel/abréviation) pour "
                       "l'AJOUTER. Chaque occurrence est indépendante : "
                       "①②③ numérotent les répétitions d'un même ingrédient.")
            rien = True
            for si, etape in enumerate(textes_courants):
                occ = occurrences_dynamiques(etape, ings_courants, idx_dyn)
                if not occ:
                    continue
                rien = False
                st.markdown(
                    f'<div style="margin:.55rem 0 .2rem;line-height:1.55">'
                    f'<b style="color:#ffb454">{si + 1}.</b> '
                    f'{apercu_occurrences(etape, occ)}</div>',
                    unsafe_allow_html=True)
                totaux = {}
                for *_x, nom in occ:
                    totaux[nom] = totaux.get(nom, 0) + 1
                rang = {}
                cols = st.columns(min(3, len(occ)))
                for j, (a, b, etat, nom) in enumerate(occ):
                    rang[nom] = rang.get(nom, 0) + 1
                    suffixe = (f" {_CERCLES.get(rang[nom], rang[nom])}"
                               if totaux[nom] > 1 else "")
                    icone = {"dyn": "✅", "sim": "≈"}.get(etat, "➕")
                    if cols[j % len(cols)].button(
                            f"{icone} {nom}{suffixe}",
                            key=f"occ_{k}_{si}_{a}_{b}", use_container_width=True):
                        etapes_courantes[si]["texte"] = \
                            basculer_marqueur(etape, a, b, etat)
                        st.session_state[ss_prep] = pd.DataFrame(
                            [{"Étape": e["texte"], "Section": e["section"],
                              "_rowid": str(i)}
                             for i, e in enumerate(etapes_courantes)],
                            columns=["Étape", "Section", "_rowid"])
                        st.session_state[f"{ss_prep}_nonce"] = \
                            st.session_state.get(f"{ss_prep}_nonce", 0) + 1
                        st.rerun()
            if rien:
                st.caption("Aucun ingrédient reconnu dans les étapes. Vérifie "
                           "l'orthographe ou les noms d'ingrédients.")

        # Aperçu live : montre les [marqueurs] surlignés (reconnu / introuvable),
        # calculés sur les ingrédients ET les étapes en cours d'édition.
        if "Étape" in edite_prep.columns:
            idx_ape = index_marqueurs(_ingredients_depuis_editeur(edite))
            lignes_ape = []
            for i, e in enumerate(edite_prep["Étape"].tolist(), start=1):
                if e is None or (isinstance(e, float) and pd.isna(e)):
                    continue
                txt = str(e).strip()
                if not txt:
                    continue
                lignes_ape.append(
                    f'<div style="margin:.3rem 0;line-height:1.55">'
                    f'<b style="color:#ffb454">{i}.</b> '
                    f'{apercu_marqueurs(txt, idx_ape)}</div>')
            if lignes_ape:
                st.caption("Aperçu — 🟩 ingrédient reconnu · 🟥 introuvable "
                           "(corrige l'orthographe ou vérifie l'ingrédient)")
                st.markdown(
                    '<div style="padding:.6rem .8rem;border:1px solid #2a2d36;'
                    'border-radius:8px;background:#12141a;font-size:.92rem;'
                    'color:#e9efff">'
                    + "".join(lignes_ape) + "</div>",
                    unsafe_allow_html=True)

    if st.button("💾 Enregistrer les modifications", type="primary",
                 use_container_width=True, key=f"save_{k}"):
        nouveaux = _ingredients_depuis_editeur(edite)
        etapes = _etapes_depuis_editeur(edite_prep)

        # L'élément de base (étiquette + valeur de référence + unité) est
        # obligatoire pour chaque recette : c'est ce qui s'ajuste avec le nombre
        # de personnes en cuisine.
        erreurs = []
        if _titre_duplique(titre, RECETTES, sauf=k):
            erreurs.append(
                f"Une autre recette porte déjà le titre « {titre.strip()} » "
                "(comparaison sans casse ni accents). Choisis un titre différent.")
        jumelle = _recette_jumelle_ingredients(nouveaux, RECETTES, sauf=k)
        if jumelle:
            erreurs.append(
                f"La recette « {jumelle} » a exactement la même liste "
                "d'ingrédients : c'est probablement un doublon. Modifie les "
                "ingrédients, ou supprime la recette en trop.")
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
                               "multiples": bool(b_multiples),
                               "pas_personnes": int(b_pas_personnes)}
            recette["ingredients"] = nouveaux
            # Les étapes sont enregistrées telles quelles : le marquage dynamique
            # [ainsi] se fait à la demande via « 🔍 Rescanner » (aucun marquage
            # automatique ici). Les crochets présents font foi.
            recette["preparation"] = etapes
            # Tags : enregistre les nouveaux au catalogue global, applique les
            # noms canoniques à la recette.
            recette["tags"] = enregistrer_tags(tags_appliques)
            if persister(RECETTES):
                # Repart des données sauvées : on vide les tables de travail
                # (et leurs nonces/compteurs de remontage) ainsi que l'état du
                # panneau de marquage dynamique.
                for base in (f"agg_ing_{k}", f"agg_prep_{k}"):
                    for cle in (base, f"{base}_nonce", f"{base}_seq"):
                        st.session_state.pop(cle, None)
                st.session_state.pop(f"rescan_actif_{k}", None)
                st.session_state["_toast_recette"] = True
                st.rerun()
    toast_enregistre("_toast_recette")            # pop-up juste sous le bouton

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
