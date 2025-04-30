import streamlit as st
import os

from api import fetchAssets, api_init
from db import startup_db_configurations, startup_processed_duplicate_faiss_db
from startup import startup_sidebar
from imageDuplicate import generate_db_duplicate, show_duplicate_photos_faiss, calculateFaissIndex

# Erlaubt mehrere OpenMP‐Bibliotheken
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Seiteneinstellungen
st.set_page_config(
    page_title="Immich Duplicate Finder",
    page_icon="https://immich.app/img/immich-logo-stacked-dark.svg",
    layout="wide"
)

def setup_session_state():
    session_defaults = {
        'calculate_faiss': False,
        'generate_db_duplicate': False,
        'show_faiss_duplicate': False,
        'limit': 100,
        'faiss_min_threshold': 0.0,
        'faiss_max_threshold': 1.0,
        'photo_choice': 'Thumbnail (fast)',
    }
    for key, default in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

def configure_sidebar():
    with st.sidebar:
        st.markdown("### Immich Duplicate Finder")
        st.markdown("---")
        # 1) Index berechnen
        if st.button('Create/Update FAISS index'):
            st.session_state['calculate_faiss'] = True
        # 2) Dubletten in DB schreiben
        if st.button('Create/Update duplicate DB'):
            st.session_state['generate_db_duplicate'] = True
        # 3) Gefundene Dubletten anzeigen
        if st.button('Find duplicate photos'):
            st.session_state['show_faiss_duplicate'] = True
        st.markdown("---")
        # Anzeigeparameter
        st.slider(
            label='Max duplicates to show',
            min_value=1,
            max_value=1000,
            value=st.session_state['limit'],
            key='limit'
        )
        st.number_input(
            "Minimum Faiss threshold",
            min_value=0.0, max_value=1.0, step=0.01,
            value=st.session_state['faiss_min_threshold'],
            key='faiss_min_threshold'
        )
        st.number_input(
            "Maximum Faiss threshold",
            min_value=0.0, max_value=1.0, step=0.01,
            value=st.session_state['faiss_max_threshold'],
            key='faiss_max_threshold'
        )
        st.selectbox(
            "Photo quality",
            options=['Thumbnail (fast)', 'Full size'],
            index=0 if st.session_state['photo_choice']=='Thumbnail (fast)' else 1,
            key='photo_choice'
        )

def main():
    # Einstellungen einlesen
    immich_server_url, api_key, timeout = startup_sidebar()

    # Session-State vorbereiten
    setup_session_state()
    configure_sidebar()

    # API und Datenbanken initialisieren
    api_init(immich_server_url, api_key, timeout)
    startup_db_configurations()
    startup_processed_duplicate_faiss_db()

    # Assets laden
    assets = fetchAssets('IMAGE')
    if not assets:
        st.error("No assets found or failed to fetch assets.")
        return

    # 1) FAISS‐Index erstellen
    if st.session_state['calculate_faiss']:
        calculateFaissIndex(assets)

    # 2) Dubletten in DB speichern
    if st.session_state['generate_db_duplicate']:
        generate_db_duplicate()

    # 3) Gefundene Dubletten anzeigen
    if st.session_state['show_faiss_duplicate']:
        show_duplicate_photos_faiss(
            st.session_state['limit'],
            st.session_state['faiss_min_threshold'],
            st.session_state['faiss_max_threshold']
        )

if __name__ == "__main__":
    main()