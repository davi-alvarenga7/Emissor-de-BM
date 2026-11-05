"""Tela de listagem de empresas cadastradas."""

from typing import Any

import customtkinter as ctk
from tkinter import messagebox, filedialog
from openpyxl import load_workbook
from datetime import date, datetime

from src.ui.widgets import (
    campo_entrada,
    estilo_tabela,
    cabecalho_tela,
    logo_ctk,
    ttk_treeview,
)
from src.config import AZUL, AZUL_ESCURO, FONT, FONT_BOLD
from src.utils import (
    mensagem_erro_segura,
    so_digitos,
    parse_data_flex,
)


class TelaEmpresas(ctk.CTkFrame):
    """Tela de listagem e gerenciamento de empresas."""

    def __init__(self, parent: ctk.CTkFrame, app: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: Any = app
        self.tv: Any = None

    def ao_mostrar(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.app.cabec(self, "Empresas Cadastradas", "TelaHome")
        busca: ctk.CTkEntry = ctk.CTkEntry(
            self,
            width=560,
            font=FONT,
            placeholder_text="Buscar por responsavel, razao social ou CNPJ...",
        )
        busca.pack(padx=12, pady=(4, 2), anchor="w")

        cols: tuple[str, ...] = ("responsavel", "nome", "cnpj")
        tv: Any = ttk_treeview(self, cols, ("Responsável", "Razão Social", "CNPJ"), [260, 260, 260])
        tv.pack(fill="both", expand=True, padx=12, pady=6)
        self.tv = tv

        def recarrega(*_):
            q: str = busca.get().strip()
            like: str = f"%{q}%" if q else "%"
            tv.delete(*tv.get_children())
            if self.app.user_is_admin:
                rows = self.app.banco.listar_empresas(like)
            else:
                rows = self.app.banco.listar_empresas(like, company_id=self.app.company_id)
            for i, r in enumerate(rows):
                tag: str = "even" if i % 2 == 0 else "odd"
                tv.insert(
                    "",
                    "end",
                    iid=str(r["id"]),
                    values=(r["responsavel"], r["nome"], r["cnpj"]),
                    tags=(tag,),
                )

        busca.bind("<KeyRelease>", recarrega)
        recarrega()

        row: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=8)
        if self.app.user_is_admin:
            ctk.CTkButton(
                row, text="Editar", command=self.editar
            ).pack(side="left", padx=6)
            ctk.CTkButton(
                row,
                text="Emitir Boletim (manual)",
                fg_color=AZUL,
                hover_color=AZUL_ESCURO,
                font=FONT_BOLD,
                command=self.manual,
            ).pack(side="left", padx=6)
            ctk.CTkButton(
                row,
                text="Excluir",
                fg_color="#C62828",
                hover_color="#B71C1C",
                font=FONT_BOLD,
                command=self.excluir,
            ).pack(side="left", padx=6)
            ctk.CTkButton(
                row,
                text="Importar BM Preenchido",
                command=self.importar_bm_preenchido,
            ).pack(side="left", padx=6)
        ctk.CTkButton(
            row, text="Boletins Emitidos", command=self.boletins
        ).pack(side="left", padx=6)

    def selecionada(self) -> int | None:
        s = self.tv.selection()
        if not s:
            messagebox.showwarning("Aviso", "Selecione uma empresa na lista")
            return None
        return int(str(s[0]))

    def editar(self) -> None:
        i: int | None = self.selecionada()
        if i:
            self.app.telas["TelaEditar"].cid = i
            self.app.ir("TelaEditar")

    def manual(self) -> None:
        i: int | None = self.selecionada()
        if i:
            self.app.telas["TelaManual"].cid = i
            self.app.ir("TelaManual")

    def boletins(self) -> None:
        i: int | None = self.selecionada()
        if i:
            self.app.telas["TelaBoletins"].cid = i
            self.app.ir("TelaBoletins")

    def importar_bm_preenchido(self) -> None:
        i: int | None = self.selecionada()
        if not i:
            return
        p: str = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if not p:
            return
        try:
            wb = load_workbook(p, data_only=True)
            ws = wb.active
            emp = self.app.banco.buscar_empresa(i)
            cnpj_arquivo: str = so_digitos(str(ws["H9"].value or ""))
            if cnpj_arquivo and cnpj_arquivo != so_digitos(emp["cnpj"]):
                messagebox.showerror(
                    "Erro",
                    f"CNPJ do arquivo ({cnpj_arquivo}) difere da empresa ({emp['cnpj']})",
                )
                return
            rm: str = str(ws["I1"].value or "").strip()
            per: str = str(ws["I2"].value or "")
            import re

            ds: list[date | None] = [
                parse_data_flex(x)
                for x in re.findall(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", per)
            ]
            pi: date | None = ds[0] if len(ds) > 0 and ds[0] else parse_data_flex(
                emp["po_inicio"]
            )
            pf: date | None = ds[1] if len(ds) > 1 and ds[1] else parse_data_flex(
                emp["po_fim"]
            )
            emi: date = parse_data_flex(ws["I3"].value) or date.today()
            mrev: re.Match[str] | None = re.search(r"(\d+)", str(ws["K6"].value or "0"))
            rev: int = int(mrev.group(1)) if mrev else 0

            from src.boletim import DESCRICAO_PADRAO

            itens: list[tuple[str, str, float, Any, float]] = []
            for r_idx in range(12, 21):
                proj: Any = ws.cell(row=r_idx, column=3).value
                if not proj:
                    continue
                ativ: str = str(
                    ws.cell(row=r_idx, column=4).value or DESCRICAO_PADRAO
                ).strip()
                vh: float = parse_num(ws.cell(row=r_idx, column=5).value) or 0
                ha: float | None = parse_num(ws.cell(row=r_idx, column=6).value)
                hp: float = parse_num(ws.cell(row=r_idx, column=7).value) or 0
                itens.append((str(proj), ativ, vh, ha, hp))

            self.app.gerar_e_salvar_bm(emp, pi, pf, emi, rm, rev, itens, "BASE")
            messagebox.showinfo("OK", "BM base importado")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def excluir(self) -> None:
        i: int | None = self.selecionada()
        if not i:
            return
        emp = self.app.banco.buscar_empresa(i)
        confirm: bool = messagebox.askyesno(
            "Confirmar exclusao",
            f"Tem certeza que deseja excluir a empresa '{emp['nome']}' (CNPJ: {emp['cnpj']})?\n"
            "Todos os boletins e vinculos serao removidos.",
        )
        if not confirm:
            return
        try:
            self.app.banco.excluir_empresa(i)
            messagebox.showinfo("OK", "Empresa excluida com sucesso")
            self.ao_mostrar()
        except Exception as e:
            from src.utils import mensagem_erro_segura

            messagebox.showerror("Erro", mensagem_erro_segura(e))
