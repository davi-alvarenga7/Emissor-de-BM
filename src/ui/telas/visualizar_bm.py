"""Tela de visualizacao e validacao de boletim."""

from typing import Any

import customtkinter as ctk
from tkinter import messagebox, filedialog

from src.ui.widgets import cabecalho_tela
from src.config import AZUL, AZUL_ESCURO, FONT, FONT_BOLD
from src.utils import fmt_br, mensagem_erro_segura


class TelaVisualizarBM(ctk.CTkFrame):
    """Tela para visualizar boletim sem download e validar/nao validar."""

    bm_id: int | None = None
    company_id: int | None = None

    def __init__(self, parent: ctk.CTkFrame, app: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: Any = app

    def ao_mostrar(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        bm_id: int | None = self.bm_id
        cid: int | None = self.company_id
        if not bm_id or not cid:
            self.app.ir("TelaBoletins")
            return
        bm = self.app.banco.buscar_bm(bm_id)
        emp = self.app.banco.buscar_empresa(cid)
        if not bm or not emp:
            self.app.ir("TelaBoletins")
            return
        status: str = str(bm.get("status_validacao") or "PENDENTE")

        if status == "VALIDADO":
            cor_status: str = "#2E7D32"
            txt_status: str = "Validado"
        elif status == "NAO_VALIDADO":
            cor_status = "#C62828"
            txt_status = "Nao Validado"
        else:
            cor_status = "#F9A825"
            txt_status = "Aguardando Validacao"

        self.app.cabec(
            self, f"Visualizar BM — {bm.get('rm_numero') or '(sem RM)'}", "TelaBoletins"
        )

        box: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="x", padx=15, pady=10)
        box.grid_columnconfigure(1, weight=1)

        linhas: list[tuple[str, str]] = [
            ("RM:", str(bm.get("rm_numero") or "(sem RM)")),
            ("Empresa:", str(emp["nome"])),
            ("PO:", str(bm.get("snap_po") or emp.get("po_codigo", ""))),
            (
                "Periodo:",
                f"{fmt_br(bm.get('periodo_ini'))} ate {fmt_br(bm.get('periodo_fim'))}",
            ),
            ("Emissao:", fmt_br(bm.get("emissao"))),
            ("Revisao:", str(bm.get("revisao", 0))),
            (
                "Valor Total PO:",
                f"R$ {float(bm.get('snap_valor_total') or emp.get('po_valor_total') or 0):,.2f}",
            ),
            ("Status:", txt_status),
        ]

        for i, (rotulo, valor) in enumerate(linhas):
            ctk.CTkLabel(box, text=rotulo, font=FONT_BOLD).grid(
                row=i, column=0, sticky="w", pady=3
            )
            lbl_valor: ctk.CTkLabel = ctk.CTkLabel(
                box, text=valor, font=FONT, text_color=cor_status if rotulo == "Status:" else None
            )
            lbl_valor.grid(row=i, column=1, sticky="w", pady=3)

        ctk.CTkLabel(self, text="Itens do Boletim:", font=FONT_BOLD).pack(
            pady=(12, 4)
        )
        import tkinter.ttk as ttk

        cols: tuple[str, ...] = ("projeto", "descricao", "valor_hora", "horas_periodo")
        tv: Any = ttk.Treeview(self, columns=cols, show="headings", height=8)
        for c, t in zip(cols, ["Projeto", "Descricao", "Valor Hora", "Horas Periodo"]):
            tv.heading(c, text=t)
            tv.column(c, width=220, anchor="w")
        itens: list[dict[str, Any]] = self.app.banco.buscar_itens_bm(bm_id)
        for i, it in enumerate(itens):
            tag: str = "even" if i % 2 == 0 else "odd"
            tv.insert(
                "",
                "end",
                values=(
                    it["projeto"],
                    it["descricao"],
                    f"{float(it['valor_hora']):,.2f}",
                    f"{float(it['horas_periodo'] or 0):,.2f}",
                ),
                tags=(tag,),
            )
        tv.pack(fill="both", expand=True, padx=12, pady=6)

        row: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=14)
        ctk.CTkButton(
            row,
            text="Validar",
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            font=FONT_BOLD,
            command=lambda: self._set_status("VALIDADO"),
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            row,
            text="Nao Validar",
            fg_color="#C62828",
            hover_color="#B71C1C",
            font=FONT_BOLD,
            command=lambda: self._set_status("NAO_VALIDADO"),
        ).pack(side="left", padx=8)

        if status == "VALIDADO":
            ctk.CTkButton(
                row,
                text="Importar Boletim PDF Assinado",
                fg_color="#1F6AA5",
                hover_color="#15456B",
                font=FONT_BOLD,
                command=self.importar_pdf_assinado,
            ).pack(side="left", padx=8)

        pdf_assinado: bytes | None = bm.get("pdf_assinado")
        if pdf_assinado:
            ctk.CTkButton(
                row,
                text="Baixar PDF Assinado",
                fg_color="#1565C0",
                hover_color="#0D47A1",
                font=FONT_BOLD,
                command=self.baixar_pdf_assinado,
            ).pack(side="left", padx=8)

        ctk.CTkButton(
            row,
            text="Voltar",
            fg_color="transparent",
            text_color=AZUL,
            hover_color=AZUL_ESCURO,
            command=lambda: self.app.ir("TelaBoletins"),
        ).pack(side="left", padx=8)

    def _set_status(self, status_novo: str) -> None:
        bm_id: int | None = self.bm_id
        if not bm_id:
            return
        login: str = self.app.usuario.get("login") if self.app.usuario else ""
        self.app.banco.atualizar_status_validacao_bm(bm_id, status_novo, login)
        msg: str = (
            "Validado com sucesso!"
            if status_novo == "VALIDADO"
            else "Marcado como Nao Validado."
        )
        messagebox.showinfo("OK", msg)
        self.ao_mostrar()

    def importar_pdf_assinado(self) -> None:
        bm_id: int | None = self.bm_id
        if not bm_id:
            return
        bm = self.app.banco.buscar_bm(bm_id)
        status: str = str(bm.get("status_validacao") or "PENDENTE")
        if status != "VALIDADO":
            messagebox.showerror(
                "Erro", "O boletim precisa estar validado antes de assinar."
            )
            return

        path: str = filedialog.askopenfilename(
            title="Selecionar Boletim PDF Assinado",
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                pdf_bytes: bytes = f.read()
            nome_arquivo: str = path.split("/")[-1].split("\\")[-1]
            login: str = self.app.usuario.get("login") if self.app.usuario else ""
            self.app.banco.salvar_pdf_assinado(bm_id, pdf_bytes, nome_arquivo, login)
            messagebox.showinfo("OK", "PDF assinado importado com sucesso!")
            self.ao_mostrar()
        except Exception as exc:
            messagebox.showerror("Erro", mensagem_erro_segura(exc))

    def baixar_pdf_assinado(self) -> None:
        bm_id: int | None = self.bm_id
        if not bm_id:
            return
        pdf_info: dict[str, Any] | None = self.app.banco.obter_pdf_assinado(bm_id)
        if not pdf_info or not pdf_info.get("pdf_assinado"):
            messagebox.showerror("Erro", "Nenhum PDF assinado encontrado.")
            return

        sug: str = pdf_info.get("pdf_assinado_nome") or f"Boletim_{bm_id}_assinado.pdf"
        dest: str = filedialog.asksaveasfilename(
            initialfile=sug, defaultextension=".pdf"
        )
        if dest:
            with open(dest, "wb") as f:
                f.write(bytes(pdf_info["pdf_assinado"]))
            messagebox.showinfo("OK", f"PDF assinado salvo em:\n{dest}")
