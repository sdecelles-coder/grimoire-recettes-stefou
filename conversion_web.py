"""Conversion d'une recette web (URL) vers le format de recettes.json.

Module AUTONOME (aucune dépendance à Streamlit) pour rester testable seul.

Pipeline :
  1. Récupérer la page (fetch_html).
  2. Extraire les données structurées schema.org/Recipe si présentes
     (extraire_recette_jsonld) — gratuit, marche sur la majorité des sites.
     Sinon, repli sur le texte visible de la page.
  3. Demander à Claude de produire une recette au format de l'app, en français
     (convertir_texte).

La fonction de haut niveau `convertir_url(url, api_key, model)` enchaîne le tout
et renvoie (recette_dict, source) où source ∈ {"jsonld", "html"}.

Les erreurs sont remontées via des exceptions dédiées pour que l'interface
affiche le bon message (URL invalide, recette introuvable, crédit épuisé…).
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import sys

import requests


# ── Exceptions dédiées ───────────────────────────────────────────────────────
class ConversionError(Exception):
    """Erreur générique de conversion."""


class URLInvalide(ConversionError):
    """L'adresse fournie n'est pas une URL http(s) valide / joignable."""


class SiteBloque(ConversionError):
    """Le site refuse les requêtes automatisées (protection anti-bot / paywall)."""


class RecetteIntrouvable(ConversionError):
    """Aucune recette exploitable trouvée sur la page."""


class CreditEpuise(ConversionError):
    """Le solde de crédits de l'API Claude est épuisé."""


class ConfigManquante(ConversionError):
    """Clé API absente ou invalide."""


# ── 1. Récupération de la page ───────────────────────────────────────────────
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 grimoire-recettes")

