# -*- coding: utf-8 -*-
"""
必剪字幕导出工具 - 一键发布到 GitHub
自动完成: Git 提交推送 + 创建 Release + 上传安装包
"""
import os
import sys
import json
import base64
import subprocess
import urllib.request
import urllib.error
from urllib.parse import quote
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "publish_config.json"
INSTALLER_DIR = ROOT / "installer"
INSTALLER_NAME = "必剪字幕导出工具_v1.0_setup.exe"


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("   配置已保存到 publish_config.json（此文件不会被提交到 GitHub）")


def input_config():
    print("\n--- 首次配置 ---")
    print("请准备以下信息：")
    print("  1. GitHub 用户名")
    print("  2. 仓库名（需先在 GitHub 上创建好空仓库）")
    print("  3. Personal Access Token（令牌）")
    print()
    print("如何获取 Personal Access Token:")
    print("  GitHub 右上角头像 → Settings → 左侧 Developer settings")
    print("  → Personal access tokens → Tokens (classic) → Generate new token")
    print("  → 勾选 repo 权限 → Generate token → 复制令牌（只显示一次！）")
    print()
    username = input("GitHub 用户名: ").strip()
    repo = input("仓库名: ").strip()
    token = input("Personal Access Token: ").strip()
    return {"username": username, "repo": repo, "token": token}


def run_git(args, cwd=None):
    cmd = ["git"] + args
    print("\n$ git " + " ".join(args))
    try:
        result = subprocess.run(cmd, cwd=cwd or str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        print("   未找到 Git，跳过此步骤。")
        return False
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip()[:1000])
    return result.returncode == 0


def github_api(method, url, token, data=None, binary=False):
    headers = {
        "Authorization": "token " + token,
        "Accept": "application/vnd.github+json",
    }
    if data is not None and not binary:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif binary:
        body = data
        headers["Content-Type"] = "application/octet-stream"
    else:
        body = None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            if binary:
                return resp.status, raw
            return resp.status, json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print("   HTTP 错误 {}: {}".format(e.code, err_body[:500]))
        return e.code, None
    except Exception as e:
        print("   请求失败: " + str(e))
        return 0, None


def ensure_repo_not_empty(username, repo_name, token):
    """确保仓库不为空，如果为空则自动创建 README.md"""
    api_url = "https://api.github.com/repos/{}/{}/contents/".format(username, repo_name)
    status, resp = github_api("GET", api_url, token)

    if status == 200 and resp:
        return True

    if status == 404 or (status == 200 and not resp):
        print("仓库为空，正在自动创建 README.md ...")
        readme_content = """# 必剪字幕导出工具

必剪（BCut）项目字幕、音频轨道导出工具。

## 功能
- 草稿管理（重命名/复制/删除）
- 字幕轨道查看与 SRT 导出/导入
- 音频轨道查看与 WAV/M4A/MP3 导出
- 轨道删除（自动备份原文件）
- 项目预览、路径记忆、全中文界面

内置 ffmpeg，无需额外配置。

## 下载
在右侧 Releases 页面下载最新版本安装包。
"""
        content_b64 = base64.b64encode(readme_content.encode("utf-8")).decode("utf-8")
        put_url = "https://api.github.com/repos/{}/{}/contents/README.md".format(username, repo_name)
        data = {
            "message": "初始化: 添加 README.md",
            "content": content_b64
        }
        status2, resp2 = github_api("PUT", put_url, token, data)
        if status2 in (200, 201):
            print("README.md 创建成功！")
            return True
        else:
            print("README.md 创建失败，请检查仓库是否存在、Token是否有 repo 权限。")
            return False

    print("无法检查仓库状态（HTTP {}），继续尝试...".format(status))
    return False


