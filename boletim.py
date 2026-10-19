# -*- coding: utf-8 -*-
"""Geracao do Boletim de Medicao (XLSX no template DBR + PDF) e leitura das
planilhas de horas 'por item'."""
import io
import os
import re
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from util import parse_data_flex, parse_data_us

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTRATANTE = "DBR ENERGIES S/A"


def recurso(nome: str) -> str:
    base = getattr(sys, "_MEIPASS", BASE_DIR)
    return os.path.join(base, nome)


LOGO_PATH = recurso("logo.png")

MONEY = 'R$ #,##0.00'
HOURS = '#,##0.00'


# ------------------------------------------------------------------ XLSX
def construir_xlsx_bm(dados):
    """Monta o BM no template.

    dados: rm, periodo_txt, emissao_txt, revisao, po, po_ini_txt, po_fim_txt,
           valor_total, objeto, contratada, cnpj, itens[(projeto, vh, h_ant, h_per)]

    Retorna (bytes_xlsx, total_anterior, total_periodo, total_acumulado, saldo).
    """
    wb = Workbook()
    ws = wb.active
    ws.title = (dados.get("rm") or "BM")[:31]

    larg = {"B": 8, "C": 30, "D": 34, "E": 14, "F": 14, "G": 14,
            "H": 14, "I": 15, "J": 15, "K": 15, "L": 15}
    for col, w in larg.items():
        ws.column_dimensions[col].width = w

    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    bold = Font(bold=True)
    fill_h = PatternFill("solid", fgColor="D9E2F3")
    borda = Border(left=Side(style="thin"), right=Side(style="thin"),
                   top=Side(style="thin"), bottom=Side(style="thin"))

    valor_total = float(dados.get("valor_total") or 0)

    # ------------------------------------------------------ cabecalho
    ws.merge_cells("D1:G3")
    ws["D1"] = "BOLETIM DE MEDIÇÃO"
    ws["D1"].font = Font(bold=True, size=14)
    ws["D1"].alignment = center
    ws["H1"] = "RM N.°:"
    ws["I1"] = dados.get("rm") or ""
    ws["H2"] = "Período:"
    ws["I2"] = dados.get("periodo_txt") or ""
    ws["H3"] = "Emissão:"
    ws["I3"] = dados.get("emissao_txt") or ""
    ws["K6"] = f"Revisão: {dados.get('revisao', 0)}"
    ws["B7"] = "Contrato: "
    ws["E7"] = f"PO: {dados.get('po', '')}"
    ws["G7"] = f"Início PO: {dados.get('po_ini_txt', '')}"
    ws["B8"] = f"Objeto: {dados.get('objeto', '')}"
    ws["E8"] = "Valor Estimado PO:"
    ws["F8"] = "=E21"
    ws["F8"].number_format = MONEY
    ws["G8"] = f"Fim PO: {dados.get('po_fim_txt', '')}"
    ws["B9"] = f"Contratante: {CONTRATANTE}"
    ws["E9"] = f"Contratada: {datas_contratada(dados)}"
    ws["G9"] = "CNPJ Contratada: "
    ws["H9"] = dados.get("cnpj", "")
    ws["I9"] = " TOTAL (R$)"

    # logo
    if os.path.exists(LOGO_PATH):
        try:
            from openpyxl.drawing.image import Image as XLImage
            img = XLImage(LOGO_PATH)
            img.width, img.height = 170, 75
            ws.add_image(img, "L1")
        except Exception:
            ws["L1"] = "Logo da empresa prestadora de serviço"

    # ------------------------------------------------------ cabecalho tabela
    head = ["Item", "Projeto", "Descrição Atividades", "Valor Hora Unitário",
            "Horas Período anterior", "Horas No Período", "Horas Acumuladas",
            "Total Acum. Período anterior", "Total no Período", "Acumulado", "Saldo"]
    for j, h in enumerate(head):
        c = ws.cell(row=10, column=2 + j, value=h)
        c.font = bold
        c.fill = fill_h
        c.alignment = center
        c.border = borda

    # ------------------------------------------------------ itens
    r = 12
    tot_ant = tot_per = tot_acu = 0.0
    primeiro = True
    for i, (proj, vh, h_ant, h_per) in enumerate(dados.get("itens", []), start=1):
        h_ant_n = h_ant if h_ant is not None else None
        h_acu = (h_ant + h_per) if h_ant is not None else h_per
        t_ant = (h_ant * vh) if h_ant is not None else None
        t_per = h_per * vh
        t_acu = ((t_ant or 0) + t_per)

        ws.cell(row=r, column=2, value=i).alignment = center
        ws.cell(row=r, column=3, value=proj).alignment = left
        ws.cell(row=r, column=4, value="Serviços de Consultoria em TELECOM").alignment = left
        ws.cell(row=r, column=5, value=vh).number_format = MONEY
        if h_ant_n is None:
            ws.cell(row=r, column=6, value=None)
        else:
            ws.cell(row=r, column=6, value=h_ant_n)
        ws.cell(row=r, column=7, value=h_per)
        ws.cell(row=r, column=8, value=f"=IF(F{r}=\"\",G{r},F{r}+G{r})")
        ws.cell(row=r, column=9, value=f"=IF(F{r}=\"\",\"\",F{r}*E{r})")
        ws.cell(row=r, column=10, value=f"=E{r}*G{r}")
        ws.cell(row=r, column=11, value=f"=I{r}+J{r}")
        if primeiro:
            ws.cell(row=r, column=12, value="=E21-K12-K13-K14-K15-K16-K17-K18-K19")
            ws.cell(row=r, column=12).number_format = MONEY
            primeiro = False
        for col in range(2, 13):
            ws.cell(row=r, column=col).border = borda
        for col in (6, 7, 8):
            ws.cell(row=r, column=col).number_format = HOURS
        for col in (9, 10, 11):
            ws.cell(row=r, column=col).number_format = MONEY

        if t_ant:
            tot_ant += t_ant
        tot_per += t_per
        tot_acu += t_acu
        r += 1

    # ------------------------------------------------------ totais
    ws["B21"] = "TOTAL CONTRATO:"
    ws["B21"].font = bold
    ws["E21"] = valor_total
    ws["E21"].number_format = MONEY
    ws["F21"] = "=SUM(F12:F20)"
    ws["G21"] = "=SUM(G12:G20)"
    ws["H21"] = "=SUM(H12:H20)"
    ws["I21"] = "=SUM(I12:I20)"
    ws["J21"] = "=SUM(J12:J20)"
    ws["K21"] = "=SUM(K12:K20)"
    ws["L21"] = "=SUM(L12:L16)"
    for col in "FGHIJKL":
        ws[f"{col}21"].number_format = HOURS if col in "FGH" else MONEY
        ws[f"{col}21"].font = bold
        ws[f"{col}21"].border = borda

    ws["I23"] = "=I21"
    ws["J23"] = "=J21"
    ws["K23"] = "=K21"
    ws["L23"] = "=L21"
    for col in "IJKL":
        ws[f"{col}23"].number_format = MONEY

    ws["D30"] = "Gerente DBR Energies S.A."
    ws["F30"] = dados.get("contratada", "")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), tot_ant, tot_per, tot_acu, (valor_total - tot_acu)


