"""Tela inicial (home) do sistema."""

from typing import Any

import customtkinter as ctk

from src.ui.widgets import logo_ctk, cabecalho_tela


class TelaHome(ctk.CTkFrame):
    """Tela inicial com botoes de acao principais."""

    def __init__(self, parent: ctk.CTkFrame, app: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: Any = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

    def ao_mostrar(self) -> None:
        """Reconstroi a tela ao ser exibida."""
        for w in self.winfo_children():
            w.destroy()

        barra: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", padx=15, pady=(14, 8))
        barra.grid_columnconfigure(0, weight=1)

        botoes: ctk.CTkFrame = ctk.CTkFrame(barra, fg_color="transparent")
        botoes.grid(row=0, column=0, sticky="")

        if self.app.user_is_admin:
            for txt, dst in [
                ("Cadastro de Nova Empresa", "TelaCadEmpresa"),
                ("Emissao de Boletins em Lote", "TelaLote"),
            ]:
                ctk.CTkButton(
                    botoes,
                    text=txt,
                    fg_color="#1F6AA5",
                    hover_color="#15456B",
                    font=("Segoe UI", 12, "bold"),
                    width=250,
                    command=lambda d=dst: self.app.ir(d),
                ).pack(side="left", padx=8)

        ctk.CTkButton(
            botoes,
            text="Empresas Cadastradas",
            fg_color="#1F6AA5",
            hover_color="#15456B",
            font=("Segoe UI", 12, "bold"),
            width=250,
            command=lambda: self.app.ir("TelaEmpresas"),
        ).pack(side="left", padx=8)

        if self.app.usuario and self.app.usuario.get("is_admin"):
            ctk.CTkButton(
                botoes,
                text="Usuarios",
                width=250,
                command=lambda: self.app.ir("TelaUsuarios"),
            ).pack(side="left", padx=8)
            ctk.CTkButton(
                botoes,
                text="Boletins Assinados",
                width=250,
                command=lambda: self.app.ir("TelaBoletinsAssinados"),
            ).pack(side="left", padx=8)

        centro: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        centro.grid(row=1, column=0, sticky="nsew")
        centro.grid_rowconfigure(0, weight=1)
        centro.grid_columnconfigure(0, weight=1)

        meio: ctk.CTkFrame = ctk.CTkFrame(centro, fg_color="transparent")
        meio.grid(row=0, column=0)

        lg = logo_ctk(220)
        if lg:
            lab = ctk.CTkLabel(meio, image=lg, text="")
            lab.image = lg
            lab.pack(anchor="center", pady=(0, 10))

        ctk.CTkLabel(
            meio, text="E-BM", font=("Segoe UI", 40, "bold"), text_color="#1F6AA5"
        ).pack(anchor="center")
