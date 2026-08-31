from calendar import monthrange
from datetime import date

from shiny import ui


def add_one_month(current_date):
    year = current_date.year + (1 if current_date.month == 12 else 0)
    month = 1 if current_date.month == 12 else current_date.month + 1
    last_day = monthrange(year, month)[1]
    day = min(current_date.day, last_day)
    return date(year, month, day)


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
            ui.card(
                ui.card_header("Liste du matériel"),
                ui.output_data_frame("table_materiel"),
        ),
    ),

    ui.nav_panel(
        "📅 Disponibilités",
        ui.layout_sidebar(
            ui.sidebar(
                ui.input_date("date_dispo_debut", "Date de début", value=date.today()),
                ui.input_date("date_dispo_fin", "Date de fin", value=add_one_month(date.today())),
            ),
            ui.card(
                ui.card_header("Disponibilité par sous-catégorie"),
                ui.output_data_frame("calendrier_disponibilite"),
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
                                "": "Sélectionner",
                                "son": "Son",
                                "camera": "Caméra",
                                "lumiere": "Lumière",
                                "elec": "Électrique",
                                "scene": "Scène",
                            },
                        ),
                        ui.input_selectize(
                            "sous_cat",
                            "Sous-Catégorie",
                            choices={},
                            selected="",
                            options={"create": True, "placeholder": "Choisir ou taper une sous-catégorie"},
                        ),
                        ui.input_numeric("nombre",'Nombre',1),
                        ui.input_numeric("prix", "Prix (€)", value=0.0, min=0),
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
            ui.output_data_frame("table_demande_materiel"),
            ui.input_text("demandeur", "Nom du demandeur"),
            ui.input_text("email", "Email"),
            ui.input_date("date_debut", "Date de début"),
            ui.input_date("date_fin", "Date de fin"),
            ui.input_text("heure_debut", "Heure de début", placeholder="09:00"),
            ui.input_text("heure_fin", "Heure de fin", placeholder="18:00"),
            ui.input_text_area("motif", "Motif de l'emprunt"),
            ui.input_action_button("envoyer_demande", "Envoyer la demande", class_="btn-success"),
            ui.output_ui("message_demande"),
            ui.card(
                ui.card_header("Devis récapitulatif"),
                ui.output_ui("devis_demande"),
            ),
        ),
    ),

    ui.nav_panel(
        "📋 Demandes",
        ui.card(
            ui.card_header("Demandes d'emprunt"),
            ui.input_select("demande_validation", "Demande à traiter", choices={"": "Sélectionner une demande"}),
            ui.layout_columns(
                ui.input_action_button("accepter_demande", "Valider", class_="btn-success"),
                ui.input_action_button("refuser_demande", "Refuser", class_="btn-danger"),
            ),
            ui.output_data_frame("table_demandes"),
        ),
    ),

    title="🧰 Gestion du matériel",
)
