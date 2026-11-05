"""Aplicacao principal E-BM - camada de interface."""

import os
import sys
import threading
from datetime import date, datetime, timedelta
from typing import Any

import customtkinter as ctk
from tkinter import messagebox

from src.config import APP_TITLE, APP_GEOMETRY, AZUL, AZUL_ESCURO
from src.database import Banco, ErroBanco, recurso, recurso_assets
from src.services.auth_service import AuthService
from src.services.boletim_service import BoletimService
from src.utils import mensagem_erro_segura

# Importacao tardia das telas para evitar importacao circular
from src.ui.telas.login import TelaLogin  # noqa: F401
from src.ui.telas.cadastro_user import TelaCadastroUser  # noqa: F401
from src.ui.telas.home import TelaHome  # noqa: F401
from src.ui.telas.cad_empresa import TelaCadEmpresa  # noqa: F401
from src.ui.telas.empresas import TelaEmpresas  # noqa: F401
from src.ui.telas.editar import TelaEditar  # noqa: F401
from src.ui.telas.usuarios import TelaUsuarios  # noqa: F401
from src.ui.telas.boletins import TelaBoletins  # noqa: F401
from src.ui.telas.visualizar_bm import TelaVisualizarBM  # noqa: F401
from src.ui.telas.boletins_assinados import TelaBoletinsAssinados  # noqa: F401
from src.ui.telas.manual import TelaManual  # noqa: F401
from src.ui.telas.lote import TelaLote  # noqa: F401

from src.ui.widgets import logo_ctk


