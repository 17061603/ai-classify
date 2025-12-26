#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
向量库初始化脚本
从 hdl_material_pure 表读取数据，分批存入向量库
"""

import chromadb
import pymysql
from config.db_config import DBConfig
from llm.model import OpenAIOfficialEmbeddingFunction
import time
from tqdm import tqdm


# 配置
EMBEDDING_MODEL = "bge"  
BATCH_SIZE = 1000  
VECTOR_DB_PATH = "./file_classification_db"
COLLECTION_NAME = "material_categories_b"


def init_collection():
    """
    初始化向量库集合
    
    Returns:
        chromadb.Collection: 向量库集合对象
    """
    # 创建持久化客户端
    chroma_client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
    
    # 使用自定义的OpenAI嵌入函数（调用本地API）
    embedding_function = OpenAIOfficialEmbeddingFunction(
        api_key="xxxxxxxx",  # 从环境变量或配置文件读取
        model=EMBEDDING_MODEL
    )
    
    # 获取或创建集合
    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={"hnsw:space": "cosine"}  # 余弦相似度适配文本语义
    )
    
    return collection


def get_db_connection():
    """
    获取MySQL数据库连接
    
    Returns:
        pymysql.Connection: 数据库连接对象
    """
    params = DBConfig.get_connection_params()
    params['cursorclass'] = pymysql.cursors.DictCursor
    connection = pymysql.connect(**params)
    return connection


def get_total_count(connection):
    """
    获取总记录数
    
    Args:
        connection: 数据库连接
        
    Returns:
        int: 总记录数
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) as total FROM hdl_material_pure")
        result = cursor.fetchone()
        return result['total'] if result else 0


def fetch_materials_batch(connection, offset, limit):
    """
    分批获取材料数据
    
    Args:
        connection: 数据库连接
        offset: 偏移量
        limit: 每批数量
        
    Returns:
        list: 材料数据列表
    """
    with connection.cursor() as cursor:
        sql = """
            SELECT 
                id,
                material_name,
                big_class_name,
                middle_class_name,
                small_class_name,
                small_class_code
            FROM hdl_material_pure
            ORDER BY id
            LIMIT %s OFFSET %s
        """
        cursor.execute(sql, (limit, offset))
        return cursor.fetchall()


def build_document(material):    
    material_name = material.get('material_name', '')
    small_class_code = material.get('small_class_code', '')
    return f"{material_name} {small_class_code}".strip()


def build_metadata(material):
    """
    构建元数据
    
    Args:
        material: 材料数据字典
        
    Returns:
        dict: 元数据字典
    """
    metadata = {}
    
    if material.get('id'):
        metadata['id'] = str(material['id'])
    
    if material.get('material_name'):
        metadata['material_name'] = str(material['material_name'])
    
    if material.get('big_class_name'):
        metadata['big_class_name'] = str(material['big_class_name'])
    
    if material.get('middle_class_name'):
        metadata['middle_class_name'] = str(material['middle_class_name'])
    
    if material.get('small_class_name'):
        metadata['small_class_name'] = str(material['small_class_name'])

    if material.get('small_class_code'):
        metadata['small_class_code'] = str(material['small_class_code'])
        
    
    return metadata


def process_batch(collection, materials):
    """
    处理一批数据，存入向量库
    
    Args:
        collection: 向量库集合对象
        materials: 材料数据列表
        
    Returns:
        int: 成功处理的数量
    """
    if not materials:
        return 0
    
    ids = []
    documents = []
    metadatas = []
    
    for material in materials:
        # 构建唯一ID
        material_code = material.get('id', '')
        material_name = material.get('material_name', '')
        small_class_code = material.get('small_class_code', '')
        if not material_code or not material_name or not small_class_code:
            continue  # 跳过
        
        material_id = f"material_{material_code}"
        
        # 构建文档内容
        document = build_document(material)
        if not document:
            continue  # 跳过空文档
        
        # 构建元数据
        metadata = build_metadata(material)
        
        ids.append(material_id)
        documents.append(document)
        metadatas.append(metadata)
    
    if ids:
        try:
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            return len(ids)
        except Exception as e:
            print(f"批量添加失败: {e}")
            return 0
    
    return 0


def main():
    """主函数"""
    print("=" * 60)
    print("向量库初始化程序")
    print("=" * 60)
    
    # 初始化向量库
    print("\n[1/4] 初始化向量库...")
    try:
        collection = init_collection()
        print(f"✓ 向量库初始化成功: {VECTOR_DB_PATH}")
        print(f"✓ 集合名称: {COLLECTION_NAME}")
    except Exception as e:
        print(f"✗ 向量库初始化失败: {e}")
        return
    
    # 连接数据库
    print("\n[2/4] 连接数据库...")
    try:
        connection = get_db_connection()
        print("✓ 数据库连接成功")
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return
    
    # 获取总记录数
    print("\n[3/4] 获取数据统计...")
    try:
        total_count = get_total_count(connection)
        print(f"✓ 总记录数: {total_count:,} 条")
    except Exception as e:
        print(f"✗ 获取记录数失败: {e}")
        connection.close()
        return
    
    if total_count == 0:
        print("⚠ 没有数据需要处理")
        connection.close()
        return
    
    # 计算批次数
    total_batches = (total_count + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"✓ 将分 {total_batches} 批处理，每批 {BATCH_SIZE} 条")
    
    # 开始处理
    print("\n[4/4] 开始处理数据...")
    print("-" * 60)
    
    processed_count = 0
    failed_count = 0
    start_time = time.time()
    
    try:
        # 使用tqdm显示进度条
        with tqdm(total=total_count, desc="处理进度", unit="条") as pbar:
            for batch_num in range(total_batches):
                offset = batch_num * BATCH_SIZE
                
                try:
                    # 获取一批数据
                    materials = fetch_materials_batch(connection, offset, BATCH_SIZE)
                    
                    if not materials:
                        break
                    
                    # 处理并存入向量库
                    success_count = process_batch(collection, materials)
                    processed_count += success_count
                    failed_count += len(materials) - success_count
                    
                    # 更新进度条
                    pbar.update(len(materials))
                    
                    # 每10批显示一次详细信息
                    if (batch_num + 1) % 10 == 0:
                        elapsed_time = time.time() - start_time
                        speed = processed_count / elapsed_time if elapsed_time > 0 else 0
                        pbar.set_postfix({
                            '已处理': f"{processed_count:,}",
                            '失败': f"{failed_count:,}",
                            '速度': f"{speed:.1f}条/秒"
                        })
                
                except Exception as e:
                    print(f"\n✗ 批次 {batch_num + 1} 处理失败: {e}")
                    failed_count += BATCH_SIZE
                    continue
        
        elapsed_time = time.time() - start_time
        
        print("\n" + "=" * 60)
        print("处理完成！")
        print("=" * 60)
        print(f"总记录数: {total_count:,} 条")
        print(f"成功处理: {processed_count:,} 条")
        print(f"处理失败: {failed_count:,} 条")
        print(f"总耗时: {elapsed_time:.2f} 秒")
        print(f"平均速度: {processed_count / elapsed_time:.2f} 条/秒" if elapsed_time > 0 else "N/A")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n⚠ 用户中断处理")
        print(f"已处理: {processed_count:,} 条")
    except Exception as e:
        print(f"\n✗ 处理过程中发生错误: {e}")
    finally:
        connection.close()
        print("\n✓ 数据库连接已关闭")


if __name__ == "__main__":
    main()
