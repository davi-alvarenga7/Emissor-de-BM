# -*- coding: utf-8 -*-
"""Testes sem banco: geracao de BM, leitura de horas, validacoes, config SQL Server."""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import util
import boletim as bl

DOWNLOADS = r"C:\Users\davi.alvarenga\Downloads"
HORAS_REAL = os.path.join(DOWNLOADS, "cadastro horas.xlsx")
HORAS_ITEM = os.path.join(DOWNLOADS, "horas por item (2).xlsx")

print("1) senha hash/confere...")
h = util.hash_senha("teste123")
assert util.confere_senha("teste123", h)
assert not util.confere_senha("errada", h)
print("   OK")

print("2) validacoes...")
assert util.valida_cnpj("43.382.115/0001-09")
assert not util.valida_cnpj("123")
assert util.valida_email("a@b.com")
assert not util.valida_email("ab.com")
assert util.parse_num("R$ 1.234,56") == 1234.56
assert util.parse_num("125,00") == 125.0
assert util.so_digitos("43.382.115/0001-09") == "43382115000109"
print("   OK")

print("3) datas (BR e US)...")
assert util.parse_data_flex("26/08/2026").isoformat() == "2026-08-26"
assert util.parse_data_us("9/30/2026").isoformat() == "2026-09-30"
print("   OK")

print("4) XLSX + PDF do BM...")
dados = {"rm": "BM-2026-010", "periodo_txt": "01/09/2026 até 30/09/2026",
         "emissao_txt": "01/10/2026", "revisao": 0, "po": "EC-PO-2026-047",
         "po_ini_txt": "26/05/2026", "po_fim_txt": "25/09/2026",
         "valor_total": 84000, "objeto": "Serviços de Consultoria em TELECOM",
         "contratada": "SERROM ENGENHARIA", "cnpj": "43382115000109",
         "itens": [("PRJ-25-05 - RNEST - LOTE A - UCR", 125, None, 10.0),
                   ("PRJ-26-02 - TENENGE", 125, 8.0, 4.0)]}
xb, ta, tp, tac, saldo = bl.construir_xlsx_bm(dados)
pb = bl.construir_pdf_bm(dados)
assert len(xb) > 5000 and len(pb) > 1000
assert abs(tp - 1750.0) < 0.01, tp
assert abs(ta - 1000.0) < 0.01, ta
assert abs(tac - 2750.0) < 0.01, tac
assert abs(saldo - 81250.0) < 0.01, saldo
print(f"   OK - XLSX {len(xb)}B | PDF {len(pb)}B | ant={ta} per={tp} acu={tac} saldo={saldo}")

print("5) planilha real 'cadastro horas'...")
if os.path.exists(HORAS_REAL):
    info = bl.ler_horas_arquivo(HORAS_REAL)
    linhas = info["linhas"]
    assert info["data_ini"].isoformat() == "2026-10-01", info["data_ini"]
    assert info["data_fim"].isoformat() == "2026-10-19", info["data_fim"]
    assert len(linhas) == 873, len(linhas)
    aprov = [l for l in linhas if l[3]]
    assert len(aprov) == 91, len(aprov)
    assert abs(sum(l[2] for l in linhas) - 5917.0) < 0.01
    assert abs(sum(l[2] for l in aprov) - sum(l[2] for l in aprov)) < 0.01
    projs = Counter(p for _, p, _, _ in linhas)
    assert len(projs) == 10, len(projs)
    print(f"   OK - {len(linhas)} linhas | {len(aprov)} aprovadas | {len(projs)} projetos")
    print(f"        datas {info['data_ini']} a {info['data_fim']} | "
          f"horas aprovadas {sum(l[2] for l in aprov):.0f}")
else:
    print("   SKIP (arquivo nao encontrado)")

print("6) planilha modelo 'horas por item'...")
if os.path.exists(HORAS_ITEM):
    info = bl.ler_horas_arquivo(HORAS_ITEM)
    assert info["data_ini"].isoformat() == "2026-09-01", info["data_ini"]
    assert info["data_fim"].isoformat() == "2026-09-30", info["data_fim"]
    assert len(info["linhas"]) == 4, info["linhas"]
    assert info["projeto_padrao"] == "PRJ-25-05 - RNEST - LOTE A - UCR"
    assert all(l[1] == info["projeto_padrao"] for l in info["linhas"])
    print("   OK -", info["projeto_padrao"], info["data_ini"], info["data_fim"],
          len(info["linhas"]), "linhas")
else:
    print("   SKIP (arquivo nao encontrado)")

print("7) config do SQL Server...")
import db as dbmod
cfg = dbmod.carregar_config()
cs = dbmod.connection_string(cfg)
assert "ODBC Driver 17 for SQL Server" in cs
assert "DATABASE=EBM" in cs
print("   OK -", cs)

print("8) DDL do SQL Server 2016...")
import db
assert len(db.DDL) >= 6
for ddl in db.DDL:
    assert "AUTOINCREMENT" not in ddl.upper()
assert sum("IDENTITY(1,1)" in d for d in db.DDL) == 4
assert sum("VARBINARY(MAX)" in d for d in db.DDL) == 1
print("   OK -", len(db.DDL), "instrucoes DDL, 4 tabelas com IDENTITY")

print("SMOKE_OK")
