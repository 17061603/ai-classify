#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
向量库查询测试脚本
"""

import chromadb
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.model import OpenAIOfficialEmbeddingFunction

# 配置
VECTOR_DB_PATH = "./file_classification_db"
COLLECTION_NAME = "material_categories"

# 初始化向量库
chroma_client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
embedding_function = OpenAIOfficialEmbeddingFunction(
    api_key="xxxxxxxx",
    model="bge"
)
collection = chroma_client.get_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_function
)

# 查询测试
query_text = "凝水泵"
n_results = 5

print(f"查询文本: {query_text}")
print(f"返回结果数: {n_results}\n")
print("=" * 80)

# 执行查询
results = collection.query(
    query_texts=[query_text],
    n_results=n_results
)

# 显示结果
print("查询返回结果:")
print(f"keys: {list(results.keys())}\n")

if results.get('metadatas') and results['metadatas'][0]:
    metadatas = results['metadatas'][0]
    distances = results.get('distances', [[]])[0] if results.get('distances') else []
    ids = results.get('ids', [[]])[0] if results.get('ids') else []
    documents = results.get('documents', [[]])[0] if results.get('documents') else []
    
    for i, metadata in enumerate(metadatas):
        print(f"\n结果 #{i + 1}:")
        print(f"  ID: {ids[i] if i < len(ids) else 'N/A'}")
        print(f"  文档: {documents[i] if i < len(documents) else 'N/A'}")
        
        if i < len(distances):
            distance = distances[i]
            similarity = 1 - (distance / 2.0) if distance <= 2.0 else 0.0
            similarity = max(0.0, min(1.0, similarity))
            print(f"  距离: {distance:.4f}")
            print(f"  相似度: {similarity:.4f} ({similarity:.2%})")
        
        print(f"  元数据: {metadata}")
else:
    print("未找到结果")

print("\n" + "=" * 80)
print("完整返回结果:")
print(results)
