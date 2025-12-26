#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI文件分类工具 - 主程序入口
"""

import sys
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("AI文件分类工具")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