# Repli empirique : certains pare-feux anti-bot bloquent un jeu d'en-têtes
# « trop parfait » (UA Chrome complet + Accept + Accept-Language + ...) mais
# laissent passer un jeu minimal qui ne correspond à aucune signature connue
# de leurs règles. Fragile et propre à chaque site (pas une vraie technique
# robuste), donc utilisé seulement en second essai, jamais en premier.
_UA_MINIMAL = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def fetch_html(url: str, timeout: int = 15) -> str:
    """Télécharge le HTML de l'URL. Lève URLInvalide / ConversionError.

    Deux tentatives : en-têtes complets d'abord (comportement standard),
    puis, si le site répond 401/403/429, en-têtes minimaux (voir
    _UA_MINIMAL) avant de déclarer le site bloqué."""
    url = (url or "").strip()
    if not re.match(r"^https?://", url, re.I):
        raise URLInvalide("L'adresse doit commencer par http:// ou https://.")

    jeux_entetes = (
        {
            "User-Agent": _UA,
            "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                       "image/avif,image/webp,*/*;q=0.8"),
            "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        },
        {"User-Agent": _UA_MINIMAL},
    )
    r = None
    for entetes in jeux_entetes:
        try:
            r = requests.get(url, headers=entetes, timeout=timeout)
        except requests.RequestException as e:
            raise URLInvalide(f"Impossible de récupérer la page : {e}") from e
        if r.status_code not in (401, 403, 429):
            break
    if r.status_code in (401, 403, 429):
        raise SiteBloque(
            "Ce site refuse les requêtes automatisées (protection anti-bot ou "
            "contenu payant).")
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        raise URLInvalide(f"Impossible de récupérer la page : {e}") from e
    # requests retombe sur ISO-8859-1 quand le serveur ne déclare pas de charset ;
    # on corrige via la détection sur le contenu (souvent de l'UTF-8 mal deviné),
    # sinon les accents des pages sans charset sont cassés (« Ã  » au lieu de « à »).
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        detecte = r.apparent_encoding
        if detecte:
            r.encoding = detecte
    return r.text


# ── 2. Extraction schema.org/Recipe (JSON-LD) ────────────────────────────────
def _iter_jsonld(html_text: str):
    """Itère les objets JSON de chaque bloc <script type="application/ld+json">."""
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text, re.I | re.S,
    ):
        bloc = m.group(1).strip()
        try:
            yield json.loads(bloc)
        except json.JSONDecodeError:
            continue


def _trouver_recipe(obj):
    """Cherche récursivement un nœud dont @type contient « Recipe »."""
    if isinstance(obj, dict):
        t = obj.get("@type")
        types = t if isinstance(t, list) else [t]
        if any(str(x).lower() == "recipe" for x in types):
            return obj
        if "@graph" in obj:
            trouve = _trouver_recipe(obj["@graph"])
            if trouve:
                return trouve
        for v in obj.values():
            trouve = _trouver_recipe(v)
            if trouve:
                return trouve
    elif isinstance(obj, list):
        for item in obj:
            trouve = _trouver_recipe(item)
            if trouve:
                return trouve
    return None


def extraire_recette_jsonld(html_text: str):
    """Renvoie le nœud Recipe brut (dict schema.org) ou None."""
    for data in _iter_jsonld(html_text):
        recipe = _trouver_recipe(data)
        if recipe:
            return recipe
    return None


def _jsonld_recette_valide(recipe: dict) -> bool:
    """Un nœud JSON-LD Recipe n'est utilisable que s'il a de vrais ingrédients.
    Certains sites publient un JSON-LD Recipe avec des champs vides en
    placeholder (recipeIngredient: [], recipeInstructions: "") — le contenu
    réel n'existe alors que dans le HTML visible, pas dans les données
    structurées, et il faut retomber sur texte_visible plutôt que de faire
    confiance à ce JSON-LD creux."""
    ings = recipe.get("recipeIngredient") or recipe.get("ingredients") or []
    if isinstance(ings, str):
        ings = [ings]
    return any(_clean(i) for i in ings)


# Le JSON-LD aplatit les sections d'ingrédients ; on les récupère dans le HTML
# (WP Recipe Maker et thèmes similaires exposent des groupes nommés).
_RE_GROUPE_NOM = re.compile(
    r'wprm-recipe-ingredient-group-name[^>]*>(.*?)</', re.I | re.S)
_RE_INGREDIENT_LI = re.compile(
    r'<li[^>]*wprm-recipe-ingredient[^>]*>(.*?)</li>', re.I | re.S)


def extraire_groupes_ingredients(html_text: str):
    """Renvoie [(nom_section, [textes_ingredients])] à partir des groupes du HTML,
    ou [] si la page n'expose pas de groupes reconnus. Chaque ingrédient est
    rattaché au dernier nom de groupe qui le précède dans la page."""
    noms = [(m.start(), _clean(m.group(1)).rstrip(" :·-"))
            for m in _RE_GROUPE_NOM.finditer(html_text)]
    ingredients = [(m.start(), _clean(m.group(1)))
                   for m in _RE_INGREDIENT_LI.finditer(html_text)]
    if not ingredients:
        return []
    groupes: list[tuple[str, list[str]]] = []
    for pos, texte in ingredients:
        if not texte:
            continue
        nom = ""
        for npos, nnom in noms:
            if npos < pos:
                nom = nnom
            else:
                break
        if groupes and groupes[-1][0] == nom:
            groupes[-1][1].append(texte)
        else:
            groupes.append((nom, [texte]))
    # Sans aucun nom de section (groupe unique anonyme), inutile de sectionner.
    if len(groupes) == 1 and not groupes[0][0]:
        return []
    return groupes


# ── Helpers de nettoyage / mise en forme du texte source ─────────────────────
def _clean(txt) -> str:
    """Déséchappe les entités HTML, retire les balises et compresse les espaces."""
    if not isinstance(txt, str):
        txt = "" if txt is None else str(txt)
    txt = _html.unescape(txt)
    txt = re.sub(r"<[^>]+>", " ", txt)          # retire d'éventuelles balises
    return re.sub(r"\s+", " ", txt).strip()


def _flatten_instructions(instr) -> list[str]:
    """Aplati recipeInstructions (string | liste de strings | HowToStep |
    HowToSection) en une liste de phrases propres."""
    etapes: list[str] = []

    def _ajoute(x):
        if isinstance(x, str):
            t = _clean(x)
            if t:
                etapes.append(t)
        elif isinstance(x, dict):
            typ = str(x.get("@type", "")).lower()
            if typ == "howtosection":
                _ajoute(x.get("itemListElement", []))
            else:  # HowToStep ou autre : on prend .text ou .name
                t = _clean(x.get("text") or x.get("name") or "")
                if t:
                    etapes.append(t)
        elif isinstance(x, list):
            for item in x:
                _ajoute(item)

    _ajoute(instr)
    return etapes


def _yield_str(y) -> str:
    if isinstance(y, list):
        y = y[0] if y else ""
    return _clean(y)


def texte_depuis_jsonld(recipe: dict, groupes=None) -> str:
    """Assemble un texte lisible à partir du nœud Recipe schema.org.

    Si `groupes` (issu de extraire_groupes_ingredients) est fourni, la liste des
    ingrédients est structurée par section ; sinon on utilise la liste plate du
    JSON-LD."""
    lignes = []
    nom = _clean(recipe.get("name"))
    if nom:
        lignes.append(f"TITRE : {nom}")

    desc = _clean(recipe.get("description"))
    if desc:
        lignes.append(f"DESCRIPTION : {desc}")

    rendement = _yield_str(recipe.get("recipeYield"))
    if rendement:
        lignes.append(f"RENDEMENT : {rendement}")

    if recipe.get("prepTime"):
        lignes.append(f"TEMPS PRÉPARATION (ISO 8601) : {recipe['prepTime']}")
    if recipe.get("cookTime"):
        lignes.append(f"TEMPS CUISSON (ISO 8601) : {recipe['cookTime']}")
    if recipe.get("totalTime"):
        lignes.append(f"TEMPS TOTAL (ISO 8601) : {recipe['totalTime']}")

    if groupes:
        lignes.append("INGRÉDIENTS :")
        for nom, items in groupes:
            if nom:
                lignes.append(f"[Section : {nom}]")
            lignes += [f"- {it}" for it in items if it]
    else:
        ings = recipe.get("recipeIngredient") or recipe.get("ingredients") or []
        if isinstance(ings, str):
            ings = [ings]
        ings = [_clean(i) for i in ings if _clean(i)]
        if ings:
            lignes.append("INGRÉDIENTS :")
            lignes += [f"- {i}" for i in ings]

    etapes = _flatten_instructions(recipe.get("recipeInstructions"))
    if etapes:
        lignes.append("PRÉPARATION :")
        lignes += [f"{n}. {e}" for n, e in enumerate(etapes, 1)]

    return "\n".join(lignes)


def texte_visible(html_text: str, limite: int = 12000) -> str:
    """Repli : texte visible approximatif de la page (sans script/style/balises)."""
    txt = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html_text)
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    txt = _html.unescape(txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt)
    txt = txt.strip()
    return txt[:limite]


def _texte_source_depuis_html(html_text: str) -> tuple[str, str]:
    """Choisit la meilleure source de texte pour un HTML donné : le JSON-LD
    schema.org/Recipe s'il existe ET contient de vrais ingrédients, sinon le
    texte visible de la page. Partagé par convertir_url et
    convertir_url_via_navigateur. Renvoie (source_texte, origine)."""
    recipe = extraire_recette_jsonld(html_text)
    if recipe and _jsonld_recette_valide(recipe):
        groupes = extraire_groupes_ingredients(html_text)
        return texte_depuis_jsonld(recipe, groupes), "jsonld"
    return texte_visible(html_text), "html"


# ── 3. Conversion par l'IA (Claude) ──────────────────────────────────────────
_SYSTEME = """\
Tu convertis une recette de cuisine en un objet JSON strict pour une application \
de recettes québécoise. Tu réponds UNIQUEMENT avec l'objet JSON, sans texte avant \
ni après, sans balise de code.

LANGUE : la sortie est TOUJOURS en français. Traduis si la source est dans une \
autre langue ; garde tel quel si c'est déjà en français. N'invente jamais un \
ingrédient ou une étape absents de la source.

SI LE TEXTE NE CONTIENT AUCUNE RECETTE de cuisine (article, page d'erreur, \
liste de liens, etc.), réponds EXACTEMENT avec cet objet et rien d'autre :
{"erreur": "aucune_recette"}

FORMAT EXACT de l'objet :
{
  "titre": "string",
  "sous_titre": "string (court ; sinon \\"\\")",
  "temps_prep": entier (minutes, 0 si inconnu),
  "temps_cuisson": entier (minutes, 0 si inconnu),
  "base": {
    "label": "Portions",
    "unite": "portions",
    "valeur": nombre (= nb de portions),
    "personnes": entier (= nb de portions ; 4 si inconnu),
    "max_personnes": 20,
    "multiples": false
  },
  "ingredients": [
    {"nom": "string", "qte": nombre|null, "unite": "string",
     "palier": nombre|null, "section": "string"}
  ],
  "preparation": ["étape 1", "étape 2", ...],
  "tags": ["Mot1", "Mot2"]
}

SECTIONS D'INGRÉDIENTS : si la recette regroupe ses ingrédients sous des \
sous-titres (« Pour la garniture », « Pour le bouillon », « Glaçage », \
marqueurs [Section : …], etc.), mets le nom du groupe dans "section" pour chaque \
ingrédient concerné — sous une forme COURTE et cohérente (« Garniture », \
« Bouillon », « Pâte », « Glaçage »). Garde l'ordre des ingrédients par section. \
Si la recette n'a AUCUN regroupement, mets "section": "" partout.

UNITÉS (privilégie ces formes québécoises) :
- cuillère à soupe / tablespoon / tbsp  -> "c. à table"   (palier 0.5)
- cuillère à thé / teaspoon / tsp        -> "c. à thé"     (palier 0.25)
- tasse / cup                            -> "tasse"        (palier 0.25)
- millilitre -> "ml", litre -> "l", gramme -> "g", kilogramme -> "kg"  (palier null)
- unités entières (œuf, gousse, tranche…) -> "unité" ou le nom (palier null ou 1)
- sel, poivre et assaisonnements « au goût » -> qte:null, unite:"au goût", palier:null

RÈGLES qte / palier :
- "qte" est un nombre décimal ; convertis les fractions (1/2 -> 0.5, 1/4 -> 0.25).
- "palier" = pas d'ajustement : 0.5 pour "c. à table", 0.25 pour "c. à thé" et \
"tasse", null pour g/ml/l et pour tout ingrédient "au goût" (qte null).
- Si la quantité source est un tiers ou un multiple de tiers (1/3, 2/3, 1 1/3, \
etc., quelle que soit l'unité), mets "palier": 0.3333333333333333 pour cet \
ingrédient — sinon la mise à l'échelle arrondirait un 2/3 à l'entier le plus \
proche.
- Si un ingrédient a une portion entre parenthèses (ex. « 1 boîte (796 ml) »), \
garde le plus utile pour cuisiner.

preparation : étapes courtes et claires. tags : 1 à 3 mots-clés pertinents \
(type de plat, ingrédient vedette…), première lettre en majuscule.
"""


def _extraire_json(txt: str) -> dict:
    """Isole et parse l'objet JSON de la réponse (tolère les clôtures ``` ou du
    texte autour)."""
    txt = (txt or "").strip()
    txt = re.sub(r"^```(?:json)?\s*", "", txt, flags=re.I)
    txt = re.sub(r"\s*```$", "", txt)
    i, j = txt.find("{"), txt.rfind("}")
    if i != -1 and j != -1 and j > i:
        txt = txt[i:j + 1]
    return json.loads(txt)


def _appeler_claude(messages: list[dict], api_key: str, model: str,
                    tools: list[dict] | None = None):
    """Appel bas niveau à l'API Claude, partagé par convertir_texte et
    convertir_url_via_ia. Lève ConfigManquante (clé absente/invalide),
    CreditEpuise (solde à zéro) ou ConversionError (autre problème API)."""
    import anthropic  # importé ici pour garder le module léger à l'import

    if not api_key:
        raise ConfigManquante("Clé API Claude absente des secrets.")

    client = anthropic.Anthropic(api_key=api_key)
    kwargs = {"model": model, "max_tokens": 4096, "system": _SYSTEME,
              "messages": messages}
    if tools:
        kwargs["tools"] = tools
    try:
        resp = client.messages.create(**kwargs)
    except anthropic.AuthenticationError as e:
        raise ConfigManquante("Clé API Claude invalide.") from e
    except anthropic.APIStatusError as e:
        msg = (getattr(e, "message", "") or str(e)).lower()
        etype = (getattr(e, "type", "") or "").lower()
        if "credit balance" in msg or "billing" in etype or e.status_code == 402:
            raise CreditEpuise(
                "Plus de crédits API Claude. Ajoute des crédits sur "
                "console.anthropic.com.") from e
        raise ConversionError(f"Erreur de l'API Claude : {e}") from e
    except anthropic.APIConnectionError as e:
        raise ConversionError("Connexion à l'API Claude impossible.") from e

    if getattr(resp, "stop_reason", None) == "refusal":
        raise ConversionError(
            "L'IA a refusé de traiter le contenu de cette page.")
    if getattr(resp, "stop_reason", None) == "pause_turn":
        raise RecetteIntrouvable(
            "La récupération de la page par l'IA a pris trop de temps.")
    return resp


def _reponse_vers_recette(resp) -> dict:
    """Extrait le dict recette de la réponse Claude, ou lève RecetteIntrouvable."""
    texte = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        data = _extraire_json(texte)
    except (json.JSONDecodeError, ValueError) as e:
        raise RecetteIntrouvable(
            "Aucune recette n'a pu être extraite de cette page ou de ce texte.") from e
    if isinstance(data, dict) and data.get("erreur") == "aucune_recette":
        raise RecetteIntrouvable(
            "Aucune recette détectée dans cette page ou ce texte.")
    return data


def _erreur_fetch_ia(resp) -> str | None:
    """Renvoie le code d'erreur si l'outil web_fetch de Claude n'a pas réussi
    à récupérer la page, sinon None. Best-effort : on ignore silencieusement
    les formes de réponse non reconnues plutôt que de lever une exception ici."""
    for bloc in getattr(resp, "content", []):
        if getattr(bloc, "type", "") != "web_fetch_tool_result":
            continue
        code = getattr(getattr(bloc, "content", None), "error_code", None)
        if code:
            return str(code)
    return None


def convertir_texte(source_texte: str, api_key: str,
                    model: str = "claude-sonnet-4-6") -> dict:
    """Envoie le texte de la recette à Claude et renvoie le dict au format app.

    Lève ConfigManquante (clé absente/invalide), CreditEpuise (solde à zéro) ou
    ConversionError (autre problème API / réponse illisible).
    """
    resp = _appeler_claude(
        [{"role": "user", "content": source_texte}], api_key, model)
    return _reponse_vers_recette(resp)


def convertir_url_via_ia(url: str, api_key: str,
                         model: str = "claude-sonnet-4-6") -> tuple[dict, str]:
    """Repli quand le scraping local échoue : demande à Claude d'aller chercher
    la page lui-même (outil serveur web_fetch, exécuté depuis l'infrastructure
    Anthropic) puis d'en extraire la recette, en un seul appel API. Utile
    contre les sites anti-bot/paywall qui bloquent nos propres requêtes.

    Renvoie (recette, "ia_fetch"). Lève les mêmes exceptions que convertir_texte,
    plus RecetteIntrouvable si l'IA n'a pas non plus réussi à récupérer la page."""
    messages = [{
        "role": "user",
        "content": (
            "Utilise l'outil web_fetch pour récupérer le contenu de cette "
            f"page, puis extrais-en la recette : {url}"
        ),
    }]
    tools = [{"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 2}]
    resp = _appeler_claude(messages, api_key, model, tools=tools)

    if _erreur_fetch_ia(resp):
        raise RecetteIntrouvable(
            "Ce site refuse aussi les requêtes de l'IA (protection anti-bot). "
            "Essaie de copier-coller directement le texte de la recette dans "
            "le champ ci-dessus.")

    return _reponse_vers_recette(resp), "ia_fetch"


# ── 4. Dernier repli : navigateur automatisé (isolé dans un sous-processus) ──
# Lancer un vrai navigateur peut planter au niveau natif (segfault) sur
# certains environnements de déploiement contraints — un crash natif tue tout
# le processus qui l'a lancé, sans passer par un except Python. On isole donc
# ce palier dans un vrai sous-processus OS (subprocess.run sur
# _navigateur_repli.py, un script autonome) : s'il plante, seul ce
# sous-processus meurt, jamais le serveur Streamlit principal.
_SCRIPT_NAVIGATEUR_REPLI = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_navigateur_repli.py")


def _assurer_chromium_installe():
    """S'assure que le binaire Chromium de Playwright est présent. En
    déploiement (Streamlit Cloud), `playwright install chromium` n'est pas
    exécuté automatiquement après `pip install` — on le tente ici, une seule
    fois par processus, avant le premier lancement du navigateur de repli.
    Échec silencieux : si l'installation rate, la suite échouera proprement."""
    import subprocess

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        if os.path.exists(p.chromium.executable_path):
            return
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False, capture_output=True, timeout=180)


def convertir_url_via_navigateur(url: str, api_key: str,
                                 model: str = "claude-sonnet-4-6") -> tuple[dict, str]:
    """Dernier repli, après convertir_url et convertir_url_via_ia : ouvre un
    vrai navigateur (Chromium via Playwright) en mode VISIBLE, DANS UN VRAI
    SOUS-PROCESSUS OS ISOLÉ (_navigateur_repli.py), pour récupérer la page,
    puis envoie le texte obtenu à Claude.

    Constat empirique : certains sites bloquent les requêtes HTTP classiques
    (les nôtres et celle de l'outil web_fetch de Claude) mais pas un
    navigateur complet en mode visible — probablement une détection du mode
    « headless » plutôt qu'un blocage par IP. Nettement plus lourd/lent
    (plusieurs secondes, lance un vrai navigateur), donc réservé au dernier
    recours. L'isolation en sous-processus protège le serveur principal d'un
    crash natif du navigateur (ex. segfault), fréquent sur les environnements
    de déploiement contraints.

    Renvoie (recette, "navigateur"). Lève RecetteIntrouvable si le
    sous-processus plante/dépasse le délai/ne renvoie rien d'exploitable ;
    les mêmes exceptions que convertir_texte sinon."""
    import subprocess
    import tempfile

    try:
        _assurer_chromium_installe()
    except Exception:
        pass  # best-effort ; un binaire manquant fera échouer le sous-processus plus bas

    fd, fichier_sortie = tempfile.mkstemp(suffix=".html")
    os.close(fd)
    try:
        try:
            resultat = subprocess.run(
                [sys.executable, _SCRIPT_NAVIGATEUR_REPLI, url, fichier_sortie],
                capture_output=True, text=True, timeout=50)
        except subprocess.TimeoutExpired:
            raise RecetteIntrouvable(
                "Le navigateur de repli a mis trop de temps à répondre.")
        if resultat.returncode != 0:
            detail = (resultat.stderr or "erreur inconnue").strip().splitlines()
            raise RecetteIntrouvable(
                f"Le navigateur de repli a échoué (code {resultat.returncode}) : "
                f"{detail[-1] if detail else 'erreur inconnue'}")
        with open(fichier_sortie, encoding="utf-8") as f:
            html_text = f.read()
    finally:
        try:
            os.unlink(fichier_sortie)
        except OSError:
            pass

    source_texte, _ = _texte_source_depuis_html(html_text)
    if len(source_texte) < 40:
        raise RecetteIntrouvable(
            "Aucune recette exploitable trouvée sur cette page (navigateur).")
    recette = convertir_texte(source_texte, api_key, model)
    return recette, "navigateur"


# ── Orchestration de haut niveau ─────────────────────────────────────────────
def convertir_url(url: str, api_key: str,
                  model: str = "claude-sonnet-4-6") -> tuple[dict, str]:
    """Convertit l'URL en recette. Renvoie (recette, source ∈ {"jsonld","html"})."""
    html_text = fetch_html(url)
    source_texte, origine = _texte_source_depuis_html(html_text)
    if len(source_texte) < 40:
        raise RecetteIntrouvable(
            "Aucune recette exploitable trouvée sur cette page.")
    recette = convertir_texte(source_texte, api_key, model)
    return recette, origine


_RE_URL_NUE = re.compile(r"^https?://\S+$", re.I)


def convertir(entree: str, api_key: str,
             model: str = "claude-sonnet-4-6") -> tuple[dict, str]:
    """Point d'entrée unique : détecte automatiquement si `entree` est une URL
    ou du texte de recette collé. Pour une URL, enchaîne automatiquement,
    sans intervention de l'utilisateur, trois paliers du moins coûteux au
    plus coûteux : scraping local (convertir_url) → l'IA récupère la page
    elle-même (convertir_url_via_ia) → navigateur automatisé en dernier
    recours (convertir_url_via_navigateur), chacun tenté seulement si le
    précédent échoue à trouver une recette exploitable.

    Renvoie (recette, source). Les exceptions ConfigManquante/CreditEpuise ne
    déclenchent pas de repli : elles échoueraient de la même façon partout."""
    entree = (entree or "").strip()
    if _RE_URL_NUE.match(entree):
        try:
            return convertir_url(entree, api_key, model)
        except (URLInvalide, SiteBloque, RecetteIntrouvable):
            pass
        try:
            return convertir_url_via_ia(entree, api_key, model)
        except RecetteIntrouvable:
            return convertir_url_via_navigateur(entree, api_key, model)
    if len(entree) < 40:
        raise RecetteIntrouvable(
            "Colle au moins le titre, les ingrédients et les étapes de la "
            "recette, ou une adresse web (http:// ou https://).")
    return convertir_texte(entree, api_key, model), "texte"
