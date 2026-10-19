# Sistema Emissor de Boletim de Medição (BM) — Especificação para Desenvolvimento

> Documento-prompt. Fonte única da verdade para implementação. Não desenvolver fora deste escopo sem atualizar aqui.

## 1. Visão geral e propósito

Sistema **desktop** para emissão automática do **Boletim de Medição** de serviços de consultoria em TELECOM da **contratante fixa DBR ENERGIES S/A**.

Propósito do documento BM (template `206000_PRJ-25-06_PRJ-25-05_SERROM ENGENHARIA_BM-2026-009.xlsx`, aba `BM-2026-009`, `B1:O46`):
- Formalizar por **PO (contrato)** as horas trabalhadas por projeto no período, converter em valores (`horas × valor hora`) e controlar acumulado vs. saldo do contrato.
- Servir como base de faturamento. Cabeçalho traz `RM N.º, Período, Emissão, Revisão, Contrato, PO, Início/Fim PO, Objeto, Valor Estimado, Contratante, Contratada, CNPJ`. Tabela traz 7+ linhas `Item, Projeto, Descrição, Valor Hora, Horas Anterior, Horas Período, Horas Acumuladas, Total Anterior, Total Período, Acumulado, Saldo`. Rodapé com assinaturas `Gerente DBR` e `Contratada`.

Outras abas do arquivo original (`Tdocumlist`, `Sheet2`, `Resumo`) são **legado/referência e NÃO fazem parte do sistema**. Sistema só lê/escreve o template BM.

## 2. Stack (definida)

- **Desktop:** Python 3.11+ com Tkinter (layout azul/branco). Executável via PyInstaller (`E-BM.exe`).
- **Banco:** **SQL Server 2016** via `pyodbc` + Microsoft ODBC Driver 17. Conexão em `config.json`.
- **Excel:** `openpyxl` (leitura do lote + escrita do BM preservando template, fórmulas e formatação `R$`).
- **PDF:** `reportlab` (template próprio com o logo DBR, mesma informação do XLSX).
- **Senha:** `bcrypt` (cost 12) com fallback PBKDF2-HMAC-SHA256. Nunca em claro.
- **Datas:** serial Excel ↔ `date` (ex.: 46291 = 26/09/2026).

### Módulos

| Arquivo | Responsabilidade |
|---|---|
| `app.py` | Interface gráfica (Tkinter) e navegação entre telas. |
| `db.py` | Conexão com o SQL Server, DDL e operações de domínio. |
| `boletim.py` | Geração do BM em XLSX e PDF; leitura das planilhas de horas. |
| `util.py` | Senha, datas, números e validações. |

## 3. Modelo de dados (SQL Server 2016)

Script de criação: `schema_sqlserver2016.sql` (executar no SSMS) — o sistema também
cria as tabelas automaticamente ao iniciar (DDL idempotente em `db.DDL`).

| Tabela | Papel | Chaves / regras |
|---|---|---|
| `dbo.users` | Usuários do sistema (multiusuário, sem logout) | `login` UNIQUE (collation `Latin1_General_CI_AS` → case-insensitive); `is_admin` = 1 apenas no 1º cadastrado |
| `dbo.companies` | Empresas (1 empresa = 1 PO) | `cnpj` UNIQUE; `po_codigo` UNIQUE; `usuario_eclic` UNIQUE (CI); CHECK `po_fim >= po_inicio`; CHECK valores `>= 0` |
| `dbo.bms` | Boletins emitidos | `IDENTITY(1,1)`; UNIQUE `(company_id, rm_numero, revisao)`; `xlsx_blob`/`pdf_blob` `VARBINARY(MAX)`; CHECK `origem IN ('LOTE','MANUAL','BASE')`; snapshot dos dados da empresa/PO no momento da emissão |
| `dbo.bm_items` | Itens (1 linha por projeto distinto) | `bm_id` FK `ON DELETE CASCADE`; UNIQUE `(bm_id, projeto)`; `horas_anterior` NULL = sem base/histórico |

Tipos: `INT IDENTITY(1,1)`, `NVARCHAR`, `DATE`, `DECIMAL(18,2)` (dinheiro), `DECIMAL(18,4)` (horas), `DATETIME2(0)`, `VARBINARY(MAX)`, `BIT`.

**Regra de snapshot:** editar a empresa **não** altera boletins já emitidos — `bms` guarda cópia de nome, CNPJ, PO, datas, valor total, objeto e valor hora.

## 4. Telas (fluxo + layout azul/branco moderno)

