# -*- coding: utf-8 -*-
"""Smoke test sem GUI: banco + xlsx + pdf + horas."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# impede Tk de abrir: importa só funções, não instancia App
import app as A

print("1) conectar/criar banco...")
con = A.conectar()
print("   OK:", A.DB_PATH, os.path.exists(A.DB_PATH))

print("2) hash/confere senha...")
h = A.hash_senha("teste123")
assert A.confere_senha("teste123", h) and not A.confere_senha("errada", h)
print("   OK")

print("3) gerar XLSX+PDF de BM fake...")
dados = {"rm": "BM-2026-010", "periodo_txt": "01/09/2026 até 30/09/2026",
         "emissao_txt": "01/10/2026", "revisao": 0, "po": "EC-PO-2026-047",
         "po_ini_txt": "26/05/2026", "po_fim_txt": "25/09/2026",
         "valor_total": 84000, "objeto": "Serviços de Consultoria em TELECOM",
         "contratada": "SERROM ENGENHARIA", "cnpj": "43382115000109",
         "itens": [("PRJ-25-05 - RNEST - LOTE A - UCR", 125, None, 10.0)]}
xb, ta, tp, tac, saldo = A.construir_xlsx_bm(dados)
pb = A.construir_pdf_bm(dados)
print(f"   XLSX {len(xb)} bytes | PDF {len(pb)} bytes | tot_per={tp} saldo={saldo}")
assert len(xb) > 5000 and len(pb) > 1000 and tp == 1250.0

print("4) ler planilha de horas real...")
proj, ini, fim, linhas = A.ler_horas_arquivo(r"C:\Users\davi.alvarenga\Downloads\horas por item (2).xlsx")
print("   proj:", proj, "| ini:", ini, "| fim:", fim, "| linhas:", linhas)
assert proj and linhas

print("5) tabelas do banco...")
tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print("   ", tabs)
assert set(["users", "companies", "bms", "bm_items"]) <= set(tabs)
con.close()
print("SMOKE_OK")
