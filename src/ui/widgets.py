"""Widgets reutilizáveis da interface do usuário."""

from typing import Any

import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import darkdetect

from src.config import AZUL, AZUL_ESCURO, FONT, FONT_BOLD, FONT_TITULO
from src.database import recurso_assets


def campo_entrada(
    parent: ctk.CTkFrame,
    rotulo: str,
    row: int,
    valor: str = "",
    largura: int = 560,
    show: str | None = None,
) -> ctk.CTkEntry:
    """Cria um label + entry em um grid."""
    ctk.CTkLabel(parent, text=rotulo, font=FONT).grid(
        row=row, column=0, sticky="w", pady=6
    )
    e: ctk.CTkEntry = ctk.CTkEntry(
        parent, width=largura, font=FONT, show=show or ""
    )
    e.grid(row=row, column=1, sticky="ew", pady=6, padx=(15, 0))
    if valor:
        e.insert(0, valor)
    return e


def campo_texto(
    parent: ctk.CTkFrame,
    rotulo: str,
    row: int,
    valor: str = "",
    altura: int = 3,
    largura: int = 560,
) -> ctk.CTkTextbox:
    """Cria um campo de texto de varias linhas."""
    ctk.CTkLabel(parent, text=rotulo, font=FONT).grid(
        row=row, column=0, sticky="nw", pady=6
    )
    t: ctk.CTkTextbox = ctk.CTkTextbox(
        parent, width=largura, height=altura * 22, font=FONT
    )
    t.grid(row=row, column=1, sticky="ew", pady=6, padx=(15, 0))
    if valor:
        t.insert("1.0", valor)
    return t


def campo_tipo_faturamento(
    parent: ctk.CTkFrame,
    rotulo: str,
    row: int,
    valor: str = "HORISTA",
) -> dict[str, Any]:
    """Cria radio buttons para tipo de faturamento (Horista/Mensalista)."""
    ctk.CTkLabel(parent, text=rotulo, font=FONT).grid(
        row=row, column=0, sticky="w", pady=6
    )
    frame: ctk.CTkFrame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.grid(row=row, column=1, sticky="w", pady=6, padx=(15, 0))
    var: ctk.StringVar = ctk.StringVar(value=valor)
    rb1: ctk.CTkRadioButton = ctk.CTkRadioButton(
        frame, text="Horista", variable=var, value="HORISTA", font=FONT
    )
    rb1.pack(side="left", padx=(0, 14))
    rb2: ctk.CTkRadioButton = ctk.CTkRadioButton(
        frame, text="Mensal - fixo", variable=var, value="MENSALISTA", font=FONT
    )
    rb2.pack(side="left")
    return {"var": var, "widget": frame}


def criar_campo_valor(
    parent: ctk.CTkFrame,
    rotulo: str,
    chave: str,
    valor: str = "",
    largura: int = 220,
) -> ctk.CTkEntry:
    """Cria label + entry lado a lado dentro de um frame (usa pack)."""
    ctk.CTkLabel(parent, text=rotulo, font=FONT).pack(side="left", padx=(0, 10))
    e: ctk.CTkEntry = ctk.CTkEntry(parent, width=largura, font=FONT)
    e.pack(side="left")
    if valor:
        e.insert(0, valor)
    setattr(parent, f"ent_{chave}", e)
    return e


def cabecalho_tela(
    parent: ctk.CTkFrame,
    titulo: str,
    voltar: str = "TelaHome",
    app: Any = None,
) -> ctk.CTkFrame:
    """Cria o cabeçalho padrao de uma tela."""
    top: ctk.CTkFrame = ctk.CTkFrame(parent, fg_color="transparent")
    top.pack(fill="x", padx=15, pady=(10, 6))
    top.grid_columnconfigure(1, weight=1)

    if app:
        ctk.CTkButton(
            top,
            text="← Voltar",
            width=110,
            command=lambda: app.ir(voltar),
        ).grid(row=0, column=0, sticky="w")

    ctk.CTkLabel(top, text=titulo, font=FONT_TITULO, text_color=AZUL).grid(
        row=0, column=1, sticky="w", padx=15
    )
    return top


def logo_ctk(largura: int = 220) -> Any:
    """Logo DBR para o CustomTkinter (imagens clara e escura)."""
    from PIL import Image as PI

    try:
        im = PI.open(recurso_assets("logo.png")).convert("RGBA")
        h: int = max(1, int(im.height * largura / im.width))

        def preparar(cor_fundo: str) -> Any:
            bg: Any = PI.new("RGBA", im.size, cor_fundo)
            bg.alpha_composite(im)
            return bg.convert("RGB").resize((largura, h), PI.LANCZOS)

        img_clara = preparar((255, 255, 255, 255))
        img_escura = preparar((43, 43, 43, 255))
        return ctk.CTkImage(
            light_image=img_clara, dark_image=img_escura, size=(largura, h)
        )
    except Exception:
        return None


def estilo_tabela(style: ttk.Style, escuro: bool = False) -> None:
    """Aplica estilo plano e profissional para a ttk.Treeview."""
    cores_bg: str = "#2B2B2B" if escuro else "#F5F6F8"
    cores_txt: str = "#FFFFFF" if escuro else "#212529"
    cores_z1: str = "#333333" if escuro else "#FFFFFF"
    cores_z2: str = "#3A3A3A" if escuro else "#EEF2F6"

    style.configure(
        "Treeview",
        background=cores_bg,
        fieldbackground=cores_bg,
        foreground=cores_txt,
        rowheight=26,
        font=FONT,
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        background=AZUL,
        foreground="white",
        font=FONT_BOLD,
        borderwidth=0,
    )
    style.map(
        "Treeview",
        background=[("selected", AZUL_ESCURO)],
        foreground=[("selected", "white")],
    )


def ttk_treeview(
    parent: Any,
    cols: tuple[str, ...],
    headers: tuple[str, ...],
    widths: list[int],
    height: int = 15,
) -> Any:
    """Cria um ttk.Treeview com estilo padrao."""
    style: ttk.Style = ttk.Style(parent)
    try:
        escuro: bool = darkdetect.theme() == "Dark"
    except Exception:
        escuro = False
    estilo_tabela(style, escuro)

    tv: Any = ttk.Treeview(parent, columns=cols, show="headings", height=height)
    for c, t in zip(cols, headers):
        tv.heading(c, text=t)
        tv.column(c, width=widths[cols.index(c)], anchor="w")
    if escuro:
        tv.tag_configure("even", background="#333333")
        tv.tag_configure("odd", background="#3A3A3A")
    else:
        tv.tag_configure("even", background="#FFFFFF")
        tv.tag_configure("odd", background="#EEF2F6")
    return tv
