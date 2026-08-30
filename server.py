from datetime import date

from shiny import reactive, render, ui

from database import (
    ajouter_demande,
    ajouter_materiel,
    ajouter_proprio,
    supprimer_materiel,
    demande_possible,
    get_categories,
    get_proprio,
    get_proprio_df,
    get_proprio_id,
    get_demandes,
    get_materiels,
    get_materiels_empruntables,
    get_statistiques,
)


def server(input, output, session):

    refresh = reactive.Value(0)
    message_ajout_val = reactive.Value("")
    message_demande_val = reactive.Value("")

    @reactive.calc
    def filtered_materiels():
        refresh()
        return get_materiels(
            recherche=input.recherche(),
            categorie=input.categorie(),
            etat=input.etat(),
        ).iloc[:,1:]

    @reactive.calc
    def filtered_modif():
        refresh()
        return get_materiels(recherche=input.recherche_modif(), categorie = input.categorie_modif())
    
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
    def update_emprunt_choices():
        refresh()
        df = get_materiels_empruntables()
        choices = {
            str(row.id): f"{row.nom}"
            for row in df.itertuples()
        }
        ui.update_select("materiel_emprunt", choices=choices)

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
        return render.DataGrid(filtered_materiels(), width="100%", height="500px")

    @output
    @render.data_frame
    def table_materiel_modif():
        refresh()
        return render.DataGrid(filtered_modif().iloc[:,1:], width="100%", height="500px", selection_mode = "rows")

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
    @reactive.event(input.ajouter_materiel,input.retirer_materiel, input.creer_proprio)
    def message_ajout():
        m = ui.modal(
            message_ajout_val(),
            title="",
            easy_close=True,
            footer=None,
        )
        ui.modal_show(m)

    @reactive.effect
    @reactive.event(input.envoyer_demande)
    def submit_request():
        message_demande_val.set("")

        if not input.materiel_emprunt():
            message_demande_val.set("❌ Sélectionnez un matériel.")
            return

        if not input.demandeur().strip() or not input.email().strip():
            message_demande_val.set("❌ Le nom et l'email sont obligatoires.")
            return

        start = input.date_debut()
        end = input.date_fin()

        if not start or not end:
            message_demande_val.set("❌ Les deux dates sont obligatoires.")
            return

        if end < start:
            message_demande_val.set("❌ La date de fin doit être après la date de début.")
            return

        if not demande_possible(int(input.materiel_emprunt()), start.isoformat(), end.isoformat()):
            message_demande_val.set("❌ Ce matériel est déjà demandé sur cette période.")
            return

        request_id = ajouter_demande(
            int(input.materiel_emprunt()),
            input.demandeur().strip(),
            input.email().strip(),
            start.isoformat(),
            end.isoformat(),
            input.motif().strip(),
        )

        message_demande_val.set(f"✅ Demande #{request_id} enregistrée.")
        refresh.set(refresh() + 1)

    @output
    @render.ui
    def message_demande():
        msg = message_demande_val()
        return ui.p(msg) if msg else ui.p()
