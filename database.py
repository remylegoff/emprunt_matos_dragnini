import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).parent / "data" / "materiel.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS materiel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        reference TEXT NOT NULL,
        categorie TEXT NOT NULL,
        sous_categorie TEXT NOT NULL,
        description TEXT,
        proprietaire_id INTEGER,
        proprietaire TEXT,
        etat TEXT NOT NULL DEFAULT 'disponible',
        date_ajout TEXT NOT NULL DEFAULT CURRENT_DATE,
        FOREIGN KEY (proprietaire_id) REFERENCES proprio(id)
    );

    CREATE TABLE IF NOT EXISTS proprio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT UNIQUE NOT NULL,
        mail TEXT NOT NULL,
        telephone TEXT,
        ville TEXT DEFAULT 'Montpellier'
    );

    CREATE TABLE IF NOT EXISTS demandes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        materiel_id INTEGER NOT NULL,
        demandeur TEXT NOT NULL,
        email TEXT NOT NULL,
        date_debut TEXT NOT NULL,
        date_fin TEXT NOT NULL,
        motif TEXT,
        statut TEXT NOT NULL DEFAULT 'en_attente',
        date_demande TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (materiel_id) REFERENCES materiel(id)
    );
    """)
    conn.commit()
    conn.close()


def get_categories():
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT DISTINCT categorie FROM materiel ORDER BY categorie", conn
    )
    conn.close()
    return df["categorie"].tolist()

def get_proprio():
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT DISTINCT nom FROM proprio ORDER BY nom", conn
    )
    conn.close()
    return df["nom"].tolist()

def get_proprio_df():
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT nom, mail, telephone, ville FROM proprio WHERE 1=1 ORDER BY nom", conn
    )
    conn.close()
    return df

def get_materiels(recherche="", categorie="", sous_cat = "", etat=""):
    conn = get_connection()
    query = """
        SELECT m.id, m.nom, m.reference, m.categorie, m.description,
               p.nom AS proprietaire, m.etat, m.date_ajout
        FROM materiel m
        JOIN proprio p ON p.id = m.proprietaire_id
        WHERE 1=1
    """
    params = []

    if recherche:
        query += " AND (m.nom LIKE ? OR m.reference LIKE ?)"
        params += [f"%{recherche}%", f"%{recherche}%"]

    if categorie:
        query += " AND m.categorie = ?"
        params.append(categorie)

    if sous_cat:
        query += " AND m.sous_categorie = ?"
        params.append(sous_cat)
    if etat:
        query += " AND m.etat = ?"
        params.append(etat)

    query += " ORDER BY m.nom"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_materiels_empruntables():
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT id, nom
        FROM materiel
        WHERE etat = 'disponible'
        ORDER BY nom
        """,
        conn,
    )
    conn.close()
    return df

def ajouter_proprio(nom, email,telephone, ville):
    print("Connection à la base de données")
    conn = get_connection()

    try:
        cur = conn.execute(
            """
            INSERT INTO proprio
            (nom, mail, telephone, ville)
            VALUES (?, ?, ?, ?)
            """,
            (nom, email, telephone, ville),
        )
        conn.commit()
        return cur.lastrowid, None
    except sqlite3.IntegrityError:
        return None, "Cette référence existe déjà."
    finally:
        conn.close()


def get_proprio_id(nom):
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM proprio WHERE nom = ?",
        (nom.strip(),),
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def ajouter_materiel(nom, reference, categorie, sous_cat, description, proprietaire):
    print("Connection à la base de données")

    if isinstance(proprietaire, str):
        proprietaire_id = get_proprio_id(proprietaire)
        if proprietaire_id is None:
            return None, "Le propriétaire sélectionné n'existe pas dans la base."
    else:
        proprietaire_id = proprietaire

    conn = get_connection()

    try:
        cur = conn.execute(
            """
            INSERT INTO materiel
            (nom, reference, categorie, sous_categorie, description, proprietaire_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (nom or None, reference, categorie, sous_cat, description, proprietaire_id),
        )
        conn.commit()
        return cur.lastrowid, None
    except sqlite3.IntegrityError as exc:
        return None, f"Erreur d'insertion: {exc}"
    finally:
        conn.close()

def supprimer_materiel(materiel_id):
    conn = get_connection()

    conn.execute(
        "DELETE FROM materiel WHERE id = ?",
        (materiel_id,)
    )

    conn.commit()
    conn.close()

def demande_possible(materiel_id, date_debut, date_fin):
    conn = get_connection()
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM demandes
        WHERE materiel_id = ?
          AND statut IN ('en_attente', 'acceptee')
          AND date_debut <= ?
          AND date_fin >= ?
        """,
        (materiel_id, date_fin, date_debut),
    ).fetchone()
    conn.close()
    return row["n"] == 0


def ajouter_demande(materiel_id, demandeur, email, date_debut, date_fin, motif):
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO demandes
        (materiel_id, demandeur, email, date_debut, date_fin, motif)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (materiel_id, demandeur, email, date_debut, date_fin, motif),
    )
    conn.commit()
    demande_id = cur.lastrowid
    conn.close()
    return demande_id


def get_demandes():
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT
            d.id,
            m.nom AS materiel,
            d.demandeur,
            d.email,
            d.date_debut,
            d.date_fin,
            d.motif,
            d.statut,
            d.date_demande
        FROM demandes d
        JOIN materiel m ON m.id = d.materiel_id
        ORDER BY d.date_demande DESC
        """,
        conn,
    )
    conn.close()
    return df


def get_statistiques():
    conn = get_connection()
    row = conn.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN etat = 'disponible' THEN 1 ELSE 0 END) AS disponible,
            SUM(CASE WHEN etat = 'emprunte' THEN 1 ELSE 0 END) AS emprunte,
            SUM(CASE WHEN etat = 'maintenance' THEN 1 ELSE 0 END) AS maintenance
        FROM materiel
    """).fetchone()
    conn.close()
    return {
        "total": row["total"] or 0,
        "disponible": row["disponible"] or 0,
        "emprunte": row["emprunte"] or 0,
        "maintenance": row["maintenance"] or 0,
    }


init_db()
