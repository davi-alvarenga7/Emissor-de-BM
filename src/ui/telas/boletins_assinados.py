"""Tela de boletins assinados (apenas administradores)."""

from typing import Any

import customtkinter as ctk
from tkinter import messagebox, filedialog
import zipfile

from src.ui.widgets import cabecalho_tela
from src.config import AZUL, AZUL_ESCURO, FONT, FONT_BOLD
from src.utils import fmt_br, mensagem_erro_segura


class TelaBoletinsAssinados(ctk.CTkFrame):
    """Tela para administrador visualizar e gerenciar boletins assinados."""

    def __init__(self, parent: ctk.CTkFrame, app: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: Any = app
        self.tv: Any = None

    def ao_mostrar(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        if not self.app.user_is_admin:
            messagebox.showerror(
                "Acesso negado", "Apenas administradores podem acessar esta tela."
            )
            self.app.ir("TelaHome")
            return

        self.app.cabec(self, "Boletins Assinados", "TelaHome")

        ctk.CTkLabel(
            self, text="Lista de boletins com PDF assinado:", font=FONT_BOLD
        ).pack(pady=(10, 5), padx=12, anchor="w")

        import tkinter.ttk as ttk

        cols: tuple[str, ...] = (
            "id", "rm", "empresa", "cnpj", "emissao", "periodo", "assinado_por", "data_assinatura", "status"
        )
        headers: dict[str, str] = {
            "id": "ID",
            "rm": "RM",
            "empresa": "Empresa",
            "cnpj": "CNPJ",
            "emissao": "Emissao",
            "periodo": "Periodo",
            "assinado_por": "Assinado por",
            "data_assinatura": "Data Assinatura",
            "status": "Status Validacao",
        }
        widths: dict[str, int] = {
            "id": 50,
            "rm": 120,
            "empresa": 200,
            "cnpj": 120,
            "emissao": 100,
            "periodo": 180,
            "assinado_por": 150,
            "data_assinatura": 130,
            "status": 130,
        }

        tv: Any = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c in cols:
            tv.heading(c, text=headers[c])
            tv.column(c, width=widths[c], anchor="w")

        tv.pack(fill="both", expand=True, padx=12, pady=6)
        self.tv = tv

        def recarrega():
            tv.delete(*tv.get_children())
            rows: list[dict[str, Any]] = (
                self.app.banco.listar_boletins_assinados()
            )
            for i, r in enumerate(rows):
                tag: str = "even" if i % 2 == 0 else "odd"
                periodo: str = (
                    f"{fmt_br(r['periodo_ini'])} ate {fmt_br(r['periodo_fim'])}"
                    if r.get("periodo_ini")
                    else ""
                )
                emissao: str = fmt_br(r.get("emissao")) if r.get("emissao") else ""
                data_assinatura: str = (
                    str(r.get("data_assinatura"))[:16] if r.get("data_assinatura") else ""
                )
                tv.insert(
                    "",
                    "end",
                    iid=str(r["id"]),
                    values=(
                        r["id"],
                        r.get("rm_numero") or "",
                        r.get("empresa_nome") or "",
                        r.get("empresa_cnpj") or "",
                        emissao,
                        periodo,
                        r.get("assinado_por") or "",
                        data_assinatura,
                        r.get("status_validacao") or "",
                    ),
                    tags=(tag,),
                )

        recarrega()

        row: ctk.CTkFrame = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=12)
        ctk.CTkButton(
            row,
            text="Baixar PDF Selecionado",
            fg_color="#1565C0",
            hover_color="#0D47A1",
            font=FONT_BOLD,
            command=self.baixar_selecionado,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            row,
            text="Baixar Todos (ZIP)",
            fg_color="#1565C0",
            hover_color="#0D47A1",
            font=FONT_BOLD,
            command=self.baixar_todos_zip,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            row,
            text="Enviar por E-mail",
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            font=FONT_BOLD,
            command=self.enviar_email,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            row, text="Atualizar Lista", command=recarrega
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            row,
            text="Voltar",
            fg_color="transparent",
            text_color=AZUL,
            hover_color=AZUL_ESCURO,
            command=lambda: self.app.ir("TelaHome"),
        ).pack(side="left", padx=6)

    def _selecionado_id(self) -> int | None:
        s = self.tv.selection()
        if not s:
            messagebox.showwarning("Aviso", "Selecione um boletim na lista")
            return None
        return int(str(s[0]))

    def baixar_selecionado(self) -> None:
        bm_id: int | None = self._selecionado_id()
        if not bm_id:
            return
        pdf_info: dict[str, Any] | None = self.app.banco.obter_pdf_assinado(bm_id)
        if not pdf_info or not pdf_info.get("pdf_assinado"):
            messagebox.showerror("Erro", "Nenhum PDF assinado encontrado para este boletim.")
            return
        sug: str = pdf_info.get("pdf_assinado_nome") or f"Boletim_{bm_id}_assinado.pdf"
        dest: str = filedialog.asksaveasfilename(
            initialfile=sug, defaultextension=".pdf"
        )
        if dest:
            with open(dest, "wb") as f:
                f.write(bytes(pdf_info["pdf_assinado"]))
            messagebox.showinfo("OK", f"PDF assinado salvo em:\n{dest}")

    def baixar_todos_zip(self) -> None:
        rows: list[dict[str, Any]] = self.app.banco.listar_boletins_assinados()
        if not rows:
            messagebox.showwarning("Aviso", "Nenhum boletim assinado encontrado.")
            return
        dest: str = filedialog.asksaveasfilename(
            defaultextension=".zip",
            initialfile="Boletins_Assinados.zip",
            filetypes=[("ZIP", "*.zip")],
        )
        if not dest:
            return
        try:
            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
                for r in rows:
                    bm_id: int = r["id"]
                    pdf_info: dict[str, Any] | None = self.app.banco.obter_pdf_assinado(bm_id)
                    if pdf_info and pdf_info.get("pdf_assinado"):
                        nome: str = (
                            pdf_info.get("pdf_assinado_nome")
                            or f"Boletim_{bm_id}_assinado.pdf"
                        )
                        zf.writestr(nome, bytes(pdf_info["pdf_assinado"]))
            messagebox.showinfo(
                "OK", f"ZIP criado com {len(rows)} arquivo(s) em:\n{dest}"
            )
        except Exception as exc:
            messagebox.showerror("Erro", mensagem_erro_segura(exc))

    def enviar_email(self) -> None:
        """Envia os boletins assinados por e-mail ao responsavel financeiro."""
        from email.message import EmailMessage
        import smtplib
        import ssl
        import io

        cfg = self.app.banco.cfg
        smtp_cfg: dict[str, Any] = cfg.get("smtp", {})
        if not smtp_cfg.get("servidor") or not smtp_cfg.get("usuario"):
            messagebox.showerror(
                "Erro",
                "Configuracao de SMTP nao encontrada em config.json.\n"
                "Preencha servidor, porta, usuario e senha na secao smtp.",
            )
            return

        rows: list[dict[str, Any]] = self.app.banco.listar_boletins_assinados()
        if not rows:
            messagebox.showwarning("Aviso", "Nenhum boletim assinado para enviar.")
            return

        dialog: ctk.CTkInputDialog = ctk.CTkInputDialog(
            text="E-mail do responsavel financeiro:",
            title="Envio por E-mail",
        )
        destinatario: str | None = dialog.get_input()
        if not destinatario:
            return
        from src.utils import valida_email

        if not valida_email(destinatario):
            messagebox.showerror("Erro", "E-mail invalido.")
            return

        dialog_assunto: ctk.CTkInputDialog = ctk.CTkInputDialog(
            text="Assunto do e-mail:",
            title="Envio por E-mail",
        )
        assunto: str | None = dialog_assunto.get_input()
        assunto = assunto or "Boletins de Medicao Assinados"

        try:
            msg: EmailMessage = EmailMessage()
            msg["From"] = smtp_cfg.get("remetente") or smtp_cfg.get("usuario")
            msg["To"] = destinatario
            msg["Subject"] = assunto
            msg.set_content(
                f"Prezado(a),\n\n"
                f"Seguem em anexo os boletins de medição assinados ({len(rows)} arquivo(s)).\n\n"
                f"Atenciosamente,\nE-BM - Emissor de Boletim de Medição"
            )

            buf: io.BytesIO = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf_mem:
                for r in rows:
                    bm_id: int = r["id"]
                    pdf_info: dict[str, Any] | None = self.app.banco.obter_pdf_assinado(bm_id)
                    if pdf_info and pdf_info.get("pdf_assinado"):
                        nome: str = (
                            pdf_info.get("pdf_assinado_nome")
                            or f"Boletim_{bm_id}_assinado.pdf"
                        )
                        zf_mem.writestr(nome, bytes(pdf_info["pdf_assinado"]))
            zip_bytes: bytes = buf.getvalue()

            msg.add_attachment(
                zip_bytes, maintype="application", subtype="zip",
                filename="Boletins_Assinados.zip",
            )

            porta: int = int(smtp_cfg.get("porta", 587))
            usar_tls: bool = bool(smtp_cfg.get("usar_tls", True))
            contexto = ssl.create_default_context() if usar_tls else None

            with smtplib.SMTP(
                smtp_cfg["servidor"], porta, timeout=30
            ) as server:
                if usar_tls:
                    server.starttls(context=contexto)
                server.login(smtp_cfg["usuario"], smtp_cfg["senha"])
                server.send_message(msg)

            messagebox.showinfo("OK", f"E-mail enviado com sucesso para {destinatario}")
        except Exception as exc:
            messagebox.showerror("Erro ao enviar e-mail", mensagem_erro_segura(exc))
