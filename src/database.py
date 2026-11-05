"""Camada de acesso ao SQL Server 2016 (via pyodbc) - camada de dados."""

import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pyodbc

from src.config import CONTRATANTE
from src.utils import (
    chave_texto,
    lista_eclics,
    para_data,
    parse_num,
    so_digitos,
)


class ErroBanco(Exception):
    """Falha de conexao ou de operacao no banco."""


# ------------------------------------------------------------------ caminhos
# Raiz do projeto (pai de src/)
PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def recurso(nome: str) -> str:
    """Caminho de um recurso na raiz do projeto (ex.: config.json).

    Tanto em execucao normal quanto no .exe congelado.
    """
    base = getattr(sys, "_MEIPASS", PROJECT_ROOT)
    return os.path.join(base, nome)


def recurso_assets(nome: str) -> str:
    """Caminho de um asset estatico (logo, template, icone) na pasta assets/."""
    base = getattr(sys, "_MEIPASS", PROJECT_ROOT)
    return os.path.join(base, "assets", nome)


def caminho_config() -> str:
    """config.json editavel pelo usuario.

    Quando congelado (.exe), fica na mesma pasta do executavel; em execucao
    normal, na pasta do projeto. O modelo embutido no .exe serve apenas como
    fallback inicial.
    """
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "config.json")
    return os.path.join(PROJECT_ROOT, "config.json")


CONFIG_PATH: str = caminho_config()
CONFIG_EMBUTIDO: str = recurso("config.json")

CONFIG_PADRAO: dict[str, Any] = {
    "driver": "ODBC Driver 17 for SQL Server",
    "server": "localhost",
    "port": "",
    "database": "EBM",
    "username": "",
    "password": "",
    "trusted_connection": False,
    "encrypt": True,
    "trust_server_certificate": False,
    "connection_timeout": 15,
}


def carregar_config() -> dict[str, Any]:
    """Le o config.json do usuario; se nao existir, usa o embutido; senao o padrao."""
    cfg: dict[str, Any] = dict(CONFIG_PADRAO)
    for caminho in (CONFIG_PATH, CONFIG_EMBUTIDO):
        if not caminho or not os.path.exists(caminho):
            continue
        try:
            with open(caminho, encoding="utf-8") as f:
                dados: dict[str, Any] = json.load(f)
            for k, v in dados.items():
                if not k.startswith("_"):
                    cfg[k] = v
            break
        except Exception as e:
            raise ErroBanco(f"{os.path.basename(caminho)} invalido: {e}")
    return cfg


