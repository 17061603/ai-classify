#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件管理器 - 管理分类后的文件
"""

import os
import json
from pathlib import Path


class FileManager:
    """文件管理器类"""
    
    def __init__(self, data_dir="data"):
        """
        初始化文件管理器
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.db_file = self.data_dir / "files_db.json"
        self.files_db = self._load_database()
    
    def _load_database(self):
        """加载文件数据库"""
        if self.db_file.exists():
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载数据库失败: {e}")
                return {}
        return {}
    
    def _save_database(self):
        """保存文件数据库"""
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.files_db, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存数据库失败: {e}")
    
    def add_file(self, file_path, category_path, similarity_score=None):
        """
        添加文件记录
        
        Args:
            file_path: 文件原始路径
            category_path: 分类路径（可以是字符串或元组(路径, 分数)）
            similarity_score: 相似度分数（可选，如果category_path是元组则从此参数获取）
        """
        file_path = str(file_path)
        
        # 处理category_path可能是元组的情况 (路径, 分数)
        if isinstance(category_path, tuple):
            actual_path, score = category_path
            similarity_score = score
            category_path = actual_path
        
        file_info = {
            'original_path': file_path,
            'category': category_path,
            'file_name': os.path.basename(file_path)
        }
        
        # 如果有相似度分数，保存它
        if similarity_score is not None:
            file_info['similarity_score'] = similarity_score
        
        self.files_db[file_path] = file_info
        self._save_database()
    
    def remove_file(self, file_path):
        """
        删除文件记录
        
        Args:
            file_path: 文件路径
        """
        file_path = str(file_path)
        if file_path in self.files_db:
            del self.files_db[file_path]
            self._save_database()
    
    def get_files_in_category(self, category_path):
        """
        获取指定分类下的所有文件
        
        Args:
            category_path: 分类路径
            
        Returns:
            list: 文件信息列表
        """
        files = []
        for file_path, file_info in self.files_db.items():
            if file_info['category'] == category_path:
                files.append(file_info)
        return files
    
    def get_all_categories(self):
        """
        获取所有分类路径
        
        Returns:
            set: 分类路径集合
        """
        categories = set()
        for file_info in self.files_db.values():
            categories.add(file_info['category'])
        return categories
    
    def get_all_files(self):
        """
        获取所有文件
        
        Returns:
            list: 所有文件信息列表
        """
        return list(self.files_db.values())
    
    def get_file_count(self):
        """获取文件总数"""
        return len(self.files_db)
    
    def clear_all(self):
        """清空所有文件记录"""
        self.files_db = {}
        self._save_database()