def datas_contratada(dados):
    return dados.get("contratada", "")


# ------------------------------------------------------------------ PDF
def construir_pdf_bm(dados):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                    Spacer, Image as RLImage)
    from reportlab.lib.styles import getSampleStyleSheet

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=18, bottomMargin=18)
    st = getSampleStyleSheet()
    els = []
    if os.path.exists(LOGO_PATH):
        try:
            els.append(RLImage(LOGO_PATH, width=170, height=75))
        except Exception:
            pass
    els.append(Paragraph(f"BOLETIM DE MEDIÇÃO — {dados.get('rm') or '(sem RM)'}", st["Heading1"]))
    els.append(Paragraph(
        f"<b>{dados.get('contratada','')}</b> | CNPJ {dados.get('cnpj','')} | "
        f"PO {dados.get('po','')} ({dados.get('po_ini_txt','')} a {dados.get('po_fim_txt','')})<br/>"
        f"Objeto: {dados.get('objeto','')}<br/>"
        f"Período {dados.get('periodo_txt','')} | Emissão {dados.get('emissao_txt','')} | "
        f"Revisão {dados.get('revisao',0)} | Valor Estimado PO: R$ {dados.get('valor_total',0):,.2f}",
        st["Normal"]))
    els.append(Spacer(1, 8))

    cab = ["Item", "Projeto", "Vlr Hora", "H Ant", "H Per", "H Acu", "Tot Ant", "Tot Per", "Acumulado"]
    tab = [cab]
    tot_ant = tot_per = tot_acu = 0.0
    for i, (proj, vh, h_ant, h_per) in enumerate(dados.get("itens", []), start=1):
        h_acu = (h_ant + h_per) if h_ant is not None else h_per
        t_ant = (h_ant * vh) if h_ant is not None else 0
        t_per = h_per * vh
        tot_ant += t_ant
        tot_per += t_per
        tot_acu += (h_ant or 0) * vh + t_per
        tab.append([i, str(proj)[:70], f"{vh:,.2f}",
                    f"{h_ant:,.2f}" if h_ant is not None else "-",
                    f"{h_per:,.2f}", f"{h_acu:,.2f}",
                    f"{t_ant:,.2f}", f"{t_per:,.2f}", f"{(h_ant or 0)*vh + t_per:,.2f}"])
    tab.append(["", "TOTAL", "", "", "", "",
                f"{tot_ant:,.2f}", f"{tot_per:,.2f}", f"{tot_acu:,.2f}"])

    t = Table(tab, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5ED7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, len(tab) - 1), (-1, len(tab) - 1), "Helvetica-Bold"),
    ]))
    els.append(t)
    els.append(Spacer(1, 10))
    els.append(Paragraph(
        f"Saldo do contrato: R$ {float(dados.get('valor_total', 0)) - tot_acu:,.2f}", st["Normal"]))
    doc.build(els)
    return buf.getvalue()


