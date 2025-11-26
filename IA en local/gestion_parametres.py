# gestion_parametres.py
# S'occupe de lire et écrire le fichier parametres.json

import json
import os

NOM_FICHIER = "parametres.json"

def creer_parametres_defaut():
    """Crée un dictionnaire de paramètres par défaut."""
    return {
        "jouabilite": {
            "langue": "fr",
            "sensibilite_souris": 0.5
        },
        "video": {
            "plein_ecran": False,
            "vsync": False
        },
        "controles": {
            "gauche": "q",
            "droite": "d",
            "saut": "space",
            "echo": "e"
        }
    }

def charger_parametres():
    """
    Charge les paramètres depuis le fichier JSON.
    S'il n'existe pas, il le crée avec les valeurs par défaut.
    """
    if not os.path.exists(NOM_FICHIER):
        print(f"Fichier {NOM_FICHIER} non trouvé, création avec les valeurs par défaut.")
        parametres = creer_parametres_defaut()
        sauvegarder_parametres(parametres)
        return parametres
    
    try:
        with open(NOM_FICHIER, 'r', encoding='utf-8') as f:
            parametres = json.load(f)
            
            # Vérification de l'intégrité (ajoute les clés manquantes)
            parametres_defaut = creer_parametres_defaut()
            parametres_modifies = False
            for cle_section, section in parametres_defaut.items():
                if cle_section not in parametres:
                    parametres[cle_section] = section
                    parametres_modifies = True
                else:
                    for cle, valeur in section.items():
                        if cle not in parametres[cle_section]:
                            parametres[cle_section][cle] = valeur
                            parametres_modifies = True
            
            if parametres_modifies:
                print("Paramètres manquants détectés, mise à jour du fichier.")
                sauvegarder_parametres(parametres)
                
            return parametres
    except json.JSONDecodeError:
        print(f"Erreur en lisant {NOM_FICHIER}. Recréation avec les valeurs par défaut.")
        parametres = creer_parametres_defaut()
        sauvegarder_parametres(parametres)
        return parametres
    except Exception as e:
        print(f"Erreur inattendue au chargement des paramètres: {e}")
        return creer_parametres_defaut()

def sauvegarder_parametres(parametres):
    """Sauvegarde le dictionnaire de paramètres dans le fichier JSON."""
    try:
        with open(NOM_FICHIER, 'w', encoding='utf-8') as f:
            json.dump(parametres, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Erreur lors de la sauvegarde des paramètres: {e}")