def gravar_config(cfg: dict[str, Any]) -> None:
    """Grava a configuracao no config.json do usuario."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def connection_string(cfg: dict[str, Any] | None = None) -> str:
    """Monta a string de conexao ODBC para o SQL Server.

    `server` e o nome completo do servidor/instancia. Exemplos aceitos:
        localhost
        localhost,1433
        localhost\\SQLEXPRESS
        (localdb)\\MSSQLLocalDB
        SERVIDOR\\INSTANCIA

    `port` so e acrescido quando o server nao traz instancia, virgula nem localdb.
    """
    cfg = cfg or carregar_config()
    driver: str = str(cfg.get("driver") or CONFIG_PADRAO["driver"])
    server: str = str(cfg.get("server") or "localhost").strip()
    porta: str = str(cfg.get("port") or "").strip()
    if porta and "\\" not in server and "," not in server and "localdb" not in server.lower():
        server = f"{server},{porta}"
    partes: list[str] = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={cfg.get('database') or 'EBM'}",
    ]
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
    """Verifica se existe algum driver ODBC instalado."""
    try:
        return bool(pyodbc.drivers())
    except Exception:
        return False


def drivers_disponiveis() -> list[str]:
    """Lista os drivers ODBC disponíveis."""
    try:
        return list(pyodbc.drivers())
    except Exception:
        return []


# ------------------------------------------------------------------ DDL
DDL: list[str] = [
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
    id                INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_companies PRIMARY KEY,
    nome              NVARCHAR(200) NOT NULL,
    cnpj              NVARCHAR(14) NOT NULL,
    responsavel       NVARCHAR(200) NOT NULL,
    email_contato     NVARCHAR(200) NOT NULL,
    usuario_eclic     NVARCHAR(100) COLLATE Latin1_General_CI_AS NULL,
    po_codigo         NVARCHAR(50)  COLLATE Latin1_General_CI_AS NOT NULL,
    po_inicio         DATE NOT NULL,
    po_fim            DATE NOT NULL,
    po_valor_total    DECIMAL(18,2) NOT NULL,
    po_objeto         NVARCHAR(500) NOT NULL,
    valor_hora        DECIMAL(18,2) NOT NULL,
    tipo_faturamento  NVARCHAR(20)  NOT NULL CONSTRAINT DF_companies_tipo_faturamento DEFAULT ('HORISTA'),
    valor_fixo_mensal DECIMAL(18,2) NULL,
    notificado_vencimento_em DATE NULL,
    gerente_aprovador NVARCHAR(200) NULL,
    diretor_aprovador NVARCHAR(200) NULL,
    criado_em         DATETIME2(0) NOT NULL CONSTRAINT DF_companies_criado_em DEFAULT (SYSDATETIME()),
    atualizado_em     DATETIME2(0) NOT NULL CONSTRAINT DF_companies_atualizado_em DEFAULT (SYSDATETIME()),
    CONSTRAINT UQ_companies_cnpj   UNIQUE (cnpj),
    CONSTRAINT UQ_companies_po     UNIQUE (po_codigo),
    CONSTRAINT CK_companies_valor  CHECK (po_valor_total >= 0),
    CONSTRAINT CK_companies_vh     CHECK (valor_hora >= 0),
    CONSTRAINT CK_companies_datas  CHECK (po_fim >= po_inicio),
    CONSTRAINT CK_companies_tipo   CHECK (tipo_faturamento IN ('HORISTA','MENSALISTA'))
);""",
    # ---------------- vinculo empresa <-> usuario e-clic (1:N)
    """IF OBJECT_ID('dbo.companies_login_eclic','U') IS NULL
CREATE TABLE dbo.companies_login_eclic (
    id            INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_companies_login_eclic PRIMARY KEY,
    company_id    INT NOT NULL CONSTRAINT FK_companies_login_eclic_company REFERENCES dbo.companies(id) ON DELETE CASCADE,
    usuario_eclic NVARCHAR(100) COLLATE Latin1_General_CI_AS NOT NULL,
    criado_em     DATETIME2(0) NOT NULL CONSTRAINT DF_companies_login_eclic_criado DEFAULT (SYSDATETIME()),
    CONSTRAINT UQ_companies_login_eclic_eclic UNIQUE (usuario_eclic)
);""",
    """IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_companies_login_eclic_company'
              AND object_id=OBJECT_ID('dbo.companies_login_eclic'))
CREATE INDEX IX_companies_login_eclic_company ON dbo.companies_login_eclic(company_id);""",
    # ---- migracoes de bancos criados com o modelo antigo (1 e-clic por empresa)
    """IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE name='UQ_companies_eclic')
ALTER TABLE dbo.companies DROP CONSTRAINT UQ_companies_eclic;""",
    """IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.companies')
              AND name='usuario_eclic' AND is_nullable=0)
ALTER TABLE dbo.companies ALTER COLUMN usuario_eclic
    NVARCHAR(100) COLLATE Latin1_General_CI_AS NULL;""",
    """IF NOT EXISTS (SELECT 1 FROM dbo.companies_login_eclic)
INSERT INTO dbo.companies_login_eclic (company_id, usuario_eclic)
SELECT c.id, c.usuario_eclic FROM dbo.companies c
WHERE c.usuario_eclic IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM dbo.companies_login_eclic u
                  WHERE u.usuario_eclic = c.usuario_eclic);""",
    # ---- migracao: adicionar colunas de tipo de faturamento se nao existirem
    """IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.companies') AND name='tipo_faturamento')
ALTER TABLE dbo.companies ADD tipo_faturamento NVARCHAR(20) NOT NULL CONSTRAINT DF_companies_tipo_faturamento DEFAULT ('HORISTA');""",
    """IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.companies') AND name='valor_fixo_mensal')
ALTER TABLE dbo.companies ADD valor_fixo_mensal DECIMAL(18,2) NULL;""",
    """IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.companies') AND name='notificado_vencimento_em')
ALTER TABLE dbo.companies ADD notificado_vencimento_em DATE NULL;""",
    """IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.companies') AND name='gerente_aprovador')
ALTER TABLE dbo.companies ADD gerente_aprovador NVARCHAR(200) NULL;""",
    """IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.companies') AND name='diretor_aprovador')
ALTER TABLE dbo.companies ADD diretor_aprovador NVARCHAR(200) NULL;""",
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
    CONSTRAINT UQ_bm_items UNIQUE (bm_id, projeto, descricao)
);""",
    # ---- campo de status de validacao nos boletins
    """IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.bms') AND name='status_validacao')
