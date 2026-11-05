"""Tela de gerenciamento de usuarios (apenas administradores)."""

from typing import Any

import customtkinter as ctk
from tkinter import messagebox

from src.services.auth_service import AuthService
from src.ui.widgets import cabecalho_tela, ttk_treeview
from src.config import FONT, FONT_BOLD


class TelaUsuarios(ctk.CTkFrame):
    """Tela de gerenciamento de usuarios (somente administradores)."""

    def __init__(self, parent: ctk.CTkFrame, app: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: Any = app
        self.tv: Any = None
        self.ent_nome: ctk.CTkEntry | None = None
        self.ent_login: ctk.CTkEntry | None = None
        self.ent_email: ctk.CTkEntry | None = None
        self.ent_senha: ctk.CTkEntry | None = None
        self.var_admin: Any = None
        self.edit_mode: bool = False
        self.edit_login: str | None = None
        self.auth_service: AuthService = self.app.auth_service

    def ao_mostrar(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.app.cabec(self, "Gerenciamento de Usuarios", "TelaHome")
        self.edit_mode = False
        self.edit_login = None

        cols: tuple[str, ...] = ("id", "nome_completo", "login", "email", "perfil", "criado_em")
        headers: dict[str, str] = {
            "id": "ID",
            "nome_completo": "Nome Completo",
            "login": "Login",
            "email": "E-mail",
            "perfil": "Perfil",
            "criado_em": "Criado em",
        }
        widths: dict[str, int] = {"id": 50, "nome_completo": 220, "login": 150, "email": 220, "perfil": 100, "criado_em": 140}

        tv: Any = ttk_treeview(self, cols, headers, [widths[c] for c in cols])
        tv.pack(fill="both", expand=True, padx=12, pady=6)
        self.tv = tv

        def recarrega(*_):
            tv.delete(*tv.get_children())
            for i, r in enumerate(self.auth_service.listar_usuarios()):
                perfil: str = "Administrador" if r.get("is_admin") else "Usuario"
                tag: str = "even" if i % 2 == 0 else "odd"
                tv.insert(
                    "",
                    "end",
                    iid=str(r["login"]),
                    values=(
                        r["id"],
                        r["nome_completo"],
                        r["login"],
                        r["email"],
                        perfil,
                        str(r["criado_em"]),
                    ),
                    tags=(tag,),
                )

        recarrega()

        form: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=12, pady=10)
        form.grid_columnconfigure(1, weight=1)

        lbl_nome = ctk.CTkLabel(form, text="Nome Completo:", font=FONT)
        lbl_nome.grid(row=0, column=0, sticky="w", pady=5)
        self.ent_nome = ctk.CTkEntry(form, font=FONT, width=400)
        self.ent_nome.grid(row=0, column=1, sticky="ew", pady=5, padx=(10, 0))

        lbl_login = ctk.CTkLabel(form, text="Login:", font=FONT)
        lbl_login.grid(row=1, column=0, sticky="w", pady=5)
        self.ent_login = ctk.CTkEntry(form, font=FONT, width=400)
        self.ent_login.grid(row=1, column=1, sticky="ew", pady=5, padx=(10, 0))

        lbl_email = ctk.CTkLabel(form, text="E-mail:", font=FONT)
        lbl_email.grid(row=2, column=0, sticky="w", pady=5)
        self.ent_email = ctk.CTkEntry(form, font=FONT, width=400)
        self.ent_email.grid(row=2, column=1, sticky="ew", pady=5, padx=(10, 0))

        lbl_senha = ctk.CTkLabel(
            form, text="Nova Senha (deixe em branco para nao alterar):", font=FONT
        )
        lbl_senha.grid(row=3, column=0, sticky="w", pady=5)
        self.ent_senha = ctk.CTkEntry(form, font=FONT, width=400, show="*")
        self.ent_senha.grid(row=3, column=1, sticky="ew", pady=5, padx=(10, 0))

        lbl_perfil = ctk.CTkLabel(form, text="Perfil:", font=FONT)
        lbl_perfil.grid(row=4, column=0, sticky="w", pady=5)
        self.var_admin = ctk.BooleanVar(value=False)
        chk_admin = ctk.CTkCheckBox(form, text="Administrador", variable=self.var_admin, font=FONT)
        chk_admin.grid(row=4, column=1, sticky="w", pady=5, padx=(10, 0))

        self._set_form_state(False)

        def ao_selecionar(*_):
            sel = tv.selection()
            if not sel:
                self._set_form_state(False)
                self.edit_mode = False
                self.edit_login = None
                self._limpar_form()
                return
            login: str = str(sel[0])
            usuario = self.auth_service.obter_perfil(login)
            if not usuario:
                return
            self.edit_mode = True
            self.edit_login = login
            self.ent_nome.delete(0, "end")
            self.ent_nome.insert(0, str(usuario.get("nome_completo") or ""))
            self.ent_login.delete(0, "end")
            self.ent_login.insert(0, str(usuario.get("login") or ""))
            self.ent_login.configure(state="disabled")
            self.ent_email.delete(0, "end")
            self.ent_email.insert(0, str(usuario.get("email") or ""))
            self.ent_senha.delete(0, "end")
            self.var_admin.set(bool(usuario.get("is_admin")))
            self._set_form_state(True)

        tv.bind("<<TreeviewSelect>>", ao_selecionar)

        row: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=12)
        ctk.CTkButton(
            row,
            text="Editar",
            fg_color="#1F6AA5",
            hover_color="#15456B",
            font=FONT_BOLD,
            command=self.salvar_edicao,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            row,
            text="Excluir",
            fg_color="#C62828",
            hover_color="#B71C1C",
            font=FONT_BOLD,
            command=self.excluir_usuario,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            row,
            text="Resetar Senha",
            fg_color="#1F6AA5",
            hover_color="#15456B",
            font=FONT_BOLD,
            command=self.resetar_senha_usuario,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            row,
            text="Voltar",
            fg_color="transparent",
            text_color="#1F6AA5",
            hover_color="#15456B",
            command=lambda: self.app.ir("TelaHome"),
        ).pack(side="left", padx=8)

    def _limpar_form(self) -> None:
        self.ent_nome.delete(0, "end")
        self.ent_login.delete(0, "end")
        self.ent_email.delete(0, "end")
        self.ent_senha.delete(0, "end")
        self.var_admin.set(False)

    def _set_form_state(self, habilitado: bool) -> None:
        state: str = "normal" if habilitado else "disabled"
        for ent in (self.ent_nome, self.ent_email, self.ent_senha):
            if ent:
                ent.configure(state=state)
        if self.ent_login:
            self.ent_login.configure(state=("disabled" if self.edit_mode else state))

    def salvar_edicao(self) -> None:
        if not self.edit_mode or not self.edit_login:
            messagebox.showwarning("Aviso", "Selecione um usuario na lista")
            return
        nome: str = self.ent_nome.get().strip()
        email: str = self.ent_email.get().strip()
        senha: str = self.ent_senha.get().strip()
        is_admin: bool = bool(self.var_admin.get())
        if not nome or not email:
            messagebox.showerror("Erro", "Nome e e-mail sao obrigatorios")
            return
        try:
            self.auth_service.atualizar_usuario(
                self.edit_login, nome, email, is_admin=is_admin, senha=senha or None
            )
            messagebox.showinfo("OK", "Usuario atualizado com sucesso")
            self.edit_mode = False
            self.edit_login = None
            self._set_form_state(False)
            self._limpar_form()
            for w in self.winfo_children():
                if isinstance(w, ttk_treeview_type()):
                    w.delete(*w.get_children())
                    for i, r in enumerate(self.auth_service.listar_usuarios()):
                        perfil: str = "Administrador" if r.get("is_admin") else "Usuario"
                        tag: str = "even" if i % 2 == 0 else "odd"
                        w.insert(
                            "",
                            "end",
                            iid=str(r["login"]),
                            values=(
                                r["id"],
                                r["nome_completo"],
                                r["login"],
                                r["email"],
                                perfil,
                                str(r["criado_em"]),
                            ),
                            tags=(tag,),
                        )
        except Exception as exc:
            from src.utils import mensagem_erro_segura

            messagebox.showerror("Erro", mensagem_erro_segura(exc))

    def excluir_usuario(self) -> None:
        if not self.edit_mode or not self.edit_login:
            messagebox.showwarning("Aviso", "Selecione um usuario na lista")
            return
        if self.edit_login == self.app.usuario["login"]:
            messagebox.showerror("Erro", "Voce nao pode excluir o proprio usuario")
            return
        confirm: bool = messagebox.askyesno(
            "Confirmar exclusao",
            f"Tem certeza que deseja excluir o usuario '{self.edit_login}'?",
        )
        if not confirm:
            return
        try:
            self.auth_service.excluir_usuario(self.edit_login, self.app.usuario["login"])
            messagebox.showinfo("OK", "Usuario excluido com sucesso")
            self.edit_mode = False
            self.edit_login = None
            self._set_form_state(False)
            self._limpar_form()
            for w in self.winfo_children():
                if isinstance(w, ttk_treeview_type()):
                    w.delete(*w.get_children())
                    for i, r in enumerate(self.auth_service.listar_usuarios()):
                        perfil: str = "Administrador" if r.get("is_admin") else "Usuario"
                        tag: str = "even" if i % 2 == 0 else "odd"
                        w.insert(
                            "",
                            "end",
                            iid=str(r["login"]),
                            values=(
                                r["id"],
                                r["nome_completo"],
                                r["login"],
                                r["email"],
                                perfil,
                                str(r["criado_em"]),
                            ),
                            tags=(tag,),
                        )
        except Exception as exc:
            from src.utils import mensagem_erro_segura

            messagebox.showerror("Erro", mensagem_erro_segura(exc))

    def resetar_senha_usuario(self) -> None:
        if not self.edit_mode or not self.edit_login:
            messagebox.showwarning("Aviso", "Selecione um usuario na lista")
            return
        nova: str = self.ent_senha.get().strip()
        if len(nova) < 8:
            messagebox.showerror("Erro", "Nova senha deve ter minimo de 8 caracteres")
            return
        try:
            self.auth_service.resetar_senha(self.edit_login, nova)
            messagebox.showinfo("OK", "Senha redefinida com sucesso")
            self.ent_senha.delete(0, "end")
        except Exception as exc:
            from src.utils import mensagem_erro_segura

            messagebox.showerror("Erro", mensagem_erro_segura(exc))


def ttk_treeview_type() -> type[Any]:
    """Retorna o tipo de ttk.Treeview para verificacao isinstance."""
    import tkinter.ttk as ttk

    return ttk.Treeview
