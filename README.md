# E-BM - Emissor de Boletim de Medição

Sistema desktop para emissão automática do Boletim de Medição (BM) de serviços de
consultoria da contratante **DBR ENERGIES S/A**.

Banco: **SQL Server 2016** (via `pyodbc` / ODBC Driver 17).

## Requisitos

| Item | Versão |
|---|---|
| Python | 3.11+ |
| SQL Server | 2016 ou superior |
| Microsoft ODBC Driver for SQL Server | 17 ou superior |

## Instalação

```bash
pip install -r requirements.txt
python app.py
```

## Configuração do banco

1. Crie o banco no SQL Server (SSMS):
   ```sql
   CREATE DATABASE EBM;
   ```
2. Execute `schema_sqlserver2016.sql` no SSMS com o banco `EBM` selecionado.
   As tabelas também são criadas automaticamente pelo sistema ao iniciar.
3. Edite `config.json`:

   ```json
   {
     "driver": "ODBC Driver 17 for SQL Server",
     "server": "localhost",
     "port": "1433",
     "database": "EBM",
     "username": "sa",
     "password": "sua_senha"
   }
   ```

   | Campo | Significado |
   |---|---|
   | `driver` | Driver ODBC instalado. Use Driver 17 para SQL Server 2016. |
   | `server` | Host ou `host\instancia`. |
   | `port` | Porta, ignorado se `instance` for informada. |
   | `instance` | Nome da instância do SQL Server (ex.: `SQLEXPRESS`). |
   | `database` | Banco de dados (padrão `EBM`). |
   | `username` / `password` | Usuário do SQL Server. |
   | `trusted_connection` | `true` usa autenticação do Windows (sem senha). |
   | `encrypt` / `trust_server_certificate` | Parâmetros de criptografia da conexão. |

> **Atenção:** o `config.json` guarda a senha em texto puro. Para uso em produção,
> prefira `trusted_connection: true` ou um cofre de segredos.

Se o banco não estiver configurado, o sistema abre uma janela explicando o que fazer
e oferece um atalho para abrir o `config.json`.

## Estrutura do projeto

| Arquivo | Responsabilidade |
|---|---|
| `app.py` | Interface gráfica (Tkinter) e navegação entre telas. |
| `db.py` | Conexão com o SQL Server, DDL e operações de domínio. |
| `boletim.py` | Geração do BM em XLSX (template DBR) e PDF; leitura das planilhas de horas. |
| `util.py` | Senha (bcrypt), datas, números e validações. |
| `config.json` | Parâmetros de conexão com o SQL Server. |
| `schema_sqlserver2016.sql` | Script de criação do esquema (para rodar no SSMS). |
| `logo.png` / `logo.ico` | Logomarca DBR Energies (nos boletins e no executável). |
| `E-BM.spec` | Configuração do PyInstaller para gerar o executável. |

## Fluxo

1. **Cadastro de usuário** — primeiro usuário vira administrador. O admin reseta senha.
2. **Tela inicial** — Cadastro de Nova Empresa, Empresas Cadastradas, Emissão em Lote.
3. **Cadastro de empresa** — Razão Social, CNPJ, PO, datas, valor total, valor hora,
   objeto, e-mail, responsável e **Usuário E-clic** (login que bate com a planilha de horas).
   Importação em lote por Excel disponível.
4. **Emissão em lote** — anexe as planilhas de horas; o sistema agrupa as horas por
   empresa (via Usuário E-clic) e por projeto, e gera um BM por empresa.
5. **Emissão manual** — digitando período, projetos e horas.
6. **Boletins Emitidos** — download em `.xlsx` e `.pdf`, reemissão gera revisão incrementada.

## Leitura das planilhas de horas

O sistema reconhece automaticamente o cabeçalho, suportando os formatos
`cadastro horas` e `horas por item`:

| Dado | Coluna | Observação |
|---|---|---|
| Usuário | `USUÁRIO` ou `RESPONSÁVEL` |detectada pelo nome, não por posição |
| Horas | `HORAS` | idem |
| Projeto | `PROJETO` | se existir, agrupa por linha; senão usa o `PROJETO:` do relatório |
| Aprovação | `APROVAÇÃO` | quando presente, **somente linhas "Sim"** são faturadas |
| Período | `DATA INICIAL` / `DATA FINAL` | aceita `dd/mm/aaaa` e `m/d/yyyy` |

## Gerar o executável

```bash
pip install pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --name E-BM --icon logo.ico --add-data "logo.png;." app.py
```

O `E-BM.exe` fica em `dist/`. Distribua junto com o `logo.png` e um `config.json`
preenchido (o sistema cria um modelo automaticamente se não existir).

## Testes

```bash
python test_smoke.py
```

Valida senha, validações, datas, geração de XLSX/PDF, leitura das planilhas de horas
e a montagem do DDL do SQL Server.
