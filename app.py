# app_brano_del_giorno.py
# Streamlit app pubblica (senza login) che mostra ogni giorno un "Brano del Giorno"
# - Esclude brani con punteggio < 6
# - Rotazione nel tempo dal peggiore al migliore
# - Ancoraggio su 23/10/2025: in quel giorno mostra il peggiore idoneo
# - KPI visibili: Votanti, Punteggio (3 decimali), Posizione in classifica (1 = primo classificato)

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime, date
from zoneinfo import ZoneInfo
from PIL import Image

# ========== CONFIG ==========
DB_CONFIG = {
    'host': "aws-0-eu-central-2.pooler.supabase.com",
    'port': 6543,
    'database': "postgres",
    'user': "postgres.vcbrxuggtttjaqmenslb",
    'password': "&8aa9Y3rASYoBYC4"
}
LOGO_PATH = "chorus_logo_dei_30_ridotto.jpg"
MIN_SCORE = 6.0
TZ = ZoneInfo("Europe/Rome")
ANCHOR_DATE = date(2025, 10, 23)

# ========== ST PAGE ==========
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
    url = f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}@" \
          f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
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
    - Assegna posizione_classifica = 1 al migliore.
    - Ruota i brani partendo dal peggiore verso il migliore.
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
df_classifica = carica_classifica_df()
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

    # KPI: Votanti, Punteggio (3 decimali), Posizione in classifica
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
