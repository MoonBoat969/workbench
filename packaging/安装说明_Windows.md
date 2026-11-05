# 专属工作台 v1.4.2 — Windows 64 位安装说明

本包**仅包含 64 位 Windows 依赖**，支持 Windows 7 / 10 / 11（64 位）。
32 位系统与银河麒麟请使用对应平台的包，二者不可混用。

## 安装与启动

1. 将整个文件夹拷到 Windows 机器（路径不要含特殊字符）
2. 双击 `install_win7.bat`
   - 自动使用随包 `packaging/offline/win/python-3.8.10-amd64.exe` 静默安装 Python 3.8.10
   - 自动从 `packaging/offline/win/wheels_win64` 安装全部离线依赖（无需联网、无需管理员）
3. 双击 `QiDong.bat`（或 `启动工作台.bat`）启动

首次运行若检测到依赖缺失，`QiDong.bat` 会自动用随包离线 wheels 补装后再启动。

## 生成 exe 绿色版

```bat
install_win7.bat                 :: 仅需执行一次
build_win.bat                    :: 生成 dist\专属工作台\（内含 专属工作台.exe）
build_win.bat /onefile           :: 额外生成单文件 exe
```

生成的 `dist\专属工作台\` 可直接拷到其他 64 位 Windows 机器运行，无需 Python。

## 内网 Web 版（可选）

```bat
python web\server.py --host 0.0.0.0 --port 8000
```

浏览器访问 `http://本机IP:8000`，与桌面版共用 `data\workbench.db`。

## 数据位置

- 源码/绿色版：本目录下 `data\workbench.db`
- 每天自动备份到 `data\backup\`（保留最近 30 份）

## 包内依赖目录（脚本只会引用这些）

| 目录 | 用途 |
|------|------|
| `packaging/offline/win/python-3.8.10-amd64.exe` | 64 位 Python 3.8.10 安装包 |
| `packaging/offline/win/wheels_win64` | 64 位业务依赖 wheels |
| `packaging/offline/win/requirements_win64.txt` | 64 位依赖清单 |
| `packaging/build_wheels_win` | PyInstaller 构建轮子 |
| `packaging/win_selfcheck.py` | 打包后依赖自检 |
