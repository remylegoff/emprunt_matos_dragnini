import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).parent / "data" / "materiel.db"


def mask_email(value):
    if not value:
        return ""
    value = str(value).strip()
    if "@" not in value:
        return value[:2] + "*" * max(len(value) - 2, 0)
    local, domain = value.split("@", 1)
    if len(local) <= 2:
        masked_local = "*" * len(local)
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def mask_phone(value):
    if not value:
        return ""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) <= 2:
        return "*" * len(digits)
    return f"{digits[:2]}******{digits[-2:]}"


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
        prix REAL DEFAULT 0,
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
        materiel_id INTEGER,
        demandeur TEXT NOT NULL,
        email TEXT NOT NULL,
        date_debut TEXT NOT NULL,
        date_fin TEXT NOT NULL,
        motif TEXT,
        statut TEXT NOT NULL DEFAULT 'en_attente',
        date_demande TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (materiel_id) REFERENCES materiel(id)
    );

    CREATE TABLE IF NOT EXISTS demande_materiel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        demande_id INTEGER NOT NULL,
        materiel_id INTEGER NOT NULL,
        FOREIGN KEY (demande_id) REFERENCES demandes(id),
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


def get_sous_categories(categorie=None):
    conn = get_connection()
    query = "SELECT DISTINCT sous_categorie FROM materiel WHERE sous_categorie IS NOT NULL"
    params = []
    if categorie:
        query += " AND categorie = ?"
        params.append(categorie)
    query += " ORDER BY sous_categorie"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df["sous_categorie"].dropna().astype(str).tolist()


def get_disponibilite_par_sous_categorie(date_debut, date_fin):
    if not date_debut or not date_fin:
        return pd.DataFrame({"Sous-catégorie": []})

    start = pd.Timestamp(date_debut)
    end = pd.Timestamp(date_fin)
    if end < start:
        start, end = end, start

    conn = get_connection()
    materiels = pd.read_sql_query(
        "SELECT id, sous_categorie FROM materiel WHERE sous_categorie IS NOT NULL ORDER BY sous_categorie, id",
        conn,
    )
    demandes = pd.read_sql_query(
        """
        SELECT dm.materiel_id, m.sous_categorie, d.date_debut, d.date_fin
        FROM demande_materiel dm
        JOIN demandes d ON d.id = dm.demande_id
        JOIN materiel m ON m.id = dm.materiel_id
        WHERE d.statut = 'acceptee'
        """,
        conn,
    )
    conn.close()

    if materiels.empty:
        return pd.DataFrame({"Sous-catégorie": []})

    if not demandes.empty:
        demandes["date_debut"] = pd.to_datetime(demandes["date_debut"])
        demandes["date_fin"] = pd.to_datetime(demandes["date_fin"])

    total_by_subcat = materiels.groupby("sous_categorie").size().sort_index()
    dates = pd.date_range(start=start.normalize(), end=end.normalize(), freq="D")

    rows = []
    for sous_cat, total in total_by_subcat.items():
        row = {"Sous-catégorie": sous_cat}
        for day in dates:
            day_label = day.strftime("%d/%m")
            day_stamp = day.normalize()
            reserved = 0
            if not demandes.empty:
                overlap = demandes[
                    (demandes["sous_categorie"] == sous_cat)
                    & (demandes["date_debut"] <= day_stamp)
                    & (demandes["date_fin"] >= day_stamp)
                ]
                reserved = overlap["materiel_id"].nunique()
            row[day_label] = f"{max(total - reserved, 0)}/{total}"
        rows.append(row)

    return pd.DataFrame(rows)


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
    if df.empty:
        return df
    df = df.copy()
    df["mail"] = df["mail"].apply(mask_email)
    df["telephone"] = df["telephone"].apply(mask_phone)
    return df

