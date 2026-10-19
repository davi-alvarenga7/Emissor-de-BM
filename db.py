# -*- coding: utf-8 -*-
"""Camada de acesso ao SQL Server 2016 (via pyodbc).

O sistema usa SQL Server. O script de criacao das tabelas esta em
`schema_sqlserver2016.sql` e pode ser executado no SSMS ou pelo proprio
sistema (Banco.criar_esquema).
"""
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal

import pyodbc

from util import (parse_data_flex, fmt_br, parse_num, so_digitos, hoje_iso)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def recurso(nome: str) -> str:
    """Caminho de um recurso tanto em execucao normal quanto no .exe congelado."""
    base = getattr(sys, "_MEIPASS", BASE_DIR)
    return os.path.join(base, nome)


def caminho_config() -> str:
    """config.json editavel pelo usuario.

    Quando congelado (.exe), fica na mesma pasta do executavel; em execucao
    normal, na pasta do projeto. O modelo embutido no .exe serve apenas como
    fallback inicial.
    """
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "config.json")
    return os.path.join(BASE_DIR, "config.json")


CONFIG_PATH = caminho_config()
CONFIG_EMBUTIDO = recurso("config.json")

CONFIG_PADRAO = {
    "driver": "ODBC Driver 17 for SQL Server",
    "server": "localhost",
    "port": "1433",
    "instance": "",
    "database": "EBM",
    "username": "",
    "password": "",
    "trusted_connection": False,
    "encrypt": False,
    "trust_server_certificate": True,
    "connection_timeout": 15,
}

CONTRATANTE = "DBR ENERGIES S/A"


class ErroBanco(Exception):
    """Falha de conexao ou de operacao no banco."""


# ------------------------------------------------------------------ config
def carregar_config() -> dict:
    """Le o config.json do usuario; se nao existir, usa o embutido; senao o padrao."""
    cfg = dict(CONFIG_PADRAO)
    for caminho in (CONFIG_PATH, CONFIG_EMBUTIDO):
        if not caminho or not os.path.exists(caminho):
            continue
        try:
            with open(caminho, encoding="utf-8") as f:
                dados = json.load(f)
            for k, v in dados.items():
                if not k.startswith("_"):
                    cfg[k] = v
            break
        except Exception as e:
            raise ErroBanco(f"{os.path.basename(caminho)} invalido: {e}")
    return cfg


def gravar_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def connection_string(cfg: dict = None) -> str:
    """Monta a string de conexao ODBC para o SQL Server."""
    cfg = cfg or carregar_config()
    driver = cfg.get("driver") or CONFIG_PADRAO["driver"]
    server = str(cfg.get("server") or "localhost").strip()
    instancia = str(cfg.get("instance") or "").strip()
    if instancia:
        server = f"{server}\\{instancia}"
    elif not server.startswith("\\\\") and "," not in server:
        porta = str(cfg.get("port") or "1433").strip()
        if porta:
            server = f"{server},{porta}"
    partes = [f"DRIVER={{{driver}}}", f"SERVER={server}",
              f"DATABASE={cfg.get('database') or 'EBM'}"]
    if cfg.get("trusted_connection"):
        partes.append("Trusted_Connection=yes")
    else:
        partes.append(f"UID={cfg.get('username') or ''}")
        partes.append(f"PWD={cfg.get('password') or ''}")
    partes.append("Encrypt=yes" if cfg.get("encrypt") else "Encrypt=no")
    if cfg.get("trust_server_certificate", True):
        partes.append("TrustServerCertificate=yes")
    return ";".join(partes) + ";"


def driver_instalado() -> bool:
    try:
        return bool(pyodbc.drivers())
    except Exception:
        return False


def drivers_disponiveis() -> list:
    try:
        return list(pyodbc.drivers())
    except Exception:
        return []


# ------------------------------------------------------------------ helpers
def _dec(v, casas="0.01"):
    """Converte para Decimal; None vira None (NULL no SQL Server)."""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    f = parse_num(v)
    if f is None:
        return None
    return Decimal(str(f)).quantize(Decimal(casas))


