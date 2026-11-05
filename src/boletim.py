"""Geracao do Boletim de Medicao (XLSX no template oficial DBR + PDF) e leitura
das planilhas de horas 'por item'.

Fluxo de processamento do lote (regra do E-BM):
  Passo 1 - identificacao dos prestadores PJ: a coluna [Responsavel] da
            planilha e comparada com os [Usuarios E-clic] cadastrados.
  Passo 2 - consolidacao: as horas sao agrupadas e somadas por combinacao
            exata de [Projeto + Atividade(ITEM)].
  Passo 3 - fechamento financeiro: total de horas do prestador x valor hora.
"""
import io
import os
import re
import sys
from copy import copy
from xml.sax.saxutils import escape

from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage

from src.config import CONTRATANTE, DESCRICAO_PADRAO, LIN_ITEM_INI, LIN_ITEM_FIM, \
    LIN_TOTAL, LIN_MIRROR, LIN_ASSIN, CAPACIDADE_ITENS, COLUNAS_ITEM, MONEY, HOURS
from src.utils import parse_data_flex, parse_data_us, parse_num, chave_texto, \
    sem_acento, lista_eclics, fmt_br


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def recurso_assets(nome: str) -> str:
    """Caminho de um asset (logo, template) tanto em execucao normal quanto no .exe congelado."""
    base = getattr(sys, "_MEIPASS", BASE_DIR)
    return os.path.join(base, "assets", nome)


LOGO_PATH = recurso_assets("logo.png")
TEMPLATE_PATH = recurso_assets("template_bm.xlsx")


# ------------------------------------------------------------------ texto
def fmt_cnpj(cnpj) -> str:
    """Formata o CNPJ no padrao NN.NNN.NNN/NNNN-NN para impressao no BM."""
    d = re.sub(r"\D", "", str(cnpj or ""))
    if len(d) != 14:
        return str(cnpj or "")
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"


# ------------------------------------------------------------------ itens
def normaliza_itens(itens):
    """Normaliza a lista de itens para (projeto, atividade, vh, h_ant, h_per).

    Aceita tambem o formato antigo de 4 campos (projeto, vh, h_ant, h_per),
    assumindo a descricao padrao de atividade.
    """
    saida = []
    for it in itens or []:
        if len(it) == 5:
            saida.append((str(it[0] or ""), str(it[1] or ""), float(it[2]),
                          None if it[3] is None else float(it[3]), float(it[4])))
        else:
            saida.append((str(it[0] or ""), DESCRICAO_PADRAO, float(it[1]),
                          None if it[2] is None else float(it[2]), float(it[3])))
    return saida


# ------------------------------------------------------------------ XLSX
def _abrir_template():
    """Abre o template oficial do BM, mantendo apenas a aba do boletim."""
    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(
            f"Template do BM não encontrado: {TEMPLATE_PATH}\n"
            "Reinstale o E-BM (o arquivo template_bm.xlsx deve estar na pasta "
            "do executável).")
    wb = load_workbook(TEMPLATE_PATH)
    for nome in list(wb.sheetnames)[1:]:
        try:
            del wb[nome]
        except Exception:
            pass
    return wb


def _estender_itens(ws, extra):
    """Amplia a area de itens do template para caber mais combinacoes.

    Reancora os merges que ficam abaixo da linha de totais e replica o
    formato das linhas de item nas novas linhas.
    """
    for rng in list(ws.merged_cells.ranges):
        if rng.min_row >= LIN_TOTAL:
            ws.unmerge_cells(str(rng))
    ws.insert_rows(LIN_TOTAL, extra)
    for i in range(extra):
        r = LIN_ITEM_FIM + 1 + i
        for c in range(2, 13):
            src = ws.cell(row=LIN_ITEM_INI, column=c)
            dst = ws.cell(row=r, column=c)
            if src.has_style:
                dst._style = copy(src._style)


