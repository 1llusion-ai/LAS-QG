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

    def embed(self, text: str, **kwargs) -> list[float]:
        raise NotImplementedError("当前 LLM 不支持 embedding")

    def bind_tools(self, tools: list) -> "ToolBoundLLM":
        return ToolBoundLLM(self, tools)


class ToolBoundLLM:
    def __init__(self, llm: BaseLLM, tools: list):
        self.llm = llm
        self.tools = tools
        self._tool_schemas = self._build_tool_schemas(tools)

    def _build_tool_schemas(self, tools: list) -> list:
        schemas = []
        for tool in tools:
            schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            if hasattr(tool, 'args_schema') and tool.args_schema:
                props = {}
                required = []
                for field_name, field_info in tool.args_schema.model_fields.items():
                    field_type = field_info.annotation
                    json_type = self._get_json_type(field_type)
                    props[field_name] = {
                        "type": json_type,
                        "description": field_info.description or ""
                    }
                    if field_info.is_required():
                        required.append(field_name)
                schema["function"]["parameters"]["properties"] = props
                schema["function"]["parameters"]["required"] = required
            schemas.append(schema)
        return schemas

    def _get_json_type(self, python_type) -> str:
        type_str = str(python_type)
        if 'dict' in type_str.lower() or 'Dict' in type_str:
            return "object"
        elif 'list' in type_str.lower() or 'List' in type_str:
            return "array"
        elif 'int' in type_str.lower():
            return "integer"
        elif 'float' in type_str.lower() or 'number' in type_str.lower():
            return "number"
        elif 'bool' in type_str.lower():
            return "boolean"
        else:
            return "string"

    def invoke(self, messages: list) -> Any:
        from langchain_core.messages import AIMessage

        if hasattr(self.llm, 'client'):
            formatted_messages = []
            for msg in messages:
                if hasattr(msg, 'content'):
                    role = "user" if msg.__class__.__name__ == "HumanMessage" else "assistant"
                    if msg.__class__.__name__ == "SystemMessage":
                        role = "system"
                    formatted_messages.append({
                        "role": role,
                        "content": msg.content
                    })
                else:
                    formatted_messages.append(msg)

            response = self.llm.client.chat.completions.create(
                model=self.llm.model,
                messages=formatted_messages,
                tools=self._tool_schemas,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=2000,
            )

            msg = response.choices[0].message
            tool_calls = []
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    import json
                    try:
                        args = json.loads(tc.function.arguments)
                    except:
                        args = {}
                    tool_calls.append({
                        "name": tc.function.name,
                        "args": args,
                        "id": tc.id,
                        "type": "tool_call"
                    })

            return AIMessage(
                content=msg.content or "",
                tool_calls=tool_calls
            )

        prompt = "\n".join([
            msg.content if hasattr(msg, 'content') else str(msg)
            for msg in messages
        ])
        text_response = self.llm.generate(prompt)
        return AIMessage(content=text_response)


class SiliconFlowClient(BaseLLM):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.siliconflow.cn/v1",
        model: str = "deepseek-ai/DeepSeek-V3",
        embed_model: str = "BAAI/bge-large-zh-v1.5",
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
        self.embed_model = embed_model
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def generate(self, prompt: str, **kwargs) -> str:
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 2000)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[LLM错误] 模型: {self.model}, 错误: {type(e).__name__}: {e}")
            raise

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

    def embed(self, text: str, **kwargs) -> list[float]:
        try:
            response = self.client.embeddings.create(
                model=self.embed_model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"[Embedding错误] 模型: {self.embed_model}, 错误: {type(e).__name__}: {e}")
            raise


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
