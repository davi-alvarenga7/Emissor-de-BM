# -*- coding: utf-8 -*-
"""Emissor de Boletim de Medição — sistema desktop em Python (Tkinter + SQLite).
Especificação: ESPECIFICACAO_BM.md
Execução: pip install -r requirements.txt && python app.py
Banco: bm_system.db criado automaticamente na primeira execução.
"""
import io
import os
import re
import sqlite3
import hashlib
import binascii
from datetime import date, datetime, timedelta

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    import bcrypt
    _HAS_BCRYPT = True
except Exception:
    _HAS_BCRYPT = False

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

import sys
DB_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "bm_system.db")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
def recurso(nome):
    base = getattr(sys, "_MEIPASS", BASE_DIR)
    return os.path.join(base, nome)
LOGO_PATH = recurso("logo.png")
CONTRATANTE = "DBR ENERGIES S/A"
AZUL = "#0B5ED7"
AZUL_ESCURO = "#0849ad"

def logo_tk(largura=220):
    """Carrega logo.png redimensionado para Tkinter. Retorna None se falhar."""
    try:
        import tkinter as _tk
        from PIL import Image as _PI, ImageTk as _ITK
        im = _PI.open(LOGO_PATH).convert("RGBA")
        h = max(1, int(im.height * largura / im.width))
        im = im.resize((largura, h), _PI.LANCZOS)
        # fundo branco (logo tem transparência)
        bg = _PI.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        return _ITK.PhotoImage(bg.convert("RGB"))
    except Exception:
        return None

# ---------------------------------------------------------------- helpers
def hoje_iso():
    return date.today().isoformat()

def parse_data_flex(v):
    """Aceita datetime/date, serial excel, 'dd/mm/yyyy', 'yyyy-mm-dd'. Retorna date ou None."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)):
        try:  # serial excel
            base = date(1899, 12, 30)
            return base + timedelta(days=int(v))
        except Exception:
            return None
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s.split()[0], fmt).date()
        except Exception:
            pass
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", s)
    if m:
        try:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
            return date(y, mo, d)
        except Exception:
            return None
    return None

def fmt_br(d):
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d)
        except Exception:
            return d
    return d.strftime("%d/%m/%Y") if d else ""

def parse_num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("R$", "").replace(" ", "")
    # 84.000,00 -> 84000 / 84000.00 -> 84000
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def so_digitos(s):
    return re.sub(r"\D", "", str(s or ""))

def valida_cnpj(cnpj):
    return len(so_digitos(cnpj)) == 14

def valida_email(e):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(e or "").strip()))

def hash_senha(senha: str) -> str:
    if _HAS_BCRYPT:
        return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
    salt = binascii.hexlify(os.urandom(16)).decode()
    h = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), 200_000)
    return f"pbkdf2${salt}${binascii.hexlify(h).decode()}"

def confere_senha(senha: str, guardado: str) -> bool:
    try:
        if guardado.startswith("pbkdf2$"):
            _, salt, hexh = guardado.split("$")
            h = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), 200_000)
            return binascii.hexlify(h).decode() == hexh
        if _HAS_BCRYPT:
            return bcrypt.checkpw(senha.encode(), guardado.encode())
    except Exception:
        return False
    return False

# ---------------------------------------------------------------- banco
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome_completo TEXT NOT NULL,
  login TEXT NOT NULL UNIQUE COLLATE NOCASE,
  email TEXT NOT NULL,
  senha_hash TEXT NOT NULL,
  is_admin INTEGER NOT NULL DEFAULT 0,
  criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS companies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL,
  cnpj TEXT NOT NULL UNIQUE,
  responsavel TEXT NOT NULL,
  email_contato TEXT NOT NULL,
  usuario_eclic TEXT NOT NULL UNIQUE COLLATE NOCASE,
  po_codigo TEXT NOT NULL UNIQUE,
  po_inicio TEXT NOT NULL,
  po_fim TEXT NOT NULL,
  po_valor_total REAL NOT NULL CHECK (po_valor_total >= 0),
  po_objeto TEXT NOT NULL,
  valor_hora REAL NOT NULL CHECK (valor_hora >= 0),
  criado_em TEXT NOT NULL DEFAULT (datetime('now')),
  atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS bms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  rm_numero TEXT NOT NULL,
  periodo_ini TEXT NOT NULL,
  periodo_fim TEXT NOT NULL,
  emissao TEXT NOT NULL,
  revisao INTEGER NOT NULL DEFAULT 0,
  contratante TEXT NOT NULL DEFAULT 'DBR ENERGIES S/A',
  snap_nome TEXT NOT NULL, snap_cnpj TEXT NOT NULL, snap_po TEXT NOT NULL,
  snap_po_inicio TEXT NOT NULL, snap_po_fim TEXT NOT NULL,
  snap_valor_total REAL NOT NULL, snap_objeto TEXT NOT NULL, snap_valor_hora REAL NOT NULL,
  total_anterior REAL, total_periodo REAL, total_acumulado REAL, saldo REAL,
  xlsx_blob BLOB NOT NULL, pdf_blob BLOB NOT NULL,
  origem TEXT NOT NULL CHECK (origem IN ('LOTE','MANUAL','BASE')),
  criado_em TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(company_id, rm_numero, revisao)
);
CREATE INDEX IF NOT EXISTS idx_bms_company ON bms(company_id, criado_em DESC);
CREATE TABLE IF NOT EXISTS bm_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bm_id INTEGER NOT NULL REFERENCES bms(id) ON DELETE CASCADE,
  item_seq INTEGER NOT NULL,
  projeto TEXT NOT NULL,
  descricao TEXT NOT NULL DEFAULT 'Serviços de Consultoria em TELECOM',
  valor_hora REAL NOT NULL,
  horas_anterior REAL,
  horas_periodo REAL NOT NULL,
  horas_acumulada REAL,
  total_anterior REAL, total_periodo REAL, total_acumulado REAL,
  UNIQUE(bm_id, projeto)
);
"""

