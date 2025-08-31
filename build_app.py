#!/usr/bin/env python3
"""
Build script for the Repo Maintenance Tool.

This script creates a standalone executable for the Repo Maintenance Tool
using PyInstaller.
"""

import os
import subprocess
import sys

def build_app():
    """Build the standalone executable."""
    print("Building the Repo Maintenance Tool...")
    
    # Create the spec file
    spec_content = """
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['check_component_tags_gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RepoMaintenanceTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)
    """
    
    with open("RepoMaintenanceTool.spec", "w") as f:
        f.write(spec_content)
    
    # Build the executable
    try:
        subprocess.run(["pyinstaller", "RepoMaintenanceTool.spec"], check=True)
        print("\nBuild successful!")
        print("The executable is located in the 'dist' folder.")
        print("You can share the 'RepoMaintenanceTool.exe' file with others.")
    except subprocess.CalledProcessError as e:
        print(f"Error building the executable: {e}")
        return False
    
    return True

if __name__ == "__main__":
    build_app()