ALTER TABLE dbo.bms ADD status_validacao NVARCHAR(20) NOT NULL CONSTRAINT DF_bms_status_validacao DEFAULT ('PENDENTE');""",
    """IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name='CK_bms_status_validacao')
ALTER TABLE dbo.bms ADD CONSTRAINT CK_bms_status_validacao CHECK (status_validacao IN ('VALIDADO','PENDENTE','NAO_VALIDADO'));""",
    # ---- tabela de log de validacao de boletins
    """IF OBJECT_ID('dbo.bm_validacao_log','U') IS NULL
CREATE TABLE dbo.bm_validacao_log (
    id            INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bm_validacao_log PRIMARY KEY,
    bm_id         INT NOT NULL CONSTRAINT FK_bm_validacao_log_bm REFERENCES dbo.bms(id) ON DELETE CASCADE,
    usuario_login NVARCHAR(100) NOT NULL,
    status_anterior NVARCHAR(20),
    status_novo   NVARCHAR(20) NOT NULL,
    validado_em   DATETIME2(0) NOT NULL CONSTRAINT DF_bm_validacao_log_validado_em DEFAULT (SYSDATETIME())
);""",
    # ---- colunas de PDF assinado nos boletins
    """IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.bms') AND name='pdf_assinado')
ALTER TABLE dbo.bms ADD pdf_assinado VARBINARY(MAX) NULL;""",
    """IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.bms') AND name='pdf_assinado_nome')
ALTER TABLE dbo.bms ADD pdf_assinado_nome NVARCHAR(255) NULL;""",
    """IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.bms') AND name='data_assinatura')
ALTER TABLE dbo.bms ADD data_assinatura DATETIME2(0) NULL;""",
    """IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.bms') AND name='assinado_por')
