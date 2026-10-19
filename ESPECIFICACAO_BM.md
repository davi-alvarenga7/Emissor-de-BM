# Sistema Emissor de Boletim de Medição (BM) — Especificação para Desenvolvimento

> Documento-prompt. Fonte única da verdade para implementação. Não desenvolver fora deste escopo sem atualizar aqui.

## 1. Visão geral e propósito

Sistema **desktop** para emissão automática do **Boletim de Medição** de serviços de consultoria em TELECOM da **contratante fixa DBR ENERGIES S/A**.

Propósito do documento BM (template `206000_PRJ-25-06_PRJ-25-05_SERROM ENGENHARIA_BM-2026-009.xlsx`, aba `BM-2026-009`, `B1:O46`):
- Formalizar por **PO (contrato)** as horas trabalhadas por projeto no período, converter em valores (`horas × valor hora`) e controlar acumulado vs. saldo do contrato.
- Servir como base de faturamento. Cabeçalho traz `RM N.º, Período, Emissão, Revisão, Contrato, PO, Início/Fim PO, Objeto, Valor Estimado, Contratante, Contratada, CNPJ`. Tabela traz 7+ linhas `Item, Projeto, Descrição, Valor Hora, Horas Anterior, Horas Período, Horas Acumuladas, Total Anterior, Total Período, Acumulado, Saldo`. Rodapé com assinaturas `Gerente DBR` e `Contratada`.

Outras abas do arquivo original (`Tdocumlist`, `Sheet2`, `Resumo`) são **legado/referência e NÃO fazem parte do sistema**. Sistema só lê/escreve o template BM.

## 2. Stack proposta (padrão se não houver veto)

- **Desktop:** Electron + Vite + React + TypeScript (layout azul/branco). Alternativa aceitável: Tauri. Não usar web hospedada.
- **Banco:** SQL relacional local. Padrão: **SQLite** (`better-sqlite3`) via Drizzle/Prisma — atende "Banco SQL novo". Se cliente exigir SQL Server/Postgres, trocar provider sem mudar schema.
- **Excel:** `exceljs` (leitura do lote + escrita do BM preservando template, merges, fórmulas e formatação `R$`).
- **PDF:** gerar a partir do XLSX renderizado ou via template HTML idêntico → `electron-print` / `puppeteer-core` embutido. Entregar os dois formatos.
- **Senha:** `bcrypt` (cost 12). Nunca em claro.
- **Datas Excel:** serial ↔ JS Date (ex.: 46291 = 26/09/2026).

## 3. Modelo de dados (plano de banco)

