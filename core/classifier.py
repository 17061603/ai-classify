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
import numpy as np

# 文档提取相关导入
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("警告: PyPDF2未安装，无法提取PDF文档内容")

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    print("警告: python-docx未安装，无法提取DOCX文档内容")

try:
    import win32com.client
    DOC_AVAILABLE = True
except ImportError:
    DOC_AVAILABLE = False
    # 只在Windows系统上提示
    import sys
    if sys.platform == "win32":
        print("警告: pywin32未安装，无法提取DOC文档内容（仅Windows需要）")

class Classifier:
    """文件分类器类"""
    
    def __init__(self):
        """初始化分类器"""
        self.categories_cache = None
        self.connection = None
        self.vector_collection = None  # 向量库集合
        self.vector_db_path = "./file_classification_db"
        self.collection_name = "material_categories"
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
        使用向量检索对文件列表进行分类
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            dict: {文件路径: 分类路径} 的字典
        """
        return self.classify_files(file_paths, use_embedding=True)
    

    def _filter_quantile_with_tie(self, data, score_key="similarity_score", quantile=0.9, min_advance=2):
        """
        分位数筛选+同分归并（不损失高分同分）
        
        Args:
            data: 数据列表，每个元素包含score_key字段
            score_key: 分数字段名
            quantile: 分位数（0.9=前10%）
            min_advance: 最小晋级数≥2
            
        Returns:
            list: 筛选后的数据列表
        """
        if not data:
            return []
        
        # 1. 数据降序排序
        sorted_data = sorted(data, key=lambda x: x[score_key], reverse=True)
        n_total = len(sorted_data)
        
        if n_total <= min_advance:
            return sorted_data  # 数据量少则全部晋级
        
        # 2. 提取得分列表，计算分位数门槛
        scores = [d[score_key] for d in sorted_data]
        threshold = np.quantile(scores, quantile)  # 基础门槛分
        
        # 3. 核心：筛选≥门槛的对象 + 归并所有同分（哪怕超比例）
        # 先找所有≥门槛的对象
        advance_candidates = [d for d in sorted_data if d[score_key] >= threshold]
        
        # 若有同分在门槛线上，确保全部纳入（比如门槛90，所有90分都进）
        tie_score = threshold
        tie_candidates = [d for d in sorted_data if abs(d[score_key] - tie_score) < 0.0001]
        
        # 合并：≥门槛的 + 补充可能漏的同分（避免分位数精度问题）
        # 使用字典去重（基于category_path）
        seen_paths = set()
        advance_data = []
        for d in advance_candidates + tie_candidates:
            path = d.get('category_path', '')
            if path not in seen_paths:
                seen_paths.add(path)
                advance_data.append(d)
        
        # 重新排序（保证高分在前）
        advance_data = sorted(advance_data, key=lambda x: x[score_key], reverse=True)
        
        # 4. 兜底：若晋级数<2，取前2名（含同分）
        if len(advance_data) < min_advance:
            # 取前2名，若第2名有同分，全部纳入
            if n_total >= 2:
                top2_score = sorted_data[1][score_key]
            else:
                top2_score = sorted_data[0][score_key]
            
            seen_paths = set()
            advance_data = []
            for d in sorted_data:
                if d[score_key] >= top2_score:
                    path = d.get('category_path', '')
                    if path not in seen_paths:
                        seen_paths.add(path)
                        advance_data.append(d)
        
        return advance_data
    
    def _get_top_score_embedding_results(self, file_path, n_results=100):
        """
        使用向量检索获取分类结果，使用分位数筛选（0.9）+ 同分归并
        
        Args:
            file_path: 文件路径
            n_results: 向量检索返回的结果数量（默认100）
            
        Returns:
            list: 筛选后的分类结果列表，每个元素包含 {
                'category_path': '大类/中类/小类',
                'similarity_score': 0.85,
                'distance': 0.3,
                'metadata': {...}
            }
            如果没有找到结果或相似度 < 0.5，返回空列表
        """
        try:
            # 提取文件名（不含扩展名）
            file_name = os.path.basename(file_path)
            file_name_without_ext = os.path.splitext(file_name)[0]
            
            if not file_name_without_ext or not file_name_without_ext.strip():
                return []
            
            # 获取向量库集合
            collection = self._get_vector_collection()
            
            # 在向量库中检索多个相似的物项（检索100个结果）
            results = collection.query(
                query_texts=[file_name_without_ext],
                n_results=n_results
            )
            
            if not results or not results.get('metadatas') or not results['metadatas'][0]:
                return []
            
            # 处理结果
            classification_results = []
            metadatas = results['metadatas'][0]
            distances = results.get('distances', [[]])[0] if results.get('distances') else []
            
            # 遍历所有结果，计算相似度并构建分类信息
            for i, metadata in enumerate(metadatas):
                distance = distances[i] if i < len(distances) else None
                
                if distance is None:
                    continue
                
                # 计算相似度分数
                similarity_score = 1 - (distance / 2.0) if distance <= 2.0 else 0.0
                similarity_score = max(0.0, min(1.0, similarity_score))
                
                # 只保留相似度分数足够高的结果（>= 0.5）
                if similarity_score < 0.5:
                    continue
                
                # 构建分类路径
                category_path = []
                if metadata.get('big_class_name'):
                    category_path.append(metadata['big_class_name'])
                if metadata.get('middle_class_name'):
                    category_path.append(metadata['middle_class_name'])
                if metadata.get('small_class_name'):
                    category_path.append(metadata['small_class_name'])
                
                if category_path:
                    category_result = os.sep.join(category_path)
                    classification_results.append({
                        'category_path': category_result,
                        'similarity_score': similarity_score,
                        'distance': distance,
                        'metadata': metadata
                    })
            
            # 如果没有有效结果，返回空列表
            if not classification_results:
                return []
            
            # 使用分位数筛选（0.9分位数）+ 同分归并
            filtered_results = self._filter_quantile_with_tie(
                classification_results, 
                score_key="similarity_score", 
                quantile=0.9, 
                min_advance=2
            )
            
            return filtered_results
            
        except Exception as e:
            print(f"向量检索获取筛选结果错误: {e}")
            return []
    
    def _classify_with_fulltext_and_llm(self, file_path, embedding_results, llm_category_path=None):
        """
        基于文件名、向量检索结果和LLM逐级分类结果，使用LLM进行最终分类判断
        
        Args:
            file_path: 文件路径
            embedding_results: 向量检索筛选后的结果列表
            llm_category_path: LLM逐级分类的结果（可选）
            
        Returns:
            dict: {
                'category_path': '大类/中类/小类',
                'reason': '分类原因'
            } 或 None
        """
        try:
            # 提取文件名（不含扩展名）
            file_name = os.path.basename(file_path)
            file_name_without_ext = os.path.splitext(file_name)[0]
            
            
            if not file_name_without_ext or not file_name_without_ext.strip():
                print(f"无法提取文件名: {file_path}")
                return None
            
            # 构建候选分类列表（向量检索结果）
            candidate_categories = []
            for result in embedding_results:
                category_path = result['category_path']
                similarity_score = result['similarity_score']
                candidate_categories.append({
                    'path': category_path,
                    'score': similarity_score,
                    'source': '向量检索'
                })
            
            # 如果LLM逐级分类结果存在，也加入候选列表
            if llm_category_path:
                # 检查是否已经在向量检索结果中
                llm_path_str = os.sep.join(llm_category_path) if isinstance(llm_category_path, list) else llm_category_path
                if not any(cat['path'] == llm_path_str for cat in candidate_categories):
                    candidate_categories.append({
                        'path': llm_path_str,
                        'score': None,
                        'source': 'LLM逐级分类'
                    })
            
            if not candidate_categories:
                return None
            
            # 构建分类选项文本
            categories_text = "\n".join([
                f"{i+1}. {cat['path']} ({cat['source']}"
                for i, cat in enumerate(candidate_categories)
            ])
            
            # 构建提示词
            prompt = f"""你是一个专业的文档分类助手。请根据文件名，从以下候选分类中选择最合适的分类。