def _data(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return parse_data_flex(v)


# ------------------------------------------------------------------ DDL
DDL = [
    # ---------------- usuarios
    """IF OBJECT_ID('dbo.users','U') IS NULL
CREATE TABLE dbo.users (
    id            INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_users PRIMARY KEY,
    nome_completo NVARCHAR(200) NOT NULL,
    login         NVARCHAR(100) COLLATE Latin1_General_CI_AS NOT NULL,
    email         NVARCHAR(200) NOT NULL,
    senha_hash    NVARCHAR(300) NOT NULL,
    is_admin      BIT NOT NULL CONSTRAINT DF_users_is_admin DEFAULT (0),
    criado_em     DATETIME2(0) NOT NULL CONSTRAINT DF_users_criado_em DEFAULT (SYSDATETIME())
);""",
    """IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UX_users_login' AND object_id=OBJECT_ID('dbo.users'))
CREATE UNIQUE INDEX UX_users_login ON dbo.users(login);""",
    # ---------------- empresas
    """IF OBJECT_ID('dbo.companies','U') IS NULL
CREATE TABLE dbo.companies (
    id             INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_companies PRIMARY KEY,
    nome           NVARCHAR(200) NOT NULL,
    cnpj           NVARCHAR(14) NOT NULL,
    responsavel    NVARCHAR(200) NOT NULL,
    email_contato  NVARCHAR(200) NOT NULL,
    usuario_eclic  NVARCHAR(100) COLLATE Latin1_General_CI_AS NOT NULL,
    po_codigo      NVARCHAR(50)  COLLATE Latin1_General_CI_AS NOT NULL,
    po_inicio      DATE NOT NULL,
    po_fim         DATE NOT NULL,
    po_valor_total DECIMAL(18,2) NOT NULL,
    po_objeto      NVARCHAR(500) NOT NULL,
    valor_hora     DECIMAL(18,2) NOT NULL,
    criado_em      DATETIME2(0) NOT NULL CONSTRAINT DF_companies_criado_em DEFAULT (SYSDATETIME()),
    atualizado_em  DATETIME2(0) NOT NULL CONSTRAINT DF_companies_atualizado_em DEFAULT (SYSDATETIME()),
    CONSTRAINT UQ_companies_cnpj   UNIQUE (cnpj),
    CONSTRAINT UQ_companies_eclic  UNIQUE (usuario_eclic),
    CONSTRAINT UQ_companies_po     UNIQUE (po_codigo),
    CONSTRAINT CK_companies_valor  CHECK (po_valor_total >= 0),
    CONSTRAINT CK_companies_vh     CHECK (valor_hora >= 0),
    CONSTRAINT CK_companies_datas  CHECK (po_fim >= po_inicio)
);""",
    # ---------------- boletins
    """IF OBJECT_ID('dbo.bms','U') IS NULL
CREATE TABLE dbo.bms (
    id               INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bms PRIMARY KEY,
    company_id       INT NOT NULL CONSTRAINT FK_bms_company REFERENCES dbo.companies(id),
    rm_numero        NVARCHAR(50) NOT NULL,
    periodo_ini      DATE NOT NULL,
    periodo_fim      DATE NOT NULL,
    emissao          DATE NOT NULL,
    revisao          INT NOT NULL CONSTRAINT DF_bms_revisao DEFAULT (0),
    contratante      NVARCHAR(200) NOT NULL CONSTRAINT DF_bms_contratante DEFAULT (N'DBR ENERGIES S/A'),
    snap_nome        NVARCHAR(200) NOT NULL,
    snap_cnpj        NVARCHAR(14) NOT NULL,
    snap_po          NVARCHAR(50) NOT NULL,
    snap_po_inicio   DATE NOT NULL,
    snap_po_fim      DATE NOT NULL,
    snap_valor_total DECIMAL(18,2) NOT NULL,
    snap_objeto      NVARCHAR(500) NOT NULL,
    snap_valor_hora  DECIMAL(18,2) NOT NULL,
    total_anterior   DECIMAL(18,2) NULL,
    total_periodo    DECIMAL(18,2) NULL,
    total_acumulado  DECIMAL(18,2) NULL,
    saldo            DECIMAL(18,2) NULL,
    xlsx_blob        VARBINARY(MAX) NOT NULL,
    pdf_blob         VARBINARY(MAX) NOT NULL,
    origem           NVARCHAR(10) NOT NULL,
    criado_em        DATETIME2(0) NOT NULL CONSTRAINT DF_bms_criado_em DEFAULT (SYSDATETIME()),
    CONSTRAINT UQ_bms_unico UNIQUE (company_id, rm_numero, revisao),
    CONSTRAINT CK_bms_origem CHECK (origem IN (N'LOTE', N'MANUAL', N'BASE')),
    CONSTRAINT CK_bms_datas  CHECK (periodo_fim >= periodo_ini)
);""",
    """IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_bms_company' AND object_id=OBJECT_ID('dbo.bms'))
CREATE INDEX IX_bms_company ON dbo.bms(company_id, criado_em DESC);""",
    # ---------------- itens do boletim
    """IF OBJECT_ID('dbo.bm_items','U') IS NULL
CREATE TABLE dbo.bm_items (
    id              INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bm_items PRIMARY KEY,
    bm_id           INT NOT NULL CONSTRAINT FK_bm_items_bm REFERENCES dbo.bms(id) ON DELETE CASCADE,
    item_seq        INT NOT NULL,
    projeto         NVARCHAR(300) NOT NULL,
    descricao       NVARCHAR(300) NOT NULL CONSTRAINT DF_bm_items_desc DEFAULT (N'Servicos de Consultoria em TELECOM'),
    valor_hora      DECIMAL(18,2) NOT NULL,
    horas_anterior  DECIMAL(18,4) NULL,
    horas_periodo   DECIMAL(18,4) NOT NULL,
    horas_acumulada DECIMAL(18,4) NULL,
    total_anterior  DECIMAL(18,2) NULL,
    total_periodo   DECIMAL(18,2) NULL,
    total_acumulado DECIMAL(18,2) NULL,
    CONSTRAINT UQ_bm_items UNIQUE (bm_id, projeto)
);""",
]


# ------------------------------------------------------------------ banco
class Banco:
    """Encapsula a conexao com o SQL Server e as operacoes de dominio."""

    def __init__(self, cfg: dict = None):
        self.cfg = cfg or carregar_config()
        self.con = None

    # ------------------------------------------------------------ conexao
    def conectar(self):
        if self.con is not None:
            return self.con
        cs = connection_string(self.cfg)
        try:
            self.con = pyodbc.connect(
                cs,
                timeout=int(self.cfg.get("connection_timeout", 15)),
                autocommit=False,
            )
        except pyodbc.Error as e:
            raise ErroBanco(self._traduzir_erro(e))
        return self.con

    def _traduzir_erro(self, e) -> str:
        msg = str(e)
        if "IM002" in msg or "Data source name not found" in msg or "Can't open" in msg:
            return ("Driver ODBC nao encontrado.\n"
                    f"Drivers instalados: {drivers_disponiveis() or 'nenhum'}\n"
                    "Instale o 'Microsoft ODBC Driver 17 for SQL Server'.")
        if "08001" in msg or "Server not found" in msg or "Named Pipes" in msg:
            return ("Servidor SQL Server nao encontrado.\n"
                    f"Verifique 'server' e 'port' em config.json (atual: "
                    f"{self.cfg.get('server')},{self.cfg.get('port')}).")
        if "08001" in msg or "Login failed" in msg:
            return "Falha de autenticacao. Verifique usuario/senha em config.json."
        if "4060" in msg or "Cannot open database" in msg:
            return (f"Banco '{self.cfg.get('database')}' nao existe.\n"
                    "Crie o banco e execute schema_sqlserver2016.sql no SSMS.")
        if "28000" in msg:
            return "Login failed for user. Verifique usuario/senha em config.json."
        return msg

    def fechar(self):
        if self.con is not None:
            try:
                self.con.close()
            except Exception:
                pass
            self.con = None

    def _exec(self, sql, params=()):
        cur = self.con.cursor()
        cur.execute(sql, params)
        return cur

    def _todos(self, sql, params=()):
        cur = self._exec(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def _um(self, sql, params=()):
        r = self._todos(sql, params)
        return r[0] if r else None

    def criar_esquema(self):
        """Cria as tabelas se ainda nao existirem (idempotente)."""
        self.conectar()
        for ddl in DDL:
            self._exec(ddl)
        self.con.commit()

    # ------------------------------------------------------------ usuarios
    def tem_usuario(self) -> bool:
        self.conectar()
        return self._um("SELECT COUNT(*) AS total FROM dbo.users")["total"] > 0

    def criar_usuario(self, nome_completo, login, email, senha_hash, is_admin=False):
        self.conectar()
        sql = ("INSERT INTO dbo.users (nome_completo, login, email, senha_hash, is_admin) "
               "OUTPUT INSERTED.id VALUES (?,?,?,?,?)")
        cur = self._exec(sql, (nome_completo, login, email, senha_hash, 1 if is_admin else 0))
        novo_id = cur.fetchone()[0]
        self.con.commit()
        return novo_id

    def buscar_usuario(self, login):
        self.conectar()
        return self._um("SELECT * FROM dbo.users WHERE login = ?", (login,))

    def listar_usuarios(self):
        self.conectar()
        return self._todos("SELECT * FROM dbo.users ORDER BY nome_completo")

    def resetar_senha(self, login, senha_hash):
        """Admin redefine a senha de um usuario. Retorna True se alterou."""
        self.conectar()
        cur = self._exec("UPDATE dbo.users SET senha_hash = ? WHERE login = ?", (senha_hash, login))
        self.con.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------ empresas
    def listar_empresas(self, busca=None):
        self.conectar()
        if busca:
            pad = f"%{busca}%"
            return self._todos(
                "SELECT * FROM dbo.companies "
                "WHERE responsavel LIKE ? OR nome LIKE ? OR cnpj LIKE ? "
                "ORDER BY nome", (pad, pad, pad))
        return self._todos("SELECT * FROM dbo.companies ORDER BY nome")

    def buscar_empresa(self, emp_id):
        self.conectar()
        return self._um("SELECT * FROM dbo.companies WHERE id = ?", (emp_id,))

    def empresa_por_cnpj(self, cnpj):
        self.conectar()
        return self._um("SELECT * FROM dbo.companies WHERE cnpj = ?", (so_digitos(cnpj),))

    def empresa_por_eclic(self, usuario_eclic):
        self.conectar()
        return self._um("SELECT * FROM dbo.companies WHERE usuario_eclic = ?", (usuario_eclic,))

    def duplicado_empresa(self, cnpj, po_codigo, usuario_eclic, ignorar_id=None):
        """Retorna o campo duplicado ou None."""
        self.conectar()
        if self._um("SELECT id FROM dbo.companies WHERE cnpj = ?", (so_digitos(cnpj),)):
            return "CNPJ"
        if self._um("SELECT id FROM dbo.companies WHERE po_codigo = ?", (po_codigo,)):
            return "Código PO"
        if self._um("SELECT id FROM dbo.companies WHERE usuario_eclic = ?", (usuario_eclic,)):
            return "Usuário E-clic"
        return None

    def criar_empresa(self, d):
        self.conectar()
        sql = ("INSERT INTO dbo.companies "
               "(nome, cnpj, responsavel, email_contato, usuario_eclic, po_codigo, "
               " po_inicio, po_fim, po_valor_total, po_objeto, valor_hora) "
               "OUTPUT INSERTED.id VALUES (?,?,?,?,?,?,?,?,?,?,?)")
        params = (d["nome"], so_digitos(d["cnpj"]), d["responsavel"], d["email_contato"],
                  d["usuario_eclic"], d["po_codigo"], _data(d["po_inicio"]), _data(d["po_fim"]),
                  _dec(d["po_valor_total"]), d["po_objeto"], _dec(d["valor_hora"]))
        cur = self._exec(sql, params)
        novo_id = cur.fetchone()[0]
        self.con.commit()
        return novo_id

    def atualizar_empresa(self, emp_id, d):
        self.conectar()
        sql = ("UPDATE dbo.companies SET nome=?, cnpj=?, responsavel=?, email_contato=?, "
               "usuario_eclic=?, po_codigo=?, po_inicio=?, po_fim=?, po_valor_total=?, "
               "po_objeto=?, valor_hora=?, atualizado_em=SYSDATETIME() WHERE id=?")
        params = (d["nome"], so_digitos(d["cnpj"]), d["responsavel"], d["email_contato"],
                  d["usuario_eclic"], d["po_codigo"], _data(d["po_inicio"]), _data(d["po_fim"]),
                  _dec(d["po_valor_total"]), d["po_objeto"], _dec(d["valor_hora"]), emp_id)
        self._exec(sql, params)
        self.con.commit()

    # ------------------------------------------------------------ boletins
    def proximo_rm(self, company_id, emissao_iso):
        """Sequencial por empresa: BM-YYYY-NNN. Vazio se a empresa nao tem historico."""
        self.conectar()
        linhas = self._todos("SELECT rm_numero FROM dbo.bms WHERE company_id = ?", (company_id,))
        if not linhas:
            return ""
        ano = str(emissao_iso)[:4]
        mx = 0
        for l in linhas:
            m = re.search(r"(\d{3,})", l.get("rm_numero") or "")
            if m:
                mx = max(mx, int(m.group(1)))
        return f"BM-{ano}-{mx + 1:03d}"

    def ultimo_bm(self, company_id):
        self.conectar()
        return self._um("SELECT * FROM dbo.bms WHERE company_id = ? ORDER BY id DESC", (company_id,))

    def ultimo_mapa_itens(self, company_id):
        """projeto -> (horas_acumulada, total_acumulado) do ultimo BM da empresa."""
        self.conectar()
        ultimo = self.ultimo_bm(company_id)
        if not ultimo:
            return {}
        itens = self._todos("SELECT projeto, horas_acumulada, total_acumulado "
                            "FROM dbo.bm_items WHERE bm_id = ?", (ultimo["id"],))
        return {i["projeto"]: (i["horas_acumulada"], i["total_acumulado"]) for i in itens}

    def listar_boletins(self, company_id):
        self.conectar()
        return self._todos("SELECT * FROM dbo.bms WHERE company_id = ? ORDER BY id DESC",
                            (company_id,))

    def proxima_revisao(self, company_id, rm_numero, periodo_ini, periodo_fim):
        self.conectar()
        r = self._um("SELECT MAX(revisao) AS m FROM dbo.bms "
                     "WHERE company_id = ? AND rm_numero = ? AND periodo_ini = ? AND periodo_fim = ?",
                     (company_id, rm_numero, _data(periodo_ini), _data(periodo_fim)))
        if r is None or r["m"] is None:
            return 0
        return int(r["m"]) + 1

    def salvar_bm(self, emp, periodo_ini, periodo_fim, emissao, rm_numero, revisao,
                  itens, origem, xlsx_bytes, pdf_bytes, totais):
        """Grava boletim + itens no SQL Server. `emp` e um dict/Row da empresa."""
        self.conectar()
        ta, tp, tac, saldo = totais
        sql = ("INSERT INTO dbo.bms "
               "(company_id, rm_numero, periodo_ini, periodo_fim, emissao, revisao, contratante, "
               " snap_nome, snap_cnpj, snap_po, snap_po_inicio, snap_po_fim, snap_valor_total, "
               " snap_objeto, snap_valor_hora, total_anterior, total_periodo, total_acumulado, "
               " saldo, xlsx_blob, pdf_blob, origem) "
               "OUTPUT INSERTED.id VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
        params = (emp["id"], rm_numero or "", _data(periodo_ini), _data(periodo_fim),
                  _data(emissao), int(revisao), CONTRATANTE,
                  emp["nome"], emp["cnpj"], emp["po_codigo"],
                  _data(emp["po_inicio"]), _data(emp["po_fim"]),
                  _dec(emp["po_valor_total"]), emp["po_objeto"], _dec(emp["valor_hora"]),
                  _dec(ta), _dec(tp), _dec(tac), _dec(saldo),
                  pyodbc.Binary(xlsx_bytes), pyodbc.Binary(pdf_bytes), origem)
        cur = self._exec(sql, params)
        bm_id = cur.fetchone()[0]
        for seq, (proj, vh, h_ant, h_per) in enumerate(itens, start=1):
            acu = (h_ant + h_per) if h_ant is not None else h_per
            self._exec(
                "INSERT INTO dbo.bm_items "
                "(bm_id, item_seq, projeto, descricao, valor_hora, horas_anterior, horas_periodo, "
                " horas_acumulada, total_anterior, total_periodo, total_acumulado) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (bm_id, seq, proj, "Serviços de Consultoria em TELECOM", _dec(vh),
                 _dec(h_ant, "0.0001"), _dec(h_per, "0.0001"), _dec(acu, "0.0001"),
                 _dec((h_ant * vh) if h_ant is not None else None),
                 _dec(h_per * vh), _dec(((h_ant or 0) + h_per) * vh)))
        self.con.commit()
        return bm_id
