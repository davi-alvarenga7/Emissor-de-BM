"""Tela de cadastro de nova empresa."""

from typing import Any

import customtkinter as ctk
from tkinter import filedialog, messagebox
from openpyxl import load_workbook

from src.database import Banco
from src.services.boletim_service import BoletimService
from src.ui.widgets import (
    campo_entrada,
    campo_texto,
    campo_tipo_faturamento,
    criar_campo_valor,
    cabecalho_tela,
)
from src.config import AZUL, AZUL_ESCURO, FONT, FONT_BOLD

CAMPO_VALOR_HORA: tuple[str, str] = ("Valor Hora*", "valor_hora")
CAMPO_VALOR_FIXO: tuple[str, str] = ("Valor Fixo Mensal", "valor_fixo_mensal")

CAMPOS_EMPRESA: list[tuple[str, str]] = [
    ("Razão Social*", "nome"),
    ("CNPJ*", "cnpj"),
    ("Código PO*", "po_codigo"),
    ("Data de Início - PO (dd/mm/aaaa)*", "po_inicio"),
    ("Data de Vencimento - PO (dd/mm/aaaa)*", "po_fim"),
    ("Valor Total PO*", "po_valor_total"),
    ("Objeto*", "po_objeto"),
    ("E-mail*", "email_contato"),
    ("Responsável*", "responsavel"),
    ("Usuário/Login E-clic*", "usuario_eclic"),
    ("Tipo de Faturamento*", "tipo_faturamento"),
    ("Gerente Aprovador", "gerente_aprovador"),
    ("Diretor Aprovador", "diretor_aprovador"),
]

CAMPOS_OBRIGATORIOS: list[str] = [
    "nome",
    "cnpj",
    "po_codigo",
    "po_inicio",
    "po_fim",
    "po_valor_total",
    "po_objeto",
    "email_contato",
    "responsavel",
    "usuario_eclic",
    "tipo_faturamento",
]


