"""Servico de envio de e-mail via SMTP."""

import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

from src.utils import mensagem_erro_segura, valida_email


class EmailService:
    """Servico responsavel por enviar e-mails via SMTP."""

    def __init__(self, smtp_cfg: dict[str, Any]) -> None:
        self.smtp_cfg: dict[str, Any] = smtp_cfg

    def esta_configurado(self) -> bool:
        """Verifica se o SMTP esta configurado com servidor e usuario."""
        return bool(
            self.smtp_cfg.get("servidor") and self.smtp_cfg.get("usuario")
        )

    def enviar(
        self,
        destinatario: str,
        assunto: str,
        corpo: str,
        anexos: list[tuple[str, bytes]] | None = None,
    ) -> None:
        """Envia um e-mail com opcao de anexos.

        `anexos` e uma lista de tuplas (nome_arquivo, bytes_conteudo).
        """
        try:
            if not self.esta_configurado():
                raise ValueError("Configuracao de SMTP nao encontrada")

            if not valida_email(destinatario):
                raise ValueError("E-mail invalido")

            servidor: str = str(self.smtp_cfg.get("servidor", ""))
            porta: int = int(self.smtp_cfg.get("porta", 587))
            usuario: str = str(self.smtp_cfg.get("usuario", ""))
            senha: str = str(self.smtp_cfg.get("senha", ""))
            remetente: str = str(
                self.smtp_cfg.get("remetente") or self.smtp_cfg.get("usuario", "")
            )
            usar_tls: bool = bool(self.smtp_cfg.get("usar_tls", True))

            contexto = ssl.create_default_context() if usar_tls else None

            msg = EmailMessage()
            msg["From"] = remetente
            msg["To"] = destinatario
            msg["Subject"] = assunto
            msg.set_content(corpo)

            if anexos:
                for nome, dados in anexos:
                    msg.add_attachment(
                        dados, maintype="application", subtype="zip",
                        filename=nome,
                    )

            with smtplib.SMTP(servidor, porta, timeout=30) as server:
                if usar_tls:
                    server.starttls(context=contexto)
                server.login(usuario, senha)
                server.send_message(msg)
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(mensagem_erro_segura(exc)) from exc
