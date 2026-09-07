# -*- coding: utf-8 -*-
"""
必剪字幕导出工具 - 安装程序构建脚本
使用 PyInstaller + UPX 打包 exe，Inno Setup 制作安装包（最大压缩）
"""
import os
import sys
import shutil
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(r"F:\software\李超自开发工具\必剪字幕导出工具")
INSTALLER_DIR = ROOT / "installer"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
UPX_DIR = Path(r"C:\upx-5.1.1-win64")
PYTHON = r"C:\Users\Administrator\AppData\Local\Python\pythoncore-3.12-64\python.exe"
APP_NAME = "必剪字幕导出工具"
APP_VERSION = "1.0"

def run(cmd, cwd=None):
    print("\n>>> " + " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.stdout:
        print(result.stdout[-2000:])
    if result.stderr:
        print("STDERR:", result.stderr[-2000:])
    return result.returncode == 0

def step(msg):
    print("\n" + "=" * 60)
    print("  " + msg)
    print("=" * 60)

def main():
    step("1. 清理旧文件并创建目录")
    for d in [INSTALLER_DIR, DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    print("目录已创建: " + str(INSTALLER_DIR))

    step("2. 检查/安装 PyInstaller")
    try:
        import PyInstaller
        print("PyInstaller 已安装: " + PyInstaller.__version__)
    except ImportError:
        print("正在安装 PyInstaller...")
        if not run([PYTHON, "-m", "pip", "install", "pyinstaller", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]):
            print("PyInstaller 安装失败！")
            return

    step("3. 检查 UPX")
    upx_exe = UPX_DIR / "upx.exe"
    if upx_exe.exists():
        print("UPX 已找到: " + str(upx_exe))
    else:
        print("警告: 未找到 UPX，将不使用 UPX 压缩")

    step("4. PyInstaller 打包 exe (onefile + UPX 最大压缩)")
    exe_path = DIST_DIR / (APP_NAME + ".exe")
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / 1024 / 1024
        print("已找到打包好的 exe ({:.1f} MB)，跳过打包步骤".format(size_mb))
    else:
        pyinstaller_cmd = [
            PYTHON, "-m", "PyInstaller",
            "--onefile",
            "--windowed",
            "--name", APP_NAME,
            "--clean",
            "--noconfirm",
            "--hidden-import", "PIL._tkinter_finder",
            "--collect-submodules", "pydub",
            "--distpath", str(DIST_DIR),
            "--workpath", str(BUILD_DIR),
            "--specpath", str(ROOT),
        ]
        if upx_exe.exists():
            pyinstaller_cmd.extend(["--upx-dir", str(UPX_DIR)])
        pyinstaller_cmd.append(str(ROOT / "main.py"))

        if not run(pyinstaller_cmd, cwd=str(ROOT)):
            print("打包失败！")
            return

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / 1024 / 1024
        print("打包成功! 文件大小: {:.1f} MB".format(size_mb))
    else:
        print("错误: 未找到生成的 exe")
        return

    step("5. 复制 ffmpeg 到发布目录")
    ffmpeg_src = ROOT / "ffmpeg"
    ffmpeg_dst = DIST_DIR / "ffmpeg"
    if ffmpeg_src.exists():
        shutil.copytree(str(ffmpeg_src), str(ffmpeg_dst))
        print("ffmpeg 已复制")
    else:
        print("警告: 未找到 ffmpeg 目录")

    step("6. 检查 Inno Setup")
    iscc_paths = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    iscc = None
    for p in iscc_paths:
        if p.exists():
            iscc = p
            break
    if not iscc:
        print("未找到 Inno Setup，正在下载并静默安装...")
        installer_exe = ROOT / "innosetup_install.exe"
        urls = [
            "https://files.jrsoftware.org/is/6/innosetup-6.4.0.exe",
            "https://jrsoftware.org/download.php/is.exe",
            "https://mirrors.jrsoftware.org/is/6/innosetup-6.4.0.exe",
        ]
        downloaded = False
        for url in urls:
            try:
                print("尝试下载: " + url)
                urllib.request.urlretrieve(url, str(installer_exe))
                size_mb = installer_exe.stat().st_size / 1024 / 1024
                print("下载完成: {:.1f} MB".format(size_mb))
                if size_mb > 5:
                    downloaded = True
                    break
                else:
                    print("文件太小，可能下载失败，尝试下一个源...")
                    installer_exe.unlink(missing_ok=True)
            except Exception as e:
                print("下载失败: " + str(e))
                continue
        if not downloaded:
            print("\n" + "=" * 60)
            print("  自动下载 Inno Setup 失败！")
            print("  请手动下载安装 Inno Setup 6:")
            print("  https://jrsoftware.org/download.php/is.exe")
            print("  安装完成后重新运行 build.bat")
            print("  (exe 和 ffmpeg 已打包好，不会重复打包)")
            print("=" * 60)
            return
        try:
            print("正在静默安装 Inno Setup...")
            run([str(installer_exe), "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES", "/CURRENTUSER"])
            installer_exe.unlink(missing_ok=True)
            for p in iscc_paths:
                if p.exists():
                    iscc = p
                    break
            if not iscc:
                alt = Path.home() / "AppData" / "Local" / "Programs" / "Inno Setup 6" / "ISCC.exe"
                if alt.exists():
                    iscc = alt
        except Exception as e:
            print("Inno Setup 安装失败: " + str(e))
            print("请手动安装后重新运行")
            return

    if not iscc:
        print("错误: 仍未找到 ISCC.exe")
        return
    print("Inno Setup 编译器: " + str(iscc))

    step("7. 生成 Inno Setup 脚本 (LZMA2 ultra64 固实最大压缩)")
    iss_content = '''; Script generated by build_installer.py
#define MyAppName "必剪字幕导出工具"
#define MyAppVersion "1.0"
#define MyAppPublisher "超哥工具箱"
#define MyAppExeName "必剪字幕导出工具.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=''' + str(INSTALLER_DIR) + '''
OutputBaseFilename=BCut_Subtitle_Tool_v1.0_setup
SetupIconFile=
Compression=lzma2/ultra64
SolidCompression=yes
InternalCompressLevel=max
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\\{#MyAppExeName}
AppCopyright=Copyright (C) 2026 超哥工具箱

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"; Flags: unchecked

[Files]
Source: "''' + str(DIST_DIR / (APP_NAME + ".exe")) + '''"; DestDir: "{app}"; Flags: ignoreversion
Source: "''' + str(DIST_DIR / "ffmpeg") + '''\\*"; DestDir: "{app}\\ffmpeg"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"
Name: "{group}\\卸载{#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\\{#MyAppExeName}"; Description: "立即运行{#MyAppName}"; Flags: nowait postinstall skipifsilent
'''
    iss_path = ROOT / "installer_script.iss"
    with open(iss_path, "w", encoding="utf-8") as f:
        f.write(iss_content)
    print("Inno Setup 脚本已生成: " + str(iss_path))

    step("8. 编译安装程序")
    if not run([str(iscc), str(iss_path)]):
        print("编译失败！")
        return

    output_exe = INSTALLER_DIR / "BCut_Subtitle_Tool_v1.0_setup.exe"
    if output_exe.exists():
        size_mb = output_exe.stat().st_size / 1024 / 1024
        print("\n" + "=" * 60)
        print("  安装程序构建成功！")
        print("  路径: " + str(output_exe))
        print("  大小: {:.1f} MB".format(size_mb))
        print("=" * 60)
    else:
        print("错误: 未找到生成的安装程序")

if __name__ == "__main__":
    main()
