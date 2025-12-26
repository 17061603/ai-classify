from openai import AsyncOpenAI, OpenAI
import os
from chromadb import EmbeddingFunction, Embeddings
from typing import List

async_llm = AsyncOpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", "sk-cc240630450945948937ef1be2332331"),
    base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    
)

sync_llm = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", "sk-cc240630450945948937ef1be2332331"),
    base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
)

sync_embed = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", "xxxxxxxx"),
    base_url=os.environ.get("DEEPSEEK_BASE_URL", "http://jifang.wsb360.com:8005/v1")
)


async_embed = AsyncOpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", "xxxxxxxx"),
    base_url=os.environ.get("DEEPSEEK_BASE_URL", "http://jifang.wsb360.com:8005/v1")
)

class OpenAIOfficialEmbeddingFunction(EmbeddingFunction):
    def __init__(self, api_key: str="xxxxxxxx", model: str = "bge"):
        self.client = OpenAI(
            api_key=api_key,
            base_url="http://jifang.wsb360.com:8005/v1",
        )
        self.model = model  

    def __call__(self, texts: List[str]) -> Embeddings:
        try:
            response = self.client.embeddings.create(
                input=texts,
                model=self.model
            )
            embeddings = [item.embedding for item in response.data]
            return embeddings
        except Exception as e:
            raise RuntimeError(f"OpenAI Embedding API调用失败：{str(e)}")