```sql
-- 3.1 Usuários do sistema (multiusuário, sem logout: sessão persistente)
CREATE TABLE users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  nome_completo TEXT NOT NULL,
  login         TEXT NOT NULL UNIQUE COLLATE NOCASE,  -- trava duplicado case-insensitive
  email         TEXT NOT NULL,                        -- sem validação de existência, só formato básico com @
  senha_hash    TEXT NOT NULL,
  is_admin      INTEGER NOT NULL DEFAULT 0,           -- 1 apenas para o 1º cadastrado
  criado_em     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 3.2 Empresas (1 empresa = 1 PO. Chave única = CNPJ)
CREATE TABLE companies (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  nome          TEXT NOT NULL,
  cnpj          TEXT NOT NULL UNIQUE,  -- formato validado 00.000.000/0000-00, unique
  responsavel   TEXT NOT NULL,         -- dono/representante
  email_contato TEXT NOT NULL,
  usuario_eclic TEXT NOT NULL UNIQUE COLLATE NOCASE, -- ex DANIELE.CARVALHO; bate com col D da planilha
  po_codigo     TEXT NOT NULL UNIQUE,  -- ex EC-PO-2026-047
  po_inicio     TEXT NOT NULL,         -- ISO yyyy-mm-dd
  po_fim        TEXT NOT NULL,         -- >= po_inicio
  po_valor_total REAL NOT NULL CHECK (po_valor_total >= 0),
  po_objeto     TEXT NOT NULL,         -- ex Serviços de Consultoria em TELECOM
  valor_hora    REAL NOT NULL CHECK (valor_hora >= 0), -- aceita 0, calcula com 0
  criado_em     TEXT NOT NULL DEFAULT (datetime('now')),
  atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 3.3 Boletins emitidos (snapshot: edição da empresa NÃO retroage)
CREATE TABLE bms (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id    INTEGER NOT NULL REFERENCES companies(id),
  rm_numero     TEXT NOT NULL,         -- ex BM-2026-009; sequencial por empresa (ver regra 6.5)
  periodo_ini   TEXT NOT NULL,         -- ISO
  periodo_fim   TEXT NOT NULL,
  emissao       TEXT NOT NULL,         -- = periodo_fim + 1 dia (auto)
  revisao       INTEGER NOT NULL DEFAULT 0, -- 0 na 1ª emissão do período/RM; reemissão do mesmo RM => +1
  contratante   TEXT NOT NULL DEFAULT 'DBR ENERGIES S/A',
  -- snapshot da empresa/PO no momento da emissão:
  snap_nome TEXT NOT NULL, snap_cnpj TEXT NOT NULL, snap_po TEXT NOT NULL,
  snap_po_inicio TEXT NOT NULL, snap_po_fim TEXT NOT NULL,
  snap_valor_total REAL NOT NULL, snap_objeto TEXT NOT NULL, snap_valor_hora REAL NOT NULL,
  total_anterior REAL, total_periodo REAL, total_acumulado REAL, saldo REAL, -- espelham linha TOTAL CONTRATO
  xlsx_blob     BLOB NOT NULL,
  pdf_blob      BLOB NOT NULL,
  origem        TEXT NOT NULL CHECK (origem IN ('LOTE','MANUAL','BASE')), -- BASE = importado
  criado_em     TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(company_id, rm_numero, revisao)
);
CREATE INDEX idx_bms_company ON bms(company_id, criado_em DESC);

-- 3.4 Itens do BM (1 linha por projeto distinto, texto cheio)
CREATE TABLE bm_items (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  bm_id         INTEGER NOT NULL REFERENCES bms(id) ON DELETE CASCADE,
  item_seq      INTEGER NOT NULL,      -- 1..N na ordem de emissão
  projeto       TEXT NOT NULL,         -- texto cheio ex "PRJ-25-05 - RNEST - LOTE A - UCR"
  descricao     TEXT NOT NULL DEFAULT 'Serviços de Consultoria em TELECOM',
  valor_hora    REAL NOT NULL,
  horas_anterior REAL,                 -- em branco (NULL) se sem base/histórico; senão do último BM
  horas_periodo REAL NOT NULL,
  horas_acumulada REAL,                -- anterior + periodo (NULL se anterior NULL)
  total_anterior REAL, total_periodo REAL, total_acumulado REAL,
  UNIQUE(bm_id, projeto)
);
```

Regras de banco:
- `users.login` e `companies.usuario_eclic` UNIQUE NOCASE; comparar sempre `UPPER(TRIM())`.
- `companies.cnpj` UNIQUE (só dígitos para comparação, exibir formatado).
- Arquivos xlsx/pdf **no banco** como BLOB (decisão do cliente). Prever vacuum/limite.
- Nunca UPDATE em `bms/bm_items` após emissão, exceto para gerar nova revisão (INSERT novo com mesmo `rm_numero`, `revisao+1`).

## 4. Telas (fluxo + layout azul/branco moderno)