class TelaCadEmpresa(ctk.CTkFrame):
    """Tela de cadastro de nova empresa."""

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
        self.app.cabec(self, "Cadastro de Nova Empresa", "TelaHome")
        box: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(padx=12, fill="x")
        box.grid_columnconfigure(1, weight=1)
        self.ents = {}
        self.ent_valor_hora = None
        self.ent_valor_fixo = None
        self.var_tipo = None
        self.row_valor_hora = None
        self.row_valor_fixo = None

        row_idx: int = 0
        for rot, key in CAMPOS_EMPRESA:
            if key == "usuario_eclic":
                self.ents[key] = campo_texto(box, rot, row_idx)
            elif key == "tipo_faturamento":
                self.ents[key] = campo_tipo_faturamento(box, rot, row_idx)
                self.var_tipo = self.ents[key]["var"]
                self.row_valor_hora = ctk.CTkFrame(box, fg_color="transparent")
                self.row_valor_fixo = ctk.CTkFrame(box, fg_color="transparent")
                criar_campo_valor(self.row_valor_hora, *CAMPO_VALOR_HORA)
                criar_campo_valor(self.row_valor_fixo, *CAMPO_VALOR_FIXO)
            else:
                self.ents[key] = campo_entrada(box, rot, row_idx)
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
            text="Cadastro em lote (Excel)",
            command=self.lote,
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

    def ler_tela(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
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

    def validar(self, d: dict[str, Any], ignorar_id: int | None = None) -> str | None:
        for k in CAMPOS_OBRIGATORIOS:
            if not d.get(k):
                return f"Campo obrigatório em branco: {rotulo_campo(k)}"
        tipo: str = str(d.get("tipo_faturamento", "HORISTA")).upper()
        if tipo not in ("HORISTA", "MENSALISTA"):
            return "Tipo de faturamento invalido (use HORISTA ou MENSALISTA)"
        from src.utils import valida_cnpj, valida_email, parse_data_flex, parse_num, lista_eclics

        if not valida_cnpj(d["cnpj"]):
            return "CNPJ invalido (deve ter 14 digitos)"
        if not valida_email(d["email_contato"]):
            return "E-mail de contato invalido"
        di = parse_data_flex(d["po_inicio"])
        df = parse_data_flex(d["po_fim"])
        if not di or not df:
            return "Datas de PO invalidas (use dd/mm/aaaa)"
        if df < di:
            return "Fim PO deve ser maior ou igual ao Início PO"
        vt = parse_num(d["po_valor_total"])
        if vt is None or vt < 0:
            return "Valor Total PO deve ser numerico e maior ou igual a zero"
        if tipo == "HORISTA":
            vh = parse_num(d["valor_hora"])
            if vh is None or vh < 0:
                return "Valor Hora deve ser numerico e maior ou igual a zero"
            vfm: float | None = None
        else:
            vh = parse_num(d["valor_hora"]) or 0
            vfm = parse_num(d.get("valor_fixo_mensal"))
            if vfm is None or vfm < 0:
                return "Valor Fixo Mensal deve ser numerico e maior ou igual a zero"
        eclics: list[str] = lista_eclics(d.get("usuario_eclic"))
        if not eclics:
            return "Informe ao menos um Usuario E-clic"
        d["usuario_eclic"] = eclics
        dup: str | None = self.app.banco.duplicado_empresa(
            d["cnpj"], d["po_codigo"], eclics, ignorar_id=ignorar_id
        )
        if dup:
            return f"Ja existe empresa com o mesmo {dup}"
        d["_di"], d["_df"], d["_vt"] = di, df, vt
        d["_vh"] = vh
        d["_tipo"] = tipo
        d["_vfm"] = vfm
        return None

    def salvar(self) -> None:
        d: dict[str, Any] = self.ler_tela()
        erro: str | None = self.validar(d)
        if erro:
            messagebox.showerror("Erro", erro)
            return
        try:
            self.app.banco.criar_empresa(d)
            messagebox.showinfo("OK", "Empresa cadastrada")
            self.app.ir("TelaEmpresas")
        except Exception as exc:
            from src.utils import mensagem_erro_segura

            messagebox.showerror("Erro", mensagem_erro_segura(exc))

    def lote(self) -> None:
        paths: tuple[str, ...] = filedialog.askopenfilenames(
            title="Planilha de empresas",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not paths:
            return
        from src.utils import (
            so_digitos,
            chave_texto,
            parse_data_flex,
            parse_num,
            lista_eclics,
            mensagem_erro_segura,
        )

        ok: int = 0
        pul: int = 0
        motivos: list[str] = []
        for p in paths:
            try:
                wb = load_workbook(p, data_only=True)
                rows: list[tuple[Any, ...]] = list(wb.active.iter_rows(values_only=True))
            except Exception as e:
                motivos.append(f"{__import__('os').path.basename(p)}: {e}")
                continue
            vistos: set[tuple[str, str]] = set()
            vistos_eclic: set[str] = set()
            for i, r in enumerate(rows[1:], start=2):
                if not r or all(c in (None, "") for c in r):
                    pul += 1
                    motivos.append(f"linha {i}: linha vazia")
                    continue
                try:
                    vals: list[Any] = list(r) + [""] * 11
                    chaves: list[str] = [
                        "nome",
                        "cnpj",
                        "po_codigo",
                        "po_inicio",
                        "po_fim",
                        "po_valor_total",
                        "po_objeto",
                        "email_contato",
                        "valor_hora",
                        "responsavel",
                        "usuario_eclic",
                    ]
                    d: dict[str, str] = {
                        k: str(vals[j] or "").strip() for j, k in enumerate(chaves)
                    }
                    if any(not d[k] for k in chaves):
                        pul += 1
                        motivos.append(f"linha {i}: celula em branco")
                        continue
                    chave: tuple[str, str] = (so_digitos(d["cnpj"]), d["po_codigo"].upper())
                    if chave in vistos:
                        pul += 1
                        motivos.append(f"linha {i}: duplicada no arquivo")
                        continue
                    eclics: list[str] = lista_eclics(d["usuario_eclic"])
                    if any(e in vistos_eclic for e in eclics):
                        pul += 1
                        motivos.append(f"linha {i}: Usuario E-clic ja usado no arquivo")
                        continue
                    vistos.add(chave)
                    vistos_eclic.update(e.upper() for e in eclics)
                    for idx, k in ((3, "po_inicio"), (4, "po_fim")):
                        if isinstance(r[idx], (__import__("datetime").datetime, __import__("datetime").date)):
                            d[k] = r[idx].strftime("%d/%m/%Y")
                    erro: str | None = self.validar(d)
                    if erro:
                        pul += 1
                        motivos.append(f"linha {i}: {erro}")
                        continue
                    self.app.banco.criar_empresa(d)
                    ok += 1
                except Exception as e:
                    pul += 1
                    motivos.append(f"linha {i}: {e}")
        msg: str = f"{ok} empresa(s) cadastrada(s), {pul} pulada(s)."
        if motivos:
            msg += "\n\n" + "\n".join(motivos[:25])
        messagebox.showinfo("Cadastro em lote", msg)


def rotulo_campo(chave: str) -> str:
    for rot, k in CAMPOS_EMPRESA:
        if k == chave:
            return rot.replace("*", "").strip()
    return chave
