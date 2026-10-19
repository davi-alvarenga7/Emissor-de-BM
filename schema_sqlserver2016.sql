-- =====================================================================
-- Emissor de BM (E-BM) - SQL Server 2016
-- Execute este script no SSMS (ou pelo proprio sistema) para criar o esquema.
-- Banco padrao: EBM
-- =====================================================================

IF DB_ID('EBM') IS NULL
BEGIN
    PRINT 'Banco EBM nao encontrado. Crie o banco antes de executar este script.';
    -- Para criar o banco, descomente as duas linhas abaixo e execute:
    -- CREATE DATABASE EBM;
    -- USE EBM;
END
GO

USE EBM;
GO

-- ---------------------------------------------------------------- usuarios
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
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UX_users_login' AND object_id=OBJECT_ID('dbo.users'))
CREATE UNIQUE INDEX UX_users_login ON dbo.users(login);
GO

-- ---------------------------------------------------------------- empresas
IF OBJECT_ID('dbo.companies','U') IS NULL
CREATE TABLE dbo.companies (
    id             INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_companies PRIMARY KEY,
    nome           NVARCHAR(200) NOT NULL,
    cnpj           NVARCHAR(14) NOT NULL,
    responsavel    NVARCHAR(200) NOT NULL,
    email_contato  NVARCHAR(200) NOT NULL,
    usuario_eclic  NVARCHAR(100) COLLATE Latin1_General_CI_AS NOT NULL,
    po_codigo      NVARCHAR(50)  COLLATE Latin1_General_CI_AS NOT NULL,
    po_inicio      DATE NOT NULL,
    po_fim         DATE NOT NULL,
    po_valor_total DECIMAL(18,2) NOT NULL,
    po_objeto      NVARCHAR(500) NOT NULL,
    valor_hora     DECIMAL(18,2) NOT NULL,
    criado_em      DATETIME2(0) NOT NULL CONSTRAINT DF_companies_criado_em DEFAULT (SYSDATETIME()),
    atualizado_em  DATETIME2(0) NOT NULL CONSTRAINT DF_companies_atualizado_em DEFAULT (SYSDATETIME()),
    CONSTRAINT UQ_companies_cnpj   UNIQUE (cnpj),
    CONSTRAINT UQ_companies_eclic  UNIQUE (usuario_eclic),
    CONSTRAINT UQ_companies_po     UNIQUE (po_codigo),
    CONSTRAINT CK_companies_valor  CHECK (po_valor_total >= 0),
    CONSTRAINT CK_companies_vh     CHECK (valor_hora >= 0),
    CONSTRAINT CK_companies_datas  CHECK (po_fim >= po_inicio)
);
GO

-- ---------------------------------------------------------------- boletins
IF OBJECT_ID('dbo.bms','U') IS NULL
CREATE TABLE dbo.bms (
    id               INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bms PRIMARY KEY,
    company_id       INT NOT NULL CONSTRAINT FK_bms_company REFERENCES dbo.companies(id),
    rm_numero        NVARCHAR(50) NOT NULL,
    periodo_ini      DATE NOT NULL,
    periodo_fim      DATE NOT NULL,
    emissao          DATE NOT NULL,
    revisao          INT NOT NULL CONSTRAINT DF_bms_revisao DEFAULT (0),
    contratante      NVARCHAR(200) NOT NULL CONSTRAINT DF_bms_contratante DEFAULT (N'DBR ENERGIES S/A'),
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
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_bms_company' AND object_id=OBJECT_ID('dbo.bms'))
CREATE INDEX IX_bms_company ON dbo.bms(company_id, criado_em DESC);
GO

-- ---------------------------------------------------------------- itens
IF OBJECT_ID('dbo.bm_items','U') IS NULL
CREATE TABLE dbo.bm_items (
    id              INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bm_items PRIMARY KEY,
    bm_id           INT NOT NULL CONSTRAINT FK_bm_items_bm REFERENCES dbo.bms(id) ON DELETE CASCADE,
    item_seq        INT NOT NULL,
    projeto         NVARCHAR(300) NOT NULL,
    descricao       NVARCHAR(300) NOT NULL CONSTRAINT DF_bm_items_desc DEFAULT (N'Servicos de Consultoria em TELECOM'),
    valor_hora      DECIMAL(18,2) NOT NULL,
    horas_anterior  DECIMAL(18,4) NULL,
    horas_periodo   DECIMAL(18,4) NOT NULL,
    horas_acumulada DECIMAL(18,4) NULL,
    total_anterior  DECIMAL(18,2) NULL,
    total_periodo   DECIMAL(18,2) NULL,
    total_acumulado DECIMAL(18,2) NULL,
    CONSTRAINT UQ_bm_items UNIQUE (bm_id, projeto)
);
GO

PRINT 'Esquema criado com sucesso.';
GO
