"""Tela de cadastro de novo usuario."""

from typing import Any

import customtkinter as ctk

from src.services.auth_service import AuthService
from src.ui.widgets import campo_entrada, cabecalho_tela


class TelaCadastroUser(ctk.CTkFrame):
    """Tela de cadastro de novo usuario."""

    def __init__(self, parent: ctk.CTkFrame, app: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: Any = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._montar()

    def _montar(self) -> None:
        centro: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        centro.grid(row=0, column=0)

        from src.ui.widgets import logo_ctk

        lg = logo_ctk(190)
        if lg:
            lab = ctk.CTkLabel(centro, image=lg, text="")
            lab.image = lg
            lab.pack(pady=(10, 0))

        ctk.CTkLabel(
            centro,
            text="Cadastro de usuario",
            font=("Segoe UI", 20, "bold"),
            text_color="#1F6AA5",
        ).pack(pady=10)

        box: ctk.CTkFrame = ctk.CTkFrame(centro, fg_color="transparent")
        box.pack()
        box.grid_columnconfigure(1, weight=1)

        self.nome_entry: ctk.CTkEntry = campo_entrada(
            box, "Nome Completo*", 0, largura=380
        )
        self.login_entry: ctk.CTkEntry = campo_entrada(box, "Login*", 1, largura=380)
        self.email_entry: ctk.CTkEntry = campo_entrada(box, "E-mail*", 2, largura=380)
        self.s1_entry: ctk.CTkEntry = campo_entrada(
            box, "Senha* (minimo 8)", 3, largura=380, show="*"
        )
        self.s2_entry: ctk.CTkEntry = campo_entrada(
            box, "Confirmar Senha*", 4, largura=380, show="*"
        )

        ctk.CTkButton(
            box,
            text="Salvar e entrar",
            fg_color="#1F6AA5",
            hover_color="#15456B",
            font=("Segoe UI", 12, "bold"),
            width=380,
            command=self.salvar,
        ).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(18, 0))

    def salvar(self) -> None:
        """Cadastra um novo usuario."""
        nome: str = self.nome_entry.get().strip()
        lg: str = self.login_entry.get().strip()
        em: str = self.email_entry.get().strip()
        s1: str = self.s1_entry.get()
        s2: str = self.s2_entry.get()

        auth: AuthService = self.app.auth_service

        if not all([nome, lg, em, s1, s2]):
            from tkinter import messagebox

            messagebox.showerror("Erro", "Preencha todos os campos")
            return

        try:
            auth.cadastrar_usuario(nome, lg, em, s1)
            self.app.usuario = auth.obter_perfil(lg)
            is_admin: bool = not self.app.banco.tem_usuario()
            from tkinter import messagebox

            messagebox.showinfo(
                "OK",
                "Usuario cadastrado"
                + (" (administrador)" if is_admin else ""),
            )
            self.app.ir("TelaHome")
        except ValueError as exc:
            from tkinter import messagebox

            messagebox.showerror("Erro", str(exc))
        except Exception as exc:
            from tkinter import messagebox

            messagebox.showerror("Erro", str(exc))
