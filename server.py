from datetime import date
from html import escape
from pathlib import Path

import pandas as pd
from shiny import reactive, render, ui
from create_devis import *
from create_devis import generate_devis_pdf
from database import (
    ajouter_demande,
    ajouter_materiel,
    ajouter_proprio,
    supprimer_materiel,
    demande_possible,
    get_categories,
    get_disponibilite_par_sous_categorie,
    get_proprio,
    get_proprio_df,
    get_proprio_id,
    get_sous_categories,
    get_demandes,
    get_materiels,
    get_materiels_empruntables,
    get_statistiques,
    update_demande_statut,
)



def server(input, output, session):

    refresh = reactive.Value(0)
    message_ajout_val = reactive.Value("")
    message_demande_val = reactive.Value("")
    devis_demande_html = reactive.Value("")

    @reactive.calc
    def filtered_materiels():
        refresh()
        return get_materiels(aggreger=True)

    @reactive.calc
    def filtered_modif():
        refresh()
        df = get_materiels(recherche=input.recherche_modif(), categorie = input.categorie_modif())
        return df
    
    @reactive.effect
    def update_filters():
        refresh()
        cats = get_categories()
        choices = {"": "Toutes"} | {c: c for c in cats}
        ui.update_select("categorie", choices=choices)
        ui.update_select("categorie_modif", choices=choices)

    @reactive.effect
    def update_filters2():
        refresh()
        cats = get_proprio()
        choices = {"": ""} | {c: c for c in cats}
        ui.update_select("proprietaire", choices=choices)

    @reactive.effect
    def update_sous_categorie_choices():
        categorie = input.categorie_ajout()
        base_choices = {}
        if categorie == "son":
            base_choices = {
                "Enceinte": "Enceinte",
                "micro": "Micro",
                "cable": "Cable",
                "tables": "Tables",
            }
        elif categorie == "lumiere":
            base_choices = {
                "PARLED": "PARLED",
                "Barre led": "Barre led",
                "MH": "MH",
                "découpe": "Découpe",
                "poursuite": "Poursuite",
                "PAR64": "PAR64",
                "fumée": "Fumée",
            }

        existing = {value: value for value in get_sous_categories(categorie)}
        choices = {**base_choices, **existing}

        if not choices:
            choices = {"": "Sélectionner une catégorie"}

        current = input.sous_cat()
        if current and current not in choices:
            choices[current] = current

        ui.update_selectize("sous_cat", choices=choices, selected=current or "")

    @reactive.effect
    def update_demande_choices():
        refresh()
        df = get_demandes()
        choices = {"": "Sélectionner une demande"} | {
            str(int(row.id)): f"#{int(row.id)} - {row.demandeur} ({row.statut})"
            for row in df.itertuples(index=False)
        }
        ui.update_select("demande_validation", choices=choices)

    @output
    @render.text
    def nb_materiel():
        return str(get_statistiques()["total"])

    @output
    @render.text
    def nb_disponible():
        return str(get_statistiques()["disponible"])

    @output
    @render.text
    def nb_emprunte():
        return str(get_statistiques()["emprunte"])

    @output
    @render.text
    def nb_maintenance():
        return str(get_statistiques()["maintenance"])

    @output
    @render.data_frame
    def table_materiel():
        refresh()
        return render.DataGrid(filtered_materiels(), width="100%", height="500px", filters=True)

    @output
    @render.data_frame
    def table_materiel_modif():
        refresh()
        return render.DataGrid(filtered_modif().iloc[:,1:], width="100%", height="500px", selection_mode = "rows", filters=True)

    @output
    @render.data_frame
    def table_proprio():
        refresh()
        return render.DataGrid(get_proprio_df(), width="100%", height="500px")

    @output
    @render.data_frame
    def table_demandes():
        refresh()
        return render.DataGrid(get_demandes(), width="100%", height="500px")

    @output
    @render.data_frame
    def dernieres_demandes():
        refresh()
        return render.DataGrid(get_demandes().head(5), width="100%", height="300px")

    @output
    @render.data_frame
    def table_demande_materiel():
        refresh()
        df = get_materiels(etat="disponible")
        if df.empty:
            return render.DataGrid(pd.DataFrame({"Nom": ["Aucun matériel disponible"]}), width="100%", height="300px", filters=True)
        return render.DataGrid(df.iloc[:,1:], width="100%", height="300px", selection_mode="rows", filters=True)

    @output
    @render.data_frame
    def calendrier_disponibilite():
        start = input.date_dispo_debut()
        end = input.date_dispo_fin()
        refresh()
        if not start or not end:
            return render.DataGrid(pd.DataFrame({"Sous-catégorie": ["Choisir une période"]}), width="100%", height="500px")

        df = get_disponibilite_par_sous_categorie(start, end)
        if df.empty:
            return render.DataGrid(pd.DataFrame({"Sous-catégorie": ["Aucune donnée"]}), width="100%", height="500px")
        return render.DataGrid(df, width="100%", height="500px")

    @reactive.effect
    @reactive.event(input.creer_proprio)
    def add_proprio():
        print(get_proprio())
        if not input.nom_proprio().strip() or input.nom_proprio().strip() in get_proprio():
            message_ajout_val.set("Le nom du proprietaire est obligatoire et unique.")
            return
        
        if not input.email_proprio().strip():
            message_ajout_val.set("Un email est obligatoire.")
            return
        
        id, error = ajouter_proprio(
            input.nom_proprio().strip(),
            input.email_proprio().strip(),
            input.tel_proprio().strip(),
            input.ville_proprio().strip(),
        )
        refresh.set(refresh()+1)

        if error:
            message_ajout_val.set(f"❌ {error}")
        else:
            message_ajout_val.set(f"✅ Propriétaire {input.nom_proprio().strip()} ajouté.")
            refresh.set(refresh()+1)

    @reactive.effect
    @reactive.event(input.ajouter_materiel)
    def add_equipment():
        if not input.nom().strip():
            message_ajout_val.set("Le nom du matériel est obligatoire.")
            return
        
        if not input.proprietaire().strip():
            message_ajout_val.set("Un propriétaire est obligatoire.")
            return
        
        proprietaire_nom = input.proprietaire().strip()
        proprietaire_id = None
        if proprietaire_nom:
            proprietaire_id = get_proprio_id(proprietaire_nom)

        if not proprietaire_id:
            message_ajout_val.set("❌ Le propriétaire sélectionné n'existe pas dans la base.")
            return

        for i in range(input.nombre()):
            equipment_id, error = ajouter_materiel(
                input.nom().strip(),
                i,
                input.categorie_ajout(),
                input.sous_cat(),
                input.description().strip(),
                input.prix(),
                proprietaire_id,
            )
            if error:
                message_ajout_val.set(f"❌ {error}")
                return

        refresh.set(refresh() + 1)
        message_ajout_val.set(f"✅ Matériel {input.nom().strip()} ajouté ({input.nombre()} fois).")
        refresh.set(refresh())

    @reactive.effect
    @reactive.event(input.retirer_materiel)
    def rm_equipment():
        df = filtered_modif()
        print(df)
        rows = input.table_materiel_modif_selected_rows()
        print(rows)
        if not rows:
            print("Pas de lignes select")
            message_ajout_val.set("❌ Sélectionnez un matériel à supprimer.")
            return

        # Récupération de l'ID SQLite de la ligne sélectionnée
        for i in rows:
            materiel_id = int(df.iloc[i]["id"])
        # Suppression en base
            supprimer_materiel(materiel_id)

        message_ajout_val.set(
            f"✅ Le matériel #{materiel_id} a été supprimé."
        )

        # Rafraîchissement des données
        refresh.set(refresh() + 1)

    @reactive.effect
    @reactive.event(input.ajouter_materiel,input.retirer_materiel, input.creer_proprio, input.accepter_demande, input.refuser_demande)
    def message_ajout():
        m = ui.modal(
            message_ajout_val(),
            title="",
            easy_close=True,
            footer=None,
        )
        ui.modal_show(m)

    @reactive.effect
    @reactive.event(input.accepter_demande)
    def accept_demande():
        demande_id = input.demande_validation()
        if not demande_id:
            message_ajout_val.set("❌ Sélectionnez une demande à valider.")
            return

        update_demande_statut(demande_id, "acceptee")
        message_ajout_val.set(f"✅ Demande #{demande_id} validée.")
        refresh.set(refresh() + 1)

    @reactive.effect
    @reactive.event(input.refuser_demande)
    def reject_demande():
        demande_id = input.demande_validation()
        if not demande_id:
            message_ajout_val.set("❌ Sélectionnez une demande à refuser.")
            return

        update_demande_statut(demande_id, "refusee")
        message_ajout_val.set(f"⚠️ Demande #{demande_id} refusée et supprimée.")
        refresh.set(refresh() + 1)


    @reactive.effect
    @reactive.event(input.envoyer_demande)
    def submit_request():
        message_demande_val.set("")

        df = get_materiels(etat="disponible")
        rows = input.table_demande_materiel_selected_rows()
        if not rows:
            message_demande_val.set("❌ Sélectionnez au moins un matériel dans le tableau.")
            return

        materiel_ids = [int(df.iloc[i]["id"]) for i in rows]

        if not input.demandeur().strip() or not input.email().strip():
            message_demande_val.set("❌ Le nom et l'email sont obligatoires.")
            return

        start_date = input.date_debut()
        end_date = input.date_fin()
        start_time = input.heure_debut().strip()
        end_time = input.heure_fin().strip()

        if not start_date or not end_date or not start_time or not end_time:
            message_demande_val.set("❌ Les dates et heures de début/fin sont obligatoires.")
            return

        try:
            from datetime import datetime
            start = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
            end = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            message_demande_val.set("❌ Les heures doivent être au format HH:MM.")
            return

        if end < start:
            message_demande_val.set("❌ La date/heure de fin doit être après la date/heure de début.")
            return

        unavailable = [
            item for item in materiel_ids
            if not demande_possible(item, start.isoformat(), end.isoformat())
        ]
        if unavailable:
            message_demande_val.set(
                "❌ L'un des matériels sélectionnés est déjà demandé sur cette période."
            )
            return

        request_id = ajouter_demande(
            materiel_ids,
            input.demandeur().strip(),
            input.email().strip(),
            start.isoformat(),
            end.isoformat(),
            input.motif().strip(),
        )

        devis_html = build_devis_html(
            materiel_ids,
            input.demandeur().strip(),
            input.email().strip(),
            start.isoformat(),
            end.isoformat(),
            input.motif().strip(),
            request_id=request_id,
        )
        generate_devis_pdf(
            materiel_ids,
            input.demandeur().strip(),
            input.email().strip(),
            start.isoformat(),
            end.isoformat(),
            input.motif().strip(),
            request_id=request_id,
        )
        devis_demande_html.set(devis_html)

        message_demande_val.set(f"✅ Demande #{request_id} enregistrée pour {len(materiel_ids)} matériel(s).")
        refresh.set(refresh() + 1)

    @output
    @render.ui
    def message_demande():
        msg = message_demande_val()
        return ui.p(msg) if msg else ui.p()

    @output
    @render.ui
    def devis_demande():
        html = devis_demande_html()
        if not html:
            return ui.div("Aucun devis généré pour l’instant.")
        return ui.HTML(html)
