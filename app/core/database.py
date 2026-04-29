import sqlite3
import json
from datetime import datetime
import os

DB_PATH = "storage/surf_tester.db"

def init_db():
    os.makedirs("storage", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS execucoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_execucao TEXT,
            arquivo TEXT,
            status_final TEXT,
            total_testes INTEGER,
            aprovados INTEGER,
            falhas INTEGER,
            s1_total INTEGER,
            s2_total INTEGER,
            relatorio_pdf TEXT,
            detalhes_json TEXT
        )
    ''')
    conn.commit()
    conn.close()

def salvar_execucao(dados):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO execucoes (
            data_execucao, arquivo, status_final, total_testes, 
            aprovados, falhas, s1_total, s2_total, relatorio_pdf, detalhes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(),
        dados.get("arquivo"),
        dados.get("status_final"),
        dados.get("analise_dinamica", {}).get("total_testes", 0),
        dados.get("analise_dinamica", {}).get("aprovados", 0),
        dados.get("analise_dinamica", {}).get("falhas", 0),
        dados.get("s1_total", 0),
        dados.get("s2_total", 0),
        dados.get("relatorio_pdf"),
        json.dumps(dados)
    ))
    conn.commit()
    conn.close()

def obter_historico():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM execucoes ORDER BY data_execucao DESC LIMIT 50')
    linhas = c.fetchall()
    conn.close()
    return [dict(row) for row in linhas]