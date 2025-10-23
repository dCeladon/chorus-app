# app.py — Brano del Giorno (Streamlit Community, con secrets)
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime, date
from zoneinfo import ZoneInfo
from PIL import Image

# ========== CONFIG ==========
LOGO_PATH = "chorus_logo_dei_30_ridotto.jpg"
MIN_SCORE = 6.0
TZ = ZoneInfo("Europe/Rome")
ANCHOR_DATE = date(2025, 10, 23)

st.set_page_config(page_title="Brano del Giorno — CHORUS APS", layout="centered")
st.markdown("""
<style>
.block-container { padding-top: 1rem; }
h1, h2, h3 { text-align: center; color: #c62828; }
hr { margin: 1.2rem 0; }
.small-muted { color:#666; font-size:0.9rem; text-align:center; }
.kpi { text-align:center; }
.kpi .big { font-size: 1.6rem; font-weight: 700; }
.kpi .lab { color:#666; font-size:0.9rem; }
</style>
""", unsafe_allow_html=True)

try:
    st.image(Image.open(LOGO_PATH), width=220)
except Exception:
    pass

st.title("🎵 Brano del Giorno")
st.caption("CHORUS APS – Gruppo Ritmico Corale • Verona")

# ========== HELPERS ==========
def crea_engine_sqlalchemy():
    """Crea l'engine leggendo le credenziali da st.secrets e forzando SSL (Supabase)."""
    host = st.secrets.get("DB_HOST", "")
    port = st.secrets.get("DB_PORT", "5432")
    db   = st.secrets.get("DB_NAME", "")
    user = st.secrets.get("DB_USER", "")
    pwd  = st.secrets.get("DB_PASS", "")
    sslm = st.secrets.get("DB_SSLMODE", "require")  # Supabase → 'require'

    if not all([host, port, db, user, pwd]):
        st.error("Credenziali DB mancanti nei Secrets. Vai in Settings → Secrets e impostale.")
        st.stop()

    url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}?sslmode={sslm}"
    return create_engine(url)

@st.cache_data(ttl=300)
def carica_classifica_df() -> pd.DataFrame:
    query = """
        SELECT 
            p.id,
            p.titolo,
            p.autore,
            p.link_youtube,
            COUNT(v.voto) AS numero_votanti,
            AVG(v.voto)::NUMERIC(5,3) AS media_voto,
            STDDEV(v.voto)::NUMERIC(5,3) AS std_voto,
            (AVG(v.voto) - STDDEV(v.voto) / NULLIF(SQRT(COUNT(v.voto)),0))::NUMERIC(6,3) AS punteggio_complessivo
        FROM proposte p
        JOIN voti v ON p.id = v.brano_id
        GROUP BY p.id, p.titolo, p.autore, p.link_youtube
        HAVING COUNT(v.voto) > 0
        ORDER BY punteggio_complessivo DESC NULLS LAST, media_voto DESC
    """
    engine = crea_engine_sqlalchemy()
    df = pd.read_sql(query, engine)
    for col in ["numero_votanti", "media_voto", "std_voto", "punteggio_complessivo"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def scegli_brano_del_giorno(df: pd.DataFrame, giorno: date) -> pd.Series | None:
    """
    - Filtra brani idonei (punteggio ≥ MIN_SCORE).
    - posizione_classifica: 1 = migliore.
    - Rotazione dal peggiore al migliore rispetto all'ANCHOR_DATE.
    """
    elig_desc = df[(df["punteggio_complessivo"].notna()) & (df["punteggio_complessivo"] >= MIN_SCORE)].copy()
    if elig_desc.empty:
        return None

    elig_desc.sort_values(by=["punteggio_complessivo", "media_voto"], ascending=[False, False], inplace=True)
    elig_desc["posizione_classifica"] = range(1, len(elig_desc) + 1)  # 1 = migliore, N = peggiore

    # Rotazione: invertiamo l’ordine (peggiore → migliore)
    elig = elig_desc.iloc[::-1].reset_index(drop=True)

    days = (giorno - ANCHOR_DATE).days
    idx = days % len(elig)

    return elig.iloc[idx]

# ========== LOGICA ==========
oggi = datetime.now(TZ).date()

try:
    df_classifica = carica_classifica_df()
except Exception as e:
    st.error("Errore nel caricamento dati dal database.")
    st.exception(e)
    st.stop()

scelto = scegli_brano_del_giorno(df_classifica, oggi)

if scelto is None:
    st.warning("Nessun brano idoneo (punteggio ≥ 6).")
else:
    st.markdown(f"<div class='small-muted'>Data: <b>{oggi.strftime('%d/%m/%Y')}</b></div>", unsafe_allow_html=True)
    st.subheader(f"🎧 {scelto['titolo']} — {scelto['autore']}")

    link = (scelto.get("link_youtube") or "").strip()
    if link:
        st.video(link)
    else:
        st.info("Nessun video disponibile per questo brano.")

    # KPI
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("<div class='kpi'><div class='big'>"
                    f"{scelto['numero_votanti']:.0f}</div><div class='lab'>Votanti</div></div>", unsafe_allow_html=True)
    with col2:
        punteggio = float(scelto['punteggio_complessivo']) if pd.notna(scelto['punteggio_complessivo']) else 0.0
        st.markdown("<div class='kpi'><div class='big'>"
                    f"{punteggio:.3f}</div><div class='lab'>Punteggio</div></div>", unsafe_allow_html=True)
    with col3:
        pos = int(scelto["posizione_classifica"]) if pd.notna(scelto.get("posizione_classifica")) else 0
        st.markdown("<div class='kpi'><div class='big'>"
                    f"{pos}</div><div class='lab'>Posizione</div></div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
