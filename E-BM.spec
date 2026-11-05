# -*- mode: python ; coding: utf-8 -*-

import os

import customtkinter

CTK_DIR = os.path.dirname(customtkinter.__file__)

a = Analysis(
    ['src/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Assets estaticos (logo, icone, template)
        ('assets/logo.png', 'assets'),
        ('assets/logo.ico', 'assets'),
        ('assets/template_bm.xlsx', 'assets'),
        ('config.json.example', '.'),
        # config.json NAO deve ser embarcado no executavel (contem credenciais).
        # O usuario cria o config.json localmente a partir do config.json.example.
        # CustomTkinter nao possui hook no PyInstaller: e preciso incluir
        # manualmente os arquivos de tema, fonte e icone usados em tempo de
        # execucao (mesmo caminho relativo ao pacote).
        (os.path.join(CTK_DIR, 'assets', 'themes'),
         os.path.join('customtkinter', 'assets', 'themes')),
        (os.path.join(CTK_DIR, 'assets', 'fonts'),
         os.path.join('customtkinter', 'assets', 'fonts')),
        (os.path.join(CTK_DIR, 'assets', 'icons'),
         os.path.join('customtkinter', 'assets', 'icons')),
        # Pacote src com o codigo refatorado
        ('src', 'src'),
    ],
    hiddenimports=[
        'darkdetect',
        'src.database',
        'src.utils',
        'src.config',
        'src.services.auth_service',
        'src.services.email_service',
        'src.services.boletim_service',
        'src.ui.app',
        'src.ui.widgets',
        'src.ui.telas.login',
        'src.ui.telas.cadastro_user',
        'src.ui.telas.home',
        'src.ui.telas.cad_empresa',
        'src.ui.telas.empresas',
        'src.ui.telas.editar',
        'src.ui.telas.usuarios',
        'src.ui.telas.boletins',
        'src.ui.telas.visualizar_bm',
        'src.ui.telas.boletins_assinados',
        'src.ui.telas.manual',
        'src.ui.telas.lote',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='E-BM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['logo.ico'],
)
