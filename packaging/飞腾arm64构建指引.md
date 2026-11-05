# 飞腾 D2000（arm64 架构）构建 .deb 安装包指引

适用：银河麒麟系统 + 飞腾 D2000/8 处理器（**arm64 架构**）。

> 重要：`.deb` 内是 PyInstaller 打出的**原生 arm64 可执行程序**，必须在
> **arm64 机器上构建**（不能拿 x86 电脑的产物改个名字）。本目录已内置
> arm64 全套离线依赖与构建轮子，全程断网可构建。

## 一键构建

```bash
cd workbench
bash install_kylin.sh          # ① 装业务依赖到 pylibs/（自动识别 arm64 + python 版本）
bash build_kylin.sh            # ② PyInstaller 打包绿色版 + 产物自检（12 项依赖）
bash build_deb.sh             # ③ 制作 arm64 安装包（再次自检后打包）
```

产物：`dist/专属工作台_1.4_arm64.deb`

安装：

```bash
sudo dpkg -i dist/专属工作台_1.4_arm64.deb
```

卸载：`sudo dpkg -r zhuan-shu-gong-zuo-tai`

## 构建强制自检（三重保障，杜绝"功能受限"）

构建与打 deb 全程自动执行**三道自检**，任何一道不过即报错中止：

| 阶段 | 检查 | 说明 |
|------|------|------|
| ① install_kylin.sh | 依赖导入自检 | 装完逐个 import numpy/matplotlib/fitz/OCR 等 |
| ② build_kylin.sh 打包后 | 目录自检 | 12 项依赖目录真实存在于产物 |
| ③ build_kylin.sh / build_deb.sh | **运行时自检** | 真实执行产物 `--check`，不仅 import 还验证功能（Pillow 绘图落盘、openpyxl 写出 xlsx、PyMuPDF 渲染、numpy 运算），杜绝"能导入但功能残废" |

**只要两步都输出：**
- `自检通过：全部 12 项核心依赖均已进入产物`
- `自检通过：全部 16 项依赖可用`

打包就是完整的，不会再有功能受限/依赖缺失问题。

> 提示：`bash build_deb.sh` 时若产物不完整，会先报"运行时自检失败/自检失败"
> 并中止——只需重新 `bash build_kylin.sh` 即可，绝不会打出残缺包。

## Python 版本

系统 python3 需为 **3.7 / 3.8 / 3.10** 之一（麒麟 V10 飞腾版一般预装）。
脚本自动匹配对应 arm64 离线包（`packaging/offline/linux/wheels{37,38,310}_aarch64`）。

## 常见问题

1. **提示缺少 tkinter**
   ```bash
   sudo apt install -y python3-tk   # 麒麟/适配源上为 python3-tkinter
   ```
2. **没有 dpkg-deb / dpkg**（极简系统）
   ```bash
   sudo apt install -y dpkg
   ```
3. **想改版本号**：改 `build_deb.sh` 顶部 `VERSION=1.4.2` 与 `config.py` 的 `APP_VERSION`。
4. **绿色版（免安装，拷贝即用）**：直接拷 `dist/专属工作台/` 整个目录到目标机，
   运行 `./专属工作台/专属工作台`。