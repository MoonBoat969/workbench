# 专属工作台 — 完全离线安装运行指南

本目录已集成全部运行依赖的离线安装包，**目标机器无需联网**即可安装运行。

## 一、交付包内容

```
workbench/
├── main.py                 应用入口
├── install_kylin.sh        麒麟：一键离线安装脚本
├── start.sh                麒麟：启动脚本
├── build_kylin.sh          麒麟：离线打包绿色版（可选）
├── install_win7.bat        Win7：一键离线安装脚本（自动识别 32/64 位）
├── 启动工作台.bat           Win7：启动脚本
├── build_win.bat           Win7：离线打包绿色版（可选）
├── requirements.txt        依赖清单（Python 3.8 对应版本）
├── assets/fonts/           内置中文字体（统计图表离线渲染用）
└── packaging/
    ├── offline/linux/      麒麟离线包
    │   ├── wheels37_x86_64/     Python3.7 依赖（兆芯/海光等 x86_64）
    │   ├── wheels37_aarch64/    Python3.7 依赖（飞腾/鲲鹏等 ARM64）
    │   ├── wheels38_x86_64/     Python3.8 依赖（x86_64）
    │   ├── wheels38_aarch64/    Python3.8 依赖（ARM64）
    │   ├── wheels310_x86_64/    Python3.10 依赖（x86_64）
    │   └── wheels310_aarch64/   Python3.10 依赖（ARM64）
    ├── offline/win/        Win7 离线包
    │   ├── python-3.8.10-amd64.exe   64 位 Python 安装包
    │   ├── python-3.8.10.exe         32 位 Python 安装包
    │   ├── wheels_win64/             64 位依赖（含 OCR）
    │   ├── wheels_win32/             32 位依赖（不含 OCR 运行库，见"常见问题"）
    │   ├── requirements_win64.txt    64 位依赖清单
    │   └── requirements_win32.txt    32 位依赖清单
    └── build_wheels_*/     PyInstaller 离线构建依赖（打包绿色版用）

> 其中麒麟 6 套、Win64 一套均内置 OCR 离线包（rapidocr-onnxruntime
> 及其 onnxruntime/opencv/pyclipper/shapely 等依赖），支持 PDF 工具集
> 中"OCR 识别"页签：扫描件文字识别、生成可复制/搜索文字层、
> OCR 后编辑回写。识别模型随 rapidocr 包内置，同样离线可用。
```

## 二、银河麒麟 安装（推荐：源码 + 离线依赖）

前置条件：系统自带 `python3`（3.7 / 3.8 / 3.10 之一）和 `python3-tkinter` 包
（麒麟桌面版通常已预装；若缺失请通过系统源或光盘源安装 `python3-tkinter`）。

```bash
cd 本目录
bash install_kylin.sh     # 自动识别 CPU 架构与 python 版本，装依赖到 pylibs/
bash start.sh             # 启动应用
```

- 安装不联网、不需要 root 权限、不污染系统 python 环境（依赖装在 pylibs/）。
- 数据保存在本目录 `data/workbench.db`，随包携带、整目录迁移即可。

## 三、银河麒麟 安装（可选：PyInstaller 绿色版）

适用于目标机没有 python 环境的场景。在**与目标机同 CPU 架构**的一台麒麟机器上执行：

```bash
bash build_kylin.sh       # 全部离线，产出 dist/专属工作台/
```

将 `dist/专属工作台/` 整个目录拷贝到目标机，运行其中的 `专属工作台` 可执行文件。
数据保存在可执行文件同目录 `data/` 下。

## 四、Windows 7 安装

1. 把整个 workbench 目录拷贝到 Win7 机器（U 盘/内网共享均可）。
2. 双击 `install_win7.bat`：
   - 自动识别 32/64 位；
   - 机器上已有 Python 3.8 则直接复用；
   - 没有则静默安装包内自带的 Python 3.8.10（此步需要管理员权限）；
   - 随后从包内离线 wheel 安装全部依赖。
3. 双击 `启动工作台.bat` 启动应用。

## 五、Windows 7（可选：exe 绿色版）

在装有 Python 3.8 的 Win7 机器（或打包专用机）上双击 `build_win.bat`，
产出 `dist\专属工作台\`，整个目录拷到任意 Win7 机器运行 `专属工作台.exe`。

## 六、常见问题

| 问题 | 处理 |
|------|------|
| 麒麟提示缺 tkinter | 安装系统包 `python3-tkinter`（系统源/光盘源），或改用绿色版打包 |
| 麒麟 python 版本不是 3.7/3.8/3.10 | 用 `bash build_kylin.sh` 在本机打包绿色版即可（脚本用系统 python 构建，无版本限制） |
| 图表不显示 | 依赖已内置中文字体并自动适配渲染后端，正常情况直接可用 |
| 数据备份 | 应用每天自动备份到 `data/backup/`（保留最近 30 份） |
| OCR 页签提示"未检测到 OCR 引擎" | ①确认安装脚本自检中 OCR 模块为 [OK]；②Win7 32 位不内置 OCR 运行库（onnxruntime 无 32 位版），可安装系统 Tesseract（含中文语言包）后重启应用作为备选引擎；③麒麟机器如自检为 [WARN]，多半是缺 libGL（安装 mesa 相关包） |
| 打包绿色版（PyInstaller）不含 OCR | 打包前先执行 `bash install_kylin.sh`（或对应 win 安装脚本）装上 OCR 依赖，构建脚本会自动收集 OCR 模型与运行库 |
| 卸载 | 直接删除整个目录即可（绿色安装，无注册表/系统文件） |