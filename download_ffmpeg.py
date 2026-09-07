# -*- coding: utf-8 -*-
"""
FFmpeg 便携版一键下载安装脚本
下载 ffmpeg-release-essentials 并解压到工具目录下的 ffmpeg 文件夹
"""
import os
import sys
import zipfile
import urllib.request
import shutil
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
FFMPEG_DIR = TOOL_DIR / "ffmpeg"
FFMPEG_EXE = FFMPEG_DIR / "bin" / "ffmpeg.exe"
ZIP_FILE = TOOL_DIR / "ffmpeg_temp.zip"

DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def report_progress(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        percent = min(downloaded / total_size * 100, 100)
        mb_down = downloaded / (1024 * 1024)
        mb_total = total_size / (1024 * 1024)
        print("\r  下载进度: {:.1f}% ({:.1f} / {:.1f} MB)".format(percent, mb_down, mb_total), end="", flush=True)


def main():
    print("=" * 60)
    print("  FFmpeg 便携版一键下载安装")
    print("  安装目录: " + str(FFMPEG_DIR))
    print("=" * 60)
    print()

    if FFMPEG_EXE.exists():
        print("[√] 检测到已安装的 ffmpeg.exe")
        print("    路径: " + str(FFMPEG_EXE))
        print()
        input("按回车键退出...")
        return

    print("[1/3] 正在下载 ffmpeg-release-essentials.zip ...")
    print("  下载源: " + DOWNLOAD_URL)
    print("  （文件约 80-100MB，请耐心等待）")
    print()

    try:
        urllib.request.urlretrieve(DOWNLOAD_URL, str(ZIP_FILE), reporthook=report_progress)
        print()
        print("  下载完成！")
    except Exception as e:
        print()
        print("[×] 下载失败: " + str(e))
        print()
        print("  请检查网络连接，或手动下载：")
        print("  " + DOWNLOAD_URL)
        print("  下载后解压，将文件夹重命名为 'ffmpeg' 放在:")
        print("  " + str(TOOL_DIR))
        if ZIP_FILE.exists():
            try:
                ZIP_FILE.unlink()
            except:
                pass
        input("按回车键退出...")
        return

    if not ZIP_FILE.exists():
        print("[×] 下载文件不存在！")
        input("按回车键退出...")
        return

    print()
    print("[2/3] 正在解压 ...")
    try:
        with zipfile.ZipFile(str(ZIP_FILE), "r") as zf:
            zf.extractall(str(TOOL_DIR))
        print("  解压完成！")
    except Exception as e:
        print("[×] 解压失败: " + str(e))
        if ZIP_FILE.exists():
            try:
                ZIP_FILE.unlink()
            except:
                pass
        input("按回车键退出...")
        return

    print()
    print("[3/3] 整理目录 ...")
    try:
        ZIP_FILE.unlink()
    except:
        pass

    extracted_dir = None
    for item in TOOL_DIR.iterdir():
        if not item.is_dir():
            continue
        if item.name == "ffmpeg":
            continue
        exe = item / "bin" / "ffmpeg.exe"
        if exe.exists():
            extracted_dir = item
            break
    if extracted_dir is None:
        for item in TOOL_DIR.iterdir():
            if not item.is_dir():
                continue
            name_lower = item.name.lower()
            if "ffmpeg" in name_lower and ("essentials" in name_lower or "build" in name_lower):
                extracted_dir = item
                break

    if extracted_dir is None:
        print("[×] 未找到解压后的文件夹，请检查目录内容")
        input("按回车键退出...")
        return

    if FFMPEG_DIR.exists():
        shutil.rmtree(str(FFMPEG_DIR))

    extracted_dir.rename(str(FFMPEG_DIR))

    if not FFMPEG_EXE.exists():
        print("[×] 未找到 ffmpeg.exe，解压可能出错")
        print("  请检查: " + str(FFMPEG_DIR))
        input("按回车键退出...")
        return

    print()
    print("=" * 60)
    print("  [√] FFmpeg 安装完成！")
    print()
    print("  ffmpeg.exe 路径:")
    print("  " + str(FFMPEG_EXE))
    print("=" * 60)
    print()
    print("  现在重新运行 main.py，音频导出功能将自动启用。")
    print("  程序会自动检测同目录下 ffmpeg\\bin\\ffmpeg.exe，无需手动配置。")
    print()
    input("按回车键退出...")


if __name__ == "__main__":
    main()
