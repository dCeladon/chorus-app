# -*- coding: utf-8 -*-
"""
Created on Sun Jun 22 18:50:43 2025

@author: dinoc
"""

# connect_db.py
import psycopg2
import streamlit as st

@st.cache_resource
def get_db_connection():
    return psycopg2.connect(
        host="aws-0-eu-central-2.pooler.supabase.com",
        port=6543,
        database="postgres",
        user="postgres.vcbrxuggtttjaqmenslb",
        password="&8aa9Y3rASYoBYC4"
    )
