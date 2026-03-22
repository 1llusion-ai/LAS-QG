from abc import ABC, abstractmethod
from typing import Optional, Any
import os


class BaseLLM(ABC):
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        pass

    @abstractmethod
    def generate_structured(self, prompt: str, response_model: type, **kwargs) -> Any:
        pass


class SiliconFlowClient(BaseLLM):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.siliconflow.cn/v1",
        model: str = "deepseek-ai/DeepSeek-V3",
    ):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai 包未安装，请运行: pip install openai")

        self.api_key = api_key or os.getenv("SILICONFLOW_API_KEY")
        if not self.api_key:
            raise ValueError("需要设置 SILICONFLOW_API_KEY 环境变量或传入 api_key")

        self.base_url = base_url
        self.model = model
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def generate(self, prompt: str, **kwargs) -> str:
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 1000)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def generate_structured(self, prompt: str, response_model: type, **kwargs) -> Any:
        import json

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个JSON生成器，只输出JSON，不要有其他内容。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 2000),
        )

        content = response.choices[0].message.content
        data = json.loads(content)
        return response_model(**data)


class OpenAIClient(BaseLLM):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-4",
    ):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai 包未安装，请运行: pip install openai")

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_API_BASE")
        self.model = model

        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url

        self.client = OpenAI(**kwargs)

    def generate(self, prompt: str, **kwargs) -> str:
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 1000)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def generate_structured(self, prompt: str, response_model: type, **kwargs) -> Any:
        import json

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个JSON生成器，只输出JSON，不要有其他内容。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 2000),
        )

        content = response.choices[0].message.content
        data = json.loads(content)
        return response_model(**data)


class MockLLM(BaseLLM):
    def __init__(self, response: str = "Mock response"):
        self.response = response

    def generate(self, prompt: str, **kwargs) -> str:
        return self.response

    def generate_structured(self, prompt: str, response_model: type, **kwargs) -> Any:
        import json

        try:
            data = json.loads(self.response)
            return response_model(**data)
        except (json.JSONDecodeError, TypeError):
            return response_model()


def get_llm(
    provider: str = "siliconflow",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> BaseLLM:
    if provider == "siliconflow":
        return SiliconFlowClient(
            api_key=api_key,
            base_url=base_url or "https://api.siliconflow.cn/v1",
            model=model or "deepseek-ai/DeepSeek-V3",
        )
    elif provider == "openai":
        return OpenAIClient(api_key=api_key, base_url=base_url, model=model or "gpt-4")
    elif provider == "mock":
        return MockLLM()
    else:
        raise ValueError(f"不支持的 LLM 提供商: {provider}")
