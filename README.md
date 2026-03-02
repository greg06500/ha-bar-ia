# 🥃 Home Assistant Bar Manager (AI Powered)

Ce projet transforme votre instance Home Assistant en un gestionnaire de bar intelligent.  
Il utilise l’IA pour identifier vos spiritueux, générer des fiches techniques complètes et gérer votre inventaire de manière dynamique, sans aucun module complémentaire tiers.

Ce projet est inspiré du travail remarquable d’**Aldoushx** et de son gestionnaire de cave IA.  
Il ne s’agit pas d’un fork, mais d’une adaptation conceptuelle appliquée à l’univers des spiritueux et des cocktails.

---

## ✨ Fonctionnalités

* **Identification par IA** : À partir du nom et du type, le système interroge Google Gemini. L’IA agit comme un expert en spiritueux en croisant des sources spécialisées (Difford’s Guide, Liquor.com, Whisky Advocate, etc.).

* **Fiches techniques exhaustives** :
    * **Identité** : Nom exact, Type (Rhum, Gin, Whisky…), Origine, Distillerie, Année.
    * **Caractéristiques** : ABV, Volume, Prix moyen estimé.
    * **Analyse** : Profil aromatique structuré.
    * **Cocktailabilité** : Corps cocktail (léger / moyen / puissant) et suggestions adaptées.

* **Gestion de Stock** :
    * Ajout en un clic depuis la recherche
    * Boutons +1 / -1
    * Suppression simplifiée
    * Gestion intelligente des doublons (#2, #3…)
    * Distinction Maison / Industriel

* **Statistiques** :
    * Nombre total de bouteilles
    * Valorisation estimée du bar

---

## UPDATE 1 : Mode Bouteille Maison

Ajout d’un module permettant de créer ses propres spiritueux :

* Calcul ABV estimé
* Calcul coût réel (base + ingrédients)
* Prix conseillé automatique
* Calcul marge
* Coût au litre

---

## UPDATE 2 : Accord du Barman (IA)

Un module intelligent propose un cocktail en fonction :

* De la bouteille sélectionnée (optionnel)
* Des ingrédients disponibles
* De l’occasion / envie

La réponse inclut :

* Nom du cocktail
* Style
* Raison du choix
* Ingrédients
* Recette
* Verre conseillé
* Garnish
* Niveau
* Variantes

---

## UPDATE 3 : Analyse du Stock & Cohérence

Un module compare :

* Inventaire théorique
* Bouteilles placées dans le plan
* Suroccupation
* Bouteilles non placées
* Inconnues dans le plan

---

## UPDATE 4 : Visualisation & Rangement du Bar (Frontend)

Une interface HTML permet :

* Visualisation dynamique des bouteilles
* Placement manuel (E1-1, E1-2…)
* Mode automatique (Auto-fill)
* Vidage complet
* Comparaison en direct inventaire / plan

---

## 🛠 Prérequis

1. **Clé API Google Gemini**  
   Version gratuite ou payante, à créer sur Google AI Studio.

2. **Intégration Google Generative AI**  
   Intégration native Home Assistant.  
   Nom recommandé de l’action : `google_ai_task`.

3. **Logs système activés**  
   L’intégration `system_log` doit être active pour la remontée des erreurs IA.

4. **python_scripts activé** dans `configuration.yaml`.

---

## 🚀 Installation

### 1. Organisation des fichiers

Créer les dossiers suivants dans `/config/` :
/config/packages/
/config/python_scripts/
---

### 2. Configuration du `configuration.yaml`

```yaml
homeassistant:
  packages: !include_dir_named packages

recorder:
  purge_keep_days: 7
  exclude:
    event_types:
      - system_log_event
Redémarrer Home Assistant après modification.

### 3. Emplacement des fichiers
| Fichier | Emplacement | Rôle |
| :--- | :--- | :--- |
| `bar_plan.json` | `/config/` | Base de données des emplacements |
| `generate_bar_plan.py` | `/config/` | Générateur du rendu HTML |
| `bar_cellier_ia_ultra.yaml` | `/config/packages/` | Configuration HA (Sensors, Scripts) |
| `analyze_bar_stock.py` | `/config/python_scripts/` | Calcul des écarts de stock |
| `bar_ranger.py` | `/config/python_scripts/` | Script de rangement manuel |
| `bar_autofill.py` | `/config/python_scripts/` | Script de rangement automatique |
| `bar_empty.py` | `/config/python_scripts/` | Script de vidage complet |
| `bar_plan.html` (généré auto) | `/config/www/` | Fichier de rendu final |


### 🔐 Configuration du Token API

Certains scripts nécessitent un TOKEN Home Assistant longue durée.

Insérer dans les fichiers concernés :

TOKEN = "YOUR_LONG_LIVED_TOKEN"

Fichiers concernés :
	•	generate_bar_plan.py
	•	analyze_bar_stock.py
	•	bar_autofill.py
	•	bar_empty.py

Création du token
	1.	Profil utilisateur (en bas à gauche)
	2.	Onglet Sécurité
	3.	Jetons d’accès longue durée
	4.	Créer un jeton

⚠️ Ne jamais publier un token réel sur GitHub.

📖 Utilisation
	1.	Recherche : Entrer nom et type du spiritueux puis lancer l’IA.
	2.	Ajout : Ajouter la bouteille au bar.
	3.	Gestion : Ajuster les quantités via la liste déroulante.
	4.	Accord Barman : Entrer ingrédients / occasion puis lancer la suggestion.
	5.	Rangement : Positionner les bouteilles et générer le visuel HTML.

⸻

🙏 Remerciements

Un immense merci à Aldoushx pour son projet
Home Assistant Wine Cellar Manager (AI Powered).

Son architecture, sa structuration des packages et son approche intelligente du supersensor ont été une source d’inspiration directe pour cette adaptation dédiée aux spiritueux.