def conectar():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con

def proximo_rm(con, company_id, emissao_iso):
    """Sequencial por empresa: BM-YYYY-NNN. Retorna '' se empresa nunca teve BM (regra: deixar em branco)."""
    ano = (emissao_iso or hoje_iso())[:4]
    rows = con.execute("SELECT rm_numero FROM bms WHERE company_id=? ORDER BY id DESC", (company_id,)).fetchall()
    if not rows:
        return ""  # sem base/histórico -> em branco
    # pega maior NNN do ano
    mx = 0
    for r in rows:
        m = re.search(r"(\d{3,})", r["rm_numero"] or "")
        if m:
            try:
                mx = max(mx, int(m.group(1)))
            except Exception:
                pass
    return f"BM-{ano}-{mx + 1:03d}"

def ultimo_mapa_itens(con, company_id):
    """projeto -> (horas_acumulada, total_acumulado) do último BM."""
    row = con.execute("SELECT id FROM bms WHERE company_id=? ORDER BY id DESC LIMIT 1", (company_id,)).fetchone()
    if not row:
        return {}
    itens = con.execute("SELECT projeto, horas_acumulada, total_acumulado FROM bm_items WHERE bm_id=?", (row["id"],)).fetchall()
    return {i["projeto"]: (i["horas_acumulada"], i["total_acumulado"]) for i in itens}

# ---------------------------------------------------------------- excel BM
def construir_xlsx_bm(dados):
    """dados: dict com chaves rm, periodo_txt, emissao, revisao, po, po_ini, po_fim,
    valor_total, objeto, contratada, cnpj, itens[(projeto, vh, h_ant, h_per)], totais."""
    wb = Workbook()
    ws = wb.active
    ws.title = (dados.get("rm") or "BM")[:31]
    ws.sheet_properties.pageSetUpPr = None
    larg = {"B": 8, "C": 24, "D": 32, "E": 14, "F": 14, "G": 14, "H": 14, "I": 15, "J": 15, "K": 15, "L": 15}
    for col, w in larg.items():
        ws.column_dimensions[col].width = w
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    bold = Font(bold=True)
    fill_h = PatternFill("solid", fgColor="D9E2F3")
    thin = Border(*[Side(style="thin")] * 4)

    ws.merge_cells("D1:G3")
    ws["D1"] = "BOLETIM DE MEDIÇÃO"
    ws["D1"].font = Font(bold=True, size=14)
    ws["D1"].alignment = center
    ws["H1"] = "RM N.°:"
    ws["I1"] = dados.get("rm") or ""
    try:
        if os.path.exists(LOGO_PATH):
            from openpyxl.drawing.image import Image as XLImage
            img = XLImage(LOGO_PATH)
            img.width, img.height = 170, 75
            ws.add_image(img, "L1")
    except Exception:
        ws["L1"] = "Logo da empresa prestadora de serviço"
    ws["H2"] = "Período:"
    ws["I2"] = dados.get("periodo_txt") or ""
    ws["H3"] = "Emissão:"
    ws["I3"] = dados.get("emissao_txt") or ""
    ws["K6"] = f"Revisão: {dados.get('revisao', 0)}"
    ws["B7"] = "Contrato: "
    ws["E7"] = f"PO: {dados.get('po','')}"
    ws["G7"] = f"Início PO: {dados.get('po_ini_txt','')}"
    ws["B8"] = f"Objeto: {dados.get('objeto','')}"
    ws["E8"] = "Valor Estimado PO:"
    ws["F8"] = dados.get("valor_total", 0)
    ws["F8"].number_format = 'R$ #,##0.00'
    ws["G8"] = f"Fim PO: {dados.get('po_fim_txt','')}"
    ws["B9"] = f"Contratante: {CONTRATANTE}"
    ws["E9"] = f"Contratada: {dados.get('contratada','')}"
    ws["G9"] = "CNPJ Contratada: "
    ws["H9"] = dados.get("cnpj", "")
    ws["I9"] = " TOTAL (R$)"

    head = ["Item", "Projeto", "Descrição Atividades", "Valor Hora Unitário", "Horas Período anterior",
            "Horas No Período", "Horas Acumuladas", "Total Acum. Período anterior", "Total no Período",
            "Acumulado", "Saldo"]
    for j, h in enumerate(head):
        c = ws.cell(row=10, column=2 + j, value=h)
        c.font = bold
        c.fill = fill_h
        c.alignment = center
        c.border = thin
    r = 12
    tot_ant = tot_per = tot_acu = 0.0
    for i, (proj, vh, h_ant, h_per) in enumerate(dados["itens"], start=1):
        h_ant_n = h_ant if h_ant is not None else None
        h_acu = (h_ant + h_per) if h_ant is not None else h_per
        t_ant = (h_ant * vh) if h_ant is not None else None
        t_per = h_per * vh
        t_acu = ((t_ant or 0) + t_per)
        vals = [i, proj, "Serviços de Consultoria em TELECOM", vh,
                h_ant_n, h_per, h_acu, t_ant, t_per, t_acu, ("", 0)[0]]
        # saldo só na 1ª linha espelha regra do template; demais vazio
        for j, v in enumerate(vals):
            c = ws.cell(row=r, column=2 + j, value=(0 if v == "" else v) if v == "" and j == 10 else v)
            c.border = thin
            c.alignment = center if j != 2 else left
            if j == 3:
                c.number_format = 'R$ #,##0.00'
            if j in (7, 8, 9):
                c.number_format = 'R$ #,##0.00'
        if t_ant:
            tot_ant += t_ant
        tot_per += t_per
        tot_acu += t_acu
        r += 1
    ws.cell(row=21, column=2, value="TOTAL CONTRATO:").font = bold
    ws.cell(row=21, column=5, value=dados.get("valor_total", 0)).number_format = 'R$ #,##0.00'
    for j, v in enumerate([None, None, None, tot_ant, tot_per, tot_acu], start=6):
        c = ws.cell(row=21, column=j, value=v or 0)
        c.font = bold
        c.border = thin
        if j >= 9:
            c.number_format = 'R$ #,##0.00'
    ws.cell(row=23, column=9, value=tot_ant).number_format = 'R$ #,##0.00'
    ws.cell(row=23, column=10, value=tot_per).number_format = 'R$ #,##0.00'
    ws.cell(row=23, column=11, value=tot_acu).number_format = 'R$ #,##0.00'
    ws.cell(row=23, column=12, value=(dados.get("valor_total", 0) - tot_acu)).number_format = 'R$ #,##0.00'
    ws["D30"] = "Gerente DBR Energies S.A."
    ws["F30"] = dados.get("contratada", "")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), tot_ant, tot_per, tot_acu, (dados.get("valor_total", 0) - tot_acu)

