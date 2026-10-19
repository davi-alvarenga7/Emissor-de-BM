# -*- coding: utf-8 -*-
"""Utilitários: senha, datas, números, validações."""
import os
import re
import hashlib
import binascii
from datetime import date, datetime, timedelta

try:
    import bcrypt
    _HAS_BCRYPT = True
except Exception:
    _HAS_BCRYPT = False


# ------------------------------------------------------------------ senha
def hash_senha(senha: str) -> str:
    """Gera hash da senha. bcrypt se disponível; senão PBKDF2-HMAC-SHA256."""
    if _HAS_BCRYPT:
        return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    salt = binascii.hexlify(os.urandom(16)).decode("ascii")
    h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt.encode("ascii"), 200_000)
    return f"pbkdf2${salt}${binascii.hexlify(h).decode('ascii')}"


def confere_senha(senha: str, guardado: str) -> bool:
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
    return date.today().isoformat()


def parse_data_flex(v):
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


def parse_data_us(v):
    """Planilhas 'horas por item' usam m/d/yyyy (ex. 9/30/2026)."""
    if isinstance(v, str):
        for fmt in ("%m/%d/%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(v.strip().split()[0], fmt).date()
            except Exception:
                pass
    return parse_data_flex(v)


def fmt_br(d):
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d)
        except Exception:
            return d
    return d.strftime("%d/%m/%Y") if d else ""


def para_data(v):
    """Converte para date (usado nas colunas DATE do SQL Server)."""
    d = parse_data_flex(v)
    return d if d else None


# ------------------------------------------------------------------ números
def parse_num(v):
    """Retorna float ou None. Aceita 'R$ 1.234,56' e '1,234.56'."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("R$", "").replace(" ", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def so_digitos(s) -> str:
    return re.sub(r"\D", "", str(s or ""))


# ------------------------------------------------------------------ validações
def valida_cnpj(cnpj) -> bool:
    return len(so_digitos(cnpj)) == 14


def valida_email(e) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(e or "").strip()))
