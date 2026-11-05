"""Servico de negocio para geracao de Boletins de Medicao."""

import io
import zipfile
from datetime import date, datetime, timedelta
from typing import Any

from src.config import CONTRATANTE, DESCRICAO_PADRAO
from src.database import Banco
from src.utils import (
    chave_texto,
    fmt_br,
    mensagem_erro_segura,
    para_data,
    parse_num,
)


class BoletimService:
    """Servico responsavel pela logica de negocio de geracao de boletins."""

    def __init__(self, banco: Banco) -> None:
        self.banco: Banco = banco

    def gerar_e_salvar_bm(
        self,
        emp: dict[str, Any],
        periodo_ini: Any,
        periodo_fim: Any,
        emissao: Any,
        rm: str,
        revisao: int,
        itens: list[tuple[str, str, float, Any, float]],
        origem: str,
    ) -> int:
        """Gera XLSX/PDF, calcula totais e grava no SQL Server.

        Retorna o ID do boletim gravado.
        """
        try:
            emp_dict: dict[str, Any] = dict(emp)
            po_ini: date | None = para_data(emp_dict["po_inicio"])
            po_fim: date | None = para_data(emp_dict["po_fim"])
            valor_total: float = float(emp_dict["po_valor_total"] or 0)
            tipo: str = str(emp_dict.get("tipo_faturamento") or "HORISTA").upper()
            vfm: float | None = parse_num(emp_dict.get("valor_fixo_mensal"))

            dados: dict[str, Any] = {
                "rm": rm,
                "periodo_txt": f"{fmt_br(po_ini)} ate {fmt_br(po_fim)}",
                "emissao_txt": fmt_br(para_data(emissao)),
                "revisao": revisao,
                "po": emp_dict["po_codigo"],
                "po_ini_txt": fmt_br(po_ini),
                "po_fim_txt": fmt_br(po_fim),
                "valor_total": valor_total,
                "objeto": emp_dict["po_objeto"],
                "contratada": emp_dict["nome"],
                "cnpj": emp_dict["cnpj"],
                "itens": itens,
                "tipo_faturamento": tipo,
                "valor_fixo_mensal": vfm,
            }

            # Importacao tardia para evitar dependencia circular com UI
            from src.boletim import construir_xlsx_bm, construir_pdf_bm  # type: ignore[import-not-found]

            xlsx_bytes: bytes
            ta: float
            tp: float
            tac: float
            saldo: float
            xlsx_bytes, ta, tp, tac, saldo = construir_xlsx_bm(dados)
            pdf_bytes: bytes = construir_pdf_bm(dados)

            revisao_calc: int = self.banco.proxima_revisao(
                emp_dict["id"], rm or "", para_data(periodo_ini), para_data(periodo_fim)
            )
            if revisao_calc:
                dados["revisao"] = revisao_calc
                xlsx_bytes, ta, tp, tac, saldo = construir_xlsx_bm(dados)
                pdf_bytes = construir_pdf_bm(dados)

            return self.banco.salvar_bm(
                emp_dict,
                para_data(periodo_ini),
                para_data(periodo_fim),
                para_data(emissao),
                rm,
                revisao_calc,
                itens,
                origem,
                xlsx_bytes,
                pdf_bytes,
                (ta, tp, tac, saldo),
            )
        except Exception as exc:
            raise RuntimeError(mensagem_erro_segura(exc)) from exc

    def processar_lote(
        self,
        caminhos_arquivos: list[str],
    ) -> dict[str, Any]:
        """Processa boletins em lote a partir de planilhas de horas.

        Retorna um dicionario com o relatorio de processamento.
        """
        try:
            # Importacao tardia
            from src.boletim import ler_horas_arquivo, consolidar_por_projeto_item  # type: ignore[import-not-found]

            mapa_eclic: dict[str, int] = self.banco.mapa_eclic_empresa()
            datas: set[tuple[str, str]] = set()
            n_linhas: int = 0
            n_aprov: int = 0
            n_ignorados: int = 0
            por_emp: dict[int, list[tuple[str, str, str, float, bool]]] = {}
            usuarios_por_emp: dict[int, set[str]] = {}

            for path in caminhos_arquivos:
                info: dict[str, Any] = ler_horas_arquivo(path)
                if info.get("data_ini") and info.get("data_fim"):
                    datas.add(
                        (
                            info["data_ini"].isoformat(),
                            info["data_fim"].isoformat(),
                        )
                    )
                for usu, proj, item, h, aprov in info["linhas"]:
                    n_linhas += 1
                    if not aprov:
                        continue
                    n_aprov += 1
                    cid: int | None = mapa_eclic.get(chave_texto(usu))
                    if cid is None:
                        n_ignorados += 1
                        continue
                    por_emp.setdefault(cid, []).append((usu, proj, item, h, aprov))
                    usuarios_por_emp.setdefault(cid, set()).add(chave_texto(usu))

            if len(datas) > 1:
                raise ValueError(
                    f"Datas divergentes no lote: {sorted(datas)}.\n"
                    "Todos os arquivos devem ter a mesma data inicial/final."
                )
            if not datas:
                raise ValueError(
                    "Data inicial/final nao encontrada nas planilhas"
                )

            pi: str
            pf: str
            pi, pf = sorted(datas)[0]
            data_inicio: date = date.fromisoformat(pi)
            data_fim: date = date.fromisoformat(pf)
            emissao: date = data_fim + timedelta(days=1)

            gerados: list[str] = []
            for cid, regs in por_emp.items():
                emp: dict[str, Any] | None = self.banco.buscar_empresa(cid)
                if not emp:
                    continue
                tipo: str = str(emp.get("tipo_faturamento") or "HORISTA").upper()
                mapa: dict[tuple[str, str], tuple[Any, Any]] = (
                    self.banco.ultimo_mapa_itens(cid)
                )
                vfm: float | None = parse_num(emp.get("valor_fixo_mensal"))

                if tipo == "MENSALISTA":
                    if vfm is None or vfm < 0:
                        gerados.append(
                            f"{emp['nome']} -> ERRO: Valor Fixo Mensal nao configurado"
                        )
                        continue
                    itens_lote: list[tuple[str, str, float, Any, float]] = [
                        ("REFERÊNCIA", DESCRICAO_PADRAO, 0, None, 0)
                    ]
                    total_h: float = sum(float(r[3]) for r in regs if r[4])
                    valor_periodo: float = vfm
                else:
                    vh: float = float(emp["valor_hora"])
                    consolidados: list[dict[str, Any]] = (
                        consolidar_por_projeto_item(regs, somente_aprovados=True)
                    )
                    itens_lote = []
                    for c in consolidados:
                        ant: tuple[Any, Any] | None = mapa.get(
                            (c["projeto"], c["item"]), (None, None)
                        )
                        itens_lote.append(
                            (
                                c["projeto"],
                                c["item"],
                                vh,
                                float(ant[0]) if ant[0] is not None else None,
                                float(c["horas"]),
                            )
                        )
                    total_h = sum(float(c["horas"]) for c in consolidados)
                    valor_periodo = total_h * vh

                rm: str = self.banco.proximo_rm(cid, emissao.isoformat())
                self.gerar_e_salvar_bm(
                    emp,
                    data_inicio,
                    data_fim,
                    emissao,
                    rm,
                    0,
                    itens_lote,
                    "LOTE",
                )
                gerados.append(
                    f"{emp['nome']} -> {rm or '(sem RM)'}\n"
                    f"    {len(usuarios_por_emp.get(cid, ()))} usuario(s) E-clic | "
                    f"{len(itens_lote)} item(ns) [projeto + atividade]\n"
                    f"    Total de horas: {total_h:,.2f} h | "
                    f"Valor do periodo: R$ {valor_periodo:,.2f}"
                )

            msg: str = (
                f"Periodo: {fmt_br(data_inicio)} ate {fmt_br(data_fim)}\n"
                f"Emissao: {fmt_br(emissao)}\n"
                f"Linhas lidas: {n_linhas} | aprovadas: {n_aprov} | "
                f"rejeitadas: {n_linhas - n_aprov}\n"
                f"Usuarios sem empresa cadastrada (ignorados): {n_ignorados}\n"
                f"Boletins gerados: {len(gerados)}\n\n"
                + "\n".join(gerados)
            )

            return {
                "sucesso": True,
                "mensagem": msg,
                "periodo_inicio": data_inicio,
                "periodo_fim": data_fim,
                "emissao": emissao,
                "boletins_gerados": len(gerados),
            }
        except Exception as exc:
            raise RuntimeError(mensagem_erro_segura(exc)) from exc

    def importar_bm_preenchido(
        self,
        emp_id: int,
        caminho_arquivo: str,
    ) -> str:
        """Importa um BM preenchido de uma planilha Excel."""
        try:
            from openpyxl import load_workbook  # type: ignore[import-not-found]

            from src.boletim import DESCRICAO_PADRAO as _DESC  # type: ignore[import-not-found]

            wb = load_workbook(caminho_arquivo, data_only=True)
            ws = wb.active

            emp: dict[str, Any] | None = self.banco.buscar_empresa(emp_id)
            if not emp:
                raise ValueError("Empresa nao encontrada")

            cnpj_arquivo: str = str(so_digitos_aux(ws["H9"].value or ""))
            if cnpj_arquivo and cnpj_arquivo != so_digitos_aux(emp["cnpj"]):
                raise ValueError(
                    f"CNPJ do arquivo ({cnpj_arquivo}) difere da empresa ({emp['cnpj']})"
                )

            rm: str = str(ws["I1"].value or "").strip()
            per: str = str(ws["I2"].value or "")
            import re

            ds: list[date | None] = [
                para_data(x)
                for x in re.findall(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", per)
            ]
            pi: date | None = ds[0] if len(ds) > 0 and ds[0] else para_data(
                emp["po_inicio"]
            )
            pf: date | None = ds[1] if len(ds) > 1 and ds[1] else para_data(
                emp["po_fim"]
            )
            emi: date = para_data(ws["I3"].value) or date.today()

            mrev: re.Match[str] | None = re.search(
                r"(\d+)", str(ws["K6"].value or "0")
            )
            rev: int = int(mrev.group(1)) if mrev else 0

            itens: list[tuple[str, str, float, Any, float]] = []
            for r in range(12, 21):
                proj: Any = ws.cell(row=r, column=3).value
                if not proj:
                    continue
                ativ: str = str(
                    ws.cell(row=r, column=4).value or DESCRICAO_PADRAO
                ).strip()
                vh: float = parse_num(ws.cell(row=r, column=5).value) or 0
                ha: float | None = parse_num(ws.cell(row=r, column=6).value)
                hp: float = parse_num(ws.cell(row=r, column=7).value) or 0
                itens.append((str(proj), ativ, vh, ha, hp))

            bm_id: int = self.gerar_e_salvar_bm(
                emp, pi, pf, emi, rm, rev, itens, "BASE"
            )
            return f"BM gerado (ID={bm_id})"
        except Exception as exc:
            raise RuntimeError(mensagem_erro_segura(exc)) from exc

    def reemitir_bm(
        self,
        bm_id: int,
        empresa_id: int,
        origem: str | None = None,
    ) -> int:
        """Reemite um boletim gerando uma nova revisao."""
        try:
            r: dict[str, Any] | None = self.banco.buscar_bm(bm_id)
            if not r:
                raise ValueError("Boletim nao encontrado")

            emp: dict[str, Any] | None = self.banco.buscar_empresa(empresa_id)
            if not emp:
                raise ValueError("Empresa nao encontrada")

            itens_bd: list[dict[str, Any]] = self.banco.buscar_itens_bm(r["id"])
            if not itens_bd:
                raise ValueError("Nenhum item encontrado para este boletim")

            itens: list[tuple[str, str, float, Any, float]] = [
                (
                    i["projeto"],
                    i["descricao"],
                    float(i["valor_hora"]),
                    i["horas_anterior"],
                    float(i["horas_periodo"]),
                )
                for i in itens_bd
            ]

            pi: date | None = para_data(r["periodo_ini"])
            pf: date | None = para_data(r["periodo_fim"])
            emi: date = date.today()
            rev: int = self.banco.proxima_revisao(
                emp["id"], str(r["rm_numero"]), pi, pf
            )
            tipo: str = str(emp.get("tipo_faturamento") or "HORISTA").upper()
            vfm: float | None = parse_num(emp.get("valor_fixo_mensal"))

            dados: dict[str, Any] = {
                "rm": str(r["rm_numero"]),
                "periodo_txt": f"{fmt_br(pi)} ate {fmt_br(pf)}",
                "emissao_txt": fmt_br(emi),
                "revisao": rev,
                "po": emp["po_codigo"],
                "po_ini_txt": fmt_br(emp["po_inicio"]),
                "po_fim_txt": fmt_br(emp["po_fim"]),
                "valor_total": float(emp["po_valor_total"] or 0),
                "objeto": emp["po_objeto"],
                "contratada": emp["nome"],
                "cnpj": emp["cnpj"],
                "itens": itens,
                "tipo_faturamento": tipo,
                "valor_fixo_mensal": vfm,
            }

            from src.boletim import (  # type: ignore[import-not-found]
                construir_xlsx_bm,
                construir_pdf_bm,
            )

            xlsx_bytes: bytes
            ta: float
            tp: float
            tac: float
            saldo: float
            xlsx_bytes, ta, tp, tac, saldo = construir_xlsx_bm(dados)
            pdf_bytes: bytes = construir_pdf_bm(dados)

            self.banco.salvar_bm(
                emp,
                pi,
                pf,
                emi,
                str(r["rm_numero"]),
                rev,
                itens,
                origem or r.get("origem") or "MANUAL",
                xlsx_bytes,
                pdf_bytes,
                (ta, tp, tac, saldo),
            )
            return rev
        except Exception as exc:
            raise RuntimeError(mensagem_erro_segura(exc)) from exc


def so_digitos_aux(valor: Any) -> str:
    """Retorna apenas os dígitos de uma string (funcao auxiliar local)."""
    import re

    return re.sub(r"\D", "", str(valor or ""))
