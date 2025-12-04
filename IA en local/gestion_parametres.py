# gestion_parametres.py
# S'occupe de lire et écrire le fichier parametres.json
# CORRECTION : Utilise des chemins absolus pour le fichier JSON.

import json
import os

def get_chemin_absolu_parametres():
    """Renvoie le chemin complet vers parametres.json dans le dossier du script."""
    dossier_script = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(dossier_script, "parametres.json")

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
            "echo": "e",
            "attaque": "k" 
        }
    }

def charger_parametres():
    """Charge les paramètres depuis le fichier JSON."""
    chemin_fichier = get_chemin_absolu_parametres()
    
    if not os.path.exists(chemin_fichier):
        print(f"Fichier {chemin_fichier} non trouvé, création.")
        parametres = creer_parametres_defaut()
        sauvegarder_parametres(parametres)
        return parametres
    
    try:
        with open(chemin_fichier, 'r', encoding='utf-8') as f:
            parametres = json.load(f)
            
            # Vérification de l'intégrité
            parametres_defaut = creer_parametres_defaut()
            parametres_modifies = False
            
            for cle_section, section in parametres_defaut.items():
                if cle_section not in parametres:
                    parametres[cle_section] = section
                    parametres_modifies = True
                else:
                    for cle, valeur in section.items():
                        if cle not in parametres[cle_section]:
                            print(f"Paramètre manquant ajouté : {cle}")
                            parametres[cle_section][cle] = valeur
                            parametres_modifies = True
            
            if parametres_modifies:
                sauvegarder_parametres(parametres)
                
            return parametres
    except json.JSONDecodeError:
        print(f"Erreur en lisant {chemin_fichier}. Recréation.")
        parametres = creer_parametres_defaut()
        sauvegarder_parametres(parametres)
        return parametres
    except Exception as e:
        print(f"Erreur inattendue au chargement des paramètres: {e}")
        return creer_parametres_defaut()

def sauvegarder_parametres(parametres):
    """Sauvegarde le dictionnaire de paramètres dans le fichier JSON."""
    chemin_fichier = get_chemin_absolu_parametres()
    try:
        with open(chemin_fichier, 'w', encoding='utf-8') as f:
            json.dump(parametres, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Erreur lors de la sauvegarde des paramètres: {e}")