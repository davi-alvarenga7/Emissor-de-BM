"""Constantes de configuração da aplicação (cores, fontes, temas)."""

from typing import Final

# ------------------------------------------------------------------ cores
AZUL: Final[str] = "#1F6AA5"      # cor de destaque (botoes principais / salvar)
AZUL_ESCURO: Final[str] = "#15456B"  # hover / estado ativo dos botoes principais

# ------------------------------------------------------------------ fontes
FONT: Final[tuple[str, int]] = ("Segoe UI", 11)
FONT_BOLD: Final[tuple[str, int, str]] = ("Segoe UI", 12, "bold")
FONT_TITULO: Final[tuple[str, int, str]] = ("Segoe UI", 16, "bold")

# ------------------------------------------------------------------ aplicativo
APP_TITLE: Final[str] = "E-BM - Emissor de Boletim de Medição | DBR Energies"
APP_GEOMETRY: Final[str] = "1120x720"

# ------------------------------------------------------------------ banco de dados
CONTRATANTE: Final[str] = "DBR ENERGIES S/A"
DESCRICAO_PADRAO: Final[str] = "Servicos de Consultoria em TELECOM"

# ------------------------------------------------------------------ templates
LIN_ITEM_INI: Final[int] = 12          # primeira linha de item no template
LIN_ITEM_FIM: Final[int] = 20          # ultima linha de item prevista
LIN_TOTAL: Final[int] = 21             # linha de totais
LIN_MIRROR: Final[int] = 23            # linha de repeticao dos totais
LIN_ASSIN: Final[int] = 30             # linha de assinaturas
CAPACIDADE_ITENS: Final[int] = LIN_ITEM_FIM - LIN_ITEM_INI + 1

# ------------------------------------------------------------------ colunas aceitas para atividade
COLUNAS_ITEM: Final[tuple[str, ...]] = (
    "ITEM", "ITENS", "ATIVIDADE", "ATIVIDADES", "TAREFA",
    "DESCRICAO ATIVIDADE", "DESCRICAO DE ATIVIDADE", "SERVICO",
)

# ------------------------------------------------------------------ formatos
MONEY: Final[str] = 'R$ #,##0.00'
HOURS: Final[str] = '#,##0.00'
