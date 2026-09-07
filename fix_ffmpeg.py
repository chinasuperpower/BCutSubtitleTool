# -*- coding: utf-8 -*-
"""
修复 ffmpeg 目录：找到解压后的 ffmpeg 文件夹并重命名为 ffmpeg
"""
import os
import shutil
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
FFMPEG_DIR = TOOL_DIR / "ffmpeg"
FFMPEG_EXE = FFMPEG_DIR / "bin" / "ffmpeg.exe"


def find_ffmpeg_folder():
    """在工具目录下查找包含 bin/ffmpeg.exe 的文件夹"""
    candidates = []
    for item in TOOL_DIR.iterdir():
        if not item.is_dir():
            continue
        if item.name == "ffmpeg":
            continue
        # 检查是否包含 bin/ffmpeg.exe
        exe = item / "bin" / "ffmpeg.exe"
        if exe.exists():
            candidates.append(item)
            continue
        # 检查名字是否包含 ffmpeg 和 essentials
        name_lower = item.name.lower()
        if "ffmpeg" in name_lower and ("essentials" in name_lower or "build" in name_lower or "release" in name_lower):
            candidates.append(item)
    return candidates


def main():
    print("=" * 60)
    print("  FFmpeg 目录修复脚本")
    print("  工具目录: " + str(TOOL_DIR))
    print("=" * 60)
    print()

    if FFMPEG_EXE.exists():
        print("[√] ffmpeg 已经就绪，无需修复")
        print("    路径: " + str(FFMPEG_EXE))
        print()
        input("按回车键退出...")
        return

    print("正在搜索 ffmpeg 文件夹...")
    print()

    # 列出工具目录下所有文件夹
    print("当前目录下的文件夹:")
    for item in TOOL_DIR.iterdir():
        if item.is_dir():
            exe = item / "bin" / "ffmpeg.exe"
            marker = "  <-- 包含 ffmpeg.exe!" if exe.exists() else ""
            print("  - " + item.name + marker)
    print()

    candidates = find_ffmpeg_folder()

    if not candidates:
        print("[×] 未找到包含 ffmpeg 的文件夹")
        print()
        print("  可能的原因:")
        print("  1. 解压后的文件夹不在工具目录下")
        print("  2. 压缩包结构与预期不同")
        print()
        print("  请手动检查工具目录，找到包含 bin\\ffmpeg.exe 的文件夹，")
        print("  将其重命名为 'ffmpeg'。")
        input("按回车键退出...")
        return

    if len(candidates) > 1:
        print("找到多个候选文件夹，使用第一个: " + candidates[0].name)
        for c in candidates[1:]:
            print("  其他候选: " + c.name)

    src = candidates[0]
    print()
    print("找到目标文件夹: " + src.name)
    print("  路径: " + str(src))

    # 确认里面有 ffmpeg.exe
    src_exe = src / "bin" / "ffmpeg.exe"
    if src_exe.exists():
        print("  确认包含 bin\\ffmpeg.exe: [√]")
    else:
        print("  警告: 未找到 bin\\ffmpeg.exe，仍尝试重命名")

    print()
    print("正在重命名为 'ffmpeg' ...")

    if FFMPEG_DIR.exists():
        print("  已存在 ffmpeg 文件夹，先删除...")
        shutil.rmtree(str(FFMPEG_DIR))

    try:
        src.rename(str(FFMPEG_DIR))
        print("  重命名成功！")
    except Exception as e:
        print("[×] 重命名失败: " + str(e))
        print()
        print("  请手动将文件夹 '" + src.name + "' 重命名为 'ffmpeg'")
        input("按回车键退出...")
        return

    if FFMPEG_EXE.exists():
        print()
        print("=" * 60)
        print("  [√] FFmpeg 修复完成！")
        print()
        print("  ffmpeg.exe 路径:")
        print("  " + str(FFMPEG_EXE))
        print("=" * 60)
        print()
        print("  现在重新运行 main.py，音频导出功能将自动启用。")
    else:
        print("[×] 重命名后仍未找到 ffmpeg.exe，请检查目录结构")

    print()
    input("按回车键退出...")


if __name__ == "__main__":
    main()