Todas desktop, mesma identidade: header azul (#0B5ED7), fundo branco/cinza claro, botões primários azuis, logo DBR no topo, mensagens em caixa de diálogo.

### T1 — Login (inicial se já houver usuário)
- Inputs: `Login, Senha` + botões `Entrar, Cadastrar-se, Esqueci a senha`.
- `Entrar`: valida, erro genérico "Login ou senha inválidos". Sucesso → T3.
- `Cadastrar-se` → T2. `Esqueci` → texto: "Procure o administrador (primeiro usuário) para resetar sua senha." Sem e-mail automático.
- Se banco vazio (primeiro uso) → pula direto para T2.

### T2 — Cadastro de usuário
- Inputs: `Nome Completo*, Login*, E-mail*, Senha*, Confirmar Senha*`.
- Travas: todos obrigatórios, login único (avisa "Login já existe"), e-mail com `@` e `.`, senha ≥6, confirmação igual.
- 1º cadastro: `is_admin=1`. Após salvar → entra direto na T3 (sem voltar ao login).

### T3 — Inicial (home)
- Logo DBR no canto superior esquerdo, título `E-BM`, 3 botões centralizados:
  `Cadastro de Nova Empresa → T4`, `Empresas Cadastradas → T5`, `Emissão de Boletins em Lote → T7`.
- Sem Sair/Gerenciar/Ajuda por decisão.

### T4 — Cadastro de Nova Empresa
- Campos na ordem (mesma do lote): `Razão Social*, CNPJ*, Código PO*, Início PO*, Fim PO*, Valor Total PO*, Objeto*, E-mail contato*, Valor Hora*, Responsável*, Usuário E-clic*`.
- Travas: obrigatórios, CNPJ formato+único, PO único, `fim>=inicio`, valores ≥0, e-mail básico, E-clic único.
- Ações: `Salvar` (confirmação), `Cadastro em lote (upload Excel)`.
- Lote: upload `.xlsx`, 1ª linha cabeçalho ignorada, colunas **exatamente nesta ordem**. Por linha: se qualquer célula obrigatória em branco → pula; se `CNPJ`, `PO` ou `E-clic` duplicado (banco ou no próprio arquivo) → pula. Ao final relatório: "X cadastradas, Y puladas (listar linhas/motivo)".

### T5 — Empresas Cadastradas
- Tabela `Responsável | Razão Social | CNPJ` + barra de busca (filtra pelos 3, case-insensitive) + por linha 4 botões:
  1. `Editar → T5a`
  2. `Emitir Boletim (manual) → T6`
  3. `Boletins Emitidos → T8`
  4. `Importar BM base` (upload do 1º BM, vínculo pelo `CNPJ` em `H9`; salva como `origem='BASE'`)

### T5a — Editar empresa
- Mesmos campos de T4 pré-preenchidos, `Salvar / Voltar`.
- `Salvar`: UPDATE em `companies`, mensagem "Informações atualizadas". Não altera `bms` já emitidos. `Voltar` → T5 sem salvar.

### T6 — Emitir BM individual (manual)
- Empresa travada (dados PO e valor hora exibidos, não editáveis). Digitáveis: `Período Inicial*, Período Final*` e N linhas de `Projeto*` + `Horas No Período*`.
- `Emissão` auto `= fim+1`, `RM` auto sequencial, `Anterior` puxa do último BM (ou branco).

### T7 — Emissão em Lote (upload horas)
- Upload múltiplo `.xlsx`. O sistema **detecta o cabeçalho pelo nome das colunas**, aceitando `cadastro horas` e `horas por item`:
  - Usuário: `USUÁRIO` ou `RESPONSÁVEL`
  - Horas: `HORAS`
  - Projeto: `PROJETO` (se existir, agrupa por linha; senão usa o `PROJETO:` do relatório)
  - Aprovação: `APROVAÇÃO` (quando presente, **somente linhas "Sim"** são faturadas)
  - Período: `DATA INICIAL` / `DATA FINAL` (aceita `dd/mm/aaaa` e `m/d/yyyy`, deduzido pelo formato)
- Regras: todos os arquivos devem ter a mesma data inicial/final, senão aborta com erro; usuários sem `Usuário E-clic` correspondente são ignorados; 1 BM por empresa, 1 linha por projeto.

### T8 — Boletins Emitidos (por empresa)
- Lista desc por emissão: cada item é clicável, rotulado `Boletim <NOME EMPRESA> - <dd/mm/yyyy de emissão> | <RM> | Rev <N> | <origem>`.
- Seleção habilita `Baixar XLSX` e `Baixar PDF` (bytes do banco → arquivo local).
- Reemissão do mesmo período/RM: novo registro com mesmo `rm_numero` e `revisao+1`.

## 5. Template BM — mapa de preenchimento (aba BM-2026-009)

Preservar merges, formatos `R$` e fórmulas; o logo DBR é inserido em `L1`.

- `D1=BOLETIM DE MEDIÇÃO`, `H1=RM N.°:`, `I1=rm_numero`
- `H2=Período:`, `I2="dd/mm/yyyy até dd/mm/yyyy"`, `H3=Emissão:`, `I3=data emissao`, `K6=Revisão: N`
- `B7=Contrato: (vazio)`, `E7=PO: <po>`, `G7=Início PO: dd/mm/yyyy`
- `B8=Objeto: <objeto>`, `E8=Valor Estimado PO:`, `F8==E21`, `G8=Fim PO: dd/mm/yyyy`
- `B9=Contratante: DBR ENERGIES S/A`, `E9=Contratada: <razão social>`, `G9=CNPJ Contratada:`, `H9=cnpj`, `I9=TOTAL (R$)`
- Linha 10 header fixo. Linhas 12+: `B=item_seq, C=projeto texto cheio, D=descrição, E=valor_hora, F=horas_anterior (branco se NULL), G=horas_periodo, H==IF(F="",G,F+G), I==IF(F="","",F*E), J==E*G, K==I+J, L=saldo (só 1ª linha: ==E21-K12-K13...K19)`.
- `B21=TOTAL CONTRATO:, E21=valor total da PO`, `F21=SUM(F12:F20)` … `L21=SUM(L12:L16)`.
- `I23=I21, J23=J21, K23=K21, L23=L21`. `D30=Gerente DBR Energies S.A., F30=<razão social>`.

## 6. Regras de negócio / cálculos

1. Contratante sempre `DBR ENERGIES S/A`.
2. Valor hora por empresa/PO; 0 calcula com 0.
3. Período lote = datas da planilha; emissão = `fim + 1 dia`; individual: digitado + mesma regra de emissão.
4. Anterior: do último BM da empresa; sem base/histórico → NULL/branco (não 0).
5. RM sequencial por empresa: `BM-YYYY-NNN`. Ex `BM-2026-009 → BM-2026-010`. Primeiro sem base: deixar em branco.
6. Revisão: 0 na emissão nova; reemitir mesmo RM/período → +1.
7. Arquivo de download: `Boletim <NOME EMPRESA> - <data de emissão>.xlsx` / `.pdf`.
8. Lote: match de `Usuário E-clic` sem diferenciar maiúsculas/minúsculas; soma de horas por `(empresa, projeto)`; 2 casas decimais.

## 7. Validações e erros

- Login duplicado, CNPJ/PO/E-clic duplicados, e-mail sem `@`, datas invertidas, valor negativo, lote com datas divergentes, base com CNPJ divergente, planilha sem cabeçalho reconhecível → mensagem na tela, sem crash.
- Lote nunca cadastra parcial com erro crítico de modelo; linhas com branco/duplicada apenas puladas e listadas.
- Banco indisponível ou não configurado → janela explicando `config.json`, criação do banco e execução do script de esquema.

## 8. Critérios de aceite

- [ ] Primeiro uso → cadastro → entra direto; login posterior funciona; duplicado bloqueia; admin flag no 1º.
- [ ] Cadastro de empresa individual + lote na ordem definida, com relatório de puladas.
- [ ] Lista com busca Responsável/Razão Social/CNPJ; editar mostra "Informações atualizadas" e não altera BMs antigos; base importada por CNPJ.
- [ ] Lote com 2+ planilhas gera 1 BM/empresa, horas somadas por projeto, período/emissão/RM corretos, XLSX idêntico ao template, PDF legível, ambos baixáveis com o nome correto.
- [ ] Linhas com `APROVAÇÃO = Não` não são faturadas.
- [ ] Individual manual só pede Período/Projeto/Horas; resto automático/travado.
- [ ] Reemissão gera Rev 1,2...; sem histórico deixa branco.
- [ ] Banco no SQL Server 2016, esquema criado por `schema_sqlserver2016.sql` e também automaticamente pelo sistema.

## 9. Fora de escopo (não implementar)

Abas `Tdocumlist/Sheet2/Resumo`, logout/Sair, gestão de usuários além de reset pelo admin, multi-PO por empresa, envio de e-mail automático, SQLite.
