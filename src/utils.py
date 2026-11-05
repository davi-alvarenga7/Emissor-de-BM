"""Utilitários: senha, datas, números, validações e mensagens de erro seguras."""

import binascii
import hashlib
import logging as _logging
import os
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

try:
    import bcrypt  # type: ignore[import-not-found]

    _HAS_BCRYPT: bool = True
except Exception:  # pragma: no cover - dependência opcional
    _HAS_BCRYPT: bool = False

_logger = _logging.getLogger("ebm")
_logger.addHandler(_logging.NullHandler())


# ------------------------------------------------------------------ senha
def hash_senha(senha: str) -> str:
    """Gera hash da senha. bcrypt se disponível; senão PBKDF2-HMAC-SHA256."""
    if _HAS_BCRYPT:
        return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    salt = binascii.hexlify(os.urandom(16)).decode("ascii")
    h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt.encode("ascii"), 200_000)
    return f"pbkdf2${salt}${binascii.hexlify(h).decode('ascii')}"


def confere_senha(senha: str, guardado: str) -> bool:
    """Verifica se a senha confere com o hash guardado."""
    try:
        if guardado.startswith("pbkdf2$"):
            _, salt, hexh = guardado.split("$")
            h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt.encode("ascii"), 200_000)
            return binascii.hexlify(h).decode("ascii") == hexh
        if _HAS_BCRYPT:
            return bcrypt.checkpw(senha.encode("utf-8"), guardado.encode("utf-8"))
    except Exception:
        return False
    return False


# ------------------------------------------------------------------ datas
def hoje_iso() -> str:
    """Retorna a data de hoje no formato ISO (YYYY-MM-DD)."""
    return date.today().isoformat()


def parse_data_flex(v: Any) -> date | None:
    """Aceita date/datetime, serial Excel, dd/mm/aaaa, yyyy-mm-dd, m/d/yyyy."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)):
        try:
            return date(1899, 12, 30) + timedelta(days=int(v))
        except Exception:
            return None
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s.split()[0], fmt).date()
        except Exception:
            pass
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", s)
    if m:
        try:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
            return date(y, mo, d)
        except Exception:
            return None
    return None


def parse_data_us(v: Any) -> date | None:
    """Planilhas 'horas por item' usam m/d/yyyy (ex. 9/30/2026)."""
    if isinstance(v, str):
        for fmt in ("%m/%d/%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(v.strip().split()[0], fmt).date()
            except Exception:
                pass
    return parse_data_flex(v)


def fmt_br(d: Any) -> str:
    """Formata uma data no padrão brasileiro dd/mm/yyyy."""
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d)
        except Exception:
            return str(d)
    return d.strftime("%d/%m/%Y") if d else ""  # type: ignore[union-attr]


def para_data(v: Any) -> date | None:
    """Converte para date (usado nas colunas DATE do SQL Server)."""
    d = parse_data_flex(v)
    return d if d else None


# ------------------------------------------------------------------ números
def parse_num(v: Any) -> float | None:
    """Retorna float ou None. Aceita 'R$ 1.234,56' e '1,234.56'."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("R$", "").replace("\u00a0", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def so_digitos(s: Any) -> str:
    """Retorna apenas os dígitos de uma string."""
    return re.sub(r"\D", "", str(s or ""))


# ------------------------------------------------------------------ texto
def sem_acento(s: Any) -> str:
    """Remove os acentos de um texto."""
    s_norm = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s_norm if not unicodedata.combining(c))


def chave_texto(s: Any) -> str:
    """Chave de comparacao/agrupamento: sem acento, maiuscula e sem espaco extra."""
    return " ".join(sem_acento(s).upper().split())


def lista_eclics(valor: Any) -> list[str]:
    """Normaliza o campo de Usuarios E-clic em uma lista de logins.

    Aceita uma string com varios logins separados por ponto e virgula,
    quebra de linha ou virgula.
    """
    if valor is None:
        return []
    if isinstance(valor, (list, tuple, set)):
        partes = list(valor)
    else:
        partes = re.split(r"[;\r\n,]+", str(valor))
    saida: list[str] = []
    vistos: set[str] = set()
    for p in partes:
        p_clean = str(p or "").strip()
        if not p_clean:
            continue
        k = chave_texto(p_clean)
        if k in vistos:
            continue
        vistos.add(k)
        saida.append(p_clean)
    return saida


# ------------------------------------------------------------------ validações
def valida_cnpj(cnpj: Any) -> bool:
    """Valida CNPJ: 14 digitos e digitos verificadores corretos."""
    d = so_digitos(cnpj)
    if len(d) != 14:
        return False
    if len(set(d)) == 1:
        return False
    if _digito_cnpj(d, 5) != int(d[12]):
        return False
    if _digito_cnpj(d, 6) != int(d[13]):
        return False
    return True


def _digito_cnpj(cnpj: str, peso_inicial: int) -> int:
    """Calcula um digito verificador do CNPJ."""
    pesos = list(range(peso_inicial, 1, -1)) + list(range(9, 1, -1))
    soma = sum(int(d) * p for d, p in zip(cnpj, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def valida_email(e: Any) -> bool:
    """Valida formato basico de e-mail."""
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(e or "").strip()))


# ------------------------------------------------------------------ seguranca de erro
def mensagem_erro_segura(exc: Exception) -> str:
    """Retorna uma mensagem generica para o usuario e registra o erro real no log.

    Nunca exibe rastreamento completo, senhas, strings de conexao ou dados
    internos do banco para o usuario final.
    """
    _logger.exception("Erro interno: %s", exc)
    return "Ocorreu um erro interno. Consulte o administrador do sistema."
