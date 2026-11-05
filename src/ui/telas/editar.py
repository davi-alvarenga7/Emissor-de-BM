"""Tela de edicao de empresa."""

from typing import Any

import customtkinter as ctk
from tkinter import messagebox

from src.ui.widgets import (
    campo_entrada,
    campo_texto,
    campo_tipo_faturamento,
    criar_campo_valor,
    cabecalho_tela,
)
from src.config import AZUL, AZUL_ESCURO, FONT, FONT_BOLD
from src.utils import (
    valida_cnpj,
    valida_email,
    parse_data_flex,
    parse_num,
    lista_eclics,
    chave_texto,
    mensagem_erro_segura,
    fmt_br,
)


class TelaEditar(ctk.CTkFrame):
    """Tela de edicao de empresa existente."""

    cid: int | None = None

    def __init__(self, parent: ctk.CTkFrame, app: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: Any = app
        self.ents: dict[str, Any] = {}
        self.ent_valor_hora: ctk.CTkEntry | None = None
        self.ent_valor_fixo: ctk.CTkEntry | None = None
        self.var_tipo: Any = None
        self.row_valor_hora: ctk.CTkFrame | None = None
        self.row_valor_fixo: ctk.CTkFrame | None = None

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
        eclics: list[str] = self.app.banco.eclics_da_empresa(cid)
        self.app.cabec(self, "Editar empresa", "TelaEmpresas")
        box: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(padx=12)
        box.grid_columnconfigure(1, weight=1)
        mapa: dict[str, str] = {
            "nome": emp["nome"],
            "cnpj": emp["cnpj"],
            "po_codigo": emp["po_codigo"],
            "po_inicio": fmt_br(emp["po_inicio"]),
            "po_fim": fmt_br(emp["po_fim"]),
            "po_valor_total": str(emp["po_valor_total"]),
            "po_objeto": emp["po_objeto"],
            "email_contato": emp["email_contato"],
            "valor_hora": str(emp["valor_hora"]),
            "responsavel": emp["responsavel"],
            "usuario_eclic": "\n".join(eclics) if eclics else (emp["usuario_eclic"] or ""),
            "tipo_faturamento": emp.get("tipo_faturamento") or "HORISTA",
            "valor_fixo_mensal": str(emp.get("valor_fixo_mensal") or ""),
            "gerente_aprovador": emp.get("gerente_aprovador") or "",
            "diretor_aprovador": emp.get("diretor_aprovador") or "",
        }
        self.ents = {}
        self.ent_valor_hora = None
        self.ent_valor_fixo = None
        self.var_tipo = None
        self.row_valor_hora = None
        self.row_valor_fixo = None

        row_idx: int = 0
        from src.ui.telas.cad_empresa import CAMPOS_EMPRESA, rotulo_campo

        for rot, key in CAMPOS_EMPRESA:
            if key == "usuario_eclic":
                self.ents[key] = campo_texto(box, rot, row_idx, mapa[key])
            elif key == "tipo_faturamento":
                self.ents[key] = campo_tipo_faturamento(box, rot, row_idx, mapa[key])
                self.var_tipo = self.ents[key]["var"]
                self.row_valor_hora = ctk.CTkFrame(box, fg_color="transparent")
                self.row_valor_fixo = ctk.CTkFrame(box, fg_color="transparent")
                criar_campo_valor(
                    self.row_valor_hora, *CAMPO_VALOR_HORA, mapa["valor_hora"]
                )
                criar_campo_valor(
                    self.row_valor_fixo, *CAMPO_VALOR_FIXO, mapa["valor_fixo_mensal"]
                )
            else:
                self.ents[key] = campo_entrada(box, rot, row_idx, str(mapa[key]))
            row_idx += 1

        if self.row_valor_hora:
            self.row_valor_hora.grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=4)
            row_idx += 1
        if self.row_valor_fixo:
            self.row_valor_fixo.grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=4)
            row_idx += 1

        self._atualizar_visibilidade_valores()

        if self.var_tipo:
            self.var_tipo.trace_add("write", lambda *_: self._atualizar_visibilidade_valores())

        row: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=12)
        ctk.CTkButton(
            row,
            text="Salvar",
            fg_color=AZUL,
            hover_color=AZUL_ESCURO,
            font=FONT_BOLD,
            command=self.salvar,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            row,
            text="Voltar",
            command=lambda: self.app.ir("TelaEmpresas"),
        ).pack(side="left", padx=8)

    def _atualizar_visibilidade_valores(self) -> None:
        tipo: str = self.var_tipo.get() if self.var_tipo else "HORISTA"
        if tipo == "HORISTA":
            if self.row_valor_hora:
                self.row_valor_hora.grid()
            if self.row_valor_fixo:
                self.row_valor_fixo.grid_remove()
        else:
            if self.row_valor_hora:
                self.row_valor_hora.grid_remove()
            if self.row_valor_fixo:
                self.row_valor_fixo.grid()

    def ler_tela(self) -> dict[str, str]:
        d: dict[str, str] = {}
        for k, e in self.ents.items():
            if isinstance(e, ctk.CTkTextbox):
                d[k] = "\n".join(
                    l.strip() for l in e.get("1.0", "end").splitlines() if l.strip()
                )
            elif isinstance(e, dict) and "var" in e:
                d[k] = e["var"].get()
            else:
                d[k] = e.get().strip()
        if self.ent_valor_hora:
            d["valor_hora"] = self.ent_valor_hora.get().strip()
        if self.ent_valor_fixo:
            d["valor_fixo_mensal"] = self.ent_valor_fixo.get().strip()
        return d

    def salvar(self) -> None:
        d: dict[str, str] = self.ler_tela()
        from src.ui.telas.cad_empresa import CAMPOS_OBRIGATORIOS

        for k in CAMPOS_OBRIGATORIOS:
            if not d.get(k):
                messagebox.showerror("Erro", f"Campo obrigatorio em branco: {rotulo_campo(k)}")
                return
        tipo: str = str(d.get("tipo_faturamento", "HORISTA")).upper()
        if tipo not in ("HORISTA", "MENSALISTA"):
            messagebox.showerror("Erro", "Tipo de faturamento invalido")
            return
        if not valida_cnpj(d["cnpj"]):
            messagebox.showerror("Erro", "CNPJ invalido")
            return
        if not valida_email(d["email_contato"]):
            messagebox.showerror("Erro", "E-mail de contato invalido")
            return
        di = parse_data_flex(d["po_inicio"])
        df = parse_data_flex(d["po_fim"])
        if not di or not df:
            messagebox.showerror("Erro", "Datas de PO invalidas")
            return
        if df < di:
            messagebox.showerror("Erro", "Fim PO deve ser maior ou igual ao Inicio PO")
            return
        vt = parse_num(d["po_valor_total"])
        if vt is None or vt < 0:
            messagebox.showerror("Erro", "Valor Total PO invalido")
            return
        eclics: list[str] = lista_eclics(d.get("usuario_eclic"))
        if not eclics:
            messagebox.showerror("Erro", "Informe ao menos um Usuario E-clic")
            return
        d["usuario_eclic"] = eclics
        try:
            self.app.banco.atualizar_empresa(self.cid, d)
            messagebox.showinfo("OK", "Informacoes atualizadas")
            self.app.ir("TelaEmpresas")
        except Exception as exc:
            messagebox.showerror("Erro", mensagem_erro_segura(exc))


from src.ui.telas.cad_empresa import (
    CAMPO_VALOR_HORA,
    CAMPO_VALOR_FIXO,
)