def construir_pdf_bm(dados):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=20, bottomMargin=20)
    st = getSampleStyleSheet()
    els = []
    try:
        if os.path.exists(LOGO_PATH):
            from reportlab.platypus import Image as RLImage
            els.append(RLImage(LOGO_PATH, width=170, height=75))
    except Exception:
        pass
    els += [Paragraph(f"BOLETIM DE MEDIÇÃO — {dados.get('rm') or '(sem RM)'}", st["Heading1"]),
           Paragraph(f"{dados.get('contratada','')} | {dados.get('cnpj','')} | PO {dados.get('po','')} | "
                     f"Período {dados.get('periodo_txt','')} | Emissão {dados.get('emissao_txt','')} | Revisão {dados.get('revisao',0)}", st["Normal"]),
           Spacer(1, 8)]
    tab = [["Item", "Projeto", "Vlr Hora", "H Ant", "H Per", "H Acu", "Tot Ant", "Tot Per", "Acumulado"]]
    for i, (proj, vh, h_ant, h_per) in enumerate(dados["itens"], start=1):
        h_acu = (h_ant + h_per) if h_ant is not None else h_per
        tab.append([i, proj[:60], f"R$ {vh:.2f}", h_ant if h_ant is not None else "-",
                    h_per, h_acu,
                    f"R$ {(h_ant*vh) if h_ant is not None else 0:.2f}",
                    f"R$ {h_per*vh:.2f}", f"R$ {((h_ant or 0)+h_per)*vh:.2f}"])
    t = Table(tab, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5ED7")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                           ("FONTSIZE", (0, 0), (-1, -1), 7)]))
    els.append(t)
    doc.build(els)
    return buf.getvalue()

# ---------------------------------------------------------------- horas
def parse_data_us(v):
    """Planilhas 'horas por item' usam m/d/yyyy (ex. 9/30/2026). Tenta US primeiro."""
    if isinstance(v, str):
        for fmt in ("%m/%d/%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(v.strip().split()[0], fmt).date()
            except Exception:
                pass
    return parse_data_flex(v)

def ler_horas_arquivo(path):
    """Retorna (projeto_texto_cheio, data_ini, data_fim, [(usuario, horas)])."""
    wb = load_workbook(path, data_only=True)
    ws = wb.active
    proj = ini = fim = None
    for row in ws.iter_rows(values_only=True):
        txt = " ".join(str(c or "") for c in row)
        if "PROJETO" in txt.upper():
            proj = txt.split(":", 1)[1].strip() if ":" in txt else txt.strip()
        if "DATA INICIAL" in txt.upper():
            m1 = re.search(r"INICIAL:\s*([0-9/\-]+)", txt, re.I)
            m2 = re.search(r"FINAL:\s*([0-9/\-]+)", txt, re.I)
            if m1:
                ini = parse_data_us(m1.group(1))
            if m2:
                fim = parse_data_us(m2.group(1))
    linhas = []
    header_ok = False
    for row in ws.iter_rows(values_only=True):
        vals = [c for c in row]
        if not header_ok:
            up = [str(c or "").upper() for c in vals]
            if "USUÁRIO" in up or "USUARIO" in up:
                header_ok = True
            continue
        if len(vals) < 5:
            continue
        usu, h = vals[3], vals[4]
        if not usu or h in (None, ""):
            continue
        try:
            linhas.append((str(usu).strip(), float(h)))
        except Exception:
            pass
    if not proj:
        raise ValueError(f"Projeto não encontrado em {os.path.basename(path)}")
    return proj, ini, fim, linhas

# ---------------------------------------------------------------- app
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Emissor de BM — DBR Energies")
        self.geometry("1100x700")
        self.con = conectar()
        self.usuario = None
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Azul.TButton", background=AZUL, foreground="white", font=("Segoe UI", 11, "bold"))
        style.map("Azul.TButton", background=[("active", AZUL_ESCURO)])
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.telas = {}
        for cls in (TelaLogin, TelaCadastroUser, TelaHome, TelaCadEmpresa, TelaEmpresas,
                    TelaEditar, TelaManual, TelaLote, TelaBoletins):
            f = cls(self.container, self)
            self.telas[cls.__name__] = f
            f.grid(row=0, column=0, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        self.ir("TelaLogin" if self.tem_usuario() else "TelaCadastroUser")

    def tem_usuario(self):
        return self.con.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] > 0

    def ir(self, nome):
        if nome == "TelaHome" and not self.usuario:
            nome = "TelaLogin"
        t = self.telas[nome]
        if hasattr(t, "ao_mostrar"):
            t.ao_mostrar()
        t.tkraise()

    def cabec(self, parent, titulo, voltar="TelaHome"):
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=12, pady=8)
        ttk.Button(top, text="← Voltar", command=lambda: self.ir(voltar)).pack(side="left")
        ttk.Label(top, text=titulo, font=("Segoe UI", 15, "bold"), foreground=AZUL).pack(side="left", padx=12)
        lg = logo_tk(130)
        if lg:
            lab = ttk.Label(top, image=lg)
            lab.image = lg  # evita garbage collection
            lab.pack(side="right")

class Base(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
    def campo(self, parent, rotulo, row, valor=""):
        ttk.Label(parent, text=rotulo).grid(row=row, column=0, sticky="w", pady=3)
        e = ttk.Entry(parent, width=55)
        e.grid(row=row, column=1, sticky="ew", pady=3, padx=6)
        e.insert(0, valor)
        return e

class TelaLogin(Base):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        lg = logo_tk(260)
        if lg:
            lab = ttk.Label(self, image=lg)
            lab.image = lg
            lab.pack(pady=(14, 0))
        ttk.Label(self, text="Emissor de BM", font=("Segoe UI", 22, "bold"), foreground=AZUL).pack(pady=10)
        box = ttk.Frame(self)
        box.pack()
        self.login = self.campo(box, "Login", 0)
        self.senha = self.campo(box, "Senha", 1)
        self.senha.config(show="*")
        ttk.Button(box, text="Entrar", style="Azul.TButton", command=self.entrar).grid(row=2, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Button(box, text="Cadastrar-se", command=lambda: app.ir("TelaCadastroUser")).grid(row=3, column=0, columnspan=2, sticky="ew")
        ttk.Button(box, text="Esqueci a senha", command=self.esqueci).grid(row=4, column=0, columnspan=2, sticky="ew", pady=4)
    def entrar(self):
        r = self.app.con.execute("SELECT * FROM users WHERE login=? COLLATE NOCASE", (self.login.get().strip(),)).fetchone()
        if not r or not confere_senha(self.senha.get(), r["senha_hash"]):
            return messagebox.showerror("Erro", "Login ou senha inválidos")
        self.app.usuario = dict(r)
        self.app.ir("TelaHome")
    def esqueci(self):
        messagebox.showinfo("Recuperação", "Procure o administrador (primeiro usuário cadastrado) para resetar sua senha.")

class TelaCadastroUser(Base):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        ttk.Label(self, text="Cadastro de usuário", font=("Segoe UI", 16, "bold"), foreground=AZUL).pack(pady=12)
        box = ttk.Frame(self)
        box.pack()
        self.nome = self.campo(box, "Nome Completo*", 0)
        self.login = self.campo(box, "Login*", 1)
        self.email = self.campo(box, "E-mail*", 2)
        self.s1 = self.campo(box, "Senha* (≥6)", 3)
        self.s1.config(show="*")
        self.s2 = self.campo(box, "Confirmar Senha*", 4)
        self.s2.config(show="*")
        ttk.Button(box, text="Salvar e entrar", style="Azul.TButton", command=self.salvar).grid(row=5, column=0, columnspan=2, sticky="ew", pady=8)
    def salvar(self):
        nome, lg, em, s1, s2 = (self.nome.get().strip(), self.login.get().strip(), self.email.get().strip(),
                                self.s1.get(), self.s2.get())
        if not all([nome, lg, em, s1, s2]):
            return messagebox.showerror("Erro", "Preencha todos os campos")
        if not valida_email(em):
            return messagebox.showerror("Erro", "E-mail inválido")
        if len(s1) < 6:
            return messagebox.showerror("Erro", "Senha mínima de 6 caracteres")
        if s1 != s2:
            return messagebox.showerror("Erro", "Senhas não conferem")
        if self.app.con.execute("SELECT 1 FROM users WHERE login=? COLLATE NOCASE", (lg,)).fetchone():
            return messagebox.showerror("Erro", "Login já existe")
        admin = 0 if self.app.tem_usuario() else 1
        cur = self.app.con.execute("INSERT INTO users (nome_completo,login,email,senha_hash,is_admin) VALUES (?,?,?,?,?)",
                                   (nome, lg, em, hash_senha(s1), admin))
        self.app.con.commit()
        self.app.usuario = dict(self.app.con.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone())
        messagebox.showinfo("OK", "Usuário cadastrado" + (" (admin)" if admin else ""))
        self.app.ir("TelaHome")

class TelaHome(Base):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        topo = ttk.Frame(self)
        topo.pack(fill="x", padx=16, pady=(14, 0))
        lg = logo_tk(150)
        if lg:
            lab = ttk.Label(topo, image=lg)
            lab.image = lg
            lab.pack(side="left", anchor="nw")
        ttk.Label(topo, text="E-BM", font=("Segoe UI", 22, "bold"), foreground=AZUL).pack(side="left", padx=16)
        centro = ttk.Frame(self)
        centro.pack(fill="both", expand=True)
        box = ttk.Frame(centro)
        box.place(relx=0.5, rely=0.5, anchor="center")
        for txt, dst in [("Cadastro de Nova Empresa", "TelaCadEmpresa"),
                         ("Empresas Cadastradas", "TelaEmpresas"),
                         ("Emissão de Boletins em Lote", "TelaLote")]:
            ttk.Button(box, text=txt, style="Azul.TButton", width=40,
                       command=lambda d=dst: app.ir(d)).pack(pady=10)

CAMPOS_EMPRESA = [("Razão Social*", "nome"), ("CNPJ*", "cnpj"), ("Código PO*", "po_codigo"),
                  ("Início PO* (dd/mm/aaaa)", "po_inicio"), ("Fim PO* (dd/mm/aaaa)", "po_fim"),
                  ("Valor Total PO*", "po_valor_total"), ("Objeto*", "po_objeto"),
                  ("E-mail contato*", "email_contato"), ("Valor Hora*", "valor_hora"),
                  ("Responsável*", "responsavel"), ("Usuário E-clic*", "usuario_eclic")]

class TelaCadEmpresa(Base):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.ents = {}
    def ao_mostrar(self):
        for w in self.winfo_children():
            w.destroy()
        self.app.cabec(self, "Cadastro de Nova Empresa", "TelaHome")
        box = ttk.Frame(self)
        box.pack(padx=12, fill="x")
        self.ents = {}
        for i, (rot, key) in enumerate(CAMPOS_EMPRESA):
            self.ents[key] = self.campo(box, rot, i)
        row = ttk.Frame(self)
        row.pack(pady=10)
        ttk.Button(row, text="Salvar", style="Azul.TButton", command=self.salvar).pack(side="left", padx=6)
        ttk.Button(row, text="Cadastro em lote (Excel)", command=self.lote).pack(side="left", padx=6)
    def ler_tela(self):
        d = {k: e.get().strip() for k, e in self.ents.items()}
        return d
    def validar(self, d, con, ignorar_id=None):
        for k in ["nome", "cnpj", "po_codigo", "po_inicio", "po_fim", "po_valor_total",
                  "po_objeto", "email_contato", "valor_hora", "responsavel", "usuario_eclic"]:
            if not d.get(k):
                return "Preencha todos os campos obrigatórios"
        if not valida_cnpj(d["cnpj"]):
            return "CNPJ inválido (14 dígitos)"
        if not valida_email(d["email_contato"]):
            return "E-mail de contato inválido"
        di, df = parse_data_flex(d["po_inicio"]), parse_data_flex(d["po_fim"])
        if not di or not df:
            return "Datas de PO inválidas (use dd/mm/aaaa)"
        if df < di:
            return "Fim PO deve ser >= Início PO"
        vt, vh = parse_num(d["po_valor_total"]), parse_num(d["valor_hora"])
        if vt is None or vt < 0 or vh is None or vh < 0:
            return "Valores devem ser numéricos >= 0"
        q = "SELECT id FROM companies WHERE (cnpj=? OR po_codigo=? OR usuario_eclic=? COLLATE NOCASE)"
        args = [so_digitos(d["cnpj"]), d["po_codigo"].strip(), d["usuario_eclic"].strip()]
        for r in con.execute(q, args):
            if ignorar_id is None or r["id"] != ignorar_id:
                return "Duplicado: CNPJ, PO ou Usuário E-clic já cadastrado"
        d["_di"], d["_df"], d["_vt"], d["_vh"] = di, df, vt, vh
        return None
    def salvar(self):
        d = self.ler_tela()
        erro = self.validar(d, self.app.con)
        if erro:
            return messagebox.showerror("Erro", erro)
        self.app.con.execute(
            "INSERT INTO companies (nome,cnpj,responsavel,email_contato,usuario_eclic,po_codigo,po_inicio,po_fim,po_valor_total,po_objeto,valor_hora)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (d["nome"], so_digitos(d["cnpj"]), d["responsavel"], d["email_contato"], d["usuario_eclic"].strip(),
             d["po_codigo"].strip(), d["_di"].isoformat(), d["_df"].isoformat(), d["_vt"], d["po_objeto"], d["_vh"]))
        self.app.con.commit()
        messagebox.showinfo("OK", "Empresa cadastrada")
        self.app.ir("TelaEmpresas")
    def lote(self):
        paths = filedialog.askopenfilenames(title="Planilha de empresas", filetypes=[("Excel", "*.xlsx")])
        if not paths:
            return
        ok = pul = 0
        motivos = []
        for p in paths:
            try:
                wb = load_workbook(p, data_only=True)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
            except Exception as e:
                motivos.append(f"{os.path.basename(p)}: {e}")
                continue
            vistos = set()
            for i, r in enumerate(rows[1:], start=2):
                if not r or all(c in (None, "") for c in r):
                    pul += 1
                    continue
                try:
                    vals = list(r) + [""] * 11
                    d = dict(zip(["nome", "cnpj", "po_codigo", "po_inicio", "po_fim", "po_valor_total",
                                  "po_objeto", "email_contato", "valor_hora", "responsavel", "usuario_eclic"],
                                 [str(c or "").strip() for c in vals[:11]]))
                    if any(not d[k] for k in d):
                        pul += 1
                        motivos.append(f"linha {i}: célula em branco")
                        continue
                    chave = (so_digitos(d["cnpj"]), d["po_codigo"].upper())
                    if chave in vistos:
                        pul += 1
                        motivos.append(f"linha {i}: duplicada no arquivo")
                        continue
                    vistos.add(chave)
                    if isinstance(r[3], (datetime, date)):
                        d["po_inicio"] = r[3].strftime("%d/%m/%Y")
                    if isinstance(r[4], (datetime, date)):
                        d["po_fim"] = r[4].strftime("%d/%m/%Y")
                    erro = self.validar(d, self.app.con)
                    if erro:
                        pul += 1
                        motivos.append(f"linha {i}: {erro}")
                        continue
                    self.app.con.execute(
                        "INSERT INTO companies (nome,cnpj,responsavel,email_contato,usuario_eclic,po_codigo,po_inicio,po_fim,po_valor_total,po_objeto,valor_hora)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (d["nome"], so_digitos(d["cnpj"]), d["responsavel"], d["email_contato"], d["usuario_eclic"],
                         d["po_codigo"], d["_di"].isoformat(), d["_df"].isoformat(), d["_vt"], d["po_objeto"], d["_vh"]))
                    ok += 1
                except Exception as e:
                    pul += 1
                    motivos.append(f"linha {i}: {e}")
            self.app.con.commit()
        messagebox.showinfo("Lote", f"{ok} cadastradas, {pul} puladas.\n" + "\n".join(motivos[:20]))

class TelaEmpresas(Base):
    def __init__(self, parent, app):
        super().__init__(parent, app)
    def ao_mostrar(self):
        for w in self.winfo_children():
            w.destroy()
        self.app.cabec(self, "Empresas Cadastradas", "TelaHome")
        busca = ttk.Entry(self, width=60)
        busca.pack(padx=12, pady=4, anchor="w")
        busca.insert(0, "Buscar por responsável, razão social ou CNPJ...")
        cols = ("responsavel", "nome", "cnpj")
        tv = ttk.Treeview(self, columns=cols, show="headings", height=15)
        for c, t in zip(cols, ["Responsável", "Razão Social", "CNPJ"]):
            tv.heading(c, text=t)
            tv.column(c, width=250)
        tv.pack(fill="both", expand=True, padx=12, pady=6)
        def recarrega(*a):
            q = busca.get().strip()
            like = f"%{q}%" if q and "Buscar" not in q else "%"
            tv.delete(*tv.get_children())
            for r in self.app.con.execute(
                    "SELECT * FROM companies WHERE responsavel LIKE ? OR nome LIKE ? OR cnpj LIKE ? ORDER BY nome",
                    (like, like, like)):
                tv.insert("", "end", iid=r["id"], values=(r["responsavel"], r["nome"], r["cnpj"]))
        busca.bind("<KeyRelease>", recarrega)
        recarrega()
        self.tv = tv
        row = ttk.Frame(self)
        row.pack(pady=8)
        ttk.Button(row, text="Editar", command=self.editar).pack(side="left", padx=4)
        ttk.Button(row, text="Emitir Boletim (manual)", style="Azul.TButton", command=self.manual).pack(side="left", padx=4)
        ttk.Button(row, text="Boletins Emitidos", command=self.boletins).pack(side="left", padx=4)
        ttk.Button(row, text="Importar BM base", command=self.base).pack(side="left", padx=4)
    def sel(self):
        s = self.tv.selection()
        if not s:
            messagebox.showwarning("Aviso", "Selecione uma empresa")
            return None
        return int(s[0])
    def editar(self):
        i = self.sel()
        if i:
            self.app.telas["TelaEditar"].cid = i
            self.app.ir("TelaEditar")
    def manual(self):
        i = self.sel()
        if i:
            self.app.telas["TelaManual"].cid = i
            self.app.ir("TelaManual")
    def boletins(self):
        i = self.sel()
        if i:
            self.app.telas["TelaBoletins"].cid = i
            self.app.ir("TelaBoletins")
    def base(self):
        i = self.sel()
        if not i:
            return
        p = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if not p:
            return
        try:
            wb = load_workbook(p, data_only=True)
            ws = wb.active
            cnpj = so_digitos(ws["H9"].value or "")
            emp = self.app.con.execute("SELECT * FROM companies WHERE id=?", (i,)).fetchone()
            if cnpj and cnpj != emp["cnpj"]:
                return messagebox.showerror("Erro", f"CNPJ do arquivo ({cnpj}) difere da empresa ({emp['cnpj']})")
            rm = str(ws["I1"].value or "").strip()
            per = str(ws["I2"].value or "")
            m = re.findall(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", per)
            pi = parse_data_flex(m[0]).isoformat() if len(m) > 0 else emp["po_inicio"]
            pf = parse_data_flex(m[1]).isoformat() if len(m) > 1 else emp["po_fim"]
            emi = parse_data_flex(ws["I3"].value)
            emi_iso = emi.isoformat() if emi else hoje_iso()
            rev = re.search(r"(\d+)", str(ws["K6"].value or "0"))
            rev = int(rev.group(1)) if rev else 0
            itens = []
            for r in range(12, 22):
                proj = ws.cell(row=r, column=3).value
                if not proj:
                    continue
                vh = parse_num(ws.cell(row=r, column=5).value) or 0
                ha = parse_num(ws.cell(row=r, column=6).value)
                hp = parse_num(ws.cell(row=r, column=7).value) or 0
                itens.append((str(proj), vh, ha, hp))
            self.salvar_bm(emp, pi, pf, emi_iso, rm or "", rev, itens, "BASE", open(p, "rb").read())
            messagebox.showinfo("OK", "BM base importado")
        except Exception as e:
            messagebox.showerror("Erro", str(e))
    def salvar_bm(self, emp, pi, pf, emi_iso, rm, rev, itens, origem, xlsx_bytes=None):
        dados = {"rm": rm, "periodo_txt": f"{fmt_br(pi)} até {fmt_br(pf)}",
                 "emissao_txt": fmt_br(emi_iso), "revisao": rev, "po": emp["po_codigo"],
                 "po_ini_txt": fmt_br(emp["po_inicio"]), "po_fim_txt": fmt_br(emp["po_fim"]),
                 "valor_total": emp["po_valor_total"], "objeto": emp["po_objeto"],
                 "contratada": emp["nome"], "cnpj": emp["cnpj"], "itens": itens}
        if xlsx_bytes is None:
            xlsx_bytes, ta, tp, tac, saldo = construir_xlsx_bm(dados)
        else:
            _, ta, tp, tac, saldo = construir_xlsx_bm(dados)
            # mantém bytes originais da base? não — padroniza pelo template:
            xlsx_bytes = _
        pdf_bytes = construir_pdf_bm(dados)
        # revisão: se mesmo rm+período já existe, incrementa
        ex = self.app.con.execute(
            "SELECT MAX(revisao) m FROM bms WHERE company_id=? AND rm_numero=? AND periodo_ini=? AND periodo_fim=?",
            (emp["id"], rm, pi, pf)).fetchone()["m"]
        if ex is not None:
            rev = ex + 1
            dados["revisao"] = rev
            xlsx_bytes, ta, tp, tac, saldo = construir_xlsx_bm(dados)
            pdf_bytes = construir_pdf_bm(dados)
        cur = self.app.con.execute(
            "INSERT INTO bms (company_id,rm_numero,periodo_ini,periodo_fim,emissao,revisao,snap_nome,snap_cnpj,snap_po,"
            "snap_po_inicio,snap_po_fim,snap_valor_total,snap_objeto,snap_valor_hora,total_anterior,total_periodo,total_acumulado,saldo,xlsx_blob,pdf_blob,origem)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (emp["id"], rm, pi, pf, emi_iso, rev, emp["nome"], emp["cnpj"], emp["po_codigo"],
             emp["po_inicio"], emp["po_fim"], emp["po_valor_total"], emp["po_objeto"], emp["valor_hora"],
             ta, tp, tac, saldo, xlsx_bytes, pdf_bytes, origem))
        bid = cur.lastrowid
        for s, (proj, vh, ha, hp) in enumerate(itens, start=1):
            acu = (ha + hp) if ha is not None else hp
            self.app.con.execute(
                "INSERT INTO bm_items (bm_id,item_seq,projeto,valor_hora,horas_anterior,horas_periodo,horas_acumulada,total_anterior,total_periodo,total_acumulado)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (bid, s, proj, vh, ha, hp, acu, (ha*vh) if ha is not None else None, hp*vh, ((ha or 0)+hp)*vh))
        self.app.con.commit()
        return bid

class TelaEditar(Base):
    cid = None
    def ao_mostrar(self):
        for w in self.winfo_children():
            w.destroy()
        self.app.cabec(self, "Editar empresa", "TelaEmpresas")
        emp = self.app.con.execute("SELECT * FROM companies WHERE id=?", (self.cid,)).fetchone()
        box = ttk.Frame(self)
        box.pack(padx=12)
        self.ents = {}
        mapa = {"nome": emp["nome"], "cnpj": emp["cnpj"], "po_codigo": emp["po_codigo"],
                "po_inicio": fmt_br(emp["po_inicio"]), "po_fim": fmt_br(emp["po_fim"]),
                "po_valor_total": emp["po_valor_total"], "po_objeto": emp["po_objeto"],
                "email_contato": emp["email_contato"], "valor_hora": emp["valor_hora"],
                "responsavel": emp["responsavel"], "usuario_eclic": emp["usuario_eclic"]}
        for i, (rot, key) in enumerate(CAMPOS_EMPRESA):
            self.ents[key] = self.campo(box, rot, i, str(mapa[key]))
        row = ttk.Frame(self)
        row.pack(pady=10)
        ttk.Button(row, text="Salvar", style="Azul.TButton", command=self.salvar).pack(side="left", padx=6)
        ttk.Button(row, text="Voltar", command=lambda: self.app.ir("TelaEmpresas")).pack(side="left", padx=6)
    def salvar(self):
        d = {k: e.get().strip() for k, e in self.ents.items()}
        t = TelaCadEmpresa(self, self.app)
        erro = t.validar(d, self.app.con, ignorar_id=self.cid)
        if erro:
            return messagebox.showerror("Erro", erro)
        self.app.con.execute(
            "UPDATE companies SET nome=?,cnpj=?,responsavel=?,email_contato=?,usuario_eclic=?,po_codigo=?,po_inicio=?,po_fim=?,po_valor_total=?,po_objeto=?,valor_hora=?,atualizado_em=datetime('now') WHERE id=?",
            (d["nome"], so_digitos(d["cnpj"]), d["responsavel"], d["email_contato"], d["usuario_eclic"],
             d["po_codigo"], d["_di"].isoformat(), d["_df"].isoformat(), d["_vt"], d["po_objeto"], d["_vh"], self.cid))
        self.app.con.commit()
        messagebox.showinfo("OK", "Informações atualizadas")
        self.app.ir("TelaEmpresas")

class TelaManual(Base):
    cid = None
    def ao_mostrar(self):
        for w in self.winfo_children():
            w.destroy()
        emp = self.app.con.execute("SELECT * FROM companies WHERE id=?", (self.cid,)).fetchone()
        self.app.cabec(self, f"Emitir BM manual — {emp['nome']}", "TelaEmpresas")
        ttk.Label(self, text=f"PO {emp['po_codigo']} | Valor hora R$ {emp['valor_hora']:.2f} (travado)",
                  foreground=AZUL).pack()
        box = ttk.Frame(self)
        box.pack(padx=12, pady=6)
        self.pi = self.campo(box, "Período Inicial* dd/mm/aaaa", 0)
        self.pf = self.campo(box, "Período Final* dd/mm/aaaa", 1)
        ttk.Label(box, text="Projetos e horas:").grid(row=2, column=0, sticky="w", pady=6)
        self.linhas = ttk.Frame(box)
        self.linhas.grid(row=3, column=0, columnspan=2)
        self.rows = []
        for _ in range(3):
            self.add_linha()
        ttk.Button(box, text="+ Adicionar projeto", command=self.add_linha).grid(row=4, column=0, columnspan=2, pady=4)
        ttk.Button(self, text="Gerar Boletim", style="Azul.TButton", command=self.gerar).pack(pady=10)
    def add_linha(self):
        f = ttk.Frame(self.linhas)
        f.pack(fill="x", pady=2)
        p = ttk.Entry(f, width=50)
        p.pack(side="left", padx=2)
        p.insert(0, "PRJ-...")
        h = ttk.Entry(f, width=12)
        h.pack(side="left", padx=2)
        h.insert(0, "0")
        self.rows.append((p, h))
    def gerar(self):
        emp = self.app.con.execute("SELECT * FROM companies WHERE id=?", (self.cid,)).fetchone()
        pi, pf = parse_data_flex(self.pi.get()), parse_data_flex(self.pf.get())
        if not pi or not pf or pf < pi:
            return messagebox.showerror("Erro", "Período inválido")
        mapa = ultimo_mapa_itens(self.app.con, emp["id"])
        itens = []
        for p, h in self.rows:
            proj = p.get().strip()
            hp = parse_num(h.get())
            if not proj or proj == "PRJ-..." or hp is None:
                continue
            ant = mapa.get(proj, (None, None))[0]
            itens.append((proj, emp["valor_hora"], ant, hp))
        if not itens:
            return messagebox.showerror("Erro", "Informe ao menos 1 projeto com horas")
        emi = (pf + timedelta(days=1)).isoformat()
        rm = proximo_rm(self.app.con, emp["id"], emi)
        helper = self.app.telas["TelaEmpresas"]
        helper.salvar_bm(dict(emp), pi.isoformat(), pf.isoformat(), emi, rm, 0, itens, "MANUAL")
        messagebox.showinfo("OK", f"BM gerado ({rm or 'sem RM'})")
        self.app.telas["TelaBoletins"].cid = emp["id"]
        self.app.ir("TelaBoletins")

class TelaLote(Base):
    def ao_mostrar(self):
        for w in self.winfo_children():
            w.destroy()
        self.app.cabec(self, "Emissão de Boletins em Lote", "TelaHome")
        ttk.Label(self, text="Anexe N planilhas 'horas por item' (mesma data inicial/final).",
                  foreground=AZUL).pack(pady=6)
        ttk.Button(self, text="Selecionar arquivos...", style="Azul.TButton", command=self.proc).pack(pady=8)
        self.log = tk.Text(self, height=20)
        self.log.pack(fill="both", expand=True, padx=12, pady=8)
    def proc(self):
        paths = filedialog.askopenfilenames(filetypes=[("Excel", "*.xlsx")])
        if not paths:
            return
        try:
            agreg = {}  # (eclic_upper, projeto) -> horas
            datas = set()
            for p in paths:
                proj, ini, fim, linhas = ler_horas_arquivo(p)
                if ini and fim:
                    datas.add((ini.isoformat(), fim.isoformat()))
                for usu, h in linhas:
                    agreg[(usu.strip().upper(), proj)] = agreg.get((usu.strip().upper(), proj), 0) + h
            if len(datas) > 1:
                return messagebox.showerror("Erro", f"Datas divergentes no lote: {datas}. Todos os arquivos devem ter a mesma data.")
            if not datas:
                return messagebox.showerror("Erro", "Data inicial/final não encontrada nas planilhas")
            pi, pf = list(datas)[0]
            emps = {r["usuario_eclic"].strip().upper(): dict(r)
                    for r in self.app.con.execute("SELECT * FROM companies")}
            por_emp = {}
            ignorados = 0
            for (eclic, proj), h in agreg.items():
                if eclic not in emps:
                    ignorados += 1
                    continue
                por_emp.setdefault(emps[eclic]["id"], []).append((proj, h))
            emi = (date.fromisoformat(pf) + timedelta(days=1)).isoformat()
            helper = self.app.telas["TelaEmpresas"]
            gerados = []
            for cid, lista in por_emp.items():
                emp = self.app.con.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone()
                emp = dict(emp)
                mapa = ultimo_mapa_itens(self.app.con, cid)
                itens = [(proj, emp["valor_hora"], mapa.get(proj, (None, None))[0], h) for proj, h in lista]
                rm = proximo_rm(self.app.con, cid, emi)
                helper.salvar_bm(emp, pi, pf, emi, rm, 0, itens, "LOTE")
                gerados.append(f"{emp['nome']} -> {rm or '(sem RM)'} ({len(itens)} projetos)")
            msg = f"Período {fmt_br(pi)} até {fmt_br(pf)} | Emissão {fmt_br(emi)}\nGerados: {len(gerados)}\n" + "\n".join(gerados)
            msg += f"\nUsuários sem cadastro ignorados: {ignorados}"
            self.log.delete("1.0", "end")
            self.log.insert("end", msg)
            messagebox.showinfo("Lote concluído", msg)
        except Exception as e:
            messagebox.showerror("Erro no lote", str(e))

class TelaBoletins(Base):
    cid = None
    def ao_mostrar(self):
        for w in self.winfo_children():
            w.destroy()
        emp = self.app.con.execute("SELECT * FROM companies WHERE id=?", (self.cid,)).fetchone()
        self.app.cabec(self, f"Boletins Emitidos — {emp['nome']}", "TelaEmpresas")
        lb = tk.Listbox(self, height=18, font=("Segoe UI", 11))
        lb.pack(fill="both", expand=True, padx=12, pady=6)
        rows = self.app.con.execute("SELECT * FROM bms WHERE company_id=? ORDER BY id DESC", (self.cid,)).fetchall()
        for r in rows:
            lb.insert("end", f"{r['id']} | Boletim {emp['nome']} - {fmt_br(r['emissao'])} | {r['rm_numero'] or '(sem RM)'} Rev {r['revisao']} ({r['origem']})")
        self.lb, self.rows = lb, list(rows)
        row = ttk.Frame(self)
        row.pack(pady=6)
        ttk.Button(row, text="Baixar XLSX", style="Azul.TButton", command=lambda: self.baixar("xlsx")).pack(side="left", padx=4)
        ttk.Button(row, text="Baixar PDF", command=lambda: self.baixar("pdf")).pack(side="left", padx=4)
    def atual(self):
        s = self.lb.curselection()
        if not s:
            messagebox.showwarning("Aviso", "Clique em um boletim da lista")
            return None
        return self.rows[s[0]]
    def baixar(self, tipo):
        r = self.atual()
        if not r:
            return
        emp = self.app.con.execute("SELECT nome FROM companies WHERE id=?", (self.cid,)).fetchone()["nome"]
        sug = f"Boletim {emp} - {r['emissao']}.{tipo}"
        dest = filedialog.asksaveasfilename(initialfile=sug, defaultextension=f".{tipo}")
        if dest:
            with open(dest, "wb") as f:
                f.write(r["xlsx_blob"] if tipo == "xlsx" else r["pdf_blob"])
            messagebox.showinfo("OK", f"Salvo em {dest}")

if __name__ == "__main__":
    App().mainloop()
