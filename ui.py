from shiny import ui

app_ui = ui.page_navbar(
    ui.nav_panel(
        "📊 Tableau de bord",
        ui.layout_column_wrap(
            ui.value_box("Matériel total", ui.output_text("nb_materiel")),
            ui.value_box("Disponible", ui.output_text("nb_disponible")),
            ui.value_box("Emprunté", ui.output_text("nb_emprunte")),
            ui.value_box("Maintenance", ui.output_text("nb_maintenance")),
        ),
        ui.hr(),
        ui.card(
            ui.card_header("Dernières demandes"),
            ui.output_data_frame("dernieres_demandes"),
        ),
    ),

    ui.nav_panel(
        "📦 Matériel",
        ui.layout_sidebar(
            ui.sidebar(
                ui.input_text("recherche", "Rechercher", placeholder="Nom, référence..."),
                ui.input_select("categorie", "Catégorie", choices={"": "Toutes"}),
                ui.input_select(
                    "etat", "État",
                    choices={
                        "": "Tous",
                        "disponible": "Disponible",
                        "emprunte": "Emprunté",
                        "maintenance": "Maintenance",
                    },
                ),
            ),
            ui.card(
                ui.card_header("Liste du matériel"),
                ui.output_data_frame("table_materiel"),
            ),
        ),
    ),

    ui.nav_panel(
        "Modifier l'inventaire",
        ui.layout_sidebar(
            ui.sidebar(
                ui.accordion(
                    ui.accordion_panel(
                        "Ajouter un matériel",
                        ui.input_text("nom", "Nom du matériel"),
                        ui.input_select(
                            "categorie_ajout", "Catégorie",
                            choices={
                                "son": "Son",
                                "camera": "Caméra",
                                "lumiere": "Lumière",
                                "elec": "Électrique",
                                "scene": "Scène",
                            },
                        ),
                        ui.input_select(
                            "sous_cat", "Sous-Catégories",
                            choices={
                                "son": "Son",
                                "camera": "Caméra",
                                "lumiere": "Lumière",
                                "elec": "Électrique",
                                "scene": "Scène",
                            },
                        ),
                        ui.input_numeric("nombre",'Nombre',1),
                        ui.input_text_area("description", "Description"),
                        ui.input_select("proprietaire","Propriétaire", choices = {"":""},),
                        ui.input_action_button("ajouter_materiel", "Ajouter le matériel", class_="btn-primary")
                        ),
                        ui.accordion_panel(
                            "Retirer du matériel",
                            ui.input_text("recherche_modif", "Rechercher", placeholder="Nom, référence..."),
                            ui.input_select("categorie_modif", "Catégorie", choices={"": ""}),
                            ui.input_action_button("retirer_materiel", "Retirer le matériel", class_="btn-primary")
                        ),
                    open = False),
                    
                ),
                ui.output_data_frame("table_materiel_modif")
            )
        ),
    ui.nav_panel(
        "Créer un propriétaire",
        ui.layout_sidebar(
            ui.sidebar(
                ui.input_text("nom_proprio",'Nom/Pseudo'),
                ui.input_text("email_proprio",'Email'),
                ui.input_text("tel_proprio",'Téléphone'),
                ui.input_text("ville_proprio",'Ville'),
                ui.input_action_button('creer_proprio','Créer un nouveau propriétaire', class_='btn-primary')
            ),
            ui.output_data_frame("table_proprio")
        )
    ),
    ui.nav_panel(
        "📅 Demande d'emprunt",
        ui.card(
            ui.card_header("Faire une demande d'emprunt"),
            ui.input_select("materiel_emprunt", "Matériel", choices={}),
            ui.input_text("demandeur", "Nom du demandeur"),
            ui.input_text("email", "Email"),
            ui.input_date("date_debut", "Date de début"),
            ui.input_date("date_fin", "Date de fin"),
            ui.input_text_area("motif", "Motif de l'emprunt"),
            ui.input_action_button("envoyer_demande", "Envoyer la demande", class_="btn-success"),
            ui.output_ui("message_demande"),
        ),
    ),

    ui.nav_panel(
        "📋 Demandes",
        ui.card(
            ui.card_header("Demandes d'emprunt"),
            ui.output_data_frame("table_demandes"),
        ),
    ),

    title="🧰 Gestion du matériel",
)
