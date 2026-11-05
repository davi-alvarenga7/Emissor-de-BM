"""Tela de emissao de boletins em lote."""

from typing import Any

import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import date

from src.ui.widgets import cabecalho_tela
from src.config import AZUL, AZUL_ESCURO, FONT, FONT_BOLD
from src.utils import fmt_br, mensagem_erro_segura


class TelaLote(ctk.CTkFrame):
    """Tela de emissao de boletins em lote."""

    def __init__(self, parent: ctk.CTkFrame, app: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: Any = app

    def ao_mostrar(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.app.cabec(self, "Emissao de Boletins em Lote", "TelaHome")
        ctk.CTkLabel(
            self,
            text="Anexe N planilhas 'horas por item' "
            "(todas com a mesma data inicial/final).",
            text_color=AZUL,
        ).pack(pady=6)
        ctk.CTkButton(
            self,
            text="Selecionar arquivos...",
            fg_color=AZUL,
            hover_color=AZUL_ESCURO,
            font=FONT_BOLD,
            command=self.processar,
        ).pack(pady=8)
        self.log: ctk.CTkTextbox = ctk.CTkTextbox(
            self, font=("Consolas", 10), height=300
        )
        self.log.pack(fill="both", expand=True, padx=12, pady=8)

    def processar(self) -> None:
        paths: tuple[str, ...] = filedialog.askopenfilenames(
            filetypes=[("Excel", "*.xlsx")]
        )
        if not paths:
            return
        try:
            from src.services.boletim_service import BoletimService

            service: BoletimService = BoletimService(self.app.banco)
            resultado: dict[str, Any] = service.processar_lote(list(paths))
            self.log.delete("1.0", "end")
            self.log.insert("end", resultado["mensagem"])
            messagebox.showinfo("Lote concluido", resultado["mensagem"])
        except Exception as exc:
            messagebox.showerror("Erro no lote", mensagem_erro_segura(exc))