# ------------------------------------------------------------------ horas
def _norm(txt):
    """Normaliza texto de cabecalho: sem acento, maiusculo, sem espacos."""
    s = str(txt or "").strip().upper()
    for a, b in (("Á", "A"), ("À", "A"), ("Ã", "A"), ("Â", "A"), ("É", "E"), ("Ê", "E"),
                 ("Í", "I"), ("Ó", "O"), ("Õ", "O"), ("Ô", "O"), ("Ú", "U"), ("Ç", "C"),
                 ("Ü", "U")):
        s = s.replace(a, b)
    return "".join(ch for ch in s if ch.isalnum())


def _detectar_colunas(ws):
    """Localiza a linha de cabecalho e mapeia as colunas por nome.

    Retorna (linha_header, {chave: indice_coluna}) ou (None, {}).
    """
    for r in range(1, min(ws.max_row, 30) + 1):
        mapa = {}
        for c in range(1, ws.max_column + 1):
            rot = _norm(ws.cell(row=r, column=c).value)
            if not rot:
                continue
            if rot in ("HORAS", "HORA") and "horas" not in mapa:
                mapa["horas"] = c
            elif rot in ("USUARIO", "RESPONSAVEL", "USUARIOS", "RESPONSAVEIS") and "usuario" not in mapa:
                mapa["usuario"] = c
            elif rot == "PROJETO" and "projeto" not in mapa:
                mapa["projeto"] = c
            elif rot in ("APROVACAO", "APROVADO") and "aprovacao" not in mapa:
                mapa["aprovacao"] = c
        if "horas" in mapa and "usuario" in mapa:
            return r, mapa
    return None, {}


def _data_intervalo(ini_txt, fim_txt):
    """Deduze o formato (dd/mm ou mm/dd) usando os valores ambiguos.

    Se algum primeiro componente > 12 -> dd/mm. Se algum segundo > 12 -> mm/dd.
    """
    def comps(t):
        m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", str(t or ""))
        return (int(m.group(1)), int(m.group(2))) if m else None

    ca, cb = comps(ini_txt), comps(fim_txt)
    if ca and cb:
        if ca[0] > 12 or cb[0] > 12:
            return parse_data_flex(ini_txt), parse_data_flex(fim_txt)
        if ca[1] > 12 or cb[1] > 12:
            return parse_data_us(ini_txt), parse_data_us(fim_txt)
    for parse in (parse_data_flex, parse_data_us):
        a, b = parse(ini_txt), parse(fim_txt)
        if a and b and b >= a:
            return a, b
    return parse_data_flex(ini_txt), parse_data_flex(fim_txt)


def ler_horas_arquivo(path):
    """Le planilhas de horas nos formatos 'cadastro horas' e 'horas por item'.

    Retorna dict:
        projeto_padrao : texto do PROJETO do cabecalho do relatorio (se houver)
        data_ini, data_fim : datas do periodo
        linhas : lista de (usuario, projeto, horas, aprovado)
    """
    wb = load_workbook(path, data_only=True)
    ws = wb.active

    projeto_padrao = None
    ini_txt = fim_txt = None
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 30), values_only=True):
        for cel in row:
            if not isinstance(cel, str):
                continue
            t = cel.strip()
            up = t.upper()
            if up.startswith("PROJETO:") and not projeto_padrao:
                projeto_padrao = t.split(":", 1)[1].strip()
            if up.startswith("DATA INICIAL:"):
                ini_txt = t.split(":", 1)[1].strip()
            if up.startswith("DATA FINAL:"):
                fim_txt = t.split(":", 1)[1].strip()
    if ini_txt and fim_txt:
        data_ini, data_fim = _data_intervalo(ini_txt, fim_txt)
    else:
        data_ini = data_fim = None

    lin_hdr, mapa = _detectar_colunas(ws)
    if not lin_hdr:
        raise ValueError(f"Não encontrei o cabeçalho com as colunas "
                         f"USUÁRIO/RESPONSÁVEL e HORAS em {os.path.basename(path)}")

    linhas = []
    for r in range(lin_hdr + 1, ws.max_row + 1):
        def cel(chave):
            if not chave:
                return None
            return ws.cell(row=r, column=mapa[chave]).value

        usu = cel("usuario")
        h = cel("horas")
        if not usu or h in (None, ""):
            continue
        if not isinstance(h, (int, float)):
            try:
                h = float(str(h).replace(",", "."))
            except (TypeError, ValueError):
                continue
        proj = cel("projeto")
        proj = str(proj).strip() if proj else (projeto_padrao or "")
        aprov = True
        if "aprovacao" in mapa:
            v = _norm(cel("aprovacao"))
            aprov = v in ("SIM", "S", "APROVADO", "APROVADA")
        linhas.append((str(usu).strip(), proj, float(h), aprov))

    if not projeto_padrao and not any(p for _, p, _, _ in linhas):
        raise ValueError(f"PROJETO não encontrado em {os.path.basename(path)}")

    return {"projeto_padrao": projeto_padrao, "data_ini": data_ini, "data_fim": data_fim,
            "linhas": linhas}
