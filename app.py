# -*- coding: utf-8 -*-
"""E-BM - Emissor de Boletim de Medicao (desktop).

Banco: SQL Server 2016 (ver config.json e schema_sqlserver2016.sql).
Executar: python app.py
"""
import os
import sys
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import ttk, messagebox, filedialog

import db as dbmod
from db import Banco, ErroBanco
from util import (parse_data_flex, parse_num, so_digitos, valida_cnpj, valida_email,
                  hash_senha, confere_senha, fmt_br, hoje_iso)
import boletim as bl

AZUL = "#0B5ED7"
AZUL_ESCURO = "#0849ad"


def recurso(nome: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, nome)


LOGO_PATH = recurso("logo.png")


def logo_tk(largura=220):
    """Logo DBR redimensionada para o Tkinter (fundo branco)."""
    try:
        from PIL import Image as PI, ImageTk as ITK
        im = PI.open(LOGO_PATH).convert("RGBA")
        h = max(1, int(im.height * largura / im.width))
        im = im.resize((largura, h), PI.LANCZOS)
        bg = PI.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        return ITK.PhotoImage(bg.convert("RGB"))
    except Exception:
        return None


CAMPOS_EMPRESA = [("Razão Social*", "nome"), ("CNPJ*", "cnpj"), ("Código PO*", "po_codigo"),
                  ("Início PO* (dd/mm/aaaa)", "po_inicio"), ("Fim PO* (dd/mm/aaaa)", "po_fim"),
                  ("Valor Total PO*", "po_valor_total"), ("Objeto*", "po_objeto"),
                  ("E-mail contato*", "email_contato"), ("Valor Hora*", "valor_hora"),
                  ("Responsável*", "responsavel"), ("Usuário E-clic*", "usuario_eclic")]

CAMPOS_OBRIGATORIOS = ["nome", "cnpj", "po_codigo", "po_inicio", "po_fim", "po_valor_total",
                       "po_objeto", "email_contato", "valor_hora", "responsavel", "usuario_eclic"]


# ------------------------------------------------------------------ app
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("E-BM - Emissor de Boletim de Medição | DBR Energies")
        self.geometry("1120x720")
        self.bd = Banco()
        self.usuario = None
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Azul.TButton", background=AZUL, foreground="white",
                        font=("Segoe UI", 11, "bold"))
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

        if not self.conectar_bd():
            return
        self.ir("TelaLogin" if self.bd.tem_usuario() else "TelaCadastroUser")

    # ------------------------------------------------------------ banco
    def conectar_bd(self):
        try:
            self.bd.conectar()
        except ErroBanco as e:
            self.mostrar_falha_bd(str(e))
            return False
        except Exception as e:
            self.mostrar_falha_bd(str(e))
            return False
        try:
            self.bd.criar_esquema()
        except Exception as e:
            self.mostrar_falha_bd(f"Não foi possível criar/verificar as tabelas:\n{e}")
            return False
        return True

    def mostrar_falha_bd(self, msg):
        dlg = tk.Toplevel(self)
        dlg.title("Banco de dados não configurado")
        dlg.geometry("640x320")
        dlg.transient(self)
        ttk.Label(dlg, text="E-BM - Configuração do SQL Server 2016",
                  font=("Segoe UI", 14, "bold"), foreground=AZUL).pack(pady=12)
        txt = tk.Text(dlg, height=9, width=78)
        txt.pack(padx=12, fill="both", expand=True)
        txt.insert("1.0", msg)
        txt.insert("end", "\n\nPara configurar:\n"
                         "1. Edite o arquivo config.json (driver, server, port, database, "
                         "usuario e senha).\n"
                         "2. Crie o banco 'EBM' no SQL Server.\n"
                         "3. Execute schema_sqlserver2016.sql no SSMS.\n"
                         "4. Reinicie o E-BM.")
        txt.config(state="disabled")
        row = ttk.Frame(dlg)
        row.pack(pady=10)
        ttk.Button(row, text="Abrir config.json", style="Azul.TButton",
                   command=self.abrir_config).pack(side="left", padx=6)
        ttk.Button(row, text="Sair", command=self.destroy).pack(side="left", padx=6)
        dlg.grab_set()

    def abrir_config(self):
        alvo = dbmod.caminho_config()
        if not os.path.exists(alvo):
            with open(alvo, "w", encoding="utf-8") as f:
                f.write('{\n  "driver": "ODBC Driver 17 for SQL Server",\n'
                        '  "server": "localhost",\n  "port": "1433",\n'
                        '  "database": "EBM",\n  "username": "",\n  "password": ""\n}\n')
        os.startfile(alvo)

    # ------------------------------------------------------------ navegacao
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
        ttk.Label(top, text=titulo, font=("Segoe UI", 15, "bold"),
                  foreground=AZUL).pack(side="left", padx=12)
        lg = logo_tk(120)
        if lg:
            lab = ttk.Label(top, image=lg)
            lab.image = lg
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