class App(ctk.CTk):
    """Classe principal da aplicacao E-BM.

    Gerencia a navegacao entre telas, inicializacao do banco
    e servicos de negocio.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(APP_GEOMETRY)
        try:
            self.iconbitmap(recurso_assets("logo.ico"))
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self.ao_fechar)

        # Camadas
        self.banco: Banco = Banco()
        self.auth_service: AuthService = AuthService(self.banco)
        self.boletim_service: BoletimService = BoletimService(self.banco)

        # Estado da sessao
        self.usuario: dict[str, Any] | None = None
        self.company_id: int | None = None
        self.user_is_admin: bool = False

        # Container de telas
        self.container: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.telas: dict[str, Any] = {}
        for cls in (
            TelaLogin,
            TelaCadastroUser,
            TelaHome,
            TelaCadEmpresa,
            TelaEmpresas,
            TelaEditar,
            TelaUsuarios,
            TelaBoletins,
            TelaVisualizarBM,
            TelaBoletinsAssinados,
            TelaManual,
            TelaLote,
        ):
            f: Any = cls(self.container, self)
            self.telas[cls.__name__] = f
            f.grid(row=0, column=0, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        # Mostra a janela imediatamente; a conexao ao banco roda em background
        self.ir("TelaLogin" if self.banco.tem_usuario() else "TelaCadastroUser")
        threading.Thread(target=self._conectar_bd_background, daemon=True).start()

    # ------------------------------------------------------------------ banco
    def _conectar_bd_background(self) -> None:
        """Tenta conectar ao banco sem bloquear a thread principal da UI."""
        ok: bool
        msg: str | None
        ok, msg = self.conectar_bd()
        self.after(0, lambda: self._apos_conexao_bd(ok, msg))

    def _apos_conexao_bd(self, ok: bool, msg: str | None) -> None:
        if not ok:
            self.mostrar_falha_bd(msg or "Erro desconhecido")

    def conectar_bd(self) -> tuple[bool, str | None]:
        """Retorna (True, None) se conectou, ou (False, mensagem_erro) se falhou."""
        try:
            self.banco.conectar()
        except ErroBanco as e:
            return False, str(e)
        except Exception as e:
            return False, str(e)
        try:
            self.banco.criar_esquema()
        except Exception as e:
            return False, f"Nao foi possivel criar/verificar as tabelas:\n{e}"
        return True, None

    def mostrar_falha_bd(self, msg: str) -> None:
        """Exibe dialog de falha de conexao com o banco."""
        dlg: ctk.CTkToplevel = ctk.CTkToplevel(self)
        dlg.title("Banco de dados nao configurado")
        dlg.geometry("660x360")
        dlg.transient(self)
        ctk.CTkLabel(
            dlg, text="E-BM - Configuracao do SQL Server 2016",
            font=("Segoe UI", 14, "bold"), text_color=AZUL,
        ).pack(pady=12)
        txt: ctk.CTkTextbox = ctk.CTkTextbox(dlg, font=("Consolas", 10))
        txt.pack(padx=15, fill="both", expand=True)
        txt.insert("1.0", msg)
        txt.insert(
            "end",
            "\n\nPara configurar:\n"
            "1. Edite o arquivo config.json (driver, server, port, database, "
            "usuario e senha).\n"
            "2. Crie o banco 'EBM' no SQL Server.\n"
            "3. Execute schema_sqlserver2016.sql no SSMS.\n"
            "4. Reinicie o E-BM.",
        )
        txt.configure(state="disabled")
        row: ctk.CTkFrame = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(pady=14)
        ctk.CTkButton(
            row,
            text="Abrir config.json",
            fg_color=AZUL,
            hover_color=AZUL_ESCURO,
            font=("Segoe UI", 12, "bold"),
            command=self.abrir_config,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            row,
            text="Sair",
            fg_color="transparent",
            text_color=AZUL,
            hover_color=AZUL_ESCURO,
            command=self.destroy,
        ).pack(side="left", padx=8)
        dlg.grab_set()

    def abrir_config(self) -> None:
        from src.database import caminho_config

        alvo: str = caminho_config()
        if not os.path.exists(alvo):
            with open(alvo, "w", encoding="utf-8") as f:
                f.write(
                    '{\n  "driver": "ODBC Driver 17 for SQL Server",\n'
                    '  "server": "localhost",\n  "port": "1433",\n'
                    '  "database": "EBM",\n  "username": "",\n  "password": ""\n}\n'
                )
        os.startfile(alvo)

    def ao_fechar(self) -> None:
        try:
            self.banco.fechar()
        except Exception:
            pass
        self.destroy()

    # ------------------------------------------------------------------ navegacao
    def ir(self, nome: str) -> None:
        if nome == "TelaHome" and not self.usuario:
            nome = "TelaLogin"
        t: Any = self.telas[nome]
        if hasattr(t, "ao_mostrar"):
            t.ao_mostrar()
        t.tkraise()

    def cabec(
        self,
        parent: ctk.CTkFrame,
        titulo: str,
        voltar: str = "TelaHome",
    ) -> None:
        """Cria cabecalho padrao para as telas filhas."""
        top: ctk.CTkFrame = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", padx=15, pady=(10, 6))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(
            top, text="← Voltar", width=110,
            command=lambda: self.ir(voltar),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            top, text=titulo, font=("Segoe UI", 16, "bold"), text_color=AZUL
        ).grid(row=0, column=1, sticky="w", padx=15)
        lg: Any = logo_ctk(120)
        if lg:
            lab: ctk.CTkLabel = ctk.CTkLabel(top, image=lg, text="")
            lab.image = lg
            lab.grid(row=0, column=2, sticky="e")

    # ------------------------------------------------------------------ geracao de boletim
    def gerar_e_salvar_bm(
        self,
        emp: dict[str, Any],
        pi: Any,
        pf: Any,
        emi: Any,
        rm: str,
        rev: int,
        itens: list[tuple[str, str, float, Any, float]],
        origem: str,
    ) -> int:
        """Gera e salva um boletim de mediacao."""
        service: BoletimService = self.boletim_service
        return service.gerar_e_salvar_bm(emp, pi, pf, emi, rm, rev, itens, origem)


def main() -> None:
    """Ponto de entrada da aplicacao."""
    try:
        app: App = App()
        app.mainloop()
    except Exception as e:
        import traceback

        erro_detalhado: str = traceback.format_exc()
        try:
            root_temp: ctk.CTk = ctk.CTk()
            root_temp.withdraw()
            messagebox.showerror(
                "Erro Critico",
                f"Ocorreu um erro fatal ao iniciar a aplicacao:\n\n{e}\n\nDetalhes:\n{erro_detalhado}",
            )
            root_temp.destroy()
        except Exception:
            print(erro_detalhado)
            input("Pressione Enter para sair...")


if __name__ == "__main__":
    main()
