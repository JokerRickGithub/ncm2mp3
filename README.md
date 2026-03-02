# NCM 音乐格式转换器

一个简单易用的网易云音乐 `.ncm` 格式解密工具，支持将加密的 NCM 文件转换为标准 MP3 或 FLAC 格式，并自动修复歌曲元数据（歌名、歌手、专辑封面等）。


## 功能特性
- **格式转换**：将 `.ncm` 文件解密为 `.mp3` 或 `.flac` 格式
- **元数据修复**：自动保留并写入歌曲名、歌手、专辑、封面图等信息
- **双模式支持**：提供命令行（CLI）和图形界面（GUI）两种使用方式
- **批量处理**：支持单文件、多文件、文件夹批量转换，支持递归扫描子文件夹
- **可选配置**：可选择是否删除原文件、自定义输出目录


## 安装与依赖
### 环境要求
- Python 3.7+

### 安装依赖
```bash
uv add pip install pycryptodome mutagen PyQt5
```

依赖说明：
- `pycryptodome`：用于 AES 解密
- `mutagen`：用于修复音频文件元数据
- `PyQt5`：用于图形界面（仅使用命令行可跳过）


## 使用方法
### 方式一：图形界面（推荐新手）
1. 运行 `gui.py` 启动程序：
   ```bash
   python gui.py
   ```
2. 将 `.ncm` 文件拖拽到窗口中
3. 可选择「输出目录」和「是否删除原文件」
4. 等待转换完成，日志会实时显示进度


### 方式二：命令行（适合批量/脚本调用）
#### 基本用法
```bash
# 转换单个文件
python main.py 歌曲.ncm

# 转换多个文件
python main.py 1.ncm 2.ncm 3.ncm

# 批量转换文件夹内所有 .ncm 文件
python main.py -d /path/to/ncm文件夹

# 递归扫描子文件夹
python main.py -d /path/to/ncm文件夹 -r

# 指定输出目录
python main.py 歌曲.ncm -o /path/to/output

# 转换成功后删除原文件
python main.py 歌曲.ncm -m
```

#### 完整参数说明
| 参数 | 说明 |
|------|------|
| `filenames` | 输入的 .ncm 文件路径（支持多个） |
| `-d, --directory` | 批量处理指定文件夹内的 .ncm 文件 |
| `-r, --recursive` | 递归扫描子文件夹（需配合 `-d` 使用） |
| `-o, --output` | 自定义输出目录（默认与原文件同目录） |
| `-m, --remove` | 转换成功后删除原 .ncm 文件 |
| `-v, --version` | 显示版本信息 |


### 方式三：双击运行（免命令行配置）
打开 `main.py`，修改文件底部的配置区域：
```python
# 在这里配置你的参数
INPUT_FOLDER = r"D:\ncm"       # 存放 .ncm 文件的文件夹
OUTPUT_FOLDER = r"D:\mp3"      # 转换后文件的输出文件夹
RECURSIVE_SCAN = False         # 是否扫描子文件夹
DELETE_ORIGINAL = False        # 转换成功后是否删除原文件
```
保存后直接双击 `main.py` 即可运行。


## 项目结构
```
ncm-converter/
├── ncmcrypt.py       # 核心解密逻辑（NCM 文件解析、RC4/AES 解密）
├── main.py           # 命令行入口 + 批量处理逻辑
├── gui.py            # PyQt5 图形界面
├── pyproject.toml    # 项目配置（可选）
└── README.md          # 本说明文档
```


## 许可证
本项目仅供学习交流使用，请勿用于商业用途。


## 常见问题
**Q: 转换后的文件没有封面/歌名？**  
A: 确保已安装 `mutagen` 库，且原 NCM 文件包含完整元数据。

**Q: 提示「Not netease protected file」？**  
A: 该文件不是标准的 NCM 加密格式，请确认文件来源。

**Q: 如何打包成 exe 给其他电脑用？**  
A: 使用 PyInstaller：
```bash
pyinstaller -F -w gui.py  # 打包图形界面（-w 隐藏控制台）
pyinstaller -F main.py     # 打包命令行版本
```