# -*- coding: utf-8 -*-
"""Notificacao de vencimento de PO por e-mail (Outlook SMTP).

Este script e independente do E-BM (app.py). Deve ser executado via Windows
Task Scheduler (ex.: diariamente as 08:00) para avisar empresas cuja PO
vence em 7 dias, independentemente da abertura do sistema.

E-mail enviado:
  Assunto: Vencimento de PO em 7 dias
  Corpo: Prezado, o contrato vigente de prestacao de servicos da sua
         empresa a DBR Energies vence em 7 dias. Por favor entre em
         contato com o financeiro para resolucao. Atenciosamente,
"""

import os
import sys
import json
import ssl
import smtplib
from datetime import date

# Garante que o diretorio raiz esteja no path para importar src
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database import Banco, caminho_config


def carregar_config():
    """Le o config.json do usuario."""
    cfg_path = caminho_config()
    if not os.path.exists(cfg_path):
        return None
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)


def enviar_email(destinatario, smtp_cfg):
    """Envia e-mail de aviso de vencimento de PO via SMTP."""
    servidor = smtp_cfg.get("servidor")
    porta = smtp_cfg.get("porta", 587)
    usuario = smtp_cfg.get("usuario", "")
    senha = smtp_cfg.get("senha", "")
    remetente = smtp_cfg.get("remetente", "")
    usar_tls = smtp_cfg.get("usar_tls", True)

    if not servidor or not usuario or not senha or not remetente:
        print("SMTP nao configurado completamente. Ignorando envio de e-mails.")
        return False

    assunto = "Vencimento de PO em 7 dias"
    corpo = (
        "Prezado, o contrato vigente de prestacao de servicos da sua empresa "
        "a DBR Energies vence em 7 dias. Por favor entre em contato com o "
        "financeiro para resolucao. Atenciosamente,"
    )

    mensagem = (
        f"From: {remetente}\r\n"
        f"To: {destinatario}\r\n"
        f"Subject: {assunto}\r\n"
        f"\r\n"
        f"{corpo}\r\n"
    )

    try:
        contexto = ssl.create_default_context() if usar_tls else None
        with smtplib.SMTP(servidor, porta, timeout=30) as smtp:
            if usar_tls:
                smtp.starttls(context=contexto)
            if usuario and senha:
                smtp.login(usuario, senha)
            smtp.sendmail(remetente, [destinatario], mensagem.encode("utf-8"))
        print(f"E-mail enviado com sucesso para {destinatario}")
        return True
    except Exception:
        # Não logar o erro bruto: pode conter credenciais SMTP.
        print(f"Falha ao enviar e-mail para {destinatario}.")
        return False


def main():
    cfg = carregar_config()
    if not cfg:
        print("config.json nao encontrado. Encerrando.")
        return

    smtp_cfg = cfg.get("smtp", {})
    if not smtp_cfg.get("servidor"):
        print("SMTP nao configurado. Encerrando sem enviar e-mails.")
        return

    bd = Banco(cfg)
    empresas = bd.buscar_empresas_proximas_vencimento()

    if not empresas:
        print("Nenhuma empresa proxima ao vencimento para notificar.")
        bd.fechar()
        return

    print(f"{len(empresas)} empresa(s) proxima(s) ao vencimento de PO.")

    for emp in empresas:
        cid = emp["id"]
        nome = emp["nome"]
        email = emp["email_contato"]
        po_codigo = emp["po_codigo"]
        po_fim = emp["po_fim"]

        if not email:
            print(f"Empresa {nome} (id={cid}) sem e-mail cadastrado. Pulando.")
            continue

        sucesso = enviar_email(email, smtp_cfg)
        if sucesso:
            bd.marcar_notificado_vencimento(cid)
            print(f"Notificacao registrada para {nome} (PO {po_codigo}, vencimento {po_fim}).")

    bd.fechar()
    print("Processo de notificacao concluido.")


if __name__ == "__main__":
    main()
