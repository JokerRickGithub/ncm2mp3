import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout,
                             QWidget, QPushButton, QTextEdit, QFileDialog, QCheckBox, QHBoxLayout)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# 直接复用你已经写好的解密核心类
from ncmcrypt import NeteaseCrypt

# ===================== 解密工作线程（防止界面卡死） =====================
class DecryptThread(QThread):
    # 信号：用于向界面发送日志、完成通知
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, file_paths, output_dir, delete_original=False):
        super().__init__()
        self.file_paths = file_paths  # 待处理的ncm文件路径列表
        self.output_dir = output_dir  # 输出目录
        self.delete_original = delete_original  # 是否删除原文件

    def run(self):
        """线程核心逻辑：批量处理文件"""
        total = len(self.file_paths)
        success = 0

        for index, file_path in enumerate(self.file_paths, 1):
            path = Path(file_path)
            filename = path.name

            # 校验文件
            if not path.exists():
                self.log_signal.emit(f"[{index}/{total}] ❌ 失败：文件不存在 {filename}")
                continue
            if path.suffix.lower() != '.ncm':
                self.log_signal.emit(f"[{index}/{total}] ⚠️ 跳过：非ncm文件 {filename}")
                continue

            # 开始解密
            try:
                self.log_signal.emit(f"[{index}/{total}] 正在处理：{filename}")
                with NeteaseCrypt(str(path)) as crypt:
                    # 确定输出目录
                    outdir = str(self.output_dir) if self.output_dir else ''
                    # 执行解密
                    crypt.dump(outdir)
                    # 修复元数据（歌名、歌手、封面）
                    crypt.fix_metadata()

                # 处理完成
                success += 1
                self.log_signal.emit(f"[{index}/{total}] ✅ 成功：{filename} -> {os.path.basename(crypt.dump_filepath())}")

                # 如果勾选了删除原文件
                if self.delete_original:
                    path.unlink()
                    self.log_signal.emit(f"   已删除原文件：{filename}")

            except Exception as e:
                self.log_signal.emit(f"[{index}/{total}] ❌ 失败：{filename}，错误原因：{str(e)}")

        # 全部处理完成
        self.log_signal.emit(f"\n--- 全部任务完成！成功 {success} 个，失败 {total-success} 个 ---")
        self.finished_signal.emit()

# ===================== 主GUI窗口 =====================
class NCMDumpWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 窗口基础配置
        self.setWindowTitle("NCM 音乐格式转换器")
        self.setGeometry(100, 100, 700, 500)
        # 全局变量
        self.output_dir = None  # 输出目录
        self.init_ui()

    def init_ui(self):
        """初始化界面布局"""
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 1. 拖拽区域（核心功能）
        self.drop_label = QLabel("👆 请将 .ncm 文件拖拽到此处 👆\n支持同时拖拽多个文件")
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setFixedHeight(150)
        self.drop_label.setStyleSheet("""
            QLabel {
                border: 3px dashed #bbbbbb;
                border-radius: 12px;
                font-size: 18px;
                color: #666666;
                background-color: #fafafa;
            }
        """)
        # 开启窗口拖拽接收
        self.setAcceptDrops(True)
        main_layout.addWidget(self.drop_label)

        # 2. 功能按钮区
        btn_layout = QHBoxLayout()

        # 选择输出目录按钮
        self.btn_select_dir = QPushButton("📂 选择输出目录")
        self.btn_select_dir.setFixedHeight(35)
        self.btn_select_dir.clicked.connect(self.select_output_dir)
        btn_layout.addWidget(self.btn_select_dir)

        # 删除原文件复选框
        self.delete_check = QCheckBox("转换成功后删除原.ncm文件")
        btn_layout.addWidget(self.delete_check)

        # 清空日志按钮
        self.btn_clear_log = QPushButton("清空日志")
        self.btn_clear_log.setFixedHeight(35)
        self.btn_clear_log.clicked.connect(lambda: self.log_text.clear())
        btn_layout.addWidget(self.btn_clear_log)

        main_layout.addLayout(btn_layout)

        # 3. 日志显示区
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("转换日志将在这里显示...")
        self.log_text.setStyleSheet("font-size: 13px;")
        main_layout.addWidget(self.log_text)

        # 绑定到主窗口
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    # ===================== 拖拽事件处理 =====================
    def dragEnterEvent(self, event):
        """拖拽进入窗口时触发"""
        # 只接收文件类型的拖拽
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            # 拖拽时高亮样式
            self.drop_label.setStyleSheet("""
                QLabel {
                    border: 3px solid #27ae60;
                    border-radius: 12px;
                    font-size: 18px;
                    color: #27ae60;
                    background-color: #eafaf1;
                }
            """)

    def dragLeaveEvent(self, event):
        """拖拽离开窗口时触发，恢复默认样式"""
        self._reset_drop_style()

    def dropEvent(self, event):
        """松开拖拽的文件时触发，开始处理"""
        # 恢复默认样式
        self._reset_drop_style()
        # 获取拖拽的所有文件路径
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        # 过滤出.ncm文件
        ncm_files = [f for f in files if f.lower().endswith('.ncm')]

        if not ncm_files:
            self.log("⚠️ 未识别到 .ncm 格式的文件，请重新拖拽")
            return

        # 开始解密
        self.log(f"\n--- 已添加 {len(ncm_files)} 个NCM文件，开始转换 ---")
        self.start_decrypt(ncm_files)

    def _reset_drop_style(self):
        """重置拖拽区域的样式"""
        self.drop_label.setStyleSheet("""
            QLabel {
                border: 3px dashed #bbbbbb;
                border-radius: 12px;
                font-size: 18px;
                color: #666666;
                background-color: #fafafa;
            }
        """)

    # ===================== 核心功能函数 =====================
    def select_output_dir(self):
        """选择输出目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择转换后文件的输出文件夹")
        if dir_path:
            self.output_dir = Path(dir_path)
            self.btn_select_dir.setText(f"📂 输出目录：{self.output_dir.name}")
            self.log(f"✅ 已设置输出目录：{str(self.output_dir)}")

    def log(self, message):
        """向日志框添加内容"""
        self.log_text.append(message)
        # 自动滚动到最底部
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def start_decrypt(self, file_paths):
        """启动解密线程，防止界面卡死"""
        # 创建线程
        self.decrypt_thread = DecryptThread(
            file_paths=file_paths,
            output_dir=self.output_dir,
            delete_original=self.delete_check.isChecked()
        )
        # 绑定信号槽
        self.decrypt_thread.log_signal.connect(self.log)
        # 启动线程
        self.decrypt_thread.start()

# ===================== 程序入口 =====================
if __name__ == '__main__':
    # 解决Windows下PyQt5的图标兼容问题
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ncm_converter")

    # 启动应用
    app = QApplication(sys.argv)
    window = NCMDumpWindow()
    window.show()
    sys.exit(app.exec_())