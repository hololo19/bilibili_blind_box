# -*- mode: python ; coding: utf-8 -*-
# 单文件打包配置 - 打包后只有一个exe文件，但启动较慢

block_cipher = None

a = Analysis(
    ['blind_box_gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'brotli',
        'aiohttp',
        'asyncio',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'flask',
        'flask_socketio',
        'socketio',
        'eventlet',
    ],  # 排除Web服务器相关库
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='盲盒统计工具_单文件版',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='盲盒统计工具_单文件版',
)