文件名：{file_name_without_ext}

候选分类列表：
{categories_text}

请仔细分析文件名，判断文档最应该属于哪个分类。你需要考虑：
1. 文件名中的关键词和术语
2. 文件名中提到的物项、设备或材料
3. 文件名的技术领域和应用场景
4. 向量检索的相似度分数（如果提供）
5. LLM逐级分类的结果（如果提供）

重要：你的最终回答必须严格按照以下JSON格式输出，不要添加任何其他文字：
{{"category":"大类/中类/小类", "reason":"你的分类理由，说明为什么选择这个分类"}}

其中：
- "category" 必须是上面候选分类列表中的一个完整分类路径
- "reason" 是你选择该分类的详细理由，应该基于文件名进行分析，并说明为什么选择这个分类而不是其他候选分类

请直接输出JSON格式，不要在前面添加任何提示文字。"""
            
            # 调用大模型
            response = sync_llm.chat.completions.create(
                model="qwen3-max",
                messages=[
                    {"role": "system", "content": "你是一个专业的文档分类助手，擅长根据文件名判断文档的分类。你必须严格按照用户要求的JSON格式返回结果，不要添加任何额外的文字说明。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 解析JSON结果
            try:
                # 尝试提取JSON
                json_match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
                if json_match:
                    result_json = json.loads(json_match.group())
                    category = result_json.get('category', '')
                    reason = result_json.get('reason', '')
                    
                    # 验证分类是否在候选列表中
                    valid_category = None
                    for cat in candidate_categories:
                        if cat['path'] == category:
                            valid_category = category
                            break
                    
                    if valid_category:
                        return {
                            'category_path': valid_category,
                            'reason': reason
                        }
                    else:
                        print(f"警告: LLM返回的分类不在候选列表中: {category}")
                        if candidate_categories:
                            vector_result = next((cat for cat in candidate_categories if cat['score'] is not None), None)
                            if vector_result:
                                return {
                                    'category_path': vector_result['path'],
                                    'reason': f"LLM返回的分类不在候选列表中，使用向量检索相似度最高的分类。原始返回: {category}"
                                }
                            else:
                                return {
                                    'category_path': candidate_categories[0]['path'],
                                    'reason': f"LLM返回的分类不在候选列表中，使用第一个候选分类。原始返回: {category}"
                                }
                else:
                    print(f"警告: 无法从LLM响应中提取JSON: {result_text}")
            except json.JSONDecodeError as e:
                print(f"JSON解析错误: {e}, 响应内容: {result_text}")
            
            # 如果解析失败，返回第一个候选分类
            if candidate_categories:
                return {
                    'category_path': candidate_categories[0]['path'],
                    'reason': f"LLM响应解析失败，使用相似度最高的分类。原始响应: {result_text[:200]}"
                }
            
            return None
            
        except Exception as e:
            print(f"基于文件名的LLM分类错误: {e}")
            return None
    
    def classify_with_fulltext_llm(self, file_path):
        """
        使用文件名、向量检索和LLM逐级分类结果进行最终分类判断
        
        工作流程：
        1. 同时进行向量检索（使用分位数筛选0.9）和LLM逐级分类
        2. 将向量检索筛选后的结果和LLM逐级分类结果一起传入 _classify_with_fulltext_and_llm
        3. 由模型判断最终分类
        """
        try:
            file_name = os.path.basename(file_path)
            file_name_without_ext = os.path.splitext(file_name)[0]
            
            # 1. 向量检索获取筛选后的结果（使用分位数筛选0.9）
            embedding_results = self._get_top_score_embedding_results(file_path, n_results=100)
            
            # 2. 同时进行LLM逐级分类
            llm_category_path = None
            try:
                llm_category_path = self._classify_with_llm(file_name_without_ext)
            except Exception as e:
                print(f"LLM逐级分类错误: {e}")
            
            # 3. 如果向量检索没有结果，且LLM逐级分类也没有结果
            if not embedding_results and not llm_category_path:
                return {
                    'category_path': '其他/未分类',
                    'reason': '向量检索和LLM逐级分类均未找到匹配分类',
                    'similarity_score': None
                }
            
            # 4. 如果向量检索没有结果，但LLM逐级分类有结果
            if not embedding_results and llm_category_path:
                category_result = os.sep.join(llm_category_path) if isinstance(llm_category_path, list) else llm_category_path
                return {
                    'category_path': category_result,
                    'reason': '向量检索未找到匹配结果，使用LLM逐级分类结果',
                    'similarity_score': None
                }
            
            llm_result = self._classify_with_fulltext_and_llm(file_path, embedding_results, llm_category_path)
            print(llm_result)
            
            if llm_result:
                # 添加相似度分数（如果有）
                if embedding_results:
                    llm_result['similarity_score'] = embedding_results[0]['similarity_score']
                else:
                    llm_result['similarity_score'] = None
                return llm_result
            else:
                # 如果LLM分类失败，优先使用向量检索结果，其次使用LLM逐级分类结果
                if embedding_results:
                    return {
                        'category_path': embedding_results[0]['category_path'],
                        'reason': 'LLM分类失败，使用向量检索相似度最高的分类',
                        'similarity_score': embedding_results[0]['similarity_score']
                    }
                elif llm_category_path:
                    category_result = os.sep.join(llm_category_path) if isinstance(llm_category_path, list) else llm_category_path
                    return {
                        'category_path': category_result,
                        'reason': 'LLM分类失败，使用LLM逐级分类结果',
                        'similarity_score': None
                    }
                else:
                    return {
                        'category_path': '其他/未分类',
                        'reason': 'LLM分类失败，且无其他可用结果',
                        'similarity_score': None
                    }
                
        except Exception as e:
            print(f"文件名LLM分类错误: {e}")
            return None
    
    def _fallback_to_llm_classify(self, file_path, reason):
        """
        回退到逐级LLM分类方法
        
        Args:
            file_path: 文件路径
            reason: 回退原因
            
        Returns:
            dict: {
                'category_path': '大类/中类/小类',
                'reason': '分类原因',
                'similarity_score': None
            }
        """
        try:
            # 提取文件名（不含扩展名）
            file_name = os.path.basename(file_path)
            file_name_without_ext = os.path.splitext(file_name)[0]
            
            # 使用逐级LLM分类
            category_path = self._classify_with_llm(file_name_without_ext)
            
            if category_path:
                category_result = os.sep.join(category_path)
                return {
                    'category_path': category_result,
                    'reason': f'{reason}，使用逐级LLM分类',
                    'similarity_score': None
                }
            else:
                return {
                    'category_path': '其他/未分类',
                    'reason': f'{reason}，逐级LLM分类未找到匹配分类',
                    'similarity_score': None
                }
        except Exception as e:
            print(f"回退到逐级LLM分类错误: {e}")
            return {
                'category_path': '其他/未分类',
                'reason': f'{reason}，逐级LLM分类出错',
                'similarity_score': None
            }
    
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None

