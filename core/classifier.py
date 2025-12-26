#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件分类器 - 分类逻辑接口
从MySQL数据库读取分类数据，使用大模型进行逐级分类
"""

import os
import pymysql
import json
from pathlib import Path
from config.db_config import DBConfig
from llm.model import OpenAIOfficialEmbeddingFunction,sync_llm
import re
import chromadb

class Classifier:
    """文件分类器类"""
    
    def __init__(self):
        """初始化分类器"""
        self.categories_cache = None
        self.connection = None
        self.vector_collection = None  # 向量库集合
        self.vector_db_path = "./file_classification_db"
        self.collection_name = "material_categories_b"
        self._load_categories_from_db()
    
    def _get_connection(self):
        """获取数据库连接"""
        if self.connection is None:
            try:
                params = DBConfig.get_connection_params()
                self.connection = pymysql.connect(**params)
            except Exception as e:
                print(f"数据库连接失败: {e}")
                raise
        return self.connection
    
    def _load_categories_from_db(self):
        """从MySQL数据库加载分类数据"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            # 查询所有分类，按category_code排序
            sql = """
                SELECT 
                    category_code,
                    cate_name,
                    CHAR_LENGTH(category_code) as code_length
                FROM hdl_category
                ORDER BY category_code
            """
            cursor.execute(sql)
            categories = cursor.fetchall()
            
            # 构建分类树结构
            self.categories_cache = self._build_category_tree(categories)
            
            cursor.close()
            print(f"成功加载 {len(categories)} 个分类")
            
        except pymysql.Error as e:
            print(f"数据库错误: {e}")
            self.categories_cache = {}
        except Exception as e:
            print(f"加载分类数据失败: {e}")
            self.categories_cache = {}
    
    def _build_category_tree(self, categories):
        """
        构建分类树结构
        
        Args:
            categories: 从数据库查询的分类列表
            
        Returns:
            dict: 分类树结构
        """
        tree = {}
        
        for cat in categories:
            code = cat['category_code']
            name = cat['cate_name']
            length = cat['code_length']
            
            if length == 2:
                # 一级分类
                tree[code] = {
                    'code': code,
                    'name': name,
                    'level': 1,
                    'children': {}
                }
            elif length == 4:
                # 二级分类
                parent_code = code[:2]
                if parent_code in tree:
                    tree[parent_code]['children'][code] = {
                        'code': code,
                        'name': name,
                        'level': 2,
                        'children': {}
                    }
            elif length == 6:
                # 三级分类
                parent_code = code[:4]
                grandparent_code = code[:2]
                if grandparent_code in tree and parent_code in tree[grandparent_code]['children']:
                    tree[grandparent_code]['children'][parent_code]['children'][code] = {
                        'code': code,
                        'name': name,
                        'level': 3,
                        'children': {}
                    }
        
        return tree
    
    def _refresh_categories(self):
        """刷新分类缓存"""
        self._load_categories_from_db()
    
    def classify_files(self, file_paths, use_embedding=False):
        """
        对文件列表进行分类
        
        Args:
            file_paths: 文件路径列表
            use_embedding: 是否使用向量检索分类方法（默认False，使用LLM分类）
            
        Returns:
            dict: {文件路径: 分类路径} 或 {文件路径: (分类路径, 相似度分数)} 的字典
            例如: {
                'C:/file1.txt': '文档/文本',  # LLM分类
                'C:/file2.jpg': ('图片/照片', 0.85)  # 向量检索分类（带分数）
            }
        """
        results = {}
        
        for file_path in file_paths:
            if use_embedding:
                # 使用向量检索分类（返回分类路径和相似度分数）
                result = self._classify_single_file_with_embedding(file_path, return_score=True)
                results[file_path] = result
            else:
                # 使用LLM逐级分类（原有方法）
                category = self._classify_single_file(file_path)
                results[file_path] = category
        
        return results
    
    def _classify_single_file(self, file_path):
        """
        对单个文件进行分类（逐级分类）
        使用大模型根据文件名逐级判断分类
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 分类路径（使用路径分隔符，如 '钢材/型钢/角钢'）
        """
        # 提取文件名（不含扩展名）
        file_name = os.path.basename(file_path)
        file_name_without_ext = os.path.splitext(file_name)[0]
        
        # 从一级分类开始逐级判断
        category_path = self._classify_with_llm(file_name_without_ext)
        
        # 如果匹配到分类，返回路径；否则返回默认分类
        if category_path:
            return os.sep.join(category_path)
        else:
            return "其他/未分类"
    
    def _classify_with_llm(self, file_name):
        """
        使用大模型逐级分类文件
        
        Args:
            file_name: 文件名（不含扩展名）
            
        Returns:
            list: 完整的分类路径列表，如 ['钢材', '型钢', '角钢']
        """
        if not self.categories_cache:
            return None
        
        category_path = []
        
        # 第一步：判断一级分类
        level1_categories = self._get_level_categories(1)
        level1_result = self._llm_classify_level(file_name, level1_categories, 1)
        
        if not level1_result:
            return None
        
        category_path.append(level1_result['name'])
        level1_code = level1_result['code']
        
        # 检查是否有二级分类
        if level1_code in self.categories_cache and self.categories_cache[level1_code]['children']:
            # 第二步：判断二级分类
            level2_categories = self._get_level_categories(2, parent_code=level1_code)
            if level2_categories:
                level2_result = self._llm_classify_level(file_name, level2_categories, 2, parent_name=level1_result['name'])
                
                if level2_result:
                    category_path.append(level2_result['name'])
                    level2_code = level2_result['code']
                    
                    # 检查是否有三级分类
                    if (level1_code in self.categories_cache and 
                        level2_code in self.categories_cache[level1_code]['children'] and
                        self.categories_cache[level1_code]['children'][level2_code]['children']):
                        # 第三步：判断三级分类
                        level3_categories = self._get_level_categories(3, parent_code=level2_code)
                        if level3_categories:
                            level3_result = self._llm_classify_level(
                                file_name, level3_categories, 3, 
                                parent_name=f"{level1_result['name']}/{level2_result['name']}"
                            )
                            
                            if level3_result:
                                category_path.append(level3_result['name'])
        
        return category_path if category_path else None
    
    def _get_level_categories(self, level, parent_code=None):
        """
        获取指定层级的分类列表
        
        Args:
            level: 分类层级（1, 2, 3）
            parent_code: 父级分类代码（用于获取子分类）
            
        Returns:
            list: 分类列表，每个元素包含 {'code': 'xx', 'name': '分类名称'}
        """
        categories = []
        
        if level == 1:
            # 一级分类
            for code, cat in self.categories_cache.items():
                categories.append({
                    'code': code,
                    'name': cat['name']
                })
        elif level == 2 and parent_code:
            # 二级分类
            if parent_code in self.categories_cache:
                for code, cat in self.categories_cache[parent_code]['children'].items():
                    categories.append({
                        'code': code,
                        'name': cat['name']
                    })
        elif level == 3 and parent_code:
            # 三级分类
            # parent_code是二级分类代码，需要找到对应的一级分类下的二级分类
            for level1_code, level1_cat in self.categories_cache.items():
                if parent_code in level1_cat['children']:
                    level2_cat = level1_cat['children'][parent_code]
                    if 'children' in level2_cat and level2_cat['children']:
                        for code, cat in level2_cat['children'].items():
                            categories.append({
                                'code': code,
                                'name': cat['name']
                            })
                    break
        
        return categories
    
    def _llm_classify_level(self, file_name, categories, level, parent_name=None):
        """
        使用大模型判断文件属于哪个分类
        
        Args:
            file_name: 文件名
            categories: 候选分类列表
            level: 分类层级（1, 2, 3）
            parent_name: 父级分类名称（用于提示词）
            
        Returns:
            dict: {'code': 'xx', 'name': '分类名称'} 或 None
        """
        try:
            # 构建分类选项文本
            categories_text = "\n".join([f"- {cat['name']}" for cat in categories])
            
            # 构建提示词
            if level == 1:
                prompt = f"""你是一个专业的分类助手。请根据文件名判断该文件应该属于以下哪个一级分类。

文件名：{file_name}

可选的一级分类：
{categories_text}

请仔细分析文件名，判断文件最可能属于哪个分类。

重要：你的最终回答必须严格按照以下JSON格式输出，不要添加任何其他文字：
{{"answer":"分类名称"}}

其中"分类名称"必须是上面可选分类列表中的一个完整名称。如果无法确定，则返回：
{{"answer":"无法确定"}}

请直接输出JSON格式，不要在前面添加"分类名称："等提示文字。"""
            elif level == 2:
                prompt = f"""你是一个专业的分类助手。请根据文件名判断该文件在"{parent_name}"分类下，应该属于哪个二级分类。

文件名：{file_name}
一级分类：{parent_name}

可选的二级分类：
{categories_text}

请仔细分析文件名，判断文件最可能属于哪个二级分类。

重要：你的最终回答必须严格按照以下JSON格式输出，不要添加任何其他文字：
{{"answer":"分类名称"}}

其中"分类名称"必须是上面可选分类列表中的一个完整名称。如果无法确定，则返回：
{{"answer":"无法确定"}}

请直接输出JSON格式，不要在前面添加"分类名称："等提示文字。"""
            else:  # level == 3
                prompt = f"""你是一个专业的分类助手。请根据文件名判断该文件在"{parent_name}"分类下，应该属于哪个三级分类。

文件名：{file_name}
上级分类：{parent_name}

可选的三级分类：
{categories_text}

请仔细分析文件名，判断文件最可能属于哪个三级分类。

重要：你的最终回答必须严格按照以下JSON格式输出，不要添加任何其他文字：
{{"answer":"分类名称"}}

其中"分类名称"必须是上面可选分类列表中的一个完整名称。如果无法确定，则返回：
{{"answer":"无法确定"}}

请直接输出JSON格式，不要在前面添加"分类名称："等提示文字。"""
            
            # 调用大模型
            response = sync_llm.chat.completions.create(
                model="qwen3-max",
                messages=[
                    {"role": "system", "content": "你是一个专业的文件分类助手，擅长根据文件名判断文件的分类。你必须严格按照用户要求的JSON格式返回结果，不要添加任何额外的文字说明。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=50
            )
            
            result_text = response.choices[0].message.content.strip()
            class_answer_list = re.findall(r'{"answer":"(.*?)"}', result_text)
            
            # 处理返回结果
            if not class_answer_list:
                return None
            
            # 提取第一个匹配的答案
            class_answer = class_answer_list[0].strip()
            
            if "无法确定" in class_answer or "不确定" in class_answer:
                return None

            
            # 精确匹配
            for cat in categories:
                if cat['name'] == class_answer:
                    return cat
            
            # 包含匹配
            for cat in categories:
                if cat['name'] in class_answer or class_answer in cat['name']:
                    return cat
            
            # 模糊匹配（忽略空格和标点）
            result_clean = class_answer.replace(" ", "").replace("、", "").replace("，", "")
            for cat in categories:
                cat_clean = cat['name'].replace(" ", "").replace("、", "").replace("，", "")
                if result_clean in cat_clean or cat_clean in result_clean:
                    return cat
            
            # 大小写不敏感匹配
            result_lower = class_answer.lower()
            for cat in categories:
                cat_lower = cat['name'].lower()
                if result_lower == cat_lower or result_lower in cat_lower or cat_lower in result_lower:
                    return cat
            
            print(f"警告: 无法匹配分类 '{result_text}' 到候选分类列表")
            return None
            
        except Exception as e:
            print(f"LLM分类错误: {e}")
            return None
    
    def get_all_categories(self):
        """
        获取所有分类（用于调试或显示）
        
        Returns:
            dict: 分类树结构
        """
        return self.categories_cache
    
    def _get_vector_collection(self):
        """
        获取向量库集合（懒加载）
        
        Returns:
            chromadb.Collection: 向量库集合对象
        """
        if self.vector_collection is None:
            try:
                # 创建持久化客户端
                chroma_client = chromadb.PersistentClient(path=self.vector_db_path)
                
                # 使用自定义的OpenAI嵌入函数
                embedding_function = OpenAIOfficialEmbeddingFunction(
                    api_key="xxxxxxxx",
                    model="bge"
                )
                
                # 获取集合
                self.vector_collection = chroma_client.get_collection(
                    name=self.collection_name,
                    embedding_function=embedding_function
                )
                print(f"向量库连接成功: {self.collection_name}")
            except Exception as e:
                print(f"向量库连接失败: {e}")
                raise
        
        return self.vector_collection
    
    def _classify_single_file_with_embedding(self, file_path, return_score=False):
        """
        使用向量检索对单个文件进行分类
        通过检索语义相似的物项，获取其分类信息
        """
        try:
            # 提取文件名（不含扩展名）
            file_name = os.path.basename(file_path)
            file_name_without_ext = os.path.splitext(file_name)[0]
            
            if not file_name_without_ext or not file_name_without_ext.strip():
                if return_score:
                    return ("其他/未分类", 0.0)
                else:
                    return "其他/未分类"
            
            # 获取向量库集合
            collection = self._get_vector_collection()
            
            # 在向量库中检索最相似的物项
            results = collection.query(
                query_texts=[file_name_without_ext],
                n_results=1
            )
            
            if not results or not results.get('metadatas') or not results['metadatas'][0]:
                if return_score:
                    return ("其他/未分类", 0.0)
                else:
                    return "其他/未分类"
            
            # 获取相似度分数（距离）
            # 对于余弦相似度：距离越小越相似，0表示完全相同，2表示完全相反
            # 通常距离 < 0.5 表示非常相似，< 1.0 表示相似
            distance = None
            if results.get('distances') and results['distances'][0]:
                distance = results['distances'][0][0]
                similarity_score = 1 - (distance / 2.0) if distance <= 2.0 else 0.0
                similarity_score = max(0.0, min(1.0, similarity_score))  # 限制在0-1之间
            else:
                similarity_score = None
            
            # 获取最相似物项的元数据
            top_match = results['metadatas'][0][0]
            
            # 构建分类路径
            category_path = []
            
            # 从元数据中提取分类信息
            if top_match.get('big_class_name'):
                category_path.append(top_match['big_class_name'])
            
            if top_match.get('middle_class_name'):
                category_path.append(top_match['middle_class_name'])
            
            if top_match.get('small_class_name'):
                category_path.append(top_match['small_class_name'])
            
            # 如果找到了分类，返回路径
            if category_path:
                category_result = os.sep.join(category_path)
                
                if not similarity_score or similarity_score < 0.5:
                        category_result = "其他/未分类"
                
                if return_score:
                    return (category_result, similarity_score)
                else:
                    return category_result
            else:
                if return_score:
                    return ("其他/未分类", similarity_score if similarity_score is not None else 0.0)
                else:
                    return "其他/未分类"
                
        except Exception as e:
            print(f"向量检索分类错误: {e}")
            return "其他/未分类"
    
    def classify_files_with_embedding(self, file_paths):
        """
        使用向量检索对文件列表进行分类（便捷方法）
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            dict: {文件路径: 分类路径} 的字典
        """
        return self.classify_files(file_paths, use_embedding=True)
    
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None

