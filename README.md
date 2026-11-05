# E-BM - Emissor de Boletim de Medição

Sistema desktop para emissão automática de Boletins de Medição (BM) de serviços
de consultoria.

Banco: **SQL Server 2016** (via `pyodbc` / ODBC Driver 17).

---

## Índice

1. [Requisitos](#requisitos)
2. [Instalação](#instalação)
3. [Configuração inicial (config.json)](#configuração-inicial-configjson)
4. [Configuração do banco de dados](#configuração-do-banco-de-dados)
5. [Estrutura do projeto](#estrutura-do-projeto)
6. [Fluxo do sistema](#fluxo-do-sistema)
7. [Leitura das planilhas de horas](#leitura-das-planilhas-de-horas)
8. [Gerar o executável](#gerar-o-executável)
9. [Especificação técnica do BM](#especificação-técnica-do-bm)
10. [Modelo de dados (SQL Server)](#modelo-de-dados-sql-server)
11. [Telas e regras de negócio](#telas-e-regras-de-negócio)
12. [Template BM — mapa de preenchimento](#template-bm---mapa-de-preenchimento)
13. [Diagnóstico de conexão](#diagnóstico-de-conexão)
14. [Guia de criação dos bancos (SSMS)](#guia-de-criação-dos-bancos-ssms)
15. [Notificação de Vencimento de PO](#notificação-de-vencimento-de-po)

---

## Requisitos

| Item | Versão |
|---|---|
| Python | 3.11+ |
| SQL Server | 2016 ou superior |
| Microsoft ODBC Driver for SQL Server | 17 ou superior |

## Instalação

```bash
pip install -r requirements.txt
python -m src
```

No Windows, também pode ser executado pelo `E-BM.bat` (duplo clique), que
define o `PYTHONPATH` e inicia `python -m src`.

## Configuração inicial (`config.json`)

O arquivo `config.json` contém a conexão com o banco de dados e credenciais de
SMTP. Por motivos de segurança, **ele não é versionado no Git** — não suba este
arquivo para nenhum repositório.

Para configurar o projeto em qualquer ambiente (sua máquina ou o servidor da
empresa):

1. Copie o arquivo de exemplo para o arquivo de configuração real:

```bash
# Linux / macOS / Git Bash
cp config.json.example config.json

# Windows (CMD)
copy config.json.example config.json

# Windows (PowerShell)
Copy-Item config.json.example config.json
```

2. Edite o `config.json` preenchendo com os dados do seu ambiente:

```json
{
  "driver": "ODBC Driver 17 for SQL Server",
  "server": "SEU_SERVIDOR\\SUA_INSTANCIA",
  "port": "",
  "database": "SEU_BANCO",
  "username": "",
  "password": "",
  "trusted_connection": true,
  "encrypt": true,
  "trust_server_certificate": false,
  "connection_timeout": 5,
  "smtp": {
    "servidor": "SEU_SERVIDOR_SMTP",
    "porta": 587,
    "usuario": "SEU_USUARIO_SMTP",
    "senha": "SUA_SENHA_SMTP",
    "remetente": "SEU_EMAIL_REMETENTE",
    "usar_tls": true
  }
}
```

3. Salve o arquivo. O sistema lerá automaticamente as configurações ao iniciar.

> **Importante:** nunca commite o `config.json` com credenciais reais. Ele está
> listado no `.gitignore` para evitar vazamento acidental. Use apenas o
> `config.json.example` como modelo de referência.

---

## Configuração do banco de dados

O sistema se conecta a um SQL Server 2016 (ou superior) por meio do driver ODBC
Driver 17. O `config.json` deve ser preenchido com os dados do seu ambiente:

| Campo | Significado |
|---|---|
| `driver` | Driver ODBC instalado. Use Driver 17 para SQL Server 2016. |
| `server` | Nome completo do servidor/instância (ex.: `SERVIDOR\\INSTANCIA`, `localhost`, `localhost,1433`). |
| `port` | Porta, só usada se o `server` não tiver instância nem vírgula. |
| `database` | Nome do banco de dados (ex.: `EBM_HOMOLOG` para desenvolvimento, `EBM_PROD` para produção). |
| `username` / `password` | Usuário do SQL Server (vazio se usar `trusted_connection`). |
| `trusted_connection` | `true` usa autenticação do Windows (sem senha). |
| `encrypt` / `trust_server_certificate` | Criptografia da conexão. |
| `connection_timeout` | Tempo limite de conexão em segundos. |

> **Atenção:** o `config.json` guarda a senha em texto puro. Para produção,
> prefira `trusted_connection: true` (Windows Authentication) ou um cofre de
> segredos.

Se o banco não estiver configurado, o sistema abre uma janela explicando o que
fazer e oferece um atalho para abrir o `config.json`.

### Criar o banco e aplicar o esquema

O banco de dados deve ser criado manualmente no SSMS (ou por um DBA) com
permissão de `CREATE DATABASE`. Depois de criado, o próprio sistema aplica o
esquema automaticamente ao iniciar (DDL idempotente em `src/database.py`),
bastando ter `db_owner` (ou `db_ddladmin`) no banco de destino.

O script DDL também está documentado na seção "Guia de criação dos bancos"
mais abaixo, para execução manual no SSMS caso desejado.

---

## Estrutura do projeto

| Arquivo / Pasta | Responsabilidade |
|---|---|
| `src/__main__.py` | Ponto de entrada (`python -m src`). |
| `src/ui/app.py` | Interface gráfica (Tkinter / CustomTkinter) e navegação entre telas. |
| `src/ui/widgets.py` | Widgets reutilizáveis da interface. |
| `src/ui/telas/` | Telas do sistema (login, cadastro, home, empresa, boletins, lote, etc.). |
| `src/database.py` | Conexão com o SQL Server, DDL idempotente e operações de domínio. |
| `src/config.py` | Constantes de UI (cores, fontes, template). |
| `src/boletim.py` | Geração do BM em XLSX e PDF; leitura das planilhas de horas. |
| `src/utils.py` | Senha (bcrypt), datas, números e validações. |
| `src/services/auth_service.py` | Serviço de autenticação. |
| `src/services/boletim_service.py` | Serviço de geração de boletins. |
| `src/services/email_service.py` | Serviço de envio de e-mail (SMTP). |
| `src/scripts/notificacao_vencimento.py` | Script independente de vencimento de PO (Task Scheduler). |
| `config.json` | Parâmetros de conexão com o SQL Server (não versionado). |
| `config.json.example` | Modelo de configuração (versionado). |
| `template_bm.xlsx` | Template oficial do BM (obrigatório para gerar os boletins). |
| `logo.png` / `logo.ico` | Logomarca (nos boletins e no executável). |
| `E-BM.spec` | Configuração do PyInstaller para gerar o executável. |
| `E-BM.bat` | Atalho para execução simplificada no Windows. |
| `requirements.txt` | Dependências Python (`openpyxl`, `reportlab`, `bcrypt`, `pyodbc`, `pillow`, `customtkinter`, `darkdetect`). |
| `Querys SQL/` | Scripts SQL de banco de dados (não versionados). |

---

## Fluxo do sistema

1. **Cadastro de usuário** — primeiro usuário vira administrador. O admin reseta
   senha.
2. **Tela inicial** — Cadastro de Nova Empresa, Empresas Cadastradas, Emissão em
   Lote.
3. **Cadastro de empresa** — dados da empresa/PO, valor total, valor hora,
   objeto, e-mail, responsável e Usuário de referência (login que bate com a
   planilha de horas). Importação em lote por Excel disponível.
4. **Emissão em lote** — anexe as planilhas de horas; o sistema agrupa as horas
   por empresa e por projeto, e gera um BM por empresa.
5. **Emissão manual** — digitando período, projetos e horas.
6. **Boletins Emitidos** — download em `.xlsx` e `.pdf`, reemissão gera revisão
   incrementada.

---

## Leitura das planilhas de horas

O sistema reconhece automaticamente o cabeçalho, suportando os formatos
`cadastro horas` e `horas por item`:

| Dado | Coluna | Observação |
|---|---|---|
| Usuário | `USUÁRIO` ou `RESPONSÁVEL` | detectada pelo nome, não por posição |
| Horas | `HORAS` | idem |
| Projeto | `PROJETO` | se existir, agrupa por linha; senão usa o `PROJETO:` do relatório |
| Aprovação | `APROVAÇÃO` | quando presente, **somente linhas "Sim"** são faturadas |
| Período | `DATA INICIAL` / `DATA FINAL` | aceita `dd/mm/aaaa` e `m/d/yyyy` |

---

## Gerar o executável

```bash
pip install pyinstaller
pyinstaller E-BM.spec
```

Ou, montando manualmente:

```bash
python -m PyInstaller --noconfirm --clean --onefile --windowed --name E-BM --icon logo.ico --add-data "logo.png;." --add-data "template_bm.xlsx;." --add-data "config.json.example;." --add-data "src;src" src/__main__.py
```

O `E-BM.exe` fica em `dist/`. Distribua junto com o `logo.png` e um `config.json`
preenchido (o sistema cria um modelo automaticamente se não existir). O
`config.json` **não** deve ser embarcado no executável — contém credenciais.

---

## Especificação técnica do BM

### Visão geral e propósito

Sistema **desktop** para emissão automática de **Boletins de Medição** de
serviços de consultoria.

Propósito do documento BM (template de preenchimento, aba do boletim):
- Formalizar por **PO (contrato)** as horas trabalhadas por projeto no período,
  converter em valores (`horas × valor hora`) e controlar acumulado vs. saldo do
  contrato.
- Servir como base de faturamento. Cabeçalho traz `RM N.º, Período, Emissão,
  Revisão, Contrato, PO, Início/Fim PO, Objeto, Valor Estimado, Contratante,
  Contratada, CNPJ`. Tabela traz linhas `Item, Projeto, Descrição, Valor Hora,
  Horas Anterior, Horas Período, Horas Acumuladas, Total Anterior, Total
  Período, Acumulado, Saldo`. Rodapé com assinaturas.

### Stack (definida)

- **Desktop:** Python 3.11+ com Tkinter/CustomTkinter. Executável via PyInstaller
  (`E-BM.exe`).
- **Banco:** **SQL Server 2016** via `pyodbc` + Microsoft ODBC Driver 17.
  Conexão em `config.json`.
- **Excel:** `openpyxl` (leitura do lote + escrita do BM preservando template,
  fórmulas e formatação `R$`).
- **PDF:** `reportlab` (template próprio com logo, mesma informação do XLSX).
- **Senha:** `bcrypt` (cost 12) com fallback PBKDF2-HMAC-SHA256. Nunca em claro.
- **Datas:** serial Excel ↔ `date`.

### Módulos

| Arquivo | Responsabilidade |
|---|---|
| `src/ui/app.py` | Interface gráfica (Tkinter) e navegação entre telas. |
| `src/database.py` | Conexão com o SQL Server, DDL e operações de domínio. |
| `src/boletim.py` | Geração do BM em XLSX e PDF; leitura das planilhas de horas. |
| `src/utils.py` | Senha, datas, números e validações. |

---

## Modelo de dados (SQL Server 2016)

O esquema (`users`, `companies`, `companies_login_eclic`, `bms`, `bm_items`,
`bm_validacao_log`) é definido pelo DDL idempotente embutido em
`src/database.py` e aplicado automaticamente ao iniciar o sistema. Também pode
ser executado manualmente no SSMS (ver seção "Guia de criação dos bancos"
abaixo).

| Tabela | Papel | Chaves / regras |
|---|---|---|
| `users` | Usuários do sistema (multiusuário, sem logout) | `login` UNIQUE (case-insensitive); `is_admin` = 1 apenas no 1º cadastrado |
| `companies` | Empresas (1 empresa = 1 PO) | `cnpj` UNIQUE; `po_codigo` UNIQUE; CHECK `po_fim >= po_inicio`; CHECK valores `>= 0` |
| `companies_login_eclic` | Vínculo 1:N empresa <-> Usuários de referência | `usuario` UNIQUE (case-insensitive); um usuário pertence a no máximo uma empresa |
| `bms` | Boletins emitidos | `IDENTITY(1,1)`; UNIQUE `(company_id, rm_numero, revisao)`; `xlsx_blob`/`pdf_blob` `VARBINARY(MAX)`; CHECK `origem IN ('LOTE','MANUAL','BASE')`; snapshot dos dados da empresa/PO no momento da emissão |
| `bm_items` | Itens (1 linha por projeto + atividade) | `bm_id` FK `ON DELETE CASCADE`; UNIQUE `(bm_id, projeto, descricao)`; `horas_anterior` NULL = sem base/histórico |
| `bm_validacao_log` | Log de mudanças de status de validação | `bm_id` FK; registra status anterior/novo, usuário e data |

Tipos: `INT IDENTITY(1,1)`, `NVARCHAR`, `DATE`, `DECIMAL(18,2)` (dinheiro),
`DECIMAL(18,4)` (horas), `DATETIME2(0)`, `VARBINARY(MAX)`, `BIT`.

**Regra de snapshot:** editar a empresa **não** altera boletins já emitidos —
`bms` guarda cópia dos dados da empresa/PO no momento da emissão.

---

## Telas e regras de negócio

Todas desktop, mesma identidade: header azul, fundo branco/cinza claro,
botões primários azuis, logo no topo, mensagens em caixa de diálogo.

### T1 — Login (inicial se já houver usuário)

- Inputs: `Login, Senha` + botões `Entrar, Cadastrar-se, Esqueci a senha`.
- `Entrar`: valida, erro genérico "Login ou senha inválidos". Sucesso → T3.
- `Cadastrar-se` → T2. `Esqueci` → texto: "Procure o administrador (primeiro
  usuário) para resetar sua senha." Sem e-mail automático.
- Se banco vazio (primeiro uso) → pula direto para T2.

### T2 — Cadastro de usuário

- Inputs: `Nome Completo*, Login*, E-mail*, Senha*, Confirmar Senha*`.
- Travas: todos obrigatórios, login único (avisa "Login já existe"), e-mail com
  `@` e `.`, senha ≥6, confirmação igual.
- 1º cadastro: `is_admin=1`. Após salvar → entra direto na T3 (sem voltar ao
  login).

### T3 — Inicial (home)

- Logo no canto superior esquerdo, título do sistema, 3 botões centralizados:
  `Cadastro de Nova Empresa → T4`, `Empresas Cadastradas → T5`, `Emissão de
  Boletins em Lote → T7`.

### T4 — Cadastro de Nova Empresa

- Campos na ordem (mesma do lote): `Razão Social*, CNPJ*, Código PO*, Data de
  Início - PO*, Data de Vencimento - PO*, Valor Total PO*, Objeto*, E-mail*,
  Responsável*, Usuário de referência*, Tipo de Faturamento*, Gerente
  Aprovador, Diretor Aprovador`.
- Tipo de faturamento: seleção por radio buttons com duas opções: `Horista` ou
  `Mensal - fixo`.
  - Se `Horista`: o campo `Valor Hora*` aparece abaixo do tipo e é obrigatório;
    `Valor Fixo Mensal` fica oculto.
  - Se `Mensal - fixo`: o campo `Valor Fixo Mensal` aparece abaixo do tipo e é
    obrigatório; `Valor Hora` fica oculto.
- Travas: obrigatórios, CNPJ formato+único, PO único, `fim>=inicio`, valores
  ≥0, e-mail básico, usuário de referência único (um ou mais, vinculados 1:N).
- `Gerente Aprovador` e `Diretor Aprovador`: campos opcionais para registro dos
  responsáveis pela aprovação do contrato.
- Ações: `Salvar` (confirmação), `Cadastro em lote (upload Excel)`.
- Lote: upload `.xlsx`, 1ª linha cabeçalho ignorada, colunas **exatamente nesta
  ordem**. Por linha: se qualquer célula obrigatória em branco → pula; se
  `CNPJ`, `PO` ou `Usuário de referência` duplicado (banco ou no próprio
  arquivo) → pula. Ao final relatório: "X cadastradas, Y puladas (listar
  linhas/motivo)".

### T5 — Empresas Cadastradas

- Tabela `Responsável | Razão Social | CNPJ` + barra de busca (filtra pelos 3,
  case-insensitive) + por linha 4 botões:
  1. `Editar → T5a`
  2. `Emitir Boletim (manual) → T6`
  3. `Boletins Emitidos → T8`
  4. `Importar BM base` (upload do 1º BM, vínculo pelo `CNPJ`; salva como
     `origem='BASE'`)

### T5a — Editar empresa

- Mesmos campos de T4 pré-preenchidos, `Salvar / Voltar`.
- `Salvar`: UPDATE em `companies`, mensagem "Informações atualizadas". Não
  altera `bms` já emitidos. `Voltar` → T5 sem salvar.

### T6 — Emitir BM individual (manual)

- Empresa travada (dados PO e valor hora exibidos, não editáveis). Digitáveis:
  `Período Inicial*, Período Final*` e N linhas de `Projeto*` + `Horas No
  Período*`.
- `Emissão` auto `= fim+1`, `RM` auto sequencial, `Anterior` puxa do último BM
  (ou branco).

### T7 — Emissão em Lote (upload horas)

- Upload múltiplo `.xlsx`. O sistema **detecta o cabeçalho pelo nome das
  colunas**, aceitando `cadastro horas` e `horas por item`:
  - Usuário: `USUÁRIO` ou `RESPONSÁVEL`
  - Horas: `HORAS`
  - Projeto: `PROJETO` (se existir, agrupa por linha; senão usa o `PROJETO:` do
    relatório)
  - Aprovação: `APROVAÇÃO` (quando presente, **somente linhas "Sim"** são
    faturadas)
  - Período: `DATA INICIAL` / `DATA FINAL` (aceita `dd/mm/aaaa` e
    `m/d/yyyy`, deduzido pelo formato)
- Regras: todos os arquivos devem ter a mesma data inicial/final, senão aborta
  com erro; usuários sem referência correspondente são ignorados; 1 BM por
  empresa, 1 linha por (projeto + atividade).

### T8 — Boletins Emitidos (por empresa)

- Lista desc por emissão: cada item é clicável, rotulado `Boletim <NOME
  EMPRESA> - <dd/mm/yyyy de emissão> | <RM> | Rev <N> | <origem>`.
- Seleção habilita `Baixar XLSX` e `Baixar PDF` (bytes do banco → arquivo
  local).
- Reemissão do mesmo período/RM: novo registro com mesmo `rm_numero` e
  `revisao+1`.

---

## Template BM — mapa de preenchimento

Preservar merges, formatos monetários e fórmulas; o logo é inserido na posição
definida do template.

- Cabeçalho com `RM N.°`, `Período`, `Emissão`, `Revisão`.
- Dados do contrato: `PO`, `Início PO`, `Fim PO`, `Objeto`, `Valor Estimado`.
- Contratante e Contratada com `CNPJ`.
- Linha 10 header fixo. Linhas 12+: `Item, Projeto, Descrição, Valor Hora,
  Horas Anterior, Horas Período, Horas Acumuladas, Total Anterior, Total
  Período, Acumulado, Saldo`.
- Linha de totais e linha de repetição dos totais.
- Rodapé com assinaturas.

---

## Regras de negócio / cálculos

1. Tipo de faturamento por empresa: `HORISTA` ou `MENSALISTA`.
2. **HORISTA:** valor da hora por empresa/PO; 0 calcula com 0. Valor do período
   = `horas × valor hora`. Desconta do saldo do contrato.
3. **MENSALISTA:** valor fixo mensal por empresa. Não há cálculo de horas
   trabalhadas. Valor do período = `valor fixo mensal`. Desconta do saldo do
   contrato.
4. Período lote = datas da planilha; emissão = `fim + 1 dia`; individual:
   digitado + mesma regra de emissão.
5. Anterior: do último BM da empresa; sem base/histórico → NULL/branco (não 0).
6. RM sequencial por empresa: `BM-YYYY-NNN`. Ex `BM-2026-009 → BM-2026-010`.
   Primeiro sem base: deixar em branco.
7. Revisão: 0 na emissão nova; reemitir mesmo RM/período → +1.
8. Arquivo de download: `Boletim <NOME EMPRESA> - <data de emissão>.xlsx` /
   `.pdf`.
9. Lote: match de `Usuário de referência` sem diferenciar maiúsculas/minúsculas;
   soma de horas por `(empresa, projeto + atividade)`; 2 casas decimais.

---

## Validações e erros

- Login duplicado, CNPJ/PO/Usuário de referência duplicados, e-mail sem `@`,
  datas invertidas, valor negativo, lote com datas divergentes, base com CNPJ
  divergente, planilha sem cabeçalho reconhecível → mensagem na tela, sem crash.
- Lote nunca cadastra parcial com erro crítico de modelo; linhas com
  branco/duplicada apenas puladas e listadas.
- Banco indisponível ou não configurado → janela explicando `config.json`,
  criação do banco e execução do script de esquema.

---

## Critérios de aceite

- [ ] Primeiro uso → cadastro → entra direto; login posterior funciona;
  duplicado bloqueia; admin flag no 1º.
- [ ] Cadastro de empresa individual + lote na ordem definida, com relatório de
  puladas.
- [ ] Lista com busca Responsável/Razão Social/CNPJ; editar mostra "Informações
  atualizadas" e não altera BMs antigos; base importada por CNPJ.
- [ ] Lote com 2+ planilhas gera 1 BM/empresa, horas somadas por projeto,
  período/emissão/RM corretos, XLSX idêntico ao template, PDF legível, ambos
  baixáveis com o nome correto.
- [ ] Linhas com `APROVAÇÃO = Não` não são faturadas.
- [ ] Individual manual só pede Período/Projeto/Horas; resto automático/travado.
- [ ] Reemissão gera Rev 1,2...; sem histórico deixa branco.
- [ ] Banco no SQL Server 2016, esquema aplicado automaticamente pelo sistema
  (DDL embutido em `src/database.py`).

---

## Fora de escopo (não implementar)

Logout/Sair, gestão de usuários além de reset pelo admin, multi-PO por empresa,
envio de e-mail automático, SQLite.

---

## Diagnóstico de conexão

O sistema mostra uma janela de erro com a causa exata quando não consegue
conectar. As mensagens mais comuns:

| Mensagem | Causa | Solução |
|---|---|---|
| `Driver ODBC não encontrado` | Driver 17 ausente | Instalar *Microsoft ODBC Driver 17 for SQL Server* |
| `Servidor SQL Server não encontrado` | `server` errado no config | conferir `server` e `port` |
| `Banco '<nome>' não existe` | banco não criado | pedir ao DBA para criar o banco (ou conceder `dbcreator`) |
| `Login failed for user` | credenciais erradas | revisar `username`/`password` / `trusted_connection` |
| `CREATE DATABASE permission denied` | sem `dbcreator` | pedir `dbcreator` ao DBA |

Para testar a conexão fora do app:

```bash
python -c "from src.database import connection_string; print(connection_string())"
```

---

## Guia de criação dos bancos (no SSMS)

### 1. Abrir o SSMS e conectar

1. Abra o **SQL Server Management Studio**.
2. Se aparecer a caixa **Connect to Server**:
   - **Server type**: *Database Engine*
   - **Server name**: `<SEU_SERVIDOR>\\<SUA_INSTANCIA>`
   - **Authentication**: *Windows Authentication* (ou SQL Server Authentication)
   - Clique em **Connect**

### 2. Criar o banco de dados

No painel **Query**, cole e execute (**F5**):

```sql
CREATE DATABASE [SEU_BANCO]
    COLLATE Latin1_General_CI_AS;
GO
```

### 3. Conceder acesso ao seu usuário no banco

```sql
USE [SEU_BANCO];
GO
CREATE USER [SEU_USUARIO] FOR LOGIN [SEU_DOMINIO\\SEU_USUARIO];
GO
ALTER ROLE [db_owner] ADD MEMBER [SEU_USUARIO];
GO
```

> ⚠️ Erro esperado se rodar duas vezes: `The database principal ... already
> exists`. É inofensivo.

### 4. Aplicar o esquema (as 4 tabelas)

O DDL está embutido em `src/database.py` e é aplicado automaticamente pelo
sistema ao iniciar. Se preferir aplicar manualmente no SSMS, use o conteúdo do
DDL abaixo (idempotente, pode executar várias vezes sem erro):

```sql
-- Tabela usuarios
IF OBJECT_ID('dbo.users','U') IS NULL
CREATE TABLE dbo.users (
    id            INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_users PRIMARY KEY,
    nome_completo NVARCHAR(200) NOT NULL,
    login         NVARCHAR(100) COLLATE Latin1_General_CI_AS NOT NULL,
    email         NVARCHAR(200) NOT NULL,
    senha_hash    NVARCHAR(300) NOT NULL,
    is_admin      BIT NOT NULL CONSTRAINT DF_users_is_admin DEFAULT (0),
    criado_em     DATETIME2(0) NOT NULL CONSTRAINT DF_users_criado_em DEFAULT (SYSDATETIME())
);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UX_users_login' AND object_id=OBJECT_ID('dbo.users'))
CREATE UNIQUE INDEX UX_users_login ON dbo.users(login);

-- Tabela empresas
IF OBJECT_ID('dbo.companies','U') IS NULL
CREATE TABLE dbo.companies (
    id                INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_companies PRIMARY KEY,
    nome              NVARCHAR(200) NOT NULL,
    cnpj              NVARCHAR(14) NOT NULL,
    responsavel       NVARCHAR(200) NOT NULL,
    email_contato     NVARCHAR(200) NOT NULL,
    usuario_referencia NVARCHAR(100) COLLATE Latin1_General_CI_AS NULL,
    po_codigo         NVARCHAR(50)  COLLATE Latin1_General_CI_AS NOT NULL,
    po_inicio         DATE NOT NULL,
    po_fim            DATE NOT NULL,
    po_valor_total    DECIMAL(18,2) NOT NULL,
    po_objeto         NVARCHAR(500) NOT NULL,
    valor_hora        DECIMAL(18,2) NOT NULL,
    tipo_faturamento  NVARCHAR(20)  NOT NULL CONSTRAINT DF_companies_tipo_faturamento DEFAULT ('HORISTA'),
    valor_fixo_mensal DECIMAL(18,2) NULL,
    notificado_vencimento_em DATE NULL,
    gerente_aprovador NVARCHAR(200) NULL,
    diretor_aprovador NVARCHAR(200) NULL,
    criado_em         DATETIME2(0) NOT NULL CONSTRAINT DF_companies_criado_em DEFAULT (SYSDATETIME()),
    atualizado_em     DATETIME2(0) NOT NULL CONSTRAINT DF_companies_atualizado_em DEFAULT (SYSDATETIME()),
    CONSTRAINT UQ_companies_cnpj   UNIQUE (cnpj),
    CONSTRAINT UQ_companies_po     UNIQUE (po_codigo),
    CONSTRAINT CK_companies_valor  CHECK (po_valor_total >= 0),
    CONSTRAINT CK_companies_vh     CHECK (valor_hora >= 0),
    CONSTRAINT CK_companies_datas  CHECK (po_fim >= po_inicio),
    CONSTRAINT CK_companies_tipo   CHECK (tipo_faturamento IN ('HORISTA','MENSALISTA'))
);

-- Tabela vinculo empresa <-> usuario de referencia (1:N)
IF OBJECT_ID('dbo.companies_login_eclic','U') IS NULL
CREATE TABLE dbo.companies_login_eclic (
    id            INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_companies_login_eclic PRIMARY KEY,
    company_id    INT NOT NULL CONSTRAINT FK_companies_login_eclic_company REFERENCES dbo.companies(id) ON DELETE CASCADE,
    usuario_eclic NVARCHAR(100) COLLATE Latin1_General_CI_AS NOT NULL,
    criado_em     DATETIME2(0) NOT NULL CONSTRAINT DF_companies_login_eclic_criado DEFAULT (SYSDATETIME()),
    CONSTRAINT UQ_companies_login_eclic_eclic UNIQUE (usuario_eclic)
);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_companies_login_eclic_company' AND object_id=OBJECT_ID('dbo.companies_login_eclic'))
CREATE INDEX IX_companies_login_eclic_company ON dbo.companies_login_eclic(company_id);

-- Tabela boletins
IF OBJECT_ID('dbo.bms','U') IS NULL
CREATE TABLE dbo.bms (
    id               INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bms PRIMARY KEY,
    company_id       INT NOT NULL CONSTRAINT FK_bms_company REFERENCES dbo.companies(id),
    rm_numero        NVARCHAR(50) NOT NULL,
    periodo_ini      DATE NOT NULL,
    periodo_fim      DATE NOT NULL,
    emissao          DATE NOT NULL,
    revisao          INT NOT NULL CONSTRAINT DF_bms_revisao DEFAULT (0),
    contratante      NVARCHAR(200) NOT NULL,
    snap_nome        NVARCHAR(200) NOT NULL,
    snap_cnpj        NVARCHAR(14) NOT NULL,
    snap_po          NVARCHAR(50) NOT NULL,
    snap_po_inicio   DATE NOT NULL,
    snap_po_fim      DATE NOT NULL,
    snap_valor_total DECIMAL(18,2) NOT NULL,
    snap_objeto      NVARCHAR(500) NOT NULL,
    snap_valor_hora  DECIMAL(18,2) NOT NULL,
    total_anterior   DECIMAL(18,2) NULL,
    total_periodo    DECIMAL(18,2) NULL,
    total_acumulado  DECIMAL(18,2) NULL,
    saldo            DECIMAL(18,2) NULL,
    xlsx_blob        VARBINARY(MAX) NOT NULL,
    pdf_blob         VARBINARY(MAX) NOT NULL,
    origem           NVARCHAR(10) NOT NULL,
    criado_em        DATETIME2(0) NOT NULL CONSTRAINT DF_bms_criado_em DEFAULT (SYSDATETIME()),
    CONSTRAINT UQ_bms_unico UNIQUE (company_id, rm_numero, revisao),
    CONSTRAINT CK_bms_origem CHECK (origem IN (N'LOTE', N'MANUAL', N'BASE')),
    CONSTRAINT CK_bms_datas  CHECK (periodo_fim >= periodo_ini)
);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_bms_company' AND object_id=OBJECT_ID('dbo.bms'))
CREATE INDEX IX_bms_company ON dbo.bms(company_id, criado_em DESC);

-- Tabela itens do boletim
IF OBJECT_ID('dbo.bm_items','U') IS NULL
CREATE TABLE dbo.bm_items (
    id              INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bm_items PRIMARY KEY,
    bm_id           INT NOT NULL CONSTRAINT FK_bm_items_bm REFERENCES dbo.bms(id) ON DELETE CASCADE,
    item_seq        INT NOT NULL,
    projeto         NVARCHAR(300) NOT NULL,
    descricao       NVARCHAR(300) NOT NULL,
    valor_hora      DECIMAL(18,2) NOT NULL,
    horas_anterior  DECIMAL(18,4) NULL,
    horas_periodo   DECIMAL(18,4) NOT NULL,
    horas_acumulada DECIMAL(18,4) NULL,
    total_anterior  DECIMAL(18,2) NULL,
    total_periodo   DECIMAL(18,2) NULL,
    total_acumulado DECIMAL(18,2) NULL,
    CONSTRAINT UQ_bm_items UNIQUE (bm_id, projeto, descricao)
);

-- Campo de status de validacao nos boletins
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.bms') AND name='status_validacao')
ALTER TABLE dbo.bms ADD status_validacao NVARCHAR(20) NOT NULL CONSTRAINT DF_bms_status_validacao DEFAULT ('PENDENTE');
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name='CK_bms_status_validacao')
ALTER TABLE dbo.bms ADD CONSTRAINT CK_bms_status_validacao CHECK (status_validacao IN ('VALIDADO','PENDENTE','NAO_VALIDADO'));

-- Tabela de log de validacao de boletins
IF OBJECT_ID('dbo.bm_validacao_log','U') IS NULL
CREATE TABLE dbo.bm_validacao_log (
    id            INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bm_validacao_log PRIMARY KEY,
    bm_id         INT NOT NULL CONSTRAINT FK_bm_validacao_log_bm REFERENCES dbo.bms(id) ON DELETE CASCADE,
    usuario_login NVARCHAR(100) NOT NULL,
    status_anterior NVARCHAR(20),
    status_novo   NVARCHAR(20) NOT NULL,
    validado_em   DATETIME2(0) NOT NULL CONSTRAINT DF_bm_validacao_log_validado_em DEFAULT (SYSDATETIME())
);

-- Colunas de PDF assinado nos boletins
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.bms') AND name='pdf_assinado')
ALTER TABLE dbo.bms ADD pdf_assinado VARBINARY(MAX) NULL;
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.bms') AND name='pdf_assinado_nome')
ALTER TABLE dbo.bms ADD pdf_assinado_nome NVARCHAR(255) NULL;
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.bms') AND name='data_assinatura')
ALTER TABLE dbo.bms ADD data_assinatura DATETIME2(0) NULL;
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.bms') AND name='assinado_por')
ALTER TABLE dbo.bms ADD assinado_por NVARCHAR(100) NULL;
```

Selecione o banco alvo no SSMS e execute F5. O script é idempotente — pode rodar
quantas vezes quiser, sem risco de duplicar ou apagar nada.

### 5. Verificar se deu certo

No SSMS: **Object Explorer** → **Databases** → deve aparecer seu banco. Expanda
**Tables**: devem estar `bm_items`, `bms`, `companies`, `users`.

Por query:

```sql
USE [SEU_BANCO];
GO
SELECT t.name AS tabela
FROM sys.tables t WHERE t.is_ms_shipped = 0 ORDER BY t.name;
GO
```

### 6. Apontar o sistema para cada ambiente

O `config.json` na pasta do projeto (ou ao lado do `E-BM.exe`):

```json
{
  "driver": "ODBC Driver 17 for SQL Server",
  "server": "SEU_SERVIDOR\\SUA_INSTANCIA",
  "port": "",
  "database": "SEU_BANCO",
  "username": "",
  "password": "",
  "trusted_connection": true,
  "encrypt": true,
  "trust_server_certificate": true,
  "connection_timeout": 30
}
```

Trocar de ambiente = trocar **uma linha**: `"database"`.

| Momento | `database` |
|---|---|
| Desenvolvimento e testes | banco de homologação |
| Uso real | banco de produção |

Ao iniciar, o sistema aplica o esquema automaticamente se alguma tabela faltar —
mas com `db_owner` (ou `db_ddladmin`) ele consegue fazer isso sozinho, sem rodar
o script na mão.

### 6.1 Testar a conexão

```bash
python -c "from src.database import connection_string; print(connection_string())"
```

### 6.2 Distribuição para o usuário final

O `E-BM.exe` que vai para o usuário final deve vir com um `config.json`
apontando para o **banco de produção**, para o usuário não ter como gerar
boletim no ambiente errado.

---

## Notificação de Vencimento de PO

O sistema avisa automaticamente o responsável pela empresa quando uma PO está
prestes a vencer, enviando um e-mail com 7 dias de antecedência.

### Como funciona

- O script `src/scripts/notificacao_vencimento.py` consulta o banco de dados e
  identifica empresas cujo `po_fim` está em 7 dias (janela de ±1 dia para
  tolerância) e que ainda não foram notificadas hoje.
- Para cada empresa encontrada, envia um e-mail para o `email_contato`
  cadastrado.
- Após o envio bem-sucedido, marca a empresa como notificada para não reenviar
  no dia seguinte.
- Se o SMTP não estiver configurado, o script encerra sem erro.

### Configuração (`config.json`)

Adicione o bloco `smtp` no `config.json` (preencha com suas credenciais de
e-mail):

```json
"smtp": {
  "servidor": "SEU_SERVIDOR_SMTP",
  "porta": 587,
  "usuario": "SEU_USUARIO_SMTP",
  "senha": "SUA_SENHA_SMTP",
  "remetente": "SEU_EMAIL_REMETENTE",
  "usar_tls": true
}
```

> Para Outlook/Office 365, use uma **senha de aplicativo** (App Password) se sua
> conta tiver autenticação de dois fatores.

### Agendamento (Windows Task Scheduler)

Como o aviso deve ser enviado **independentemente da abertura do sistema**, agende
o script para rodar diariamente:

1. Abra o **Agendador de Tarefas** (Task Scheduler).
2. Clique em **Criar Tarefa Básica**.
3. Nome: `Notificacao Vencimento PO`.
4. Gatilho: **Diariamente**, hora desejada (ex.: 08:00).
5. Ação: **Iniciar um programa**.
   - Programa/script: `python`
   - Adicionar argumentos: `"C:\caminho\do\projeto\src\scripts\notificacao_vencimento.py"`
   - Iniciar em: `C:\caminho\do\projeto`
6. Conclua.

O banco de dados recebe automaticamente a nova coluna
`notificado_vencimento_em` na primeira execução do sistema (DDL idempotente em
`src/database.py`).

---

*Este README é a versão sanitizada do projeto, destinada ao repositório público.
Não contém dados sigilosos, credenciais, servidores, IPs nem nomes de empresas
ou usuários reais.*