def get_materiels(recherche="", categorie="", sous_cat="", etat="", aggreger=False):
    conn = get_connection()
    query = """
        SELECT m.id, m.nom, m.reference, m.categorie, m.description,
               m.prix, p.nom AS proprietaire, m.etat, m.date_ajout
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

    query += " ORDER BY m.nom, p.nom"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if not aggreger or df.empty:
        return df

    grouped = (
        df.groupby(["nom", "proprietaire"], as_index=False, dropna=False)
        .agg(
            quantite=("id", "count"),
            categorie=("categorie", "first"),
            prix=("prix", "sum"),
            description=("description", "first"),
            etat=("etat", "first"),
            date_ajout=("date_ajout", "min"),
        )
        .sort_values(["proprietaire", "nom"])
        .reset_index(drop=True)
    )
    return grouped


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


def ajouter_materiel(nom, reference, categorie, sous_cat, description, prix, proprietaire):
    print("Connection à la base de données")

    if isinstance(proprietaire, str):
        proprietaire_id = get_proprio_id(proprietaire)
        if proprietaire_id is None:
            return None, "Le propriétaire sélectionné n'existe pas dans la base."
    else:
        proprietaire_id = proprietaire

    conn = get_connection()
    try:
        existing = pd.read_sql_query(
            """
            SELECT m.reference, p.nom AS proprietaire
            FROM materiel m
            JOIN proprio p ON p.id = m.proprietaire_id
            WHERE m.nom = ? AND p.id = ?
            """,
            conn,
            params=(nom.strip(), proprietaire_id),
        )
    finally:
        conn.close()

    if not existing.empty:
        numeric_refs = []
        for value in existing["reference"].dropna().astype(str):
            digits = "".join(ch for ch in value if ch.isdigit())
            if digits:
                numeric_refs.append(int(digits))
        next_ref = max(numeric_refs, default=0) + 1 if numeric_refs else int(reference) + 1
        ref = next_ref
    else:
        ref = reference

    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO materiel
            (nom, reference, categorie, sous_categorie, description, prix, proprietaire_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (nom or None, ref, categorie, sous_cat, description, float(prix or 0), proprietaire_id),
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
    if isinstance(materiel_id, (list, tuple, set)):
        return all(
            demande_possible(int(item), date_debut, date_fin)
            for item in materiel_id
        )

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
        (int(materiel_id), date_fin, date_debut),
    ).fetchone()
    conn.close()
    return row["n"] == 0


def ajouter_demande(materiel_ids, demandeur, email, date_debut, date_fin, motif):
    if isinstance(materiel_ids, (str, int)):
        materiel_ids = [int(materiel_ids)]
    else:
        materiel_ids = [int(item) for item in materiel_ids]

    conn = get_connection()
    try:
        first_id = materiel_ids[0]
        cur = conn.execute(
            """
            INSERT INTO demandes
            (materiel_id, demandeur, email, date_debut, date_fin, motif)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (first_id, demandeur, email, date_debut, date_fin, motif),
        )
        demande_id = cur.lastrowid

        for materiel_id in materiel_ids:
            conn.execute(
                """
                INSERT INTO demande_materiel (demande_id, materiel_id)
                VALUES (?, ?)
                """,
                (demande_id, materiel_id),
            )

        conn.commit()
        return demande_id
    finally:
        conn.close()


def get_demandes():
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT
            d.id,
            COALESCE(
                (SELECT GROUP_CONCAT(m2.nom, ', ')
                 FROM demande_materiel dm2
                 JOIN materiel m2 ON m2.id = dm2.materiel_id
                 WHERE dm2.demande_id = d.id),
                (SELECT m3.nom FROM materiel m3 WHERE m3.id = d.materiel_id)
            ) AS materiel,
            d.demandeur,
            d.email,
            d.date_debut,
            d.date_fin,
            d.motif,
            d.statut,
            d.date_demande
        FROM demandes d
        ORDER BY d.date_demande DESC
        """,
        conn,
    )
    conn.close()
    if df.empty:
        return df
    df = df.copy()
    df["email"] = df["email"].apply(mask_email)
    return df


def supprimer_demande(demande_id):
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM demande_materiel WHERE demande_id = ?",
            (int(demande_id),),
        )
        conn.execute(
            "DELETE FROM demandes WHERE id = ?",
            (int(demande_id),),
        )
        conn.commit()
    finally:
        conn.close()


def update_demande_statut(demande_id, statut):
    if statut not in {"en_attente", "acceptee", "refusee"}:
        raise ValueError(f"Statut invalide: {statut}")

    if statut == "refusee":
        supprimer_demande(demande_id)
        return

    conn = get_connection()
    conn.execute(
        "UPDATE demandes SET statut = ? WHERE id = ?",
        (statut, int(demande_id)),
    )
    conn.commit()
    conn.close()


def nettoyer_demandes_expirees():
    conn = get_connection()
    try:
        conn.execute(
            """
            DELETE FROM demandes
            WHERE datetime(date_fin) < datetime('now')
            """
        )
        conn.commit()
    finally:
        conn.close()

    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM demande_materiel WHERE demande_id NOT IN (SELECT id FROM demandes)"
        )
        conn.commit()
    finally:
        conn.close()


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
nettoyer_demandes_expirees()