def construir_xlsx_bm(dados):
    """Monta o BM a partir do template oficial DBR.

    dados: rm, periodo_txt, emissao_txt, revisao, po, po_ini_txt, po_fim_txt,
           valor_total, objeto, contratada, cnpj,
           itens[(projeto, atividade, valor_hora, horas_anterior, horas_periodo)],
           tipo_faturamento, valor_fixo_mensal

    Retorna (bytes_xlsx, total_anterior, total_periodo, total_acumulado, saldo).
    """
    itens = normaliza_itens(dados.get("itens"))
    valor_total = float(dados.get("valor_total") or 0)
    tipo = str(dados.get("tipo_faturamento") or "HORISTA").upper()
    vfm = parse_num(dados.get("valor_fixo_mensal"))

    wb = _abrir_template()
    ws = wb[wb.sheetnames[0]]

    n = len(itens)
    extra = max(0, n - CAPACIDADE_ITENS)
    if extra:
        _estender_itens(ws, extra)

    lin_total = LIN_TOTAL + extra
    lin_mirror = LIN_MIRROR + extra
    lin_assin = LIN_ASSIN + extra
    lin_ult = (LIN_ITEM_INI + n - 1) if n else LIN_ITEM_INI - 1

    # ------------------------------------------------------ cabecalho
    ws["D1"] = "BOLETIM DE MEDIÇÃO"
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
    ws["F8"] = f"=E{lin_total}"
    ws["G8"] = f"Fim PO: {dados.get('po_fim_txt', '')}"
    ws["B9"] = f"Contratante: {CONTRATANTE}"
    ws["E9"] = f"Contratada: {dados.get('contratada', '')}"
    ws["G9"] = "CNPJ Contratada: "
    ws["H9"] = fmt_cnpj(dados.get("cnpj"))
    ws["I9"] = " TOTAL (R$)"

    # ------------------------------------------------------ logo
    try:
        ws["L1"] = None
    except Exception:
        pass
    if os.path.exists(LOGO_PATH):
        try:
            img = XLImage(LOGO_PATH)
            img.width, img.height = 170, 75
            ws.add_image(img, "L1")
        except Exception:
            pass

    # ------------------------------------------------------ area de itens
    for r in range(LIN_ITEM_INI, LIN_ITEM_FIM + 1 + extra):
        for c in range(2, 13):
            ws.cell(row=r, column=c).value = None

    tot_ant = tot_per = tot_acu = 0.0
    for i, (proj, item, vh, h_ant, h_per) in enumerate(itens, start=1):
        r = LIN_ITEM_INI + i - 1
        h_acu = (h_ant + h_per) if h_ant is not None else h_per
        t_ant = (h_ant * vh) if h_ant is not None else None
        t_per = h_per * vh
        t_acu = ((t_ant or 0) + t_per)

        ws.cell(row=r, column=2, value=str(i))
        ws.cell(row=r, column=3, value=proj)
        ws.cell(row=r, column=4, value=item)
        ws.cell(row=r, column=5, value=vh)
        ws.cell(row=r, column=6, value=h_ant)
        ws.cell(row=r, column=7, value=h_per)
        ws.cell(row=r, column=8, value=f"=F{r}+G{r}")
        ws.cell(row=r, column=9, value=f"=F{r}*E{r}")
        ws.cell(row=r, column=10, value=f"=E{r}*G{r}")
        ws.cell(row=r, column=11, value=f"=I{r}+J{r}")
        if i == 1 and n:
            ws.cell(row=r, column=12,
                    value=f"=E{lin_total}-" +
                          "-".join(f"K{LIN_ITEM_INI + k}" for k in range(n)))

        if t_ant:
            tot_ant += t_ant
        tot_per += t_per
        tot_acu += t_acu

    # ---- sobrescreve totais para empresas MENSALISTA (valor fixo mensal)
    if tipo == "MENSALISTA" and vfm is not None:
        tot_per = vfm
        tot_acu = tot_ant + vfm

    # ------------------------------------------------------ totais
    ws.cell(row=lin_total, column=2, value="TOTAL CONTRATO:")
    ws.cell(row=lin_total, column=5, value=valor_total)
    if n:
        for col in "FGHIJKL":
            ws[f"{col}{lin_total}"] = f"=SUM({col}{LIN_ITEM_INI}:{col}{lin_ult})"
    else:
        for col in "FGHIJKL":
            ws[f"{col}{lin_total}"] = 0
    for col in "IJKL":
        ws[f"{col}{lin_mirror}"] = f"={col}{lin_total}"

    # ------------------------------------------------------ assinaturas
    ws.cell(row=lin_assin, column=4, value="Gerente DBR Energies S.A.")
    ws.cell(row=lin_assin, column=6, value=dados.get("contratada", ""))

    # ------------------------------------------------------ merges
    try:
        ws.merge_cells(start_row=lin_total, start_column=2,
                       end_row=lin_total, end_column=4)
        for idx, col in enumerate("IJKL"):
            ws.merge_cells(start_row=lin_mirror, start_column=9 + idx,
                           end_row=lin_mirror + 2, end_column=9 + idx)
    except Exception:
        pass

    try:
        ws.title = (dados.get("rm") or "BM")[:31]
    except Exception:
        pass

    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue(), tot_ant, tot_per, tot_acu, (valor_total - tot_acu)


