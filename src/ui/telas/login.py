"""Tela de login do sistema."""

from typing import Any

import customtkinter as ctk

from src.services.auth_service import AuthService
from src.ui.widgets import campo_entrada, cabecalho_tela


class TelaLogin(ctk.CTkFrame):
    """Tela de autenticacao do usuario."""

    def __init__(self, parent: ctk.CTkFrame, app: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: Any = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._montar()

    def _montar(self) -> None:
        centro: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        centro.grid(row=0, column=0)

        from src.ui.widgets import logo_ctk  # type: ignore[attr-defined]

        lg = logo_ctk(260)
        if lg:
            lab: ctk.CTkLabel = ctk.CTkLabel(centro, image=lg, text="")
            lab.image = lg
            lab.pack(pady=(14, 0))

        ctk.CTkLabel(
            centro, text="E-BM", font=("Segoe UI", 28, "bold"), text_color="#1F6AA5"
        ).pack(pady=(12, 26))

        box: ctk.CTkFrame = ctk.CTkFrame(centro, fg_color="transparent")
        box.pack()
        box.grid_columnconfigure(1, weight=1)

        self.login_entry: ctk.CTkEntry = campo_entrada(box, "Login", 0, largura=360)
        self.senha_entry: ctk.CTkEntry = campo_entrada(
            box, "Senha", 1, largura=360, show="*"
        )

        ctk.CTkButton(
            box,
            text="Entrar",
            fg_color="#1F6AA5",
            hover_color="#15456B",
            font=("Segoe UI", 12, "bold"),
            width=360,
            command=self.entrar,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(18, 4))

        ctk.CTkButton(
            box,
            text="Cadastrar-se",
            fg_color="transparent",
            text_color="#1F6AA5",
            hover_color="#15456B",
            command=lambda: self.app.ir("TelaCadastroUser"),
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=2)

        ctk.CTkButton(
            box,
            text="Esqueci a senha",
            fg_color="transparent",
            text_color="#1F6AA5",
            hover_color="#15456B",
            command=self.esqueci,
        ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(2, 0))

    def entrar(self) -> None:
        """Tenta autenticar o usuario."""
        lg: str = self.login_entry.get().strip()
        auth: AuthService = self.app.auth_service
        try:
            usuario = auth.autenticar(lg, self.senha_entry.get())
            if not usuario:
                from tkinter import messagebox

                messagebox.showerror("Erro", "Login ou senha invalidos")
                return
            self.app.usuario = usuario
            self.app.user_is_admin = bool(usuario.get("is_admin"))
            if self.app.user_is_admin:
                self.app.company_id = None
                self.app.ir("TelaHome")
            else:
                emp = self.app.banco.empresa_por_eclic(lg)
                if not emp:
                    from tkinter import messagebox

                    messagebox.showerror(
                        "Erro",
                        "Usuario nao vinculado a nenhuma empresa. "
                        "Procure o administrador.",
                    )
                    return
                self.app.company_id = emp["id"]
                self.app.ir("TelaEmpresas")
        except Exception as exc:
            from tkinter import messagebox

            messagebox.showerror("Erro", str(exc))

    def esqueci(self) -> None:
        from tkinter import messagebox

        messagebox.showinfo(
            "Recuperacao de senha",
            "Procure o administrador (primeiro usuario cadastrado) para resetar sua senha.",
        )
