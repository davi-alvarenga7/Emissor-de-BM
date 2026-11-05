"""Servico de autenticacao e gerenciamento de usuarios."""

from typing import Any

from src.database import Banco
from src.utils import confere_senha, hash_senha, mensagem_erro_segura, valida_email


class AuthService:
    """Servico responsavel por autenticacao e gerenciamento de usuarios."""

    def __init__(self, banco: Banco) -> None:
        self.banco: Banco = banco

    def autenticar(self, login: str, senha: str) -> dict[str, Any] | None:
        """Autentica um usuario. Retorna os dados do usuario ou None se falhar."""
        try:
            usuario: dict[str, Any] | None = self.banco.buscar_usuario(login)
            if not usuario:
                return None
            if not confere_senha(senha, str(usuario.get("senha_hash", ""))):
                return None
            return usuario
        except Exception as exc:
            raise RuntimeError(mensagem_erro_segura(exc)) from exc

    def cadastrar_usuario(
        self,
        nome_completo: str,
        login: str,
        email: str,
        senha: str,
    ) -> int:
        """Cadastra um novo usuario. Retorna o ID gerado."""
        try:
            if not valida_email(email):
                raise ValueError("E-mail invalido")
            if len(senha) < 8:
                raise ValueError("Senha deve ter no minimo 8 caracteres")
            if self.banco.buscar_usuario(login):
                raise ValueError("Login ja existe")
            is_admin: bool = not self.banco.tem_usuario()
            return self.banco.criar_usuario(
                nome_completo, login, email, hash_senha(senha), is_admin
            )
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(mensagem_erro_segura(exc)) from exc

    def listar_usuarios(self) -> list[dict[str, Any]]:
        """Lista todos os usuarios."""
        try:
            return self.banco.listar_usuarios()
        except Exception as exc:
            raise RuntimeError(mensagem_erro_segura(exc)) from exc

    def atualizar_usuario(
        self,
        login: str,
        nome_completo: str,
        email: str,
        is_admin: bool = False,
        senha: str | None = None,
    ) -> None:
        """Atualiza um usuario existente."""
        try:
            senha_hash: str | None = hash_senha(senha) if senha else None
            self.banco.atualizar_usuario(
                login, nome_completo, email, is_admin=is_admin, senha_hash=senha_hash
            )
        except Exception as exc:
            raise RuntimeError(mensagem_erro_segura(exc)) from exc

    def excluir_usuario(self, login: str, usuario_atual_login: str) -> None:
        """Exclui um usuario. Nao permite excluir a si mesmo."""
        try:
            if login == usuario_atual_login:
                raise ValueError("Voce nao pode excluir o proprio usuario")
            self.banco.excluir_usuario(login)
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(mensagem_erro_segura(exc)) from exc

    def resetar_senha(self, login: str, nova_senha: str) -> None:
        """Redefine a senha de um usuario (admin)."""
        try:
            if len(nova_senha) < 8:
                raise ValueError("Nova senha deve ter no minimo 8 caracteres")
            self.banco.resetar_senha(login, hash_senha(nova_senha))
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(mensagem_erro_segura(exc)) from exc

    def tem_usuario(self) -> bool:
        """Verifica se existe pelo menos um usuario cadastrado."""
        try:
            return self.banco.tem_usuario()
        except Exception as exc:
            raise RuntimeError(mensagem_erro_segura(exc)) from exc

    def obter_perfil(self, login: str) -> dict[str, Any] | None:
        """Retorna o perfil de um usuario."""
        try:
            return self.banco.obter_perfil_usuario(login)
        except Exception as exc:
            raise RuntimeError(mensagem_erro_segura(exc)) from exc
