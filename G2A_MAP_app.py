import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import json
import simplekml
import tempfile

# Nouveaux modules pour la deuxième partie
from shapely.geometry import LineString, Point
from geopy.distance import geodesic

# ------------------------------------------
# CSS
# ------------------------------------------

# CSS et bande latérale
st.markdown("""
    <style>
    /* CSS pour la bande latérale */
    .sidebar {
        position: fixed;
        top: 0;
        left: 0;
        height: 100%;
        width: 160px; /* Largeur ajustée */
        background-color: #f0f0f0;
        padding: 0; /* Supprime le padding global */
        padding-top: 0px; /* Légère marge en haut */
        text-align: center;
        box-shadow: 2px 0 5px rgba(0,0,0,0.1);
        z-index: 1000;
    }

    .sidebar img {
        max-width: 80%; /* Taille ajustée pour le logo */
        margin-top: -40px; /* Rehausse le logo */
        margin-bottom: 20px; /* Espace sous le logo */
    }

    .main-content {
        margin-left: 170px; /* Décalage pour le contenu principal */
    }

    /* Réduction du padding général de Streamlit */
    .block-container {
        padding-top: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Affichage du logo dans la bande latérale
with st.sidebar:
    # Logo
    st.image("G2A_logo.png", caption="G2A Consulting Labo", width=160)
    
    # Texte sous le logo
    st.markdown("""
    <div style="margin-top: 10px; font-size: 14px; color: #333333; line-height: 1.5;">
        Pilote de discussion pour clarifier le besoin des commerciaux et consultants
        devant visiter des sites d'hébergeurs.
    </div>
    """, unsafe_allow_html=True)


# ------------------------------------------
# Première partie : Vue d'ensemble des trajets et sites
# ------------------------------------------

# Début du contenu principal
st.markdown('<div class="main-content">', unsafe_allow_html=True)


# Charger les trajets figés depuis le fichier JSON
try:
    with open("calculated_routes.json", "r") as f:
        calculated_routes = json.load(f)
except FileNotFoundError:
    st.error("Le fichier 'calculated_routes.json' est introuvable. Veuillez d'abord exécuter le script de calcul des trajets.")
    st.stop()

# Charger les données du fichier Excel
file_path = "Etablissements_Rhone_Alpes.xlsx"
try:
    df = pd.read_excel(file_path)
except FileNotFoundError:
    st.error("Le fichier 'Etablissements_Rhone_Alpes.xlsx' est introuvable.")
    st.stop()

# Vérifier les colonnes nécessaires
if not all(col in df.columns for col in ["Latitude", "Longitude", "Type", "Priorité"]):
    st.error("Le fichier Excel doit contenir les colonnes : Latitude, Longitude, Type, Priorité.")
    st.stop()

# Interface utilisateur pour filtrer les données
st.title("Carte interactive des trajets et hébergeurs à visiter")
types = st.multiselect("Types d'hébergement :", options=df["Type"].unique(), default=df["Type"].unique())
priorities = st.multiselect("Niveaux de priorité :", options=df["Priorité"].unique(), default=df["Priorité"].unique())

# Filtrer les données
filtered_df = df[(df["Type"].isin(types)) & (df["Priorité"].isin(priorities))]

# Définir les couleurs par priorité
priority_colors = {
    1: "red",
    2: "orange",
    3: "green"
}

# Fonction pour créer un cercle ou goutte avec texte
def create_shape_with_text(color, text):
    return f"""
    <div style="
        background-color: {color};
        width: 25px;
        height: 25px;
        border-radius: 50%;  /* Cercle */
        border: 2px solid black;
        display: flex;
        justify-content: center;
        align-items: center;
        font-size: 12px;
        font-weight: bold;
        color: white;">
        {text}
    </div>
    """

# Associer une lettre à chaque type d'hébergement
type_labels = {
    "Camping": "C",
    "Village vacances": "V",
    "Hôtel 2 étoiles": "H**",
    "Hôtel 1 étoile": "H*",
    "Hôtel": "H"
}

# Initialiser la carte
mymap = folium.Map(location=[45.5, 5.5], zoom_start=8)

# Ajouter les marqueurs pour les hébergements
for _, row in filtered_df.iterrows():
    color = priority_colors.get(row["Priorité"], "gray")  # Couleur par priorité
    label = type_labels.get(row["Type"], "?")  # Lettre associée au type d'hébergement
    html_icon = create_shape_with_text(color, label)  # Générer le marqueur avec texte

    # Ajouter le marqueur avec un tooltip et un popup
    folium.Marker(
        location=[row["Latitude"], row["Longitude"]],
        popup=f"{row['Nom']} - {row['Type']} (Priorité: {row['Priorité']})",
        tooltip=row['Nom'],  # Ajout du tooltip pour afficher le nom au survol
        icon=folium.DivIcon(html=html_icon)  # Icône HTML personnalisée
    ).add_to(mymap)

# Interface pour sélectionner les trajets
routes = list(calculated_routes.keys())
selected_routes = st.multiselect(
    "Trajets à afficher :", 
    options=routes, 
    default=routes
)

# Ajouter les trajets à la carte
for route_name in selected_routes:
    route = calculated_routes[route_name]
    folium.GeoJson(
        route,
        name=route_name,
        style_function=lambda x: {"color": "blue", "weight": 2.5},
    ).add_to(mymap)


# Afficher la carte
st_folium(mymap, width=800, height=600)



# ------------------------------------------
# Deuxième partie : Sélecteurs de sites selon trajet
# ------------------------------------------

# Fonction pour calculer les sites proches d'un trajet
def find_sites_near_route(route_coords, sites_df, max_distance_km):
    """
    Trouve les sites situés à moins de max_distance_km du trajet.
    """
    route_line = LineString([(lon, lat) for lat, lon in route_coords])
    close_sites = []
    for _, site in sites_df.iterrows():
        site_point = Point(site["Longitude"], site["Latitude"])
        distance = site_point.distance(route_line) * 111  # Approximation en km
        if distance <= max_distance_km:
            close_sites.append(site)
    return pd.DataFrame(close_sites)

st.markdown("---")  # Séparateur visuel dans l'application
st.header("Sélecteur de sites prioritaires")

# Étape 1 : Sélection du trajet
selected_route = st.selectbox("Choisissez un trajet :", list(calculated_routes.keys()))

# Étape 2 : Sélection de la distance maximale
max_distance = st.slider("Distance maximale des hébergeurs à visiter (en km) :", min_value=1, max_value=50, value=20)

# Étape 3 : Calcul des hébergeurs proches
if selected_route:
    route_coords = calculated_routes[selected_route]["features"][0]["geometry"]["coordinates"]
    route_coords = [(coord[1], coord[0]) for coord in route_coords]

    # Utiliser la fonction find_sites_near_route
    nearby_sites = find_sites_near_route(route_coords, df, max_distance)

    # Initialiser la nouvelle carte
    filtered_map = folium.Map(location=[45.5, 5.5], zoom_start=8)

    # Ajouter le trajet sélectionné sur la carte
    folium.GeoJson(
        calculated_routes[selected_route],
        name=selected_route,
        style_function=lambda x: {"color": "blue", "weight": 2.5},
    ).add_to(filtered_map)

    # Ajouter les sites proches sur la carte
    for _, site in nearby_sites.iterrows():
        color = priority_colors.get(site["Priorité"], "gray")
        label = type_labels.get(site["Type"], "?")
        html_icon = create_shape_with_text(color, label)
        folium.Marker(
            location=[site["Latitude"], site["Longitude"]],
            popup=f"{site['Nom']} - {site['Type']} (Priorité: {site['Priorité']})",
            tooltip=site['Nom'],
            icon=folium.DivIcon(html=html_icon)
        ).add_to(filtered_map)

    # Afficher la nouvelle carte
    st_folium(filtered_map, width=800, height=600)
else:
    st.info("Veuillez sélectionner un trajet pour afficher les sites proches.")


# ------------------------------------------
# Troisième partie : Bouton d'exportation de KML
# ------------------------------------------

# Fonction pour générer le fichier KML
def generate_kml(sites_df, file_name="destinations.kml"):
    kml = simplekml.Kml()
    for _, site in sites_df.iterrows():
        # Ajouter chaque site au fichier KML
        kml.newpoint(
            name=site['Nom'],  # Nom affiché sur Google Maps
            coords=[(site['Longitude'], site['Latitude'])],  # Coordonnées du site
            description=f"{site['Type']} - Priorité {site['Priorité']}"  # Description
        )
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".kml")
    kml.save(temp_file.name)
    return temp_file.name

# Bouton pour exporter les sites proches
if len(nearby_sites) > 0:  # Vérifie qu'il y a des résultats
    if st.button("Exporter un fichier Google Maps (KML)"):
        kml_file = generate_kml(nearby_sites)  # Génère le fichier KML
        with open(kml_file, "rb") as f:
            st.download_button(
                label="Téléchargez votre fichier KML",
                data=f,
                file_name="sites_proches.kml",
                mime="application/vnd.google-earth.kml+xml"
            )
else:
    st.info("Aucun site proche sélectionné. Ajustez les filtres pour voir les résultats.")