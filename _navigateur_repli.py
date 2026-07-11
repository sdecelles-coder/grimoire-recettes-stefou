"""Script isolé, invoqué en sous-processus par conversion_web.py
(convertir_url_via_navigateur), pour récupérer le HTML d'une page via un
vrai navigateur (Playwright) en mode visible.

Isolé dans un sous-processus séparé (subprocess.run, pas un thread ni
multiprocessing) pour qu'un crash natif du navigateur (ex. segfault, fréquent
sur les environnements de déploiement contraints) ne puisse jamais faire
tomber le serveur Streamlit principal — seul ce script meurt.

Usage : python _navigateur_repli.py <url> <fichier_sortie>
Écrit le HTML récupéré dans <fichier_sortie> et quitte avec le code 0 en cas
de succès ; quitte avec un code non nul (rien dans le fichier) sinon.
"""
from __future__ import annotations

import sys


def _ecran_virtuel():
    """Sur un serveur Linux sans écran (déploiement), ouvre un écran virtuel
    (Xvfb, via pyvirtualdisplay) pour permettre de lancer Chrome en mode
    « visible ». Sans effet sur Windows. Dupliqué de conversion_web.py (au
    lieu d'importer) pour que ce script reste exécutable seul, sans
    dépendre du répertoire de travail du sous-processus."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        from pyvirtualdisplay import Display
        ecran = Display(visible=False, size=(1280, 800))
        ecran.start()
        return ecran
    except Exception:
        return None


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: _navigateur_repli.py <url> <fichier_sortie>", file=sys.stderr)
        return 2
    url, fichier_sortie = sys.argv[1], sys.argv[2]

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright n'est pas installé.", file=sys.stderr)
        return 3

    ecran = _ecran_virtuel()
    try:
        with sync_playwright() as p:
            try:
                navigateur = p.chromium.launch(
                    headless=False,
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
                )
            except Exception as e:
                print(f"Lancement du navigateur impossible : {e}", file=sys.stderr)
                return 4
            try:
                page = navigateur.new_page(locale="fr-CA")
                page.goto(url, timeout=25000, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
                html = page.content()
            except Exception as e:
                print(f"Chargement de la page impossible : {e}", file=sys.stderr)
                return 5
            finally:
                navigateur.close()
    finally:
        if ecran:
            ecran.stop()

    with open(fichier_sortie, "w", encoding="utf-8") as f:
        f.write(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
