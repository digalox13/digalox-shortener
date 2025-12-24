import os
import random
import string
import re
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mysql.connector
from user_agents import parse

app = FastAPI()

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Regex para validar URLs
URL_REGEX = re.compile(
    r'^(?:http|ftp)s?://' 
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' 
    r'localhost|' 
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' 
    r'(?::\d+)?' 
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"]
    )

class URLCreate(BaseModel):
    url: str

# --- RUTAS ---

@app.post("/shorten")
def shorten_url(item: URLCreate):
    if not item.url:
        raise HTTPException(status_code=400, detail="La URL no puede estar vacía.")
    
    if not re.match(URL_REGEX, item.url):
        raise HTTPException(status_code=400, detail="Formato de URL inválido. Incluye http:// o https://")

    short_code = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        query = "INSERT INTO urls (original_url, short_code) VALUES (%s, %s)"
        cursor.execute(query, (item.url, short_code))
        conn.commit()
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Error en BD: {err}")
    finally:
        cursor.close()
        conn.close()
    
    return {"short_code": short_code}

@app.get("/stats/{short_code}")
def get_stats(short_code: str):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT id, original_url FROM urls WHERE short_code = %s", (short_code,))
        url_data = cursor.fetchone()
        
        if not url_data:
            raise HTTPException(status_code=404, detail="Link no encontrado")
            
        url_id = url_data['id']
        
        # KPI 1: Total Clics
        cursor.execute("SELECT COUNT(*) as total FROM clicks WHERE url_id = %s", (url_id,))
        total_clicks = cursor.fetchone()['total']
        
        # KPI 2: Navegadores
        cursor.execute("SELECT browser, COUNT(*) as count FROM clicks WHERE url_id = %s GROUP BY browser", (url_id,))
        browsers = cursor.fetchall()
        
    finally:
        cursor.close()
        conn.close()
    
    return {
        "original_url": url_data['original_url'],
        "total_clicks": total_clicks,
        "browsers": browsers
    }

@app.get("/{short_code}")
def redirect_to_url(short_code: str, request: Request):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT id, original_url FROM urls WHERE short_code = %s", (short_code,))
        result = cursor.fetchone()
        
        if not result:
            # Redirección de error (Link no existe)
            return RedirectResponse(url="/?error=not_found", status_code=302)
        
        # --- ANALÍTICA ---
        user_agent_str = request.headers.get('user-agent', '')
        user_agent = parse(user_agent_str)
        browser = user_agent.browser.family
        os_name = user_agent.os.family
        referer = request.headers.get('referer', 'Directo')
        
        # DE MOMENTO NO GUARDAMOS IP REAL 
        user_ip = "anónimo"
        
        insert_query = """
        INSERT INTO clicks (url_id, browser, os, referer, ip_address) 
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (result['id'], browser, os_name, referer, user_ip))
        conn.commit()
        
        target_url = result['original_url']
    finally:
        cursor.close()
        conn.close()
    
    # IMPORTANTE: status_code=302 fuerza al navegador a usar GET en la destino.
    # Esto soluciona posibles errores de "Method Not Allowed".
    return RedirectResponse(target_url, status_code=302)
