from __future__ import annotations

import re
from datetime import date
from html import escape
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from database import get_connection, get_materiels


def sanitize_name(value):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "inconnu")).strip("_. ")
    return cleaned or "inconnu"


def get_owner_details_map():
    conn = get_connection()
    rows = conn.execute(
        "SELECT nom, mail, telephone, ville FROM proprio"
    ).fetchall()
    conn.close()
    details = {}
    for row in rows:
        details[row["nom"]] = {
            "email": row["mail"] or "",
            "telephone": row["telephone"] or "",
            "ville": row["ville"] or "",
        }
    return details


def build_devis_html(materiel_ids, demandeur, email, date_debut, date_fin, motif, request_id=None):
    if isinstance(materiel_ids, (str, int)):
        materiel_ids = [int(materiel_ids)]
    else:
        materiel_ids = [int(item) for item in materiel_ids]

    if not materiel_ids:
        return ""

    df = get_materiels()
    selected = df[df["id"].isin(materiel_ids)].copy()
    if selected.empty:
        return ""

    selected["prix"] = pd.to_numeric(selected["prix"], errors="coerce").fillna(0.0)
    selected["proprietaire"] = selected["proprietaire"].fillna("Non renseigné")
    owner_details = get_owner_details_map()

    summary = (
        selected.groupby(["proprietaire", "categorie", "nom"], as_index=False)
        .agg(
            quantite=("id", "count"),
            prix_unitaire=("prix", "first"),
            total=("prix", "sum"),
        )
        .sort_values(["proprietaire", "categorie", "nom"])
        .reset_index(drop=True)
    )

    doc_dir = Path(__file__).parent / "data"
    doc_dir.mkdir(parents=True, exist_ok=True)

    def render_owner_html(proprio_name, proprio_group):
        proprio_total = 0.0
        categories_html = ""
        owner_data = owner_details.get(proprio_name, {})
        email_owner = owner_data.get("email", "")
        telephone_owner = owner_data.get("telephone", "")
        ville_owner = owner_data.get("ville", "")

        for categorie, cat_group in proprio_group.groupby("categorie", sort=False):
            rows_html = "".join(
                f"<tr><td>{escape(str(row['nom']))}</td><td>{escape(str(int(row['quantite'])))}</td><td>{float(row['prix_unitaire']):.2f} €</td><td>{float(row['total']):.2f} €</td></tr>"
                for _, row in cat_group.sort_values("nom").iterrows()
            )
            categories_html += f"""
            <h3>Catégorie : {escape(str(categorie))}</h3>
            <table>
              <thead>
                <tr>
                  <th>Nom</th>
                  <th>Quantité</th>
                  <th>Prix unitaire</th>
                  <th>Sous-total</th>
                </tr>
              </thead>
              <tbody>
                {rows_html}
              </tbody>
            </table>
            """
            proprio_total += float(cat_group["total"].sum())

        owner_html = f"""
        <html>
          <head>
            <meta charset="utf-8" />
            <title>Devis {escape(str(proprio_name))}</title>
            <style>
              body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }}
              h1 {{ margin-bottom: 8px; }}
              .meta {{ margin: 12px 0 24px; line-height: 1.6; }}
              h2 {{ margin-bottom: 12px; }}
              h3 {{ margin: 12px 0 8px; color: #374151; }}
              table {{ border-collapse: collapse; width: 100%; margin-top: 8px; margin-bottom: 12px; }}
              th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; }}
              th {{ background: #f3f4f6; }}
              .total {{ margin-top: 20px; font-size: 18px; font-weight: bold; text-align: right; }}
              .footer {{ margin-top: 28px; font-size: 12px; color: #4b5563; }}
            </style>
          </head>
          <body>
            <h1>Devis d'emprunt</h1>
            <div class="meta">
              <strong>Propriétaire :</strong> {escape(str(proprio_name))}<br>
              <strong>Email propriétaire :</strong> {escape(str(email_owner))}<br>
              <strong>Téléphone :</strong> {escape(str(telephone_owner))}<br>
              <strong>Ville :</strong> {escape(str(ville_owner))}<br>
              <strong>Demandeur :</strong> {escape(str(demandeur))}<br>
              <strong>Email demandeur :</strong> {escape(str(email))}<br>
              <strong>Période :</strong> {escape(str(date_debut))} au {escape(str(date_fin))}<br>
              <strong>Motif :</strong> {escape(str(motif or 'Non précisé'))}
            </div>
            <h2>Récapitulatif</h2>
            {categories_html}
            <div class="total">Total individuel : {proprio_total:.2f} €</div>
            <div class="footer">Document généré automatiquement pour la demande d'emprunt.</div>
          </body>
        </html>
        """
        return owner_html, proprio_total

    sections_html = ""
    global_total = 0.0

    for proprio, proprio_group in summary.groupby("proprietaire", sort=False):
        owner_html, owner_total = render_owner_html(proprio, proprio_group)
        sections_html += f"""
        <section class="proprietaire-block">
          <h2>Propriétaire : {escape(str(proprio))}</h2>
          {owner_html.split('<h2>Récapitulatif</h2>')[1].split('<div class="total">Total individuel :')[0]}
          <div class="proprio-total">Total individuel : {owner_total:.2f} €</div>
        </section>
        """
        global_total += owner_total

    html = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Devis d'emprunt</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }}
          h1 {{ margin-bottom: 8px; }}
          .meta {{ margin: 12px 0 24px; line-height: 1.6; }}
          .proprietaire-block {{ margin-top: 28px; border-top: 2px solid #e5e7eb; padding-top: 18px; }}
          h2 {{ margin-bottom: 12px; }}
          h3 {{ margin: 12px 0 8px; color: #374151; }}
          table {{ border-collapse: collapse; width: 100%; margin-top: 8px; margin-bottom: 12px; }}
          th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; }}
          th {{ background: #f3f4f6; }}
          .proprio-total {{ font-weight: bold; text-align: right; margin: 8px 0 12px; }}
          .total {{ margin-top: 26px; font-size: 20px; font-weight: bold; text-align: right; }}
          .footer {{ margin-top: 28px; font-size: 12px; color: #4b5563; }}
        </style>
      </head>
      <body>
        <h1>Devis d'emprunt</h1>
        <div class="meta">
          <strong>Demandeur :</strong> {escape(str(demandeur))}<br>
          <strong>Email :</strong> {escape(str(email))}<br>
          <strong>Période :</strong> {escape(str(date_debut))} au {escape(str(date_fin))}<br>
          <strong>Motif :</strong> {escape(str(motif or 'Non précisé'))}
        </div>
        {sections_html}
        <div class="total">Total global : {global_total:.2f} €</div>
        <div class="footer">Document généré automatiquement pour la demande d'emprunt.</div>
      </body>
    </html>
    """

    global_doc_name = f"devis_demande_{request_id or 'preview'}.html"
    (doc_dir / global_doc_name).write_text(html, encoding="utf-8")
    return html


def generate_devis_pdf(materiel_ids, demandeur, email, date_debut, date_fin, motif, request_id=None, owner_name=None):
    if isinstance(materiel_ids, (str, int)):
        materiel_ids = [int(materiel_ids)]
    else:
        materiel_ids = [int(item) for item in materiel_ids]

    if not materiel_ids:
        return []

    df = get_materiels()
    selected = df[df["id"].isin(materiel_ids)].copy()
    if selected.empty:
        return []

    selected["prix"] = pd.to_numeric(selected["prix"], errors="coerce").fillna(0.0)
    selected["proprietaire"] = selected["proprietaire"].fillna("Non renseigné")

    summary = (
        selected.groupby(["proprietaire", "categorie", "nom"], as_index=False)
        .agg(
            quantite=("id", "count"),
            prix_unitaire=("prix", "first"),
            total=("prix", "sum"),
        )
        .sort_values(["proprietaire", "categorie", "nom"])
        .reset_index(drop=True)
    )

    base_dir = Path(__file__).resolve().parent / "data" / "devis"
    base_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")
    request_number = request_id if request_id is not None else "preview"
    created = []

    demandeur_dir = base_dir / sanitize_name(demandeur)
    demandeur_dir.mkdir(parents=True, exist_ok=True)

    for proprio, proprio_group in summary.groupby("proprietaire", sort=False):
        folder_name = sanitize_name(owner_name or proprio or demandeur)
        owner_dir = base_dir / "proprietaires" / folder_name
        owner_dir.mkdir(parents=True, exist_ok=True)

        title = f"{today}-Devis#{request_number}"
        owner_pdf_path = owner_dir / f"{title}.pdf"
        owner_html_path = owner_dir / f"{title}.html"
        demandeur_pdf_path = demandeur_dir / f"{title}.pdf"
        demandeur_html_path = demandeur_dir / f"{title}.html"

        html = build_devis_html(
            materiel_ids,
            demandeur,
            email,
            date_debut,
            date_fin,
            motif,
            request_id=request_number,
        )
        owner_html_path.write_text(html, encoding="utf-8")
        demandeur_html_path.write_text(html, encoding="utf-8")

        styles = getSampleStyleSheet()
        body_style = ParagraphStyle("Body", fontName="Helvetica", fontSize=10, leading=14)
        story = []
        story.append(Paragraph("Devis d'emprunt", styles["Title"]))
        owner_data = get_owner_details_map().get(proprio, {})

        info_table = Table(
            [
                [
                    Paragraph(f"Demandeur : {demandeur}", body_style),
                    Paragraph(f"Propriétaire : {proprio}", body_style),
                ],
                [
                    Paragraph(f"Email demandeur : {email}", body_style),
                    Paragraph(f"Email propriétaire : {owner_data.get('email', '')}", body_style),
                ],
                [
                    Paragraph(f"Période : {date_debut} au {date_fin}", body_style),
                    Paragraph(f"Téléphone : {owner_data.get('telephone', '')}", body_style),
                ],
                [
                    Paragraph(f"Motif : {motif or 'Non précisé'}", body_style),
                    Paragraph(f"Ville : {owner_data.get('ville', '')}", body_style),
                ],
            ],
            colWidths=[95 * mm, 95 * mm],
        )
        info_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(info_table)
        story.append(Spacer(1, 10 * mm))

        for categorie, cat_group in proprio_group.groupby("categorie", sort=False):
            story.append(Paragraph(f"Catégorie : {categorie}", styles["Heading3"]))
            rows = [["Nom", "Quantité", "Prix unitaire", "Sous-total"]]
            for _, row in cat_group.sort_values("nom").iterrows():
                rows.append([
                    str(row["nom"]),
                    str(int(row["quantite"])),
                    f"{float(row['prix_unitaire']):.2f} €",
                    f"{float(row['total']):.2f} €",
                ])
            table = Table(rows, colWidths=[70 * mm, 22 * mm, 35 * mm, 35 * mm])
            table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfe7f5")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ])
            )
            story.append(table)
            story.append(Spacer(1, 6 * mm))

        total_owner = float(proprio_group["total"].sum())
        story.append(Paragraph(f"Total individuel : {total_owner:.2f} €", styles["Heading2"]))
        story.append(Spacer(1, 8 * mm))

        document = SimpleDocTemplate(str(owner_pdf_path), pagesize=A4)
        document.build(story)
        owner_pdf_path.write_bytes(owner_pdf_path.read_bytes())
        demandeur_pdf_path.write_bytes(owner_pdf_path.read_bytes())

        created.extend([str(owner_pdf_path), str(demandeur_pdf_path)])

    return created


def generate_facture_pdf(materiel_ids, demandeur, email, date_debut, date_fin, motif, request_id=None, owner_name=None):
    paths = generate_devis_pdf(
        materiel_ids,
        demandeur,
        email,
        date_debut,
        date_fin,
        motif,
        request_id=request_id,
        owner_name=owner_name,
    )
    if not paths:
        return []

    new_paths = []
    for path in paths:
        source = Path(path)
        target = source.with_name(source.name.replace("Devis#", "Facture#"))
        if source.exists():
            target.write_bytes(source.read_bytes())
        new_paths.append(str(target))
    return new_paths
