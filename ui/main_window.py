#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
主窗口界面
"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QFileDialog, QTreeWidget, QTreeWidgetItem,
                             QLabel, QMessageBox, QSplitter, QTableWidget,
                             QTableWidgetItem, QHeaderView, QAbstractItemView,
                             QFrame, QSizePolicy, QDialog, QDialogButtonBox,
                             QListWidget, QListWidgetItem, QScrollArea, QComboBox)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor
import os
from core.file_manager import FileManager
from core.classifier import Classifier


class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        self.file_manager = FileManager()
        self.classifier = Classifier()
        self.uploaded_files = []  # 存储上传的文件路径
        self.classify_method = "llm"  # 默认使用LLM分类方法
        self.init_ui()
        # 启用拖拽功能
        self.setAcceptDrops(True)
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("AI文件分类工具")
        self.setGeometry(100, 100, 1400, 900)
        
        # 应用现代化样式
        self.apply_modern_style()
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 顶部工具栏容器（带背景）
        toolbar_container = QFrame()
        toolbar_container.setObjectName("toolbarContainer")
        toolbar_container.setFixedHeight(80)
        toolbar_layout = QHBoxLayout(toolbar_container)
        toolbar_layout.setContentsMargins(20, 15, 20, 15)
        toolbar_layout.setSpacing(15)
        
        # 上传文件按钮
        self.upload_btn = QPushButton("📁 上传文件")
        self.upload_btn.setObjectName("primaryButton")
        self.upload_btn.setFixedHeight(45)
        self.upload_btn.setMinimumWidth(150)
        self.upload_btn.clicked.connect(self.upload_files)
        toolbar_layout.addWidget(self.upload_btn)
        
        # 分类方法选择器
        method_label = QLabel("分类方法:")
        method_label.setObjectName("methodLabel")
        toolbar_layout.addWidget(method_label)
        
        self.method_combo = QComboBox()
        self.method_combo.addItem("🤖 LLM逐级分类", "llm")
        self.method_combo.addItem("🔍 向量检索分类", "embedding")
        self.method_combo.addItem("🎯 全文LLM分类", "fulltext_llm")
        self.method_combo.setFixedHeight(45)
        self.method_combo.setMinimumWidth(180)
        self.method_combo.currentIndexChanged.connect(self.on_method_changed)
        toolbar_layout.addWidget(self.method_combo)
        
        # 分类按钮
        self.classify_btn = QPushButton("🚀 开始分类")
        self.classify_btn.setObjectName("successButton")
        self.classify_btn.setFixedHeight(45)
        self.classify_btn.setMinimumWidth(150)
        self.classify_btn.clicked.connect(self.classify_files)
        self.classify_btn.setEnabled(False)
        toolbar_layout.addWidget(self.classify_btn)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("🔄 刷新目录")
        self.refresh_btn.setObjectName("secondaryButton")
        self.refresh_btn.setFixedHeight(45)
        self.refresh_btn.setMinimumWidth(120)
        self.refresh_btn.clicked.connect(self.refresh_tree)
        toolbar_layout.addWidget(self.refresh_btn)
        
        # 清空分类目录按钮
        self.clear_btn = QPushButton("🗑️ 清空分类")
        self.clear_btn.setObjectName("dangerButton")
        self.clear_btn.setFixedHeight(45)
        self.clear_btn.setMinimumWidth(120)
        self.clear_btn.clicked.connect(self.clear_classification)
        toolbar_layout.addWidget(self.clear_btn)
        
        # 查看完整分类树按钮
        self.view_categories_btn = QPushButton("🌳 查看分类树")
        self.view_categories_btn.setObjectName("secondaryButton")
        self.view_categories_btn.setFixedHeight(45)
        self.view_categories_btn.setMinimumWidth(130)
        self.view_categories_btn.clicked.connect(self.show_categories_tree)
        toolbar_layout.addWidget(self.view_categories_btn)
        
        toolbar_layout.addStretch()
        
        # 文件计数标签（现代化样式）
        count_container = QFrame()
        count_container.setObjectName("countContainer")
        count_layout = QVBoxLayout(count_container)
        count_layout.setContentsMargins(20, 10, 20, 10)
        self.file_count_label = QLabel("已上传文件: 0/100")
        self.file_count_label.setObjectName("countLabel")
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self.file_count_label.setFont(font)
        count_layout.addWidget(self.file_count_label)
        toolbar_layout.addWidget(count_container)
        
        main_layout.addWidget(toolbar_container)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # 左侧：分类目录树容器
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        tree_label = QLabel("📂 分类目录")
        tree_label.setObjectName("sectionLabel")
        tree_label.setFixedHeight(40)
        tree_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(tree_label)
        
        self.category_tree = QTreeWidget()
        self.category_tree.setObjectName("categoryTree")
        self.category_tree.setHeaderHidden(True)
        self.category_tree.itemDoubleClicked.connect(self.on_tree_item_double_clicked)
        self.category_tree.setAlternatingRowColors(True)
        self.category_tree.setIndentation(15)
        left_layout.addWidget(self.category_tree)
        
        splitter.addWidget(left_container)
        
        # 右侧：文件列表容器
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        table_label = QLabel("📋 文件列表")
        table_label.setObjectName("sectionLabel")
        table_label.setFixedHeight(40)
        table_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(table_label)
        
        self.file_table = QTableWidget()
        self.file_table.setObjectName("fileTable")
        self.file_table.setColumnCount(5)
        self.file_table.setHorizontalHeaderLabels(["文件名", "原路径", "分类", "相似度", "操作"])
        # 设置列宽
        self.file_table.setColumnWidth(0, 200)  # 文件名
        self.file_table.setColumnWidth(1, 300)  # 原路径
        self.file_table.setColumnWidth(2, 200)  # 分类
        self.file_table.setColumnWidth(3, 80)   # 相似度
        self.file_table.horizontalHeader().setStretchLastSection(True)  # 操作列自动拉伸
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setShowGrid(False)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setSelectionMode(QAbstractItemView.SingleSelection)
        right_layout.addWidget(self.file_table)
        
        splitter.addWidget(right_container)
        
        # 设置分割器比例
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([350, 950])
        
        main_layout.addWidget(splitter)
        
        # 状态栏
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #f5f5f5;
                border-top: 1px solid #e0e0e0;
                padding: 5px;
            }
        """)
        self.statusBar().showMessage("就绪")
        
        # 初始化分类树
        self.refresh_tree()
    
    def apply_modern_style(self):
        """应用现代化样式表"""
        self.setStyleSheet("""
            /* 主窗口背景 */
            QMainWindow {
                background-color: #f8f9fa;
            }
            
            /* 工具栏容器 */
            #toolbarContainer {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f0f0f0);
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
            
            /* 主要按钮样式 */
            #primaryButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a90e2, stop:1 #357abd);
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 20px;
            }
            #primaryButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5aa0f2, stop:1 #4080cd);
            }
            #primaryButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #357abd, stop:1 #2a5a9d);
            }
            
            /* 成功按钮样式 */
            #successButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #52c41a, stop:1 #389e0d);
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 20px;
            }
            #successButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #73d13d, stop:1 #52c41a);
            }
            #successButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #389e0d, stop:1 #237804);
            }
            #successButton:disabled {
                background: #d9d9d9;
                color: #999999;
            }
            
            /* 次要按钮样式 */
            #secondaryButton {
                background: #ffffff;
                color: #595959;
                border: 2px solid #d9d9d9;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 20px;
            }
            #secondaryButton:hover {
                background: #f5f5f5;
                border-color: #40a9ff;
                color: #40a9ff;
            }
            #secondaryButton:pressed {
                background: #e6f7ff;
                border-color: #1890ff;
            }
            
            /* 危险按钮样式（用于删除/清空操作） */
            #dangerButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff4d4f, stop:1 #cf1322);
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 20px;
            }
            #dangerButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff7875, stop:1 #ff4d4f);
            }
            #dangerButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #cf1322, stop:1 #a8071a);
            }
            
            /* 计数容器 */
            #countContainer {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e6f7ff, stop:1 #bae7ff);
                border-radius: 8px;
                border: 1px solid #91d5ff;
            }
            #countLabel {
                color: #0050b3;
            }
            
            /* 区域标签 */
            #sectionLabel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fafafa, stop:1 #f0f0f0);
                color: #262626;
                font-weight: bold;
                font-size: 14px;
                border-bottom: 2px solid #e0e0e0;
            }
            
            /* 分类树样式 */
            #categoryTree {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-top: none;
                border-radius: 0 0 8px 8px;
                font-size: 13px;
                padding: 10px;
            }
            #categoryTree::item {
                padding: 8px 12px;
                border-radius: 6px;
                margin: 2px 0px;
            }
            #categoryTree::item:hover {
                background-color: #e6f7ff;
                color: #1890ff;
            }
            #categoryTree::item:selected {
                background-color: #1890ff;
                color: white;
            }
            #categoryTree::branch {
                background: transparent;
            }
            #categoryTree::branch:has-siblings:!adjoins-item {
                border-image: none;
                border: none;
            }
            #categoryTree::branch:has-siblings:adjoins-item {
                border-image: none;
                border: none;
            }
            #categoryTree::branch:!has-children:!has-siblings:adjoins-item {
                border-image: none;
                border: none;
            }
            #categoryTree::branch:has-children:!closed:adjoins-item {
                border-image: none;
                border: none;
            }
            #categoryTree::branch:closed:has-children:has-siblings {
                border-image: none;
                border: none;
            }
            
            /* 文件表格样式 */
            #fileTable {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-top: none;
                border-radius: 0 0 8px 8px;
                gridline-color: transparent;
                font-size: 13px;
            }
            #fileTable::item {
                padding: 10px;
                border: none;
            }
            #fileTable::item:selected {
                background-color: #e6f7ff;
                color: #1890ff;
            }
            #fileTable::item:hover {
                background-color: #f0f9ff;
            }
            QHeaderView::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fafafa, stop:1 #f0f0f0);
                color: #262626;
                padding: 12px;
                border: none;
                border-bottom: 2px solid #e0e0e0;
                border-right: 1px solid #e0e0e0;
                font-weight: bold;
                font-size: 13px;
            }
            QHeaderView::section:first {
                border-left: none;
            }
            QHeaderView::section:last {
                border-right: none;
            }
            
            /* 表格中的按钮 - 基础样式 */
            QPushButton {
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 500;
                min-width: 60px;
            }
            
            /* 打开按钮样式 */
            #openButton {
                background-color: #1890ff;
            }
            #openButton:hover {
                background-color: #40a9ff;
            }
            #openButton:pressed {
                background-color: #096dd9;
            }
            
            /* 删除按钮特殊样式 */
            #deleteButton {
                background-color: #ff4d4f;
            }
            #deleteButton:hover {
                background-color: #ff7875;
            }
            #deleteButton:pressed {
                background-color: #cf1322;
            }
            
            /* 分割器样式 */
            QSplitter::handle {
                background-color: #e0e0e0;
                width: 3px;
            }
            QSplitter::handle:hover {
                background-color: #1890ff;
            }
        """)
        
    
    def upload_files(self):
        """上传文件（通过按钮）"""
        dialog = UploadDialog(self.uploaded_files, self)
        if dialog.exec_() == QDialog.Accepted:
            new_files = dialog.get_selected_files()
            if new_files:
                self.add_files(new_files)
    
    def add_files(self, files):
        """
        添加文件（通用方法，供拖拽和按钮上传使用）
        
        Args:
            files: 文件路径列表
        """
        if not files:
            return
        
        # 检查文件数量限制
        remaining_slots = 100 - len(self.uploaded_files)
        if len(files) > remaining_slots:
            QMessageBox.warning(
                self,
                "文件数量超限",
                f"最多只能上传100个文件。\n当前已上传: {len(self.uploaded_files)}\n剩余可上传: {remaining_slots}"
            )
            files = files[:remaining_slots]
        
        # 添加文件
        new_files = []
        for file_path in files:
            if file_path not in self.uploaded_files:
                self.uploaded_files.append(file_path)
                new_files.append(file_path)
        
        if new_files:
            self.update_file_count()
            self.classify_btn.setEnabled(len(self.uploaded_files) > 0)
            self.statusBar().showMessage(f"成功添加 {len(new_files)} 个文件")
            QMessageBox.information(
                self,
                "上传成功",
                f"成功添加 {len(new_files)} 个文件"
            )
        else:
            QMessageBox.warning(
                self,
                "提示",
                "所选文件已存在或没有新文件被添加"
            )
    
    def on_method_changed(self, index):
        """分类方法改变时的回调"""
        self.classify_method = self.method_combo.currentData()
    
    def classify_files(self):
        """分类文件"""
        if not self.uploaded_files:
            QMessageBox.warning(self, "提示", "请先上传文件")
            return
        
        # 获取当前选择的分类方法
        method_names = {
            "llm": "LLM逐级分类",
            "embedding": "向量检索分类",
            "fulltext_llm": "全文LLM分类"
        }
        method_name = method_names.get(self.classify_method, "未知方法")
        
        # 显示进度提示
        reply = QMessageBox.question(
            self,
            "确认分类",
            f"将对 {len(self.uploaded_files)} 个文件进行分类\n分类方法: {method_name}\n是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            self.statusBar().showMessage(f"正在分类文件（{method_name}）...")
            self.classify_btn.setEnabled(False)
            
            # 根据选择的分类方法调用不同的分类函数
            results = {}
            if self.classify_method == "fulltext_llm":
                # 使用全文LLM分类方法
                for file_path in self.uploaded_files:
                    result = self.classifier.classify_with_fulltext_llm(file_path)
                    if result:
                        # result是dict格式: {'category_path': '...', 'reason': '...', 'similarity_score': ...}
                        results[file_path] = result['category_path']
                        # 如果有相似度分数，也保存
                        if result.get('similarity_score') is not None:
                            results[file_path] = (result['category_path'], result['similarity_score'])
                    else:
                        results[file_path] = "其他/未分类"
            else:
                # 使用原有的分类方法
                use_embedding = (self.classify_method == "embedding")
                results = self.classifier.classify_files(self.uploaded_files, use_embedding=use_embedding)
            
            # 保存分类结果到文件管理器
            for file_path, result in results.items():
                # result可能是字符串（LLM分类）或元组(路径, 分数)（向量检索分类）
                self.file_manager.add_file(file_path, result)
            
            self.statusBar().showMessage("分类完成")
            QMessageBox.information(
                self,
                "分类完成",
                f"成功分类 {len(results)} 个文件\n使用方法: {method_name}"
            )
            
            # 刷新界面
            self.refresh_tree()
            self.refresh_file_table()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "分类错误",
                f"分类过程中发生错误：\n{str(e)}"
            )
            self.statusBar().showMessage("分类失败")
        finally:
            self.classify_btn.setEnabled(True)
    
    def clear_classification(self):
        """清空分类目录和已上传文件列表"""
        # 获取当前文件数量
        file_count = self.file_manager.get_file_count()
        uploaded_count = len(self.uploaded_files)
        
        if file_count == 0 and uploaded_count == 0:
            QMessageBox.information(
                self,
                "提示",
                "分类目录和已上传文件列表都是空的，无需清空"
            )
            return
        
        # 确认对话框
        message = "确定要清空所有分类目录和已上传文件列表吗？\n\n"
        if file_count > 0:
            message += f"• 将删除 {file_count} 个已分类文件的记录\n"
        if uploaded_count > 0:
            message += f"• 将清空 {uploaded_count} 个已上传文件\n"
        message += "\n此操作不可恢复！"
        
        reply = QMessageBox.question(
            self,
            "确认清空",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No  # 默认选择"否"
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            # 清空文件管理器中的所有记录
            self.file_manager.clear_all()
            
            # 清空已上传文件列表
            self.uploaded_files.clear()
            
            # 更新文件计数标签
            self.update_file_count()
            
            # 更新分类按钮状态
            self.classify_btn.setEnabled(False)
            
            # 刷新界面
            self.refresh_tree()
            self.refresh_file_table()
            
            # 显示成功消息
            self.statusBar().showMessage("分类目录和已上传文件列表已清空")
            QMessageBox.information(
                self,
                "清空成功",
                f"已成功清空：\n• 删除了 {file_count} 个文件的分类记录\n• 清空了 {uploaded_count} 个已上传文件"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "清空失败",
                f"清空时发生错误：\n{str(e)}"
            )
            self.statusBar().showMessage("清空失败")
    
    def refresh_tree(self):
        """刷新分类目录树"""
        self.category_tree.clear()
        
        # 获取所有分类目录
        categories = self.file_manager.get_all_categories()
        
        # 构建树结构
        root_items = {}
        
        for category_path in categories:
            parts = category_path.split(os.sep)
            current_path = ""
            parent_item = None
            
            for part in parts:
                if current_path:
                    current_path = os.path.join(current_path, part)
                else:
                    current_path = part
                
                if current_path not in root_items:
                    item = QTreeWidgetItem([part])
                    if parent_item:
                        parent_item.addChild(item)
                    else:
                        self.category_tree.addTopLevelItem(item)
                    root_items[current_path] = item
                else:
                    item = root_items[current_path]
                
                parent_item = item
        
        # 展开所有节点
        self.category_tree.expandAll()
        
        self.statusBar().showMessage("目录已刷新")
    
    def on_tree_item_double_clicked(self, item, column):
        """双击树节点时显示该分类下的文件"""
        # 获取完整路径
        path_parts = []
        current = item
        while current:
            path_parts.insert(0, current.text(0))
            current = current.parent()
        
        category_path = os.sep.join(path_parts)
        self.show_files_in_category(category_path)
    
    def show_files_in_category(self, category_path):
        """显示指定分类下的文件"""
        files = self.file_manager.get_files_in_category(category_path)
        self.file_table.setRowCount(len(files))
        
        for row, file_info in enumerate(files):
            # 文件名
            file_name = os.path.basename(file_info['original_path'])
            self.file_table.setItem(row, 0, QTableWidgetItem(file_name))
            
            # 原路径
            self.file_table.setItem(row, 1, QTableWidgetItem(file_info['original_path']))
            
            # 分类
            self.file_table.setItem(row, 2, QTableWidgetItem(file_info['category']))
            
            # 相似度分数（如果有）
            similarity_score = file_info.get('similarity_score')
            if similarity_score is not None:
                score_text = f"{similarity_score:.2%}"  # 显示为百分比，保留2位小数
                score_item = QTableWidgetItem(score_text)
                # 根据分数设置颜色：高分绿色，中分黄色，低分红色
                if similarity_score >= 0.7:
                    score_item.setForeground(QColor(52, 196, 26))  # 绿色
                elif similarity_score >= 0.5:
                    score_item.setForeground(QColor(250, 173, 20))  # 黄色
                else:
                    score_item.setForeground(QColor(255, 77, 79))  # 红色
                self.file_table.setItem(row, 3, score_item)
            else:
                self.file_table.setItem(row, 3, QTableWidgetItem("-"))
            
            # 操作按钮
            open_btn = QPushButton("打开")
            open_btn.setObjectName("openButton")
            open_btn.clicked.connect(
                lambda checked, path=file_info['original_path']: self.open_file(path)
            )
            delete_btn = QPushButton("删除")
            delete_btn.setObjectName("deleteButton")
            delete_btn.clicked.connect(
                lambda checked, path=file_info['original_path']: self.delete_file(path)
            )
            
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.addWidget(open_btn)
            btn_layout.addWidget(delete_btn)
            btn_layout.setContentsMargins(2, 2, 2, 2)
            
            self.file_table.setCellWidget(row, 4, btn_widget)
        
        self.statusBar().showMessage(f"显示分类 '{category_path}' 下的 {len(files)} 个文件")
    
    def refresh_file_table(self):
        """刷新文件列表（显示所有文件）"""
        all_files = self.file_manager.get_all_files()
        self.file_table.setRowCount(len(all_files))
        
        for row, file_info in enumerate(all_files):
            file_name = os.path.basename(file_info['original_path'])
            self.file_table.setItem(row, 0, QTableWidgetItem(file_name))
            self.file_table.setItem(row, 1, QTableWidgetItem(file_info['original_path']))
            self.file_table.setItem(row, 2, QTableWidgetItem(file_info['category']))
            
            # 相似度分数（如果有）
            similarity_score = file_info.get('similarity_score')
            if similarity_score is not None:
                score_text = f"{similarity_score:.2%}"  # 显示为百分比，保留2位小数
                score_item = QTableWidgetItem(score_text)
                # 根据分数设置颜色：高分绿色，中分黄色，低分红色
                if similarity_score >= 0.7:
                    score_item.setForeground(QColor(52, 196, 26))  # 绿色
                elif similarity_score >= 0.5:
                    score_item.setForeground(QColor(250, 173, 20))  # 黄色
                else:
                    score_item.setForeground(QColor(255, 77, 79))  # 红色
                self.file_table.setItem(row, 3, score_item)
            else:
                self.file_table.setItem(row, 3, QTableWidgetItem("-"))
            
            open_btn = QPushButton("打开")
            open_btn.setObjectName("openButton")
            open_btn.clicked.connect(
                lambda checked, path=file_info['original_path']: self.open_file(path)
            )
            delete_btn = QPushButton("删除")
            delete_btn.setObjectName("deleteButton")
            delete_btn.clicked.connect(
                lambda checked, path=file_info['original_path']: self.delete_file(path)
            )
            
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setSpacing(8)
            btn_layout.addWidget(open_btn)
            btn_layout.addWidget(delete_btn)
            btn_layout.setContentsMargins(10, 5, 10, 5)
            btn_layout.setAlignment(Qt.AlignCenter)
            
            self.file_table.setCellWidget(row, 4, btn_widget)
    
    def open_file(self, file_path):
        """打开文件"""
        import subprocess
        import platform
        
        try:
            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.call(['open', file_path])
            else:  # Linux
                subprocess.call(['xdg-open', file_path])
        except Exception as e:
            QMessageBox.warning(
                self,
                "打开失败",
                f"无法打开文件：\n{str(e)}"
            )
    
    def delete_file(self, file_path):
        """删除文件记录"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除文件记录吗？\n{os.path.basename(file_path)}",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.file_manager.remove_file(file_path)
            if file_path in self.uploaded_files:
                self.uploaded_files.remove(file_path)
            
            self.update_file_count()
            self.refresh_tree()
            self.refresh_file_table()
            self.statusBar().showMessage("文件已删除")
    
    def update_file_count(self):
        """更新文件计数标签"""
        count = len(self.uploaded_files)
        self.file_count_label.setText(f"已上传文件: {count}/100")
    
    def show_categories_tree(self):
        """显示完整的分类目录树对话框"""
        dialog = CategoriesTreeDialog(self.classifier, self)
        dialog.exec_()
    
    def closeEvent(self, event):
        """窗口关闭事件，确保关闭数据库连接"""
        if hasattr(self, 'classifier') and self.classifier:
            self.classifier.close()
        event.accept()


