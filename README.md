# 必剪字幕导出工具

> 超哥工具箱系列 — 必剪（Bcut）草稿字幕与音轨管理桌面工具

将 [BCutBoxWeb](https://github.com/AlexDuttonGit/BCutBoxWeb) 的核心功能移植为 Python 桌面版，提供更直观的图形界面和更便捷的本地操作体验。

## 功能特性

- **草稿管理** — 自动扫描必剪默认草稿目录，支持重命名、复制、删除
- **字幕轨道** — 查看所有字幕轨道及片段，双击查看详情，支持导出 SRT
- **音频轨道** — 查看所有音频轨道及片段，支持导出 WAV / M4A / MP3
- **字幕导入** — 导入 SRT 字幕文件，支持新建轨道或覆盖现有轨道
- **轨道删除** — 删除不需要的字幕/音频轨道，自动备份原文件后直接修改
- **项目预览** — 显示草稿封面、轨道数量、片段数量等信息
- **路径记忆** — 自动记住上次选择的草稿目录，启动即加载
- **全中文界面** — 深色标题栏 + 三栏布局，所有控件带悬停提示

## 下载安装

从 [Releases](https://github.com/你的用户名/你的仓库名/releases) 页面下载最新版安装包：

- `BCut_Subtitle_Tool_v1.0_setup.exe` — Windows 安装程序（已内置 ffmpeg，无需额外配置）

运行安装包，按提示完成安装即可。安装后桌面和开始菜单会有快捷方式。

### 系统要求

- Windows 10 / 11（64位）
- 必剪 PC 版（用于创建和编辑草稿）

## 使用说明

### 1. 选择草稿目录

程序启动后会自动加载必剪默认草稿目录（`文档\Bcut Drafts\`）。如需切换，点击左上角「选择目录」按钮。

### 2. 选择草稿

左侧列表显示所有草稿，点击选中后中间区域显示该草稿的字幕轨道和音频轨道。

### 3. 导出字幕

- 选中一个字幕轨道
- 右侧「字幕操作」区选择是否「去除格式」「对齐音频」
- 点击「导出 SRT」，选择保存位置

### 4. 导出音频

- 选中一个音频轨道
- 右侧「音频操作」区选择导出格式（WAV / M4A / MP3）
- 点击「导出音轨」，选择保存位置

### 5. 导入字幕

- 点击「导入 SRT」，选择字幕文件
- 选择导入模式：新建轨道 / 覆盖当前轨道
- 导入后自动刷新轨道列表

### 6. 删除轨道

- 选中要删除的轨道
- 点击「轨道与片段」标题栏右侧的「删除轨道」按钮
- 确认后程序会**自动备份原文件**，然后直接修改原草稿
- 打开必剪即可看到删除效果

## 本地开发

### 环境要求

- Python 3.12（64位）
- 依赖库：`pydub`、`Pillow`

### 安装依赖

```bash
pip install pydub Pillow
```

### 运行

```bash
python main.py
```

### ffmpeg

程序运行需要 ffmpeg。将 ffmpeg 便携版解压到程序目录下，结构为：

```
必剪字幕导出工具/
├── main.py
└── ffmpeg/
    └── bin/
        └── ffmpeg.exe
```

程序启动时会自动检测 `ffmpeg\bin\ffmpeg.exe` 并加入 PATH。

## 打包构建

### 前置准备

- 安装 [PyInstaller](https://pyinstaller.org/)：`pip install pyinstaller`
- 安装 [UPX](https://upx.github.io/)（可选，用于压缩 exe 体积）
- 安装 [Inno Setup 6](https://jrsoftware.org/isinfo.php)（用于制作安装程序）

### 一键打包

确保 `build.bat`、`build_installer.py` 和 `ffmpeg\` 目录在同一文件夹下，然后双击运行：

```bash
build.bat
```

脚本会自动完成：
1. PyInstaller + UPX 打包 exe（单文件、无控制台窗口）
2. 复制 ffmpeg 到发布目录
3. 生成 Inno Setup 脚本（LZMA2 ultra64 固实压缩）
4. 编译生成安装程序

最终安装包在 `installer\BCut_Subtitle_Tool_v1.0_setup.exe`。

## 技术栈

- **GUI**：tkinter / ttk（Python 标准库，无需额外安装）
- **音频处理**：pydub + ffmpeg
- **图片处理**：Pillow（封面显示）
- **打包**：PyInstaller + UPX
- **安装程序**：Inno Setup 6

## 致谢

- [BCutBoxWeb](https://github.com/AlexDuttonGit/BCutBoxWeb) — 原始网页版项目，提供了 bjson 解析逻辑的参考
- [必剪](https://bcut.bilibili.cn/) — B站旗下视频剪辑软件

## 许可证

本项目仅供学习交流使用。
