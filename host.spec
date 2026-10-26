# Build from the repository root: python -m PyInstaller --noconfirm host.spec
from pathlib import Path
import os
import sys
# Avoid collecting unrelated DLLs (for example Poppler ICU) from the host PATH.
os.environ["PATH"] = os.pathsep.join([str(Path(sys.executable).parent),
    str(Path(os.environ["SystemRoot"]) / "System32"), os.environ["SystemRoot"]])
import PySide6
import shiboken6
assert PySide6.__version__ == shiboken6.__version__ == "6.11.0", "Install requirements-build.txt in an isolated environment"

root = Path(SPECPATH)
qt = Path(PySide6.__file__).parent
# Use one consistent, Qt-provided MSVC runtime, including before Python starts.
runtime_names = {'vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll',
                 'msvcp140_1.dll', 'msvcp140_2.dll', 'msvcp140_codecvt_ids.dll', 'concrt140.dll'}
runtimes = [(str(p), '.') for p in qt.glob('*.dll') if p.name.lower() in runtime_names]
a = Analysis([str(root / 'host_app/host.py')], pathex=[], binaries=runtimes,
             datas=[], hiddenimports=[], hookspath=[],
             runtime_hooks=[str(root / 'packaging/diagnostic_hook.py')],
             excludes=[], noarchive=False, optimize=0)
# Dependency analysis may also find the older Python runtime. Replace every copy.
a.binaries = [(dest, str(qt / Path(src).name), kind)
              if Path(src).name.lower() in runtime_names and (qt / Path(src).name).exists()
              else (dest, src, kind) for dest, src, kind in a.binaries
              if Path(src).name.lower() != "icuuc.dll" and not Path(src).name.lower().startswith("icudt")]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='Conect-Host-Corrigido',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