class CategoriesTreeDialog(QDialog):
    """分类目录树对话框"""
    
    def __init__(self, classifier, parent=None):
        super().__init__(parent)
        self.classifier = classifier
        self.setWindowTitle("完整分类目录树")
        self.setGeometry(200, 200, 900, 700)
        self.apply_dialog_style()
        self.init_ui()
    
    def apply_dialog_style(self):
        """应用对话框样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QLabel {
                color: #262626;
            }
            QTreeWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 6px;
                border-radius: 4px;
            }
            QTreeWidget::item:hover {
                background-color: #e6f7ff;
                color: #1890ff;
            }
            QTreeWidget::item:selected {
                background-color: #1890ff;
                color: white;
            }
            QHeaderView::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fafafa, stop:1 #f0f0f0);
                color: #262626;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #e0e0e0;
                font-weight: bold;
                font-size: 13px;
            }
            QDialogButtonBox QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: 500;
                min-width: 80px;
            }
            QDialogButtonBox QPushButton:hover {
                background-color: #40a9ff;
            }
            QDialogButtonBox QPushButton:pressed {
                background-color: #096dd9;
            }
        """)
    
    def init_ui(self):
        """初始化对话框界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("📚 数据库中的所有分类")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 统计信息
        categories_data = self.classifier.get_all_categories()
        if not categories_data:
            # 如果没有分类数据，显示提示信息
            no_data_label = QLabel("⚠️ 未加载到分类数据，请检查数据库连接")
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet("color: #ff4d4f; font-size: 13px;")
            layout.addWidget(no_data_label)
        else:
            total_count = self._count_categories(categories_data)
            info_label = QLabel(f"共 {total_count['level1']} 个一级分类, {total_count['level2']} 个二级分类, {total_count['level3']} 个三级分类")
            info_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(info_label)
            
            # 分类树
            self.categories_tree = QTreeWidget()
            self.categories_tree.setHeaderLabels(["分类名称", "分类代码"])
            self.categories_tree.setAlternatingRowColors(True)
            self.categories_tree.setIndentation(20)
            self.categories_tree.header().setStretchLastSection(False)
            self.categories_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
            self.categories_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            layout.addWidget(self.categories_tree)
            
            # 加载分类树
            self.load_categories_tree(categories_data)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)
    
    def _count_categories(self, categories_data):
        """统计分类数量"""
        count = {'level1': 0, 'level2': 0, 'level3': 0}
        
        for level1_code, level1_cat in categories_data.items():
            count['level1'] += 1
            for level2_code, level2_cat in level1_cat['children'].items():
                count['level2'] += 1
                for level3_code, level3_cat in level2_cat['children'].items():
                    count['level3'] += 1
        
        return count
    
    def load_categories_tree(self, categories_data):
        """加载分类树数据"""
        self.categories_tree.clear()
        
        for level1_code, level1_cat in sorted(categories_data.items()):
            # 一级分类
            level1_item = QTreeWidgetItem([
                level1_cat['name'],
                level1_code
            ])
            level1_item.setExpanded(True)
            self.categories_tree.addTopLevelItem(level1_item)
            
            # 二级分类
            for level2_code, level2_cat in sorted(level1_cat['children'].items()):
                level2_item = QTreeWidgetItem([
                    level2_cat['name'],
                    level2_code
                ])
                level2_item.setExpanded(True)
                level1_item.addChild(level2_item)
                
                # 三级分类
                for level3_code, level3_cat in sorted(level2_cat['children'].items()):
                    level3_item = QTreeWidgetItem([
                        level3_cat['name'],
                        level3_code
                    ])
                    level2_item.addChild(level3_item)
        
        # 展开所有节点
        self.categories_tree.expandAll()


class UploadDialog(QDialog):
    """文件上传对话框"""
    
    def __init__(self, existing_files, parent=None):
        super().__init__(parent)
        self.existing_files = existing_files
        self.selected_files = []
        self.setWindowTitle("上传文件")
        self.setGeometry(300, 300, 700, 600)
        self.apply_upload_style()
        self.init_ui()
        # 启用拖拽功能
        self.setAcceptDrops(True)
    
    def apply_upload_style(self):
        """应用上传对话框样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QLabel {
                color: #262626;
            }
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 500;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
            QPushButton:pressed {
                background-color: #096dd9;
            }
            QPushButton#selectButton {
                background-color: #52c41a;
            }
            QPushButton#selectButton:hover {
                background-color: #73d13d;
            }
            QPushButton#removeButton {
                background-color: #ff4d4f;
            }
            QPushButton#removeButton:hover {
                background-color: #ff7875;
            }
            QFrame#dragArea {
                background-color: #fafafa;
                border: 2px dashed #d9d9d9;
                border-radius: 12px;
            }
        """)
    
    def init_ui(self):
        """初始化对话框界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 标题
        title_label = QLabel("📁 上传文件")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 拖拽区域
        self.drag_area = QFrame()
        self.drag_area.setObjectName("dragArea")
        self.drag_area.setAcceptDrops(True)
        self.drag_area.setFixedHeight(200)
        drag_layout = QVBoxLayout(self.drag_area)
        drag_layout.setAlignment(Qt.AlignCenter)
        
        drag_icon = QLabel("📤")
        drag_icon.setAlignment(Qt.AlignCenter)
        drag_font = QFont()
        drag_font.setPointSize(48)
        drag_icon.setFont(drag_font)
        drag_layout.addWidget(drag_icon)
        
        drag_text = QLabel("拖拽文件到此处，或点击下方按钮选择文件")
        drag_text.setAlignment(Qt.AlignCenter)
        drag_text_font = QFont()
        drag_text_font.setPointSize(12)
        drag_text.setFont(drag_text_font)
        drag_layout.addWidget(drag_text)
        
        hint_text = QLabel("支持多文件上传，最多100个文件")
        hint_text.setAlignment(Qt.AlignCenter)
        hint_text.setStyleSheet("color: #8c8c8c; font-size: 11px;")
        drag_layout.addWidget(hint_text)
        
        layout.addWidget(self.drag_area)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        select_btn = QPushButton("选择文件")
        select_btn.setObjectName("selectButton")
        select_btn.clicked.connect(self.select_files)
        button_layout.addWidget(select_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 文件列表
        list_label = QLabel("已选择的文件：")
        list_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(list_label)
        
        self.file_list = QListWidget()
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background-color: #e6f7ff;
            }
            QListWidget::item:selected {
                background-color: #1890ff;
                color: white;
            }
        """)
        layout.addWidget(self.file_list)
        
        # 统计信息
        self.count_label = QLabel("已选择: 0/100 个文件")
        self.count_label.setAlignment(Qt.AlignCenter)
        self.count_label.setStyleSheet("font-size: 12px; color: #595959;")
        layout.addWidget(self.count_label)
        
        # 操作按钮
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        
        remove_btn = QPushButton("移除选中")
        remove_btn.setObjectName("removeButton")
        remove_btn.clicked.connect(self.remove_selected)
        action_layout.addWidget(remove_btn)
        
        action_layout.addStretch()
        
        clear_btn = QPushButton("清空列表")
        clear_btn.clicked.connect(self.clear_files)
        action_layout.addWidget(clear_btn)
        
        layout.addLayout(action_layout)
        
        # 对话框按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            has_files = False
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if os.path.isfile(file_path):
                    has_files = True
                    break
            
            if has_files:
                event.acceptProposedAction()
                self.drag_area.setStyleSheet("""
                    QFrame#dragArea {
                        background-color: #e6f7ff;
                        border: 2px dashed #1890ff;
                        border-radius: 12px;
                    }
                """)
            else:
                event.ignore()
        else:
            event.ignore()
    
    def dragLeaveEvent(self, event):
        """拖拽离开事件"""
        self.drag_area.setStyleSheet("""
            QFrame#dragArea {
                background-color: #fafafa;
                border: 2px dashed #d9d9d9;
                border-radius: 12px;
            }
        """)
        event.accept()
    
    def dropEvent(self, event):
        """拖拽放下事件"""
        files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                files.append(file_path)
        
        if files:
            self.add_files(files)
        
        self.drag_area.setStyleSheet("""
            QFrame#dragArea {
                background-color: #fafafa;
                border: 2px dashed #d9d9d9;
                border-radius: 12px;
            }
        """)
        event.acceptProposedAction()
    
    def select_files(self):
        """选择文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择要上传的文件",
            "",
            "所有文件 (*.*)"
        )
        
        if files:
            self.add_files(files)
    
    def add_files(self, files):
        """添加文件到列表"""
        remaining_slots = 100 - len(self.selected_files)
        
        if len(files) > remaining_slots:
            QMessageBox.warning(
                self,
                "文件数量超限",
                f"最多只能上传100个文件。\n当前已选择: {len(self.selected_files)}\n剩余可添加: {remaining_slots}"
            )
            files = files[:remaining_slots]
        
        new_count = 0
        for file_path in files:
            # 检查是否已存在（在已选择列表和已有文件列表中）
            if file_path not in self.selected_files and file_path not in self.existing_files:
                self.selected_files.append(file_path)
                item = QListWidgetItem(os.path.basename(file_path))
                item.setData(Qt.UserRole, file_path)
                item.setToolTip(file_path)
                self.file_list.addItem(item)
                new_count += 1
        
        self.update_count()
        
        if new_count > 0:
            QMessageBox.information(
                self,
                "添加成功",
                f"成功添加 {new_count} 个文件"
            )
        elif files:
            QMessageBox.warning(
                self,
                "提示",
                "所选文件已存在或已达到上限"
            )
    
    def remove_selected(self):
        """移除选中的文件"""
        current_item = self.file_list.currentItem()
        if current_item:
            file_path = current_item.data(Qt.UserRole)
            if file_path in self.selected_files:
                self.selected_files.remove(file_path)
            self.file_list.takeItem(self.file_list.row(current_item))
            self.update_count()
    
    def clear_files(self):
        """清空文件列表"""
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有已选择的文件吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.selected_files.clear()
            self.file_list.clear()
            self.update_count()
    
    def update_count(self):
        """更新文件计数"""
        count = len(self.selected_files)
        self.count_label.setText(f"已选择: {count}/100 个文件")
    
    def get_selected_files(self):
        """获取已选择的文件列表"""
        return self.selected_files.copy()

