"""Tela de boletins emitidos por empresa."""

from typing import Any

import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import date

from src.ui.widgets import cabecalho_tela
from src.config import AZUL, AZUL_ESCURO, FONT, FONT_BOLD
from src.utils import fmt_br, mensagem_erro_segura


class TelaBoletins(ctk.CTkFrame):
    """Tela de listagem de boletins emitidos por uma empresa."""

    cid: int | None = None

    def __init__(self, parent: ctk.CTkFrame, app: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: Any = app
        self.linhas_bm: list[dict[str, Any]] = []
        self.row_widgets: list[ctk.CTkFrame] = []
        self.sel_index: int | None = None

    def ao_mostrar(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        cid: int | None = self.cid
        if not cid:
            self.app.ir("TelaEmpresas")
            return
        emp = self.app.banco.buscar_empresa(cid)
        if not emp:
            self.app.ir("TelaEmpresas")
            return
        self.app.cabec(self, f"Boletins Emitidos — {emp['nome']}", "TelaEmpresas")
        self.linhas_bm = self.app.banco.listar_boletins(cid)
        container: ctk.CTkScrollableFrame = ctk.CTkScrollableFrame(
            self, fg_color="transparent"
        )
        container.pack(fill="both", expand=True, padx=12, pady=6)
        self.row_widgets = []
        self.sel_index = None

        for i, r in enumerate(self.linhas_bm):
            row: ctk.CTkFrame = ctk.CTkFrame(container)
            row.pack(fill="x", pady=3, padx=4)
            txt: str = (
                f"Boletim {emp['nome']} - {fmt_br(r.get('emissao'))} | "
                f"{r.get('rm_numero') or '(sem RM)'} | Rev {r.get('revisao')} | "
                f"{r.get('origem')}"
            )
            lab: ctk.CTkLabel = ctk.CTkLabel(
                row, text=txt, font=FONT, anchor="w", cursor="hand2"
            )
            lab.pack(side="left", fill="x", expand=True, padx=12, pady=7)

            status: str = str(r.get("status_validacao") or "PENDENTE")
            if status == "VALIDADO":
                cor_status: str = "#2E7D32"
                txt_status: str = "Validado"
            elif status == "NAO_VALIDADO":
                cor_status = "#C62828"
                txt_status = "Nao Validado"
            else:
                cor_status = "#F9A825"
                txt_status = "Aguardando Validacao"

            lbl_status: ctk.CTkLabel = ctk.CTkLabel(
                row, text=txt_status, font=FONT_BOLD, text_color=cor_status, width=150, anchor="e"
            )
            lbl_status.pack(side="right", padx=12, pady=7)

            def _selecionar(idx: int, rf: ctk.CTkFrame) -> None:
                self._selecionar(idx, rf)

            row.bind("<Button-1>", lambda e, idx=i, rf=row: _selecionar(idx, rf))
            lab.bind("<Button-1>", lambda e, idx=i, rf=row: _selecionar(idx, rf))
            lbl_status.bind("<Button-1>", lambda e, idx=i, rf=row: _selecionar(idx, rf))
            self.row_widgets.append(row)

        if self.row_widgets:
            self._selecionar(0, self.row_widgets[0])

        row_botoes: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        row_botoes.pack(pady=8)
        ctk.CTkButton(
            row_botoes,
            text="Baixar XLSX",
            fg_color=AZUL,
            hover_color=AZUL_ESCURO,
            font=FONT_BOLD,
            command=lambda: self.baixar("xlsx"),
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            row_botoes,
            text="Baixar PDF",
            fg_color="transparent",
            text_color=AZUL,
            hover_color=AZUL_ESCURO,
            command=lambda: self.baixar("pdf"),
        ).pack(side="left", padx=6)
        if self.app.user_is_admin:
            ctk.CTkButton(
                row_botoes,
                text="Reemitir (nova revisão)",
                fg_color=AZUL,
                hover_color=AZUL_ESCURO,
                font=FONT_BOLD,
                command=self.reemitir,
            ).pack(side="left", padx=6)
        ctk.CTkButton(
            row_botoes,
            text="Visualizar",
            fg_color="#1F6AA5",
            hover_color="#15456B",
            font=FONT_BOLD,
            command=self.visualizar,
        ).pack(side="left", padx=6)

    def _selecionar(self, idx: int, row_frame: ctk.CTkFrame) -> None:
        if self.sel_index is not None and self.sel_index < len(self.row_widgets):
            self.row_widgets[self.sel_index].configure(fg_color="transparent")
        self.sel_index = idx
        row_frame.configure(fg_color=("#D9E6F2", "#264058"))

    def atual(self) -> dict[str, Any] | None:
        if self.sel_index is None:
            messagebox.showwarning("Aviso", "Clique em um boletim da lista")
            return None
        return self.linhas_bm[self.sel_index]

    def baixar(self, tipo: str) -> None:
        r: dict[str, Any] | None = self.atual()
        if not r:
            return
        emp = self.app.banco.buscar_empresa(self.cid or 0)
        nome_empresa: str = "".join(
            c for c in emp["nome"] if c.isalnum() or c in (" ", "-", "_")
        ).strip().replace(" ", "_")
        periodo_ini: str = fmt_br(r.get("periodo_ini")) if r.get("periodo_ini") else ""
        periodo_fim: str = fmt_br(r.get("periodo_fim")) if r.get("periodo_fim") else ""
        periodo: str = f"{periodo_ini}_ate_{periodo_fim}".replace("/", "-").replace(" ", "_")
        sug: str = f"{nome_empresa}_{periodo}.{tipo}"
        dest: str = filedialog.asksaveasfilename(
            initialfile=sug, defaultextension=f".{tipo}"
        )
        if dest:
            with open(dest, "wb") as f:
                f.write(bytes(r["xlsx_blob"]) if tipo == "xlsx" else bytes(r["pdf_blob"]))
            messagebox.showinfo("OK", f"Arquivo salvo em:\n{dest}")

    def reemitir(self) -> None:
        r: dict[str, Any] | None = self.atual()
        if not r:
            return
        emp = self.app.banco.buscar_empresa(self.cid or 0)
        itens_bd: list[dict[str, Any]] = self.app.banco.buscar_itens_bm(r["id"])
        if not itens_bd:
            messagebox.showerror("Erro", "Nenhum item encontrado para este boletim")
            return
        itens: list[tuple[str, str, float, Any, float]] = [
            (
                i["projeto"],
                i["descricao"],
                float(i["valor_hora"]),
                i["horas_anterior"],
                float(i["horas_periodo"]),
            )
            for i in itens_bd
        ]
        from src.utils import parse_data_flex

        pi: date | None = parse_data_flex(r["periodo_ini"])
        pf: date | None = parse_data_flex(r["periodo_fim"])
        emi: date = date.today()
        rev: int = self.app.banco.proxima_revisao(
            emp["id"], str(r["rm_numero"]), pi, pf
        )
        tipo: str = str(emp.get("tipo_faturamento") or "HORISTA").upper()
        from src.utils import parse_num

        vfm: float | None = parse_num(emp.get("valor_fixo_mensal"))
        dados: dict[str, Any] = {
            "rm": str(r["rm_numero"]),
            "periodo_txt": f"{fmt_br(pi)} ate {fmt_br(pf)}",
            "emissao_txt": fmt_br(emi),
            "revisao": rev,
            "po": emp["po_codigo"],
            "po_ini_txt": fmt_br(emp["po_inicio"]),
            "po_fim_txt": fmt_br(emp["po_fim"]),
            "valor_total": float(emp["po_valor_total"] or 0),
            "objeto": emp["po_objeto"],
            "contratada": emp["nome"],
            "cnpj": emp["cnpj"],
            "itens": itens,
            "tipo_faturamento": tipo,
            "valor_fixo_mensal": vfm,
        }

        from src.services.boletim_service import BoletimService

        service: BoletimService = BoletimService(self.app.banco)
        service.gerar_e_salvar_bm(
            emp,
            pi,
            pf,
            emi,
            str(r["rm_numero"]),
            rev,
            itens,
            r.get("origem") or "MANUAL",
        )
        messagebox.showinfo("OK", f"Reemissao gravada (revisao {rev})")
        self.ao_mostrar()

    def visualizar(self) -> None:
        r: dict[str, Any] | None = self.atual()
        if not r:
            return
        self.app.telas["TelaVisualizarBM"].bm_id = int(r["id"])
        self.app.telas["TelaVisualizarBM"].company_id = self.cid or 0
        self.app.ir("TelaVisualizarBM")
