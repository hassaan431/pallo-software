# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

a = Analysis(
    ['launch.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('database.py', '.'),
        ('invoice_generator.py', '.'),
    ],
    hiddenimports=[
        'flask',
        'flask_login',
        'werkzeug',
        'werkzeug.security',
        'werkzeug.serving',
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.pdfgen.canvas',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.units',
        'reportlab.lib.colors',
        'reportlab.lib.utils',
        'reportlab.pdfbase',
        'reportlab.pdfbase.pdfmetrics',
        'PIL',
        'PIL.Image',
        'sqlite3',
        'jinja2',
        'jinja2.ext',
        'markupsafe',
        'click',
        'itsdangerous',
        'flask.templating',
        'flask.json',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AKDistributors',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AKDistributors',
)

app_bundle = BUNDLE(
    coll,
    name='AK Distributors.app',
    icon=None,
    bundle_identifier='com.akdistributors.app',
)
