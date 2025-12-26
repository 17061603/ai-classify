#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库配置模块
"""

import os
from pathlib import Path


class DBConfig:
    """数据库配置类"""
    
    # MySQL连接配置
    # 你可以通过环境变量或直接修改这些值来配置数据库连接
    HOST = os.getenv('DB_HOST', 'wx.wsb360.com')
    PORT = int(os.getenv('DB_PORT', '4306'))
    DATABASE = os.getenv('DB_NAME', 'ai_db_demo1')
    USER = os.getenv('DB_USER', 'ai_db_demo1')
    PASSWORD = os.getenv('DB_PASSWORD','QWER4321')
    CHARSET = os.getenv('DB_CHARSET', 'utf8mb4')
    
    @classmethod
    def get_connection_params(cls):
        """
        获取数据库连接参数字典（用于pymysql.connect）
        
        Returns:
            dict: 连接参数字典
        """
        return {
            'host': cls.HOST,
            'port': cls.PORT,
            'user': cls.USER,
            'password': cls.PASSWORD,
            'database': cls.DATABASE,
            'charset': cls.CHARSET,
            'cursorclass': None  # 可以设置为 pymysql.cursors.DictCursor
        }
    
    @classmethod
    def get_connection_string(cls):
        """
        获取数据库连接字符串（用于其他需要字符串格式的连接）
        
        Returns:
            str: 连接字符串
        """
        return f"mysql+pymysql://{cls.USER}:{cls.PASSWORD}@{cls.HOST}:{cls.PORT}/{cls.DATABASE}?charset={cls.CHARSET}"

