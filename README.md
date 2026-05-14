# 📊 CESU-EXTRACT — Extracteur Intelligent de Rapports Qualité

## 🩺 Présentation du projet

CESU-EXTRACT est une application d'automatisation documentaire conçue pour analyser des rapports qualité au format PDF et les transformer en données structurées, normalisées et directement exploitables.

Le projet répond à un besoin métier concret : automatiser le traitement de rapports qualité issus de plateformes de formation, afin de supprimer la ressaisie manuelle, fiabiliser les indicateurs et accélérer la consolidation des résultats.

L'application couvre l'intégralité de la chaîne de traitement :

- 📥 Ingestion de rapports PDF (textuels ou scannés)
- 🧠 Extraction intelligente des informations via modèles de langage (LLM)
- 🧩 Structuration selon un schéma de données strict
- 📈 Calcul automatique d'indicateurs qualité
- 📝 Génération de synthèses et regroupement des verbatims
- 📊 Transformation vers un format Excel normalisé
- ☁️ Injection automatisée dans Google Sheets
- 🌐 Déploiement cloud via Streamlit

Le projet a été conçu comme une solution modulaire, robuste et industrialisable, destinée à des environnements institutionnels et professionnels.

---

## 🎯 Objectifs fonctionnels

- Réduire drastiquement le temps de traitement manuel des rapports
- Supprimer les tâches de ressaisie et de consolidation manuelle
- Fiabiliser l'extraction et l'interprétation des données qualité
- Standardiser les indicateurs dans le temps
- Centraliser les résultats dans des formats directement exploitables
- Faciliter le pilotage, le reporting et l'aide à la décision
- Proposer une solution sécurisée et compatible avec les contraintes institutionnelles

---

## 🚀 Fonctionnalités principales

## 1️⃣ Ingestion et lecture des rapports PDF

- Import de rapports qualité au format PDF
- Support des documents natifs et scannés
- Extraction de texte avec OCR si nécessaire
- Gestion de documents volumineux (>150 pages)

## 2️⃣ Extraction intelligente des données

- Analyse sémantique du contenu via OpenAI API
- Extraction des indicateurs quantitatifs et qualitatifs
- Harmonisation des notes, pourcentages et verbatims
- Structuration automatique des réponses ouvertes

## 3️⃣ Validation et normalisation

- Validation stricte via Pydantic
- Contrôle des types et de la cohérence des données
- Normalisation des formats numériques et textuels
- Détection des sections manquantes ou incomplètes

## 4️⃣ Calculs et synthèses automatiques

- Calcul des notes globales
- Mesure de la progression des compétences
- Agrégation des distributions de satisfaction
- Synthèse automatique des points forts et axes d'amélioration

## 5️⃣ Transformation métier

- Conversion du schéma d'extraction vers un schéma Excel métier
- Alignement strict avec le modèle de consolidation institutionnel
- Génération d'un JSON intermédiaire compatible avec les supports bureautiques

## 6️⃣ Consolidation et exploitation

- Export local vers JSON Excel
- Injection automatisée dans Google Sheets
- Compatibilité avec des modèles Excel existants
- Aucun retraitement manuel requis

---

## 📈 Optimisation pour les rapports volumineux

L'application détecte automatiquement la taille des rapports PDF et sélectionne dynamiquement le modèle OpenAI le plus adapté.

| Type de rapport | Critère | Modèle utilisé |
|----------------|--------:|----------------|
| Standard | ≤ 80 pages et ≤ 180 000 caractères | `gpt-4.1-mini` |
| Volumineux | > 80 pages ou > 180 000 caractères | `gpt-4.1` |

Cette optimisation permet de traiter de manière fiable des rapports de plus de 150 pages comportant plusieurs centaines de réponses participants.

---

## 🧩 Cas d'usage

- Analyse qualité de formations
- Consolidation multi-sessions
- Suivi semestriel ou annuel
- Préparation d'indicateurs de pilotage
- Reporting institutionnel
- Appui à la décision
- Réduction des erreurs de ressaisie
- Standardisation des pratiques d'analyse

---

## 🏗️ Architecture générale

Le projet repose sur une architecture pipeline modulaire :

```text
PDF Digiforma
    ↓
Extraction texte + OCR
    ↓
Analyse LLM (OpenAI)
    ↓
Validation Pydantic
    ↓
JSON structuré (v2.x)
    ↓
Transformation métier
    ↓
JSON Excel
    ↓
Google Sheets / Excel

**Chaque étape est isolée afin de garantir :** 

Maintenabilité
Testabilité
Robustesse
Traçabilité
Évolutivité


🌐 Déploiement
L'application est déployée sur Streamlit Community Cloud.

Architecture de déploiement :
Développement local
Gestion des branches Git (dev → main)
Déploiement automatique via GitHub
Gestion sécurisée des secrets
Authentification applicative

🔐 Sécurité et bonnes pratiques
Authentification simple par identifiant / mot de passe
Utilisation de comptes de service Google
Permissions minimales
Aucune clé sensible versionnée
Secrets gérés via Streamlit Secrets
Séparation développement / production
Workflow Git structuré

🧠 Technologies utilisées
Backend & Application
Python
Streamlit
Intelligence Artificielle
OpenAI API
GPT-4.1-mini
GPT-4.1
Data Engineering
Pydantic
JSON
openpyxl
Document Processing
PDF parsing
OCR
Cloud & APIs
Google Sheets API
Google Cloud Platform
Streamlit Cloud
Qualité logicielle
Git / GitHub
Branching strategy
Validation de schémas

📊 Résultats obtenus
Automatisation complète du processus de traitement
Réduction majeure du temps de consolidation
Suppression de la ressaisie manuelle
Fiabilisation des indicateurs qualité
Standardisation des analyses
Traçabilité complète des transformations
Support des rapports de plus de 180 pages
Déploiement opérationnel en environnement institutionnel

⭐ Points forts du projet
Solution de bout en bout
Architecture modulaire et industrialisable
Adaptation automatique à la volumétrie documentaire
Validation stricte des données
Intégration cloud sécurisée
Compatible avec des environnements institutionnels
Facilement extensible à d'autres cas d'usage

👨‍💻 À propos

Ce projet illustre une approche combinant :
Data Engineering
Automatisation intelligente
Intelligence Artificielle appliquée
Qualité et gouvernance des données
Industrialisation des processus

Il a été conçu pour transformer des processus documentaires complexes en chaînes de traitement fiables, reproductibles et scalables.

✍️ Auteur

Roméo Botuli
Ingénieur Data & Intelligence Artificielle

Projet réalisé dans un contexte institutionnel pour le Centre d'Enseignement des Soins d'Urgence du Var (CESU 83).