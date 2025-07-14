import streamlit as st
import psycopg2
import bcrypt
import datetime
from PIL import Image

# === CONFIG ===
DB_CONFIG = {
    'host': "aws-0-eu-central-2.pooler.supabase.com",
    'port': 6543,
    'database': "postgres",
    'user': "postgres.vcbrxuggtttjaqmenslb",
    'password': "&8aa9Y3rASYoBYC4"
}
LOGO_PATH = "chorus_logo_dei_30_ridotto.jpg"

# === FUNZIONI DB ===
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def verifica_password(password, hashed):
    if isinstance(hashed, memoryview):
        hashed = hashed.tobytes()
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

def votazione_attiva():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT valore FROM configurazione WHERE chiave = 'votazione_attiva'")
    row = cur.fetchone()
    conn.close()
    return row and row[0] == '1'

# === INIZIALIZZAZIONE SESSIONE ===
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.nome = ""

# === INTERFACCIA ===
st.set_page_config(page_title="Gioco Musicale", layout="centered")
st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
        }
        .stTextInput > div > input {
            font-size: 18px;
        }
        .stButton button {
            font-size: 18px;
            border-radius: 8px;
            padding: 0.5rem 1.5rem;
        }
        .stButton.logout-button button {
            background-color: #c62828;
            color: white;
        }
        .stRadio > div {
            padding-bottom: 1rem;
        }
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
            text-align: center;
            color: #c62828;
        }
        .stRadio label {
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

st.image(Image.open(LOGO_PATH), width=250)
st.title("\U0001F3B5 Gioco Musicale")

# === LOGIN ===
if not st.session_state.logged_in:
    username = st.text_input("Username").strip()
    password = st.text_input("Password", type="password").strip()

    if st.button("Login"):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, hashed_password, nome FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
        result = cur.fetchone()
        conn.close()

        if result:
            user_id, hashed_pw, nome = result
            if verifica_password(password, hashed_pw):
                st.session_state.logged_in = True
                st.session_state.user_id = user_id
                st.session_state.nome = nome
                st.success(f"Benvenuto, {nome}!")
                st.rerun()
            else:
                st.error("Password errata.")
        else:
            st.error("Utente non trovato.")
else:
    st.success(f"Benvenuto, {st.session_state.nome}!")

    # === INSERIMENTO BRANI (una sola volta) ===
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM proposte WHERE user_id = %s", (st.session_state.user_id,))
    count = cur.fetchone()[0]
    conn.close()

    if count == 0 and 'proposte_inviate' not in st.session_state:
        st.subheader("\U0001F3BC Inserisci i tuoi 3 brani preferiti")
        with st.form("form_brani"):
            titolo1 = st.text_input("Titolo Brano 1")
            autore1 = st.text_input("Autore/Interprete Brano 1")
            titolo2 = st.text_input("Titolo Brano 2")
            autore2 = st.text_input("Autore/Interprete Brano 2")
            titolo3 = st.text_input("Titolo Brano 3")
            autore3 = st.text_input("Autore/Interprete Brano 3")
            submitted = st.form_submit_button("Invia")

        if submitted:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.executemany("""
                            INSERT INTO proposte (user_id, titolo, autore, link_youtube)
                            VALUES (%s, %s, %s, NULL)
                        """, [
                            (st.session_state.user_id, titolo1, autore1),
                            (st.session_state.user_id, titolo2, autore2),
                            (st.session_state.user_id, titolo3, autore3)
                        ])
                    conn.commit()
                st.session_state.proposte_inviate = True
                st.success("\U0001F389 Proposte inviate con successo! Grazie per la partecipazione.")
            except Exception as e:
                st.error(f"Errore durante l'inserimento dei brani: {e}")

    else:
        st.success("\U0001F3B6 Hai già inserito le tue proposte. Grazie per la partecipazione!")

        if not votazione_attiva():
            st.info("La fase di ascolto e votazione non è ancora attiva. Attendi l'apertura ufficiale.")
        else:
            # === VOTAZIONE BRANO DEL GIORNO ===
            st.header("\U0001F3A7 Brano del Giorno")
            today = datetime.date.today().isoformat()

            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT brano_id FROM brano_del_giorno WHERE data = %s", (today,))
            row = cur.fetchone()
            brano_id = row[0] if row else None

            if brano_id:
                cur.execute("SELECT titolo, autore, link_youtube FROM proposte WHERE id = %s", (brano_id,))
                titolo, autore, link = cur.fetchone()
                st.subheader(f"{titolo} — {autore}")
                if link:
                    st.video(link)
                else:
                    st.info("Nessun video disponibile.")

                cur.execute("SELECT voto FROM voti WHERE user_id = %s AND brano_id = %s", (st.session_state.user_id, brano_id))
                voto_esistente = cur.fetchone()

                if voto_esistente:
                    st.success(f"Hai già votato oggi: voto = {voto_esistente[0]}")
                else:
                    voto = st.radio("Che voto dai?", [
                        "1 😖", "2 😕", "3 😐", "4 😔", "5 😑",
                        "6 🙂", "7 😊", "8 😃", "9 😍", "10 🌟"
                    ], horizontal=True)
                    voto_num = int(voto.split()[0])
                    if st.button("Invia Voto"):
                        cur.execute("INSERT INTO voti (user_id, brano_id, voto) VALUES (%s, %s, %s)",
                                    (st.session_state.user_id, brano_id, voto_num))
                        conn.commit()
                        st.success("Voto registrato con successo!")
                        st.rerun()
            else:
                st.info("Tutti i brani sono stati votati. Classifica in preparazione...")

            conn.close()

    # === LOGOUT BUTTON ===
    st.markdown("""<div style='text-align: center; padding-top: 2rem;'>""", unsafe_allow_html=True)
    if st.button("Esci", key="logout", help="Termina la sessione", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.nome = ""
        st.rerun()
    st.markdown("""</div>""", unsafe_allow_html=True)