def main():
    print("=" * 60)
    print("  必剪字幕导出工具 - 一键发布到 GitHub")
    print("=" * 60)

    # 1. 加载配置
    cfg = load_config()
    if not cfg or not cfg.get("token"):
        cfg = input_config()
        save_config(cfg)
    else:
        print("\n已加载配置: {} / {}".format(cfg["username"], cfg["repo"]))
        change = input("是否修改配置? (y/N): ").strip().lower()
        if change == "y":
            cfg = input_config()
            save_config(cfg)

    username = cfg["username"]
    repo_name = cfg["repo"]
    token = cfg["token"]
    # 带 Token 的远程仓库地址，推送时免输入密码
    repo_url = "https://{}:{}@github.com/{}/{}.git".format(username, token, username, repo_name)

    # 2. 检查 Git
    print("\n--- 检查 Git ---")
    git_available = run_git(["--version"])
    if not git_available:
        print("\n提示: 未安装 Git，将跳过代码提交与推送步骤。")
        print("      （仅创建 Release 并上传安装包，如需推送代码请安装 Git）")
        print("      下载地址: https://git-scm.com/download/win")
    else:
        # 3. Git 操作
        print("\n--- Git 提交与推送 ---")
        if not (ROOT / ".git").exists():
            print("初始化 Git 仓库...")
            run_git(["init"])
            run_git(["branch", "-M", "main"])

        # 设置用户信息（如果没有）
        subprocess.run(["git", "config", "user.name"], cwd=str(ROOT), capture_output=True)
        if subprocess.run(["git", "config", "user.name"], cwd=str(ROOT), capture_output=True, text=True).stdout.strip() == "":
            run_git(["config", "user.name", username])
            run_git(["config", "user.email", username + "@users.noreply.github.com"])

        print("添加文件...")
        run_git(["add", "-A"])

        print("检查变更...")
        status = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT), capture_output=True, text=True)
        if not status.stdout.strip():
            print("没有文件变更，跳过提交。")
        else:
            print("提交变更...")
            run_git(["commit", "-m", "更新: 必剪字幕导出工具 v1.0"])

        # 添加远程仓库
        remotes = subprocess.run(["git", "remote"], cwd=str(ROOT), capture_output=True, text=True).stdout
        if "origin" not in remotes:
            print("添加远程仓库...")
            run_git(["remote", "add", "origin", repo_url])
        else:
            print("更新远程仓库地址...")
            run_git(["remote", "set-url", "origin", repo_url])

        # 先拉取远程内容（处理远程已有 README.md 的情况）
        print("拉取远程仓库内容...")
        run_git(["pull", "origin", "main", "--allow-unrelated-histories", "--no-edit"])

        # 检测并自动解决合并冲突（保留本地版本）
        status_check = subprocess.run(["git", "status"], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
        if "You have unmerged paths" in status_check.stdout or "merge failed" in status_check.stdout.lower():
            print("检测到合并冲突，自动解决（保留本地文件）...")
            conflict_files = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=str(ROOT), capture_output=True, text=True).stdout.strip().split("\n")
            for cf in conflict_files:
                if cf:
                    print("  解决冲突: " + cf)
                    run_git(["checkout", "--ours", cf])
                    run_git(["add", cf])
            run_git(["commit", "--no-edit"])
            print("冲突已解决！")

        print("推送到 GitHub...")
        push_ok = run_git(["push", "-u", "origin", "main"])
        if not push_ok:
            # 尝试普通 push
            push_ok = run_git(["push", "origin", "main"])
        if not push_ok:
            # 尝试强制推送
            print("普通推送失败，尝试强制推送...")
            push_ok = run_git(["push", "--force", "origin", "main"])
        if not push_ok:
            print("\n警告: Git 推送失败，可能是网络问题或凭据问题。")
            print("请检查网络连接后重试，或手动执行: git push -u origin main")
            print("将继续尝试创建 Release...")

    # 4. 检查安装包
    print("\n--- 检查安装包 ---")
    installer_path = INSTALLER_DIR / INSTALLER_NAME
    if not installer_path.exists():
        # 搜索 installer 目录下的 exe
        exes = list(INSTALLER_DIR.glob("*.exe")) if INSTALLER_DIR.exists() else []
        if exes:
            installer_path = exes[0]
            print("找到安装包: " + installer_path.name)
        else:
            print("错误: 未找到安装包！请先运行 build.bat 打包。")
            input("\n按回车键退出...")
            return
    else:
        size_mb = installer_path.stat().st_size / 1024 / 1024
        print("安装包: {} ({:.1f} MB)".format(installer_path.name, size_mb))

    # 4.5 确保仓库不为空（空仓库无法创建 Release）
    print("\n--- 检查仓库状态 ---")
    ensure_repo_not_empty(username, repo_name, token)

    # 5. 创建 Release
    print("\n--- 创建 GitHub Release ---")
    tag = input("Release 版本标签 (默认 v1.0): ").strip() or "v1.0"
    title = input("Release 标题 (默认 v1.0): ").strip() or tag
    default_notes = "## 必剪字幕导出工具 {}\n\n- 草稿管理（重命名/复制/删除）\n- 字幕轨道查看与 SRT 导出/导入\n- 音频轨道查看与 WAV/M4A/MP3 导出\n- 轨道删除（自动备份原文件）\n- 项目预览、路径记忆、全中文界面\n\n内置 ffmpeg，无需额外配置。".format(tag)
    notes = input("Release 描述 (回车使用默认): ").strip() or default_notes

    release_data = {
        "tag_name": tag,
        "name": title,
        "body": notes,
        "draft": False,
        "prerelease": False,
    }

    api_url = "https://api.github.com/repos/{}/{}/releases".format(username, repo_name)
    status, resp = github_api("POST", api_url, token, release_data)

    if status in (200, 201) and resp:
        release_id = resp["id"]
        release_html_url = resp.get("html_url", "")
        print("Release 创建成功! ID: {}".format(release_id))
    elif status == 422:
        # 版本已存在，获取已有 Release
        print("版本 {} 已存在，获取已有 Release...".format(tag))
        get_url = "https://api.github.com/repos/{}/{}/releases/tags/{}".format(username, repo_name, tag)
        status2, resp2 = github_api("GET", get_url, token)
        if status2 == 200 and resp2:
            release_id = resp2["id"]
            release_html_url = resp2.get("html_url", "")
            print("使用已有 Release! ID: {}".format(release_id))
        else:
            print("错误: 获取已有 Release 失败！")
            input("\n按回车键退出...")
            return
    else:
        print("错误: 创建 Release 失败！")
        print("请检查 Token 是否有 repo 权限，仓库是否存在。")
        input("\n按回车键退出...")
        return

    # 6. 上传安装包
    print("\n--- 上传安装包 ---")
    asset_name = installer_path.name
    upload_url = "https://uploads.github.com/repos/{}/{}/releases/{}/assets?name={}".format(
        username, repo_name, release_id, quote(asset_name)
    )

    with open(installer_path, "rb") as f:
        file_data = f.read()

    print("上传中... ({:.1f} MB)".format(len(file_data) / 1024 / 1024))
    status, resp = github_api("POST", upload_url, token, file_data, binary=True)

    if status in (200, 201):
        print("安装包上传成功!")
    else:
        print("警告: 安装包上传失败，你可以手动到 Release 页面上传。")

    # 7. 完成
    print("\n" + "=" * 60)
    print("  发布完成!")
    print("  仓库地址: https://github.com/{}/{}".format(username, repo_name))
    if release_html_url:
        print("  Release 页面: {}".format(release_html_url))
    print("=" * 60)
    input("\n按回车键退出...")


if __name__ == "__main__":
    main()