Todas desktop, mesma identidade: header azul (#0B5ED7 / #0D6EFD), fundo branco/cinza claro, botões primários azuis, inputs com borda arredondada, mensagens toast.

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
- 3 botões grandes: `Cadastro de Nova Empresa → T4`, `Empresas Cadastradas → T5`, `Emissão de Boletins em Lote → T7`.
- Sem Sair/Gerenciar/Ajuda por decisão.

### T4 — Cadastro de Nova Empresa
- Campos na ordem (mesma do lote): `Nome*, CNPJ*, Código PO*, Início PO*, Fim PO*, Valor Total PO*, Objeto*, E-mail contato*, Valor Hora*, Responsável*, Usuário E-clic*`.
- Travas (decisão "Pode"): obrigatórios, CNPJ formato+único, PO único, `fim>=inicio`, valores ≥0, e-mail básico, E-clic único.
- Ações: `Salvar` (toast sucesso/erro), `Voltar → T3/T5`, link `Cadastro em lote (upload Excel)`.
- Lote: upload `.xlsx`, 1ª linha cabeçalho ignorada, colunas **exatamente nesta ordem**. Por linha: se qualquer célula obrigatória em branco → pula; se `CNPJ` ou `PO` ou `E-clic` duplicado (banco ou no próprio arquivo) → pula. Ao final relatório: "X cadastradas, Y puladas (listar linhas/motivo)". `CNPJ+PO` define duplicada; como 1:1, na prática CNPJ duplicado já pula.

### T5 — Empresas Cadastradas
- Tabela `Responsável | Nome | CNPJ` + barra de busca (filtra pelos 3, case-insensitive) + por linha 3 botões:
  1. `Editar → T5a`
  2. `Emitir Boletim (manual) → T6`
  3. `Boletins Emitidos → T8`
- Linha também tem `Importar BM base` (botão secundário): upload do 1º BM `.xlsx`, lê `H9 (CNPJ)` e amarra à empresa; valida CNPJ igual; salva como `bms(origem='BASE')` para alimentar `anterior` e sequência RM. Sem base → anterior em branco.

### T5a — Editar empresa
- Mesmos campos de T4 pré-preenchidos, `Salvar / Voltar`.
- `Salvar`: UPDATE companies, toast "Informações atualizadas". Não altera `bms` já emitidos. `Voltar` → T5 sem salvar.

### T6 — Emitir BM individual (manual)
- Empresa travada (dados PO e valor hora exibidos, não editáveis). Digitáveis: `Período Inicial*, Período Final*, Projeto* (texto cheio, pode adicionar N linhas), Horas No Período* por linha`.
- `Emissão` auto `= fim+1`, `RM` auto sequencial (ver 6.5), `Anterior` puxa do último BM (ou branco).
- `Gerar` → calcula, grava `bms+items`, gera xlsx+pdf no template, abre T8 com download.

### T7 — Emissão em Lote (upload horas)
- Upload múltiplo `.xlsx` modelo `horas por item`: aba `horas por item`, `A2=PROJETO: <texto cheio>`, `A4=DATA INICIAL: m/d/yyyy DATA FINAL:m/d/yyyy`, linha 5 header, linhas 6+ `DISCIPLINA | ITEM | TIPO ITEM | USUÁRIO (D) | HORAS (E)`.
- Regras: todos arquivos devem ter mesma `inicial/final` senão aborta com erro; `APROVAÇÃO` sempre SIM (ignorar check); para cada linha onde `UPPER(USUÁRIO)=UPPER(usuario_eclic)` soma `HORAS` por `(empresa, projeto texto cheio)`; usuários sem match ignorados; 1 BM por empresa, 1 linha por projeto.
- Gera todos, mostra relatório "BMs gerados: N — lista empresa/RM" + erros.

### T8 — Boletins Emitidos (por empresa)
- Lista desc por `criado_em`: cada item é botão `Boletim NOME DA EMPRESA - DATA EMISSÃO (dd/mm/yyyy)` + badge `RM ... Rev N`.
- Clique expande: botões `Baixar XLSX` e `Baixar PDF` (bytes do banco → arquivo local).
- Reemissão do mesmo período/RM: novo registro mesmo `rm_numero`, `revisao+1`.

## 5. Template BM — mapa de preenchimento (aba BM-2026-009)

Preservar merges, formatos `R$`, fórmulas quando possível; onde sistema calcula, gravar valor + manter fórmula espelhada:

- `D1=BOLETIM DE MEDIÇÃO`, `H1=RM N.º:`, `I1=rm_numero`, `L1=logo placeholder`
- `H2=Período:`, `I2="dd/mm/yyyy até dd/mm/yyyy"`, `H3=Emissão:`, `I3=data emissao`, `K6=Revisão: N`
- `B7=Contrato: (vazio)`, `E7=PO: <po>`, `G7=Início PO: dd/mm/yyyy`
- `B8=Objeto: <objeto>`, `E8=Valor Estimado PO:`, `F8=valor total (=E21)`, `G8=Fim PO: dd/mm/yyyy`
- `B9=Contratante: DBR ENERGIES S/A`, `E9=Contratada: <nome>`, `G9=CNPJ Contratada:`, `H9=cnpj`, `I9=TOTAL (R$)`
- Linha 10 header fixo. Linhas 12+: `B=item_seq, C=projeto texto cheio, D=descricao, E=valor_hora, F=horas_anterior (branco se NULL), G=horas_periodo, H=F+G, I=F*E, J=E*G (ou G*E), K=I+J, L=saldo por linha (só 1ª linha com fórmula original E21-K...; demais vazio)`.
- `B21=TOTAL CONTRATO:, E21=valor total (=E12*168*4 no template — no sistema usar snap_valor_total), F21=SUM(F), G21=SUM(G), H21=SUM(H), I21=SUM(I), J21=SUM(J), K21=SUM(K), L21=SUM(L)`.
- `I23=I21, J23=J21, K23=K21, L23=L21`. `D30=Gerente DBR Energies S.A., F30=<nome empresa>`.

## 6. Regras de negócio / cálculos

1. Contratante sempre `DBR ENERGIES S/A`.
2. Valor hora por empresa/PO; 0 calcula com 0.
3. Período lote = datas da planilha; emissão = fim+1 dia; individual: digitado + mesma regra emissão.
4. Anterior: do último BM da empresa (por `emissao`/`rm`); sem base → NULL/branco (não 0).
5. RM sequencial por empresa: `BM-YYYY-NNN`. Ex `BM-2026-009 → BM-2026-010`. Primeiro sem base: deixar em branco (decisão) — alternativa `BM-AAAA-001` se cliente mudar.
6. Revisão: 0 na emissão nova; reemitir mesmo RM → +1.
7. Arquivo download: `Boletim <NOME EMPRESA> - <dd-mm-yyyy emissão>.xlsx/.pdf`.
8. Lote: match `USUÁRIO` exato sem case; soma horas floats; 1 casa? manter 2 decimais.

## 7. Validações e erros

- Login duplicado, CNPJ/PO/E-clic duplicados, e-mail sem @, datas invertidas, valor negativo, lote com datas divergentes, base com CNPJ divergente, planilha fora do modelo (sem `PROJETO:`/`USUÁRIO`/`HORAS`) → toast + log, sem crash. Lote nunca cadastra parcial com erro crítico de modelo; linhas com branco/duplicada apenas puladas e listadas.

## 8. Critérios de aceite

- [ ] Primeiro uso → cadastro → entra direto; login posterior funciona; duplicado bloqueia; admin flag no 1º.
- [ ] Cadastro empresa individual + lote na ordem definida com relatório de puladas.
- [ ] Lista com busca Responsável/Nome/CNPJ; editar mostra toast e não altera BMs antigos; base importada por CNPJ.
- [ ] Lote com 2+ planilhas gera 1 BM/empresa, horas somadas por projeto texto cheio, período/emissão/RM corretos, xlsx abre idêntico ao template, pdf legível, ambos baixáveis com nome correto.
- [ ] Individual manual só pede Período/Projeto/Horas; resto automático/travado.
- [ ] Reemissão gera Rev 1,2...; sem histórico deixa branco.

## 9. Fora de escopo (não implementar)

Abas `Tdocumlist/Sheet2/Resumo`, logout/Sair, gestão de usuários além de reset pelo admin, multi-PO por empresa, envio de e-mail automático.
