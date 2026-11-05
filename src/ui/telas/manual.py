"""Tela de emissao manual de boletim."""

from typing import Any

import customtkinter as ctk
from tkinter import messagebox
from datetime import date, timedelta

from src.ui.widgets import cabecalho_tela, campo_entrada
from src.config import AZUL, AZUL_ESCURO, FONT, FONT_BOLD
from src.utils import (
    parse_data_flex,
    parse_num,
    chave_texto,
    mensagem_erro_segura,
    fmt_br,
)


class TelaManual(ctk.CTkFrame):
    """Tela de emissao manual de boletim."""

    cid: int | None = None

    def __init__(self, parent: ctk.CTkFrame, app: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: Any = app
        self.rows: list[tuple[ctk.CTkEntry, ctk.CTkEntry, ctk.CTkEntry]] = []

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
        self.app.cabec(self, f"Emitir BM manual — {emp['nome']}", "TelaEmpresas")
        ctk.CTkLabel(
            self,
            text=f"PO {emp['po_codigo']} | Valor hora R$ {float(emp['valor_hora']):,.2f} (travado)",
            text_color=AZUL,
            font=FONT_BOLD,
        ).pack(pady=(2, 8))

        box: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(padx=12, pady=6)
        box.grid_columnconfigure(1, weight=1)

        self.pi: ctk.CTkEntry = campo_entrada(
            box, "Periodo Inicial* (dd/mm/aaaa)", 0
        )
        self.pf: ctk.CTkEntry = campo_entrada(
            box, "Periodo Final* (dd/mm/aaaa)", 1
        )
        ctk.CTkLabel(
            box,
            text="Projetos, atividades e horas no periodo:",
            font=FONT_BOLD,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 4))

        cab: ctk.CTkFrame = ctk.CTkFrame(box, fg_color="transparent")
        cab.grid(row=3, column=0, columnspan=2, sticky="w")
        ctk.CTkLabel(cab, text="Projeto", width=400, text_color=AZUL, font=FONT_BOLD).pack(
            side="left", padx=(0, 10)
        )
        ctk.CTkLabel(cab, text="Atividade", width=300, text_color=AZUL, font=FONT_BOLD).pack(
            side="left", padx=(0, 10)
        )
        ctk.CTkLabel(cab, text="Horas", width=100, text_color=AZUL, font=FONT_BOLD).pack(side="left")

        self.linhas: ctk.CTkFrame = ctk.CTkFrame(box, fg_color="transparent")
        self.linhas.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.linhas.grid_columnconfigure(0, weight=1)
        self.rows = []
        for _ in range(3):
            self.add_linha()

        ctk.CTkButton(
            box,
            text="+ Adicionar projeto",
            command=self.add_linha,
            fg_color="transparent",
            text_color=AZUL,
            hover_color=AZUL_ESCURO,
        ).grid(row=5, column=0, columnspan=2, pady=(6, 0))

        ctk.CTkButton(
            self,
            text="Gerar Boletim",
            fg_color=AZUL,
            hover_color=AZUL_ESCURO,
            font=FONT_BOLD,
            command=self.gerar,
        ).pack(pady=12)

    def add_linha(self) -> None:
        f: ctk.CTkFrame = ctk.CTkFrame(self.linhas, fg_color="transparent")
        f.pack(fill="x", pady=3)
        p: ctk.CTkEntry = ctk.CTkEntry(f, width=380, font=FONT)
        p.pack(side="left", padx=(0, 6))
        p.insert(0, "PRJ-...")
        a: ctk.CTkEntry = ctk.CTkEntry(f, width=300, font=FONT)
        a.pack(side="left", padx=(0, 6))
        h: ctk.CTkEntry = ctk.CTkEntry(f, width=100, font=FONT)
        h.pack(side="left")
        h.insert(0, "0")
        self.rows.append((p, a, h))

    def gerar(self) -> None:
        cid: int | None = self.cid
        if not cid:
            return
        emp = self.app.banco.buscar_empresa(cid)
        tipo: str = str(emp.get("tipo_faturamento") or "HORISTA").upper()
        pi: date | None = parse_data_flex(self.pi.get())
        pf: date | None = parse_data_flex(self.pf.get())
        if not pi or not pf or pf < pi:
            messagebox.showerror("Erro", "Periodo invalido")
            return
        vfm: float | None = parse_num(emp.get("valor_fixo_mensal"))
        if tipo == "MENSALISTA":
            if vfm is None or vfm < 0:
                messagebox.showerror(
                    "Erro", "Valor Fixo Mensal nao configurado para esta empresa"
                )
                return
            from src.config import DESCRICAO_PADRAO

            itens: list[tuple[str, str, float, Any, float]] = [
                ("REFERÊNCIA", DESCRICAO_PADRAO, 0, None, 0)
            ]
        else:
            mapa: dict[tuple[str, str], tuple[Any, Any]] = (
                self.app.banco.ultimo_mapa_itens(emp["id"])
            )
            acc: dict[tuple[str, str], tuple[str, str, float, Any, float]] = {}
            for p, a, h in self.rows:
                proj: str = p.get().strip()
                ativ: str = a.get().strip() or "Servicos de Consultoria em TELECOM"
                hp: float | None = parse_num(h.get())
                if not proj or proj == "PRJ-..." or hp is None:
                    continue
                k: tuple[str, str] = (chave_texto(proj), chave_texto(ativ))
                if k in acc:
                    proj_a, ativ_a, _, ant, hp_acc = acc[k]
                    acc[k] = (
                        proj_a,
                        ativ_a,
                        float(emp["valor_hora"]),
                        float(ant) if ant is not None else None,
                        hp_acc + float(hp),
                    )
                else:
                    ant: tuple[Any, Any] | None = mapa.get(k, (None, None))
                    acc[k] = (
                        proj,
                        ativ,
                        float(emp["valor_hora"]),
                        float(ant[0]) if ant[0] is not None else None,
                        float(hp),
                    )
            itens = list(acc.values())
            if not itens:
                messagebox.showerror("Erro", "Informe ao menos 1 projeto com horas")
                return

        emi: date = pf + timedelta(days=1)
        rm: str = self.app.banco.proximo_rm(emp["id"], emi.isoformat())

        from src.services.boletim_service import BoletimService

        service: BoletimService = BoletimService(self.app.banco)
        service.gerar_e_salvar_bm(emp, pi, pf, emi, rm, 0, itens, "MANUAL")
        messagebox.showinfo("OK", f"BM gerado ({rm or 'sem RM'})")
        self.app.telas["TelaBoletins"].cid = emp["id"]
        self.app.ir("TelaBoletins")
