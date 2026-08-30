# Gestion du matériel — Shiny for Python

Application de gestion d'un parc de matériel avec :
- catalogue et recherche ;
- filtres par catégorie et état ;
- ajout de matériel ;
- suivi de disponibilité ;
- demandes d'emprunt ;
- contrôle des chevauchements de dates ;
- base SQLite locale.

## Installation

```bash
python -m venv .venv
```

### Linux / macOS

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Windows

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

```bash
shiny run --reload app.py
```

La base `data/materiel.db` est créée automatiquement au premier lancement.
