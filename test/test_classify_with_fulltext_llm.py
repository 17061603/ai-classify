#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 添加项目根目录到路径
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.classifier import Classifier

classifier = Classifier()
result = classifier.classify_with_fulltext_llm("mnt/d/pythonproject/ai-classify/测试/[非密]高扬程给水泵采购技术要求.pdf")
print(result)