# ------------------------------------------------------------------ telas
class TelaLogin(Base):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        lg = logo_tk(260)
        if lg:
            lab = ttk.Label(self, image=lg)
            lab.image = lg
            lab.pack(pady=(14, 0))
        ttk.Label(self, text="E-BM", font=("Segoe UI", 22, "bold"),
                  foreground=AZUL).pack(pady=10)
        box = ttk.Frame(self)
        box.pack()
        self.login = self.campo(box, "Login", 0)
        self.senha = self.campo(box, "Senha", 1)
        self.senha.config(show="*")
        ttk.Button(box, text="Entrar", style="Azul.TButton",
                   command=self.entrar).grid(row=2, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Button(box, text="Cadastrar-se", command=lambda: app.ir("TelaCadastroUser")
                   ).grid(row=3, column=0, columnspan=2, sticky="ew")
        ttk.Button(box, text="Esqueci a senha", command=self.esqueci
                   ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=4)

    def entrar(self):
        u = self.app.bd.buscar_usuario(self.login.get().strip())
        if not u or not confere_senha(self.senha.get(), u["senha_hash"]):
            return messagebox.showerror("Erro", "Login ou senha inválidos")
        self.app.usuario = u
        self.app.ir("TelaHome")

    def esqueci(self):
        messagebox.showinfo(
            "Recuperação de senha",
            "Procure o administrador (primeiro usuário cadastrado) para resetar sua senha.")


class TelaCadastroUser(Base):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        lg = logo_tk(190)
        if lg:
            lab = ttk.Label(self, image=lg)
            lab.image = lg
            lab.pack(pady=(10, 0))
        ttk.Label(self, text="Cadastro de usuário", font=("Segoe UI", 16, "bold"),
                  foreground=AZUL).pack(pady=8)
        box = ttk.Frame(self)
        box.pack()
        self.nome = self.campo(box, "Nome Completo*", 0)
        self.login = self.campo(box, "Login*", 1)
        self.email = self.campo(box, "E-mail*", 2)
        self.s1 = self.campo(box, "Senha* (mínimo 6)", 3)
        self.s1.config(show="*")
        self.s2 = self.campo(box, "Confirmar Senha*", 4)
        self.s2.config(show="*")
        ttk.Button(box, text="Salvar e entrar", style="Azul.TButton",
                   command=self.salvar).grid(row=5, column=0, columnspan=2, sticky="ew", pady=8)

    def salvar(self):
        nome = self.nome.get().strip()
        lg = self.login.get().strip()
        em = self.email.get().strip()
        s1, s2 = self.s1.get(), self.s2.get()
        if not all([nome, lg, em, s1, s2]):
            return messagebox.showerror("Erro", "Preencha todos os campos")
        if not valida_email(em):
            return messagebox.showerror("Erro", "E-mail inválido")
        if len(s1) < 6:
            return messagebox.showerror("Erro", "Senha mínima de 6 caracteres")
        if s1 != s2:
            return messagebox.showerror("Erro", "Senhas não conferem")
        if self.app.bd.buscar_usuario(lg):
            return messagebox.showerror("Erro", "Login já existe")
        is_admin = not self.app.bd.tem_usuario()
        novo_id = self.app.bd.criar_usuario(nome, lg, em, hash_senha(s1), is_admin)
        self.app.usuario = self.app.bd.buscar_usuario(lg)
        messagebox.showinfo("OK", "Usuário cadastrado" + (" (administrador)" if is_admin else ""))
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
        ttk.Label(topo, text="E-BM", font=("Segoe UI", 22, "bold"),
                  foreground=AZUL).pack(side="left", padx=16)
        centro = ttk.Frame(self)
        centro.pack(fill="both", expand=True)
        box = ttk.Frame(centro)
        box.place(relx=0.5, rely=0.5, anchor="center")
        for txt, dst in [("Cadastro de Nova Empresa", "TelaCadEmpresa"),
                         ("Empresas Cadastradas", "TelaEmpresas"),
                         ("Emissão de Boletins em Lote", "TelaLote")]:
            ttk.Button(box, text=txt, style="Azul.TButton", width=40,
                       command=lambda d=dst: app.ir(d)).pack(pady=10)


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
        ttk.Button(row, text="Salvar", style="Azul.TButton",
                   command=self.salvar).pack(side="left", padx=6)
        ttk.Button(row, text="Cadastro em lote (Excel)",
                   command=self.lote).pack(side="left", padx=6)

    def ler_tela(self):
        return {k: e.get().strip() for k, e in self.ents.items()}

    def validar(self, d, ignorar_id=None):
        for k in CAMPOS_OBRIGATORIOS:
            if not d.get(k):
                return f"Campo obrigatório em branco: {rotulo_campo(k)}"
        if not valida_cnpj(d["cnpj"]):
            return "CNPJ inválido (deve ter 14 dígitos)"
        if not valida_email(d["email_contato"]):
            return "E-mail de contato inválido"
        di, df = parse_data_flex(d["po_inicio"]), parse_data_flex(d["po_fim"])
        if not di or not df:
            return "Datas de PO inválidas (use dd/mm/aaaa)"
        if df < di:
            return "Fim PO deve ser maior ou igual ao Início PO"
        vt, vh = parse_num(d["po_valor_total"]), parse_num(d["valor_hora"])
        if vt is None or vt < 0 or vh is None or vh < 0:
            return "Valores devem ser numéricos e maiores ou iguais a zero"
        dup = self.app.bd.duplicado_empresa(d["cnpj"], d["po_codigo"], d["usuario_eclic"])
        if dup:
            return f"Já existe empresa com o mesmo {dup}"
        d["_di"], d["_df"], d["_vt"], d["_vh"] = di, df, vt, vh
        return None

    def salvar(self):
        d = self.ler_tela()
        erro = self.validar(d)
        if erro:
            return messagebox.showerror("Erro", erro)
        self.app.bd.criar_empresa(d)
        messagebox.showinfo("OK", "Empresa cadastrada")
        self.app.ir("TelaEmpresas")

    def lote(self):
        paths = filedialog.askopenfilenames(title="Planilha de empresas",
                                            filetypes=[("Excel", "*.xlsx")])
        if not paths:
            return
        from openpyxl import load_workbook
        ok = pul = 0
        motivos = []
        for p in paths:
            try:
                wb = load_workbook(p, data_only=True)
                rows = list(wb.active.iter_rows(values_only=True))
            except Exception as e:
                motivos.append(f"{os.path.basename(p)}: {e}")
                continue
            vistos = set()
            for i, r in enumerate(rows[1:], start=2):
                if not r or all(c in (None, "") for c in r):
                    pul += 1
                    motivos.append(f"linha {i}: linha vazia")
                    continue
                try:
                    vals = list(r) + [""] * 11
                    chaves = ["nome", "cnpj", "po_codigo", "po_inicio", "po_fim",
                              "po_valor_total", "po_objeto", "email_contato", "valor_hora",
                              "responsavel", "usuario_eclic"]
                    d = {k: str(vals[j] or "").strip() for j, k in enumerate(chaves)}
                    if any(not d[k] for k in chaves):
                        pul += 1
                        motivos.append(f"linha {i}: célula em branco")
                        continue
                    chave = (so_digitos(d["cnpj"]), d["po_codigo"].upper())
                    if chave in vistos:
                        pul += 1
                        motivos.append(f"linha {i}: duplicada no arquivo")
                        continue
                    vistos.add(chave)
                    for idx, k in ((3, "po_inicio"), (4, "po_fim")):
                        if isinstance(r[idx], (datetime, date)):
                            d[k] = r[idx].strftime("%d/%m/%Y")
                    erro = self.validar(d)
                    if erro:
                        pul += 1
                        motivos.append(f"linha {i}: {erro}")
                        continue
                    self.app.bd.criar_empresa(d)
                    ok += 1
                except Exception as e:
                    pul += 1
                    motivos.append(f"linha {i}: {e}")
        msg = f"{ok} empresa(s) cadastrada(s), {pul} pulada(s)."
        if motivos:
            msg += "\n\n" + "\n".join(motivos[:25])
        messagebox.showinfo("Cadastro em lote", msg)


def rotulo_campo(chave):
    for rot, k in CAMPOS_EMPRESA:
        if k == chave:
            return rot.replace("*", "").strip()
    return chave


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
            tv.column(c, width=260)
        tv.pack(fill="both", expand=True, padx=12, pady=6)
        self.tv = tv

        def recarrega(*_):
            q = busca.get().strip()
            like = f"%{q}%" if q and "Buscar" not in q else "%"
            tv.delete(*tv.get_children())
            for r in self.app.bd.listar_empresas(like):
                tv.insert("", "end", iid=r["id"],
                          values=(r["responsavel"], r["nome"], r["cnpj"]))
        busca.bind("<KeyRelease>", recarrega)
        recarrega()

        row = ttk.Frame(self)
        row.pack(pady=8)
        ttk.Button(row, text="Editar", command=self.editar).pack(side="left", padx=4)
        ttk.Button(row, text="Emitir Boletim (manual)", style="Azul.TButton",
                   command=self.manual).pack(side="left", padx=4)
        ttk.Button(row, text="Boletins Emitidos", command=self.boletins).pack(side="left", padx=4)
        ttk.Button(row, text="Importar BM base", command=self.base).pack(side="left", padx=4)

    def selecionada(self):
        s = self.tv.selection()
        if not s:
            messagebox.showwarning("Aviso", "Selecione uma empresa na lista")
            return None
        return int(s[0])

    def editar(self):
        i = self.selecionada()
        if i:
            self.app.telas["TelaEditar"].cid = i
            self.app.ir("TelaEditar")

    def manual(self):
        i = self.selecionada()
        if i:
            self.app.telas["TelaManual"].cid = i
            self.app.ir("TelaManual")

    def boletins(self):
        i = self.selecionada()
        if i:
            self.app.telas["TelaBoletins"].cid = i
            self.app.ir("TelaBoletins")

    def base(self):
        i = self.selecionada()
        if not i:
            return
        p = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if not p:
            return
        from openpyxl import load_workbook
        try:
            wb = load_workbook(p, data_only=True)
            ws = wb.active
            emp = self.app.bd.buscar_empresa(i)
            cnpj_arquivo = so_digitos(ws["H9"].value or "")
            if cnpj_arquivo and cnpj_arquivo != so_digitos(emp["cnpj"]):
                return messagebox.showerror(
                    "Erro", f"CNPJ do arquivo ({cnpj_arquivo}) difere da empresa ({emp['cnpj']})")
            rm = str(ws["I1"].value or "").strip()
            per = str(ws["I2"].value or "")
            ds = [parse_data_flex(x) for x in
                  __import__("re").findall(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", per)]
            pi = ds[0] if len(ds) > 0 and ds[0] else parse_data_flex(emp["po_inicio"])
            pf = ds[1] if len(ds) > 1 and ds[1] else parse_data_flex(emp["po_fim"])
            emi = parse_data_flex(ws["I3"].value) or date.today()
            import re as _re
            mrev = _re.search(r"(\d+)", str(ws["K6"].value or "0"))
            rev = int(mrev.group(1)) if mrev else 0

            itens = []
            for r in range(12, 21):
                proj = ws.cell(row=r, column=3).value
                if not proj:
                    continue
                vh = parse_num(ws.cell(row=r, column=5).value) or 0
                ha = parse_num(ws.cell(row=r, column=6).value)
                hp = parse_num(ws.cell(row=r, column=7).value) or 0
                itens.append((str(proj), vh, ha, hp))
            self.app.gerar_e_salvar_bm(emp, pi, pf, emi, rm, rev, itens, "BASE")
            messagebox.showinfo("OK", "BM base importado")
        except Exception as e:
            messagebox.showerror("Erro", str(e))


class TelaEditar(Base):
    cid = None

    def ao_mostrar(self):
        for w in self.winfo_children():
            w.destroy()
        self.app.cabec(self, "Editar empresa", "TelaEmpresas")
        emp = self.app.bd.buscar_empresa(self.cid)
        box = ttk.Frame(self)
        box.pack(padx=12)
        mapa = {"nome": emp["nome"], "cnpj": emp["cnpj"], "po_codigo": emp["po_codigo"],
                "po_inicio": fmt_br(emp["po_inicio"]), "po_fim": fmt_br(emp["po_fim"]),
                "po_valor_total": emp["po_valor_total"], "po_objeto": emp["po_objeto"],
                "email_contato": emp["email_contato"], "valor_hora": emp["valor_hora"],
                "responsavel": emp["responsavel"], "usuario_eclic": emp["usuario_eclic"]}
        self.ents = {}
        for i, (rot, key) in enumerate(CAMPOS_EMPRESA):
            self.ents[key] = self.campo(box, rot, i, str(mapa[key]))
        row = ttk.Frame(self)
        row.pack(pady=10)
        ttk.Button(row, text="Salvar", style="Azul.TButton",
                   command=self.salvar).pack(side="left", padx=6)
        ttk.Button(row, text="Voltar",
                   command=lambda: self.app.ir("TelaEmpresas")).pack(side="left", padx=6)

    def salvar(self):
        d = {k: e.get().strip() for k, e in self.ents.items()}
        validador = TelaCadEmpresa(self, self.app)
        erro = validador.validar(d, ignorar_id=self.cid)
        if erro:
            return messagebox.showerror("Erro", erro)
        self.app.bd.atualizar_empresa(self.cid, d)
        messagebox.showinfo("OK", "Informações atualizadas")
        self.app.ir("TelaEmpresas")


class TelaManual(Base):
    cid = None

    def ao_mostrar(self):
        for w in self.winfo_children():
            w.destroy()
        emp = self.app.bd.buscar_empresa(self.cid)
        self.app.cabec(self, f"Emitir BM manual — {emp['nome']}", "TelaEmpresas")
        ttk.Label(self, text=f"PO {emp['po_codigo']} | Valor hora R$ "
                             f"{float(emp['valor_hora']):,.2f} (travado)",
                  foreground=AZUL).pack()
        box = ttk.Frame(self)
        box.pack(padx=12, pady=6)
        self.pi = self.campo(box, "Período Inicial* (dd/mm/aaaa)", 0)
        self.pf = self.campo(box, "Período Final* (dd/mm/aaaa)", 1)
        ttk.Label(box, text="Projetos e horas no período:").grid(row=2, column=0,
                                                                   sticky="w", pady=6)
        self.linhas = ttk.Frame(box)
        self.linhas.grid(row=3, column=0, columnspan=2)
        self.rows = []
        for _ in range(3):
            self.add_linha()
        ttk.Button(box, text="+ Adicionar projeto", command=self.add_linha
                   ).grid(row=4, column=0, columnspan=2, pady=4)
        ttk.Button(self, text="Gerar Boletim", style="Azul.TButton",
                   command=self.gerar).pack(pady=10)

    def add_linha(self):
        f = ttk.Frame(self.linhas)
        f.pack(fill="x", pady=2)
        p = ttk.Entry(f, width=52)
        p.pack(side="left", padx=2)
        p.insert(0, "PRJ-...")
        h = ttk.Entry(f, width=12)
        h.pack(side="left", padx=2)
        h.insert(0, "0")
        self.rows.append((p, h))

    def gerar(self):
        emp = self.app.bd.buscar_empresa(self.cid)
        pi, pf = parse_data_flex(self.pi.get()), parse_data_flex(self.pf.get())
        if not pi or not pf or pf < pi:
            return messagebox.showerror("Erro", "Período inválido")
        mapa = self.app.bd.ultimo_mapa_itens(emp["id"])
        itens = []
        for p, h in self.rows:
            proj = p.get().strip()
            hp = parse_num(h.get())
            if not proj or proj == "PRJ-..." or hp is None:
                continue
            ant = mapa.get(proj, (None, None))[0]
            itens.append((proj, float(emp["valor_hora"]),
                          float(ant) if ant is not None else None, float(hp)))
        if not itens:
            return messagebox.showerror("Erro", "Informe ao menos 1 projeto com horas")
        emi = pf + timedelta(days=1)
        rm = self.app.bd.proximo_rm(emp["id"], emi.isoformat())
        self.app.gerar_e_salvar_bm(emp, pi, pf, emi, rm, 0, itens, "MANUAL")
        messagebox.showinfo("OK", f"BM gerado ({rm or 'sem RM'})")
        self.app.telas["TelaBoletins"].cid = emp["id"]
        self.app.ir("TelaBoletins")


class TelaLote(Base):
    def ao_mostrar(self):
        for w in self.winfo_children():
            w.destroy()
        self.app.cabec(self, "Emissão de Boletins em Lote", "TelaHome")
        ttk.Label(self, text="Anexe N planilhas 'horas por item' "
                             "(todas com a mesma data inicial/final).",
                  foreground=AZUL).pack(pady=6)
        ttk.Button(self, text="Selecionar arquivos...", style="Azul.TButton",
                   command=self.processar).pack(pady=8)
        self.log = tk.Text(self, height=20, font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, padx=12, pady=8)

    def processar(self):
        paths = filedialog.askopenfilenames(filetypes=[("Excel", "*.xlsx")])
        if not paths:
            return
        try:
            agreg = {}
            datas = set()
            n_linhas = n_aprov = 0
            for p in paths:
                info = bl.ler_horas_arquivo(p)
                if info["data_ini"] and info["data_fim"]:
                    datas.add((info["data_ini"].isoformat(), info["data_fim"].isoformat()))
                for usu, proj, h, aprov in info["linhas"]:
                    n_linhas += 1
                    if not aprov:
                        continue
                    n_aprov += 1
                    k = (usu.strip().upper(), proj)
                    agreg[k] = agreg.get(k, 0) + h
            if len(datas) > 1:
                return messagebox.showerror(
                    "Erro", f"Datas divergentes no lote: {sorted(datas)}.\n"
                            "Todos os arquivos devem ter a mesma data inicial/final.")
            if not datas:
                return messagebox.showerror("Erro", "Data inicial/final não encontrada "
                                                "nas planilhas")
            pi, pf = list(datas)[0]
            por_emp = {}
            ignorados = 0
            empresas = self.app.bd.listar_empresas()
            for (eclic, proj), h in agreg.items():
                alvo = next((e for e in empresas
                             if str(e["usuario_eclic"]).strip().upper() == eclic), None)
                if not alvo:
                    ignorados += 1
                    continue
                por_emp.setdefault(alvo["id"], []).append((proj, h))
            emi = date.fromisoformat(pf) + timedelta(days=1)
            gerados = []
            for cid, lista in por_emp.items():
                emp = self.app.bd.buscar_empresa(cid)
                mapa = self.app.bd.ultimo_mapa_itens(cid)
                itens = []
                for proj, h in lista:
                    ant = mapa.get(proj, (None, None))[0]
                    itens.append((proj, float(emp["valor_hora"]),
                                  float(ant) if ant is not None else None, float(h)))
                rm = self.app.bd.proximo_rm(cid, emi.isoformat())
                self.app.gerar_e_salvar_bm(emp, date.fromisoformat(pi), date.fromisoformat(pf),
                                          emi, rm, 0, itens, "LOTE")
                gerados.append(f"{emp['nome']} -> {rm or '(sem RM)'} ({len(itens)} projeto(s))")
            msg = (f"Período: {fmt_br(pi)} até {fmt_br(pf)}\nEmissão: {fmt_br(emi)}\n"
                   f"Linhas lidas: {n_linhas} | aprovadas: {n_aprov} | "
                   f"rejeitadas: {n_linhas - n_aprov}\n"
                   f"Boletins gerados: {len(gerados)}\n\n" + "\n".join(gerados) +
                   f"\n\nUsuários sem empresa cadastrada (ignorados): {ignorados}")
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
        emp = self.app.bd.buscar_empresa(self.cid)
        self.app.cabec(self, f"Boletins Emitidos — {emp['nome']}", "TelaEmpresas")
        lb = tk.Listbox(self, height=18, font=("Segoe UI", 11))
        lb.pack(fill="both", expand=True, padx=12, pady=6)
        self.linhas_bm = self.app.bd.listar_boletins(self.cid)
        for r in self.linhas_bm:
            lb.insert("end", f"Boletim {emp['nome']} - {fmt_br(r['emissao'])} | "
                             f"{r['rm_numero'] or '(sem RM)'} | Rev {r['revisao']} "
                             f"| {r['origem']}")
        self.lb = lb
        row = ttk.Frame(self)
        row.pack(pady=6)
        ttk.Button(row, text="Baixar XLSX", style="Azul.TButton",
                   command=lambda: self.baixar("xlsx")).pack(side="left", padx=4)
        ttk.Button(row, text="Baixar PDF",
                   command=lambda: self.baixar("pdf")).pack(side="left", padx=4)

    def atual(self):
        s = self.lb.curselection()
        if not s:
            messagebox.showwarning("Aviso", "Clique em um boletim da lista")
            return None
        return self.linhas_bm[s[0]]

    def baixar(self, tipo):
        r = self.atual()
        if not r:
            return
        emp = self.app.bd.buscar_empresa(self.cid)
        sug = f"Boletim {emp['nome']} - {fmt_br(r['emissao'])}.{tipo}"
        dest = filedialog.asksaveasfilename(initialfile=sug, defaultextension=f".{tipo}")
        if dest:
            with open(dest, "wb") as f:
                f.write(bytes(r["xlsx_blob"]) if tipo == "xlsx" else bytes(r["pdf_blob"]))
            messagebox.showinfo("OK", f"Arquivo salvo em:\n{dest}")


# ------------------------------------------------------------------ helpers do App
def _gerar_e_salvar_bm(self, emp, pi, pf, emi, rm, rev, itens, origem):
    """Gera XLSX/PDF, calcula totais e grava no SQL Server."""
    emp = dict(emp)
    po_ini = parse_data_flex(emp["po_inicio"])
    po_fim = parse_data_flex(emp["po_fim"])
    valor_total = float(emp["po_valor_total"] or 0)
    dados = {"rm": rm, "periodo_txt": f"{fmt_br(pi)} até {fmt_br(pf)}",
             "emissao_txt": fmt_br(emi), "revisao": rev, "po": emp["po_codigo"],
             "po_ini_txt": fmt_br(po_ini), "po_fim_txt": fmt_br(po_fim),
             "valor_total": valor_total, "objeto": emp["po_objeto"],
             "contratada": emp["nome"], "cnpj": emp["cnpj"], "itens": itens}
    xlsx_bytes, ta, tp, tac, saldo = bl.construir_xlsx_bm(dados)
    pdf_bytes = bl.construir_pdf_bm(dados)
    rev = self.bd.proxima_revisao(emp["id"], rm or "", pi, pf)
    if rev:
        dados["revisao"] = rev
        xlsx_bytes, ta, tp, tac, saldo = bl.construir_xlsx_bm(dados)
        pdf_bytes = bl.construir_pdf_bm(dados)
    return self.bd.salvar_bm(emp, pi, pf, emi, rm, rev, itens, origem,
                             xlsx_bytes, pdf_bytes, (ta, tp, tac, saldo))


App.gerar_e_salvar_bm = _gerar_e_salvar_bm


if __name__ == "__main__":
    app = App()
    app.mainloop()