ALTER TABLE dbo.bms ADD assinado_por NVARCHAR(100) NULL;""",
]


# ------------------------------------------------------------------ banco
class Banco:
    """Encapsula a conexao com o SQL Server e as operacoes de dominio."""

    def __init__(self, cfg: dict[str, Any] | None = None) -> None:
        self.cfg: dict[str, Any] = cfg or carregar_config()
        self.con: Any = None

    # ------------------------------------------------------------ conexao
    def conectar(self) -> Any:
        """Abre e retorna a conexao com o banco de dados."""
        if self.con is not None:
            return self.con
        cs: str = connection_string(self.cfg)
        try:
            self.con = pyodbc.connect(
                cs,
                timeout=int(self.cfg.get("connection_timeout", 15)),
                autocommit=False,
            )
        except pyodbc.Error as e:
            raise ErroBanco(self._traduzir_erro(e))
        return self.con

    def _traduzir_erro(self, e: Exception) -> str:
        """Traduz o erro do driver em uma mensagem acionavel para o usuario."""
        msg: str = str(e)
        banco: str = str(self.cfg.get("database") or "EBM")

        if "IM002" in msg or "Data source name not found" in msg or "Can't open" in msg:
            return (
                "Driver ODBC nao encontrado.\n"
                f"Drivers instalados: {drivers_disponiveis() or 'nenhum'}\n"
                "Instale o 'Microsoft ODBC Driver 17 for SQL Server'."
            )

        # 4060 = banco nao existe (vem junto de 'Login failed' no SQL Server 2016,
        # por isso precisa ser testado ANTES da traducao de autenticacao)
        if "4060" in msg or "Cannot open database" in msg:
            return (
                f"O banco '{banco}' nao existe no servidor "
                f"{self.cfg.get('server')}.\n\n"
                "Peça ao DBA para criar o banco (solicitacao_dba.sql) ou rode\n"
                "  python -m src.__main__\n"
                "com um usuario que tenha permissao de CREATE DATABASE."
            )

        if "18456" in msg or "Login failed for user" in msg or "28000" in msg:
            return (
                "Falha de autenticacao no servidor "
                f"{self.cfg.get('server')}.\n"
                "Verifique 'username'/'password' ou use 'trusted_connection: true' "
                "(autenticacao Windows)."
            )

        if (
            "08001" in msg
            or "Server not found" in msg
            or "Named Pipes" in msg
            or "timeout" in msg.lower()
            or "expired" in msg.lower()
        ):
            return (
                "Servidor SQL Server nao encontrado ou sem resposta.\n"
                f"Verifique 'server' e 'port' em config.json (atual: "
                f"{self.cfg.get('server')}).\n"
                "Para instancia nomeada, o SQL Browser (UDP 1434) precisa estar "
                "acessivel na rede."
            )

        return msg

    def fechar(self) -> None:
        """Fecha a conexao com o banco de dados."""
        if self.con is not None:
            try:
                self.con.close()
            except Exception:
                pass
            self.con = None

    def _exec(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        """Executa um comando SQL com parametros."""
        cur = self.con.cursor()
        cur.execute(sql, params)
        return cur

    def _todos(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Executa uma consulta e retorna todas as linhas como lista de dicionarios."""
        cur = self._exec(sql, params)
        cols: list[str] = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def _um(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        """Executa uma consulta e retorna a primeira linha como dicionario."""
        r: list[dict[str, Any]] = self._todos(sql, params)
        return r[0] if r else None

    def criar_esquema(self) -> None:
        """Cria as tabelas se ainda nao existirem (idempotente)."""
        self.conectar()
        for ddl in DDL:
            self._exec(ddl)
        self.con.commit()

    # ------------------------------------------------------------ usuarios
    def tem_usuario(self) -> bool:
        """Verifica se ja existe pelo menos um usuario cadastrado."""
        self.conectar()
        return bool(self._um("SELECT COUNT(*) AS total FROM dbo.users")["total"] > 0)

    def criar_usuario(
        self,
        nome_completo: str,
        login: str,
        email: str,
        senha_hash: str,
        is_admin: bool = False,
    ) -> int:
        """Cria um novo usuario e retorna o ID gerado."""
        self.conectar()
        sql: str = (
            "INSERT INTO dbo.users (nome_completo, login, email, senha_hash, is_admin) "
            "OUTPUT INSERTED.id VALUES (?,?,?,?,?)"
        )
        cur = self._exec(
            sql, (nome_completo, login, email, senha_hash, 1 if is_admin else 0)
        )
        novo_id: int = cur.fetchone()[0]
        self.con.commit()
        return novo_id

    def buscar_usuario(self, login: str) -> dict[str, Any] | None:
        """Busca um usuario pelo login."""
        self.conectar()
        return self._um("SELECT * FROM dbo.users WHERE login = ?", (login,))

    def obter_perfil_usuario(self, login: str) -> dict[str, Any] | None:
        """Retorna o dicionario do usuario (com is_admin) ou None se nao existir."""
        self.conectar()
        return self._um("SELECT * FROM dbo.users WHERE login = ?", (login,))

    def listar_usuarios(self) -> list[dict[str, Any]]:
        """Lista todos os usuarios ordenados por nome."""
        self.conectar()
        return self._todos("SELECT * FROM dbo.users ORDER BY nome_completo")

    def resetar_senha(self, login: str, senha_hash: str) -> bool:
        """Admin redefine a senha de um usuario. Retorna True se alterou."""
        self.conectar()
        cur = self._exec(
            "UPDATE dbo.users SET senha_hash = ? WHERE login = ?", (senha_hash, login)
        )
        self.con.commit()
        return bool(cur.rowcount > 0)

    def excluir_usuario(self, login: str) -> bool:
        """Exclui um usuario do sistema. Retorna True se removeu."""
        self.conectar()
        cur = self._exec("DELETE FROM dbo.users WHERE login = ?", (login,))
        self.con.commit()
        return bool(cur.rowcount > 0)

    def atualizar_usuario(
        self,
        login: str,
        nome_completo: str,
        email: str,
        is_admin: bool = False,
        senha_hash: str | None = None,
    ) -> bool:
        """Atualiza os dados de um usuario existente."""
        self.conectar()
        if senha_hash:
            cur = self._exec(
                "UPDATE dbo.users SET nome_completo=?, email=?, is_admin=?, senha_hash=? WHERE login=?",
                (nome_completo, email, 1 if is_admin else 0, senha_hash, login),
            )
        else:
            cur = self._exec(
                "UPDATE dbo.users SET nome_completo=?, email=?, is_admin=? WHERE login=?",
                (nome_completo, email, 1 if is_admin else 0, login),
            )
        self.con.commit()
        return bool(cur.rowcount > 0)

    # ------------------------------------------------------------ empresas
    def listar_empresas(
        self, busca: str | None = None, company_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Lista empresas, opcionalmente filtrando por busca ou ID."""
        self.conectar()
        if company_id is not None:
            return self._todos(
                "SELECT * FROM dbo.companies WHERE id = ? ORDER BY nome", (company_id,)
            )
        if busca:
            pad: str = f"%{busca}%"
            return self._todos(
                "SELECT * FROM dbo.companies "
                "WHERE responsavel LIKE ? OR nome LIKE ? OR cnpj LIKE ? "
                "ORDER BY nome",
                (pad, pad, pad),
            )
        return self._todos("SELECT * FROM dbo.companies ORDER BY nome")

    def buscar_empresa(self, emp_id: int) -> dict[str, Any] | None:
        """Busca uma empresa pelo ID."""
        self.conectar()
        return self._um("SELECT * FROM dbo.companies WHERE id = ?", (emp_id,))

    def empresa_por_cnpj(self, cnpj: str) -> dict[str, Any] | None:
        """Busca empresa pelo CNPJ."""
        self.conectar()
        return self._um(
            "SELECT * FROM dbo.companies WHERE cnpj = ?", (so_digitos(cnpj),)
        )

    def empresa_por_eclic(self, usuario_eclic: str) -> dict[str, Any] | None:
        """Empresa prestadora de um Usuario E-clic (via vinculo 1:N)."""
        self.conectar()
        return self._um(
            "SELECT c.* FROM dbo.companies c "
            "JOIN dbo.companies_login_eclic u ON u.company_id = c.id "
            "WHERE u.usuario_eclic = ?",
            (usuario_eclic,),
        )

    def mapa_eclic_empresa(self) -> dict[str, int]:
        """Mapa {usuario_eclic em maiusculas: company_id} para o lote.

        Um E-clic pertence a no maximo uma empresa (garantido pelo indice unico).
        """
        self.conectar()
        return {
            chave_texto(r["usuario_eclic"]): r["company_id"]
            for r in self._todos("SELECT company_id, usuario_eclic "
                                 "FROM dbo.companies_login_eclic")
        }

    def eclics_da_empresa(self, company_id: int) -> list[str]:
        """Lista de Usuarios E-clic vinculados a uma empresa."""
        self.conectar()
        return [
            r["usuario_eclic"]
            for r in self._todos(
                "SELECT usuario_eclic FROM dbo.companies_login_eclic "
                "WHERE company_id = ? ORDER BY usuario_eclic",
                (company_id,),
            )
        ]

    def duplicado_empresa(
        self,
        cnpj: str,
        po_codigo: str,
        usuario_eclic: str | list[str],
        ignorar_id: int | None = None,
    ) -> str | None:
        """Retorna o campo duplicado ou None.

        `usuario_eclic` pode ser um login ou uma lista de logins.
        `ignorar_id` ignora a propria empresa (usado na edicao).
        """
        self.conectar()
        eclics: list[str] = lista_eclics(usuario_eclic)

        def _id(sql: str, params: tuple[Any, ...]) -> int | None:
            r: dict[str, Any] | None = self._um(sql, params)
            return r["id"] if r else None

        achou: int | None = _id(
            "SELECT id FROM dbo.companies WHERE cnpj = ?", (so_digitos(cnpj),)
        )
        if achou is not None and achou != ignorar_id:
            return "CNPJ"
        achou = _id("SELECT id FROM dbo.companies WHERE po_codigo = ?", (po_codigo,))
        if achou is not None and achou != ignorar_id:
            return "Código PO"
        for e in eclics:
            achou = _id(
                "SELECT c.id FROM dbo.companies_login_eclic u "
                "JOIN dbo.companies c ON c.id = u.company_id "
                "WHERE u.usuario_eclic = ?",
                (e,),
            )
            if achou is not None and achou != ignorar_id:
                return f"Usuário E-clic ({e})"
        return None

    def _gravar_eclics(self, company_id: int, eclics: list[str]) -> None:
        """Substitui o vinculo da empresa com seus Usuarios E-clic."""
        self._exec(
            "DELETE FROM dbo.companies_login_eclic WHERE company_id = ?",
            (company_id,),
        )
        for e in eclics:
            self._exec(
                "INSERT INTO dbo.companies_login_eclic (company_id, usuario_eclic) "
                "VALUES (?,?)",
                (company_id, e),
            )

    def criar_empresa(self, d: dict[str, Any]) -> int:
        """Cria uma nova empresa e retorna o ID gerado."""
        self.conectar()
        eclics: list[str] = lista_eclics(d.get("usuario_eclic"))
        sql: str = (
            "INSERT INTO dbo.companies "
            "(nome, cnpj, responsavel, email_contato, usuario_eclic, po_codigo, "
            " po_inicio, po_fim, po_valor_total, po_objeto, valor_hora, "
            " tipo_faturamento, valor_fixo_mensal, gerente_aprovador, diretor_aprovador) "
            "OUTPUT INSERTED.id VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        )
        params: tuple[Any, ...] = (
            d["nome"],
            so_digitos(d["cnpj"]),
            d["responsavel"],
            d["email_contato"],
            eclics[0] if eclics else None,
            d["po_codigo"],
            para_data(d["po_inicio"]),
            para_data(d["po_fim"]),
            parse_num(d["po_valor_total"]),
            d["po_objeto"],
            parse_num(d["valor_hora"]),
            d.get("tipo_faturamento", "HORISTA"),
            parse_num(d.get("valor_fixo_mensal")),
            d.get("gerente_aprovador"),
            d.get("diretor_aprovador"),
        )
        cur = self._exec(sql, params)
        novo_id: int = cur.fetchone()[0]
        self._gravar_eclics(novo_id, eclics)
        self.con.commit()
        return novo_id

    def atualizar_empresa(self, emp_id: int, d: dict[str, Any]) -> None:
        """Atualiza os dados de uma empresa existente."""
        self.conectar()
        eclics: list[str] = lista_eclics(d.get("usuario_eclic"))
        sql: str = (
            "UPDATE dbo.companies SET nome=?, cnpj=?, responsavel=?, email_contato=?, "
            "usuario_eclic=?, po_codigo=?, po_inicio=?, po_fim=?, po_valor_total=?, "
            "po_objeto=?, valor_hora=?, tipo_faturamento=?, valor_fixo_mensal=?, "
            "gerente_aprovador=?, diretor_aprovador=?, "
            "atualizado_em=SYSDATETIME() WHERE id=?"
        )
        params: tuple[Any, ...] = (
            d["nome"],
            so_digitos(d["cnpj"]),
            d["responsavel"],
            d["email_contato"],
            eclics[0] if eclics else None,
            d["po_codigo"],
            para_data(d["po_inicio"]),
            para_data(d["po_fim"]),
            parse_num(d["po_valor_total"]),
            d["po_objeto"],
            parse_num(d["valor_hora"]),
            d.get("tipo_faturamento", "HORISTA"),
            parse_num(d.get("valor_fixo_mensal")),
            d.get("gerente_aprovador"),
            d.get("diretor_aprovador"),
            emp_id,
        )
        self._exec(sql, params)
        self._gravar_eclics(emp_id, eclics)
        self.con.commit()

    def excluir_empresa(self, emp_id: int) -> bool:
        """Exclui uma empresa e seus vinculos de E-clic. Retorna True se removeu."""
        self.conectar()
        self._exec(
            "DELETE FROM dbo.companies_login_eclic WHERE company_id = ?", (emp_id,)
        )
        cur = self._exec("DELETE FROM dbo.companies WHERE id = ?", (emp_id,))
        self.con.commit()
        return bool(cur.rowcount > 0)

    # ------------------------------------------------------------ vencimento de PO
    def buscar_empresas_proximas_vencimento(self) -> list[dict[str, Any]]:
        """Retorna empresas com PO vencendo em 7 dias (janela ±1 dia) e ainda
        não notificadas hoje."""
        self.conectar()
        hoje: date = date.today()
        inicio: date = hoje + timedelta(days=6)
        fim: date = hoje + timedelta(days=8)
        return self._todos(
            "SELECT id, nome, email_contato, po_codigo, po_fim, po_valor_total "
            "FROM dbo.companies "
            "WHERE po_fim BETWEEN ? AND ? "
            "AND (notificado_vencimento_em IS NULL OR notificado_vencimento_em <> ?) "
            "ORDER BY po_fim",
            (inicio, fim, hoje),
        )

    def marcar_notificado_vencimento(self, company_id: int) -> None:
        """Marca a empresa como notificada de vencimento na data de hoje."""
        self.conectar()
        hoje: date = date.today()
        self._exec(
            "UPDATE dbo.companies SET notificado_vencimento_em = ? WHERE id = ?",
            (hoje, company_id),
        )
        self.con.commit()

    # ------------------------------------------------------------ boletins
    def proximo_rm(self, company_id: int, emissao_iso: str) -> str:
        """Sequencial por empresa: BM-YYYY-NNN. Vazio se a empresa nao tem historico."""
        self.conectar()
        linhas: list[dict[str, Any]] = self._todos(
            "SELECT rm_numero FROM dbo.bms WHERE company_id = ?", (company_id,)
        )
        if not linhas:
            return ""
        ano: str = str(emissao_iso)[:4]
        mx: int = 0
        for l in linhas:
            # pega o ultimo grupo de 3+ digitos (o NNN do BM-YYYY-NNN)
            partes: list[str] = re.findall(r"\d{3,}", str(l.get("rm_numero") or ""))
            if partes:
                mx = max(mx, int(partes[-1]))
        return f"BM-{ano}-{mx + 1:03d}"

    def ultimo_bm(self, company_id: int) -> dict[str, Any] | None:
        """Retorna o ultimo boletim da empresa."""
        self.conectar()
        return self._um(
            "SELECT * FROM dbo.bms WHERE company_id = ? ORDER BY id DESC",
            (company_id,),
        )

    def ultimo_mapa_itens(
        self, company_id: int
    ) -> dict[tuple[str, str], tuple[Decimal | None, Decimal | None]]:
        """(projeto, atividade) -> (horas_acumulada, total_acumulado) do ultimo BM."""
        self.conectar()
        ultimo: dict[str, Any] | None = self.ultimo_bm(company_id)
        if not ultimo:
            return {}
        itens: list[dict[str, Any]] = self._todos(
            "SELECT projeto, descricao, horas_acumulada, total_acumulado "
            "FROM dbo.bm_items WHERE bm_id = ?",
            (ultimo["id"],),
        )
        return {
            (chave_texto(i["projeto"]), chave_texto(i["descricao"])):
            (i["horas_acumulada"], i["total_acumulado"]) for i in itens
        }

    def listar_boletins(self, company_id: int) -> list[dict[str, Any]]:
        """Lista boletins de uma empresa."""
        self.conectar()
        return self._todos(
            "SELECT * FROM dbo.bms WHERE company_id = ? ORDER BY id DESC",
            (company_id,),
        )

    def buscar_bm(self, bm_id: int) -> dict[str, Any] | None:
        """Retorna os dados de um boletim pelo id."""
        self.conectar()
        return self._um("SELECT * FROM dbo.bms WHERE id = ?", (bm_id,))

    def buscar_itens_bm(self, bm_id: int) -> list[dict[str, Any]]:
        """Retorna os itens de um boletim pelo id."""
        self.conectar()
        return self._todos(
            "SELECT projeto, descricao, valor_hora, horas_anterior, horas_periodo "
            "FROM dbo.bm_items WHERE bm_id = ? ORDER BY item_seq",
            (bm_id,),
        )

    def obter_status_validacao_bm(self, bm_id: int) -> str:
        """Retorna o status de validacao atual de um boletim."""
        self.conectar()
        r: dict[str, Any] | None = self._um(
            "SELECT status_validacao FROM dbo.bms WHERE id = ?", (bm_id,)
        )
        return str(r["status_validacao"]) if r else "PENDENTE"

    def atualizar_status_validacao_bm(
        self, bm_id: int, status_novo: str, usuario_login: str
    ) -> str:
        """Atualiza o status de validacao de um boletim e grava log da mudanca."""
        self.conectar()
        r: dict[str, Any] | None = self._um(
            "SELECT status_validacao FROM dbo.bms WHERE id = ?", (bm_id,)
        )
        status_anterior: str | None = str(r["status_validacao"]) if r else None
        self._exec(
            "UPDATE dbo.bms SET status_validacao = ? WHERE id = ?",
            (status_novo, bm_id),
        )
        self._exec(
            "INSERT INTO dbo.bm_validacao_log (bm_id, usuario_login, status_anterior, status_novo) "
            "VALUES (?,?,?,?)",
            (bm_id, usuario_login, status_anterior, status_novo),
        )
        self.con.commit()
        return status_novo

    def salvar_pdf_assinado(
        self,
        bm_id: int,
        pdf_bytes: bytes,
        nome_arquivo: str,
        usuario_login: str,
    ) -> bool:
        """Salva o PDF assinado no boletim."""
        from datetime import datetime as _datetime

        self.conectar()
        self._exec(
            "UPDATE dbo.bms SET pdf_assinado = ?, pdf_assinado_nome = ?, "
            "data_assinatura = ?, assinado_por = ? WHERE id = ?",
            (
                pyodbc.Binary(pdf_bytes),
                nome_arquivo,
                _datetime.now(),
                usuario_login,
                bm_id,
            ),
        )
        self.con.commit()
        return True

    def obter_pdf_assinado(self, bm_id: int) -> dict[str, Any] | None:
        """Retorna os dados do PDF assinado de um boletim."""
        self.conectar()
        return self._um(
            "SELECT pdf_assinado, pdf_assinado_nome, data_assinatura, assinado_por "
            "FROM dbo.bms WHERE id = ?",
            (bm_id,),
        )

    def listar_boletins_assinados(
        self, company_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Lista boletins que possuem PDF assinado."""
        self.conectar()
        if company_id is not None:
            return self._todos(
                "SELECT b.id, b.rm_numero, b.emissao, b.periodo_ini, b.periodo_fim, "
                "b.pdf_assinado_nome, b.data_assinatura, b.assinado_por, b.status_validacao, "
                "c.nome as empresa_nome, c.cnpj as empresa_cnpj "
                "FROM dbo.bms b "
                "JOIN dbo.companies c ON c.id = b.company_id "
                "WHERE b.pdf_assinado IS NOT NULL AND b.company_id = ? "
                "ORDER BY b.data_assinatura DESC",
                (company_id,),
            )
        return self._todos(
            "SELECT b.id, b.rm_numero, b.emissao, b.periodo_ini, b.periodo_fim, "
            "b.pdf_assinado_nome, b.data_assinatura, b.assinado_por, b.status_validacao, "
            "c.nome as empresa_nome, c.cnpj as empresa_cnpj, b.company_id "
            "FROM dbo.bms b "
            "JOIN dbo.companies c ON c.id = b.company_id "
            "WHERE b.pdf_assinado IS NOT NULL "
            "ORDER BY b.data_assinatura DESC"
        )

    def proxima_revisao(
        self,
        company_id: int,
        rm_numero: str,
        periodo_ini: Any,
        periodo_fim: Any,
    ) -> int:
        """Retorna o proximo numero de revisao para um boletim."""
        self.conectar()
        r: dict[str, Any] | None = self._um(
            "SELECT MAX(revisao) AS m FROM dbo.bms "
            "WHERE company_id = ? AND rm_numero = ? AND periodo_ini = ? AND periodo_fim = ?",
            (
                company_id,
                rm_numero,
                para_data(periodo_ini),
                para_data(periodo_fim),
            ),
        )
        if r is None or r["m"] is None:
            return 0
        return int(r["m"]) + 1

    def salvar_bm(
        self,
        emp: dict[str, Any],
        periodo_ini: Any,
        periodo_fim: Any,
        emissao: Any,
        rm_numero: str,
        revisao: int,
        itens: list[tuple[str, str, float, Any, float]],
        origem: str,
        xlsx_bytes: bytes,
        pdf_bytes: bytes,
        totais: tuple[Decimal, Decimal, Decimal, Decimal],
    ) -> int:
        """Grava boletim + itens no SQL Server. `emp` e um dict/Row da empresa."""
        self.conectar()
        ta, tp, tac, saldo = totais
        sql: str = (
            "INSERT INTO dbo.bms "
            "(company_id, rm_numero, periodo_ini, periodo_fim, emissao, revisao, contratante, "
            " snap_nome, snap_cnpj, snap_po, snap_po_inicio, snap_po_fim, snap_valor_total, "
            " snap_objeto, snap_valor_hora, total_anterior, total_periodo, total_acumulado, "
            " saldo, xlsx_blob, pdf_blob, origem) "
            "OUTPUT INSERTED.id VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        )
        params: tuple[Any, ...] = (
            emp["id"],
            rm_numero or "",
            para_data(periodo_ini),
            para_data(periodo_fim),
            para_data(emissao),
            int(revisao),
            CONTRATANTE,
            emp["nome"],
            emp["cnpj"],
            emp["po_codigo"],
            para_data(emp["po_inicio"]),
            para_data(emp["po_fim"]),
            parse_num(emp["po_valor_total"]),
            emp["po_objeto"],
            parse_num(emp["valor_hora"]),
            parse_num(ta),
            parse_num(tp),
            parse_num(tac),
            parse_num(saldo),
            pyodbc.Binary(xlsx_bytes),
            pyodbc.Binary(pdf_bytes),
            origem,
        )
        cur = self._exec(sql, params)
        bm_id: int = cur.fetchone()[0]
        for seq, (proj, descricao, vh, h_ant, h_per) in enumerate(itens, start=1):
            acu: float | None = (
                (h_ant + h_per) if h_ant is not None else h_per
            )  # type: ignore[operator]
            self._exec(
                "INSERT INTO dbo.bm_items "
                "(bm_id, item_seq, projeto, descricao, valor_hora, horas_anterior, horas_periodo, "
                " horas_acumulada, total_anterior, total_periodo, total_acumulado) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    bm_id,
                    seq,
                    proj,
                    descricao,
                    parse_num(vh),
                    parse_num(h_ant, "0.0001"),
                    parse_num(h_per, "0.0001"),
                    parse_num(acu, "0.0001"),
                    parse_num((h_ant * vh) if h_ant is not None else None),
                    parse_num(h_per * vh),
                    parse_num(((h_ant or 0) + h_per) * vh),
                ),
            )
        self.con.commit()
        return bm_id