# ------------------------------------------------------------------ PDF
def construir_pdf_bm(dados):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                    Spacer, Image as RLImage)
    from reportlab.lib.styles import getSampleStyleSheet

    itens = normaliza_itens(dados.get("itens"))
    valor_total = float(dados.get("valor_total") or 0)
    tipo = str(dados.get("tipo_faturamento") or "HORISTA").upper()
    vfm = parse_num(dados.get("valor_fixo_mensal"))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=18, bottomMargin=18)
    st = getSampleStyleSheet()

    # Ajuste de legibilidade: fonte maior e mais espaçamento
    style_normal = st["Normal"]
    style_normal.fontSize = 10
    style_normal.leading = 14

    style_heading = st["Heading1"]
    style_heading.fontSize = 15
    style_heading.leading = 18

    els = []
    if os.path.exists(LOGO_PATH):
        try:
            els.append(RLImage(LOGO_PATH, width=170, height=75))
        except Exception:
            pass
    els.append(Paragraph(f"BOLETIM DE MEDIÇÃO — {escape(dados.get('rm') or '(sem RM)')}",
                         style_heading))
    els.append(Paragraph(
        f"<b>{escape(dados.get('contratada',''))}</b> | CNPJ {fmt_cnpj(dados.get('cnpj'))} | "
        f"PO {escape(dados.get('po',''))} ({dados.get('po_ini_txt','')} a {dados.get('po_fim_txt','')})<br/>"
        f"Objeto: {escape(dados.get('objeto',''))}<br/>"
        f"Período {dados.get('periodo_txt','')} | Emissão {dados.get('emissao_txt','')} | "
        f"Revisão {dados.get('revisao',0)} | Valor Estimado PO: R$ {valor_total:,.2f}",
        style_normal))
    els.append(Spacer(1, 12))

    cab = ["Item", "Projeto", "Atividade", "Vlr Hora", "H Ant", "H Per", "H Acu",
           "Tot Ant", "Tot Per", "Acumulado"]
    tab = [cab]
    tot_ant = tot_per = tot_acu = total_horas = 0.0
    valor_hora = float(itens[0][2]) if itens else 0.0
    for i, (proj, item, vh, h_ant, h_per) in enumerate(itens, start=1):
        h_acu = (h_ant + h_per) if h_ant is not None else h_per
        t_ant = (h_ant * vh) if h_ant is not None else 0
        t_per = h_per * vh
        tot_ant += t_ant
        tot_per += t_per
        tot_acu += (h_ant or 0) * vh + t_per
        total_horas += h_per
        tab.append([i, str(proj)[:46], str(item)[:40], f"{vh:,.2f}",
                    f"{h_ant:,.2f}" if h_ant is not None else "-",
                    f"{h_per:,.2f}", f"{h_acu:,.2f}",
                    f"{t_ant:,.2f}", f"{t_per:,.2f}", f"{(h_ant or 0)*vh + t_per:,.2f}"])
    tab.append(["", "TOTAL", "", "", "", "", "",
                f"{tot_ant:,.2f}", f"{tot_per:,.2f}", f"{tot_acu:,.2f}"])

    t = Table(tab, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5ED7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, len(tab) - 1), (-1, len(tab) - 1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    els.append(t)
    els.append(Spacer(1, 15))

    # ------------------------------------------------------ fechamento
    if tipo == "MENSALISTA" and vfm is not None:
        valor_periodo = vfm
        horas_txt = "-"
        vh_txt = "-"
    else:
        valor_periodo = total_horas * valor_hora
        horas_txt = f"{total_horas:,.2f} h"
        vh_txt = f"R$ {valor_hora:,.2f}"
    fech = [
        ["Total de horas no período", horas_txt,
         "Valor total do período", f"R$ {valor_periodo:,.2f}"],
        ["Total de horas acumuladas", f"{tot_acu / valor_hora:,.2f} h"
         if valor_hora else "-",
         "Total acumulado", f"R$ {tot_acu:,.2f}"],
        ["Valor hora unitário", vh_txt,
         "Saldo do contrato", f"R$ {valor_total - tot_acu:,.2f}"],
    ]
    tf = Table(fech, colWidths=[150, 95, 150, 95])
    tf.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF3FB")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    els.append(tf)
    els.append(Spacer(1, 10))
    if tipo == "MENSALISTA" and vfm is not None:
        els.append(Paragraph(
            f"Valor fixo mensal do período: <b>R$ {vfm:,.2f}</b> "
            f"&nbsp;|&nbsp; Saldo do contrato: <b>R$ {valor_total - tot_acu:,.2f}</b>",
            style_normal))
    else:
        els.append(Paragraph(
            f"Total geral de horas trabalhadas pelo prestador: <b>{total_horas:,.2f} h</b> "
            f"&nbsp;|&nbsp; Valor financeiro final (Horas Totais x Valor da Hora): "
            f"<b>R$ {valor_periodo:,.2f}</b>", style_normal))

    # ------------------------------------------------------ assinaturas
    els.append(Spacer(1, 40))
    assin_data = [
        ["________________________________________", "________________________________________"],
        ["DBR Energies S.A.", dados.get("contratada", "")]
    ]
    ta = Table(assin_data, colWidths=[300, 300])
    ta.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    els.append(ta)

    doc.build(els)
    return buf.getvalue()


# ------------------------------------------------------------------ horas
def _norm(txt):
    """Normaliza texto de cabecalho: sem acento, maiusculo, sem espacos."""
    s = "".join(ch for ch in sem_acento(txt).upper() if ch.isalnum())
    return s


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
            elif rot in ("USUARIO", "RESPONSAVEL", "USUARIOS", "RESPONSAVEIS") \
                    and "usuario" not in mapa:
                mapa["usuario"] = c
            elif rot == "PROJETO" and "projeto" not in mapa:
                mapa["projeto"] = c
            elif rot in COLUNAS_ITEM and "item" not in mapa:
                mapa["item"] = c
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
        linhas : lista de (usuario, projeto, item, horas, aprovado)
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
            up = sem_acento(t).upper()
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
        item = cel("item")
        item = str(item).strip() if item else ""
        aprov = True
        if "aprovacao" in mapa:
            v = _norm(cel("aprovacao"))
            aprov = v in ("SIM", "S", "APROVADO", "APROVADA")
        linhas.append((str(usu).strip(), proj, item, float(h), aprov))

    if not projeto_padrao and not any(p for _, p, _, _, _ in linhas):
        raise ValueError(f"PROJETO não encontrado em {os.path.basename(path)}")

    return {"projeto_padrao": projeto_padrao, "data_ini": data_ini, "data_fim": data_fim,
            "linhas": linhas}


# ------------------------------------------------------------------ passo 2
def consolidar_por_projeto_item(linhas, somente_aprovados=True):
    """Passo 2 da regra: agrupa e soma as horas por (Projeto + Atividade).

    O agrupamento ignora maiusculas, acentos e espacos extras, de modo que a
    mesma atividade apontada em dias diferentes vire uma unica linha no BM.
    Mantem o texto original da primeira ocorrencia para exibicao.

    Retorna lista de dicts: {projeto, item, horas, linhas}
    """
    acc = {}
    for usuario, projeto, item, horas, aprovado in linhas:
        if somente_aprovados and not aprovado:
            continue
        k = (chave_texto(projeto), chave_texto(item))
        reg = acc.get(k)
        if reg is None:
            reg = {"projeto": projeto, "item": item, "horas": 0.0, "linhas": 0,
                   "usuarios": []}
            acc[k] = reg
        reg["horas"] += float(horas)
        reg["linhas"] += 1
        u = str(usuario or "").strip()
        if u and u not in reg["usuarios"]:
            reg["usuarios"].append(u)
    saida = sorted(acc.values(),
                   key=lambda r: (chave_texto(r["projeto"]), chave_texto(r["item"])))
    return saida


def total_por_usuario(linhas, somente_aprovados=True):
    """Soma total de horas de cada usuario (passo 3 da regra).

    Retorna {usuario: horas}.
    """
    acc = {}
    for usuario, _projeto, _item, horas, aprovado in linhas:
        if somente_aprovados and not aprovado:
            continue
        u = str(usuario or "").strip()
        acc[u] = acc.get(u, 0.0) + float(horas)
    return acc
