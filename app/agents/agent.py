import json
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import os

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from app.agents.tools import get_all_tools
from app.agents.prompts import PAYMENT_SUPPORT_AGENT_PROMPT

model = ChatOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", ""),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
)


def create_merchant_agent():
    """创建商户智能体"""
    return create_agent(
        model,
        tools=get_all_tools(),
        system_prompt=PAYMENT_SUPPORT_AGENT_PROMPT,
    )


def invoke_agent(message: str):
    """调用智能体"""
    agent = create_merchant_agent()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]}
    )
    return result


if __name__ == "__main__":
    result = invoke_agent("支持哪些交易币种和结算币种")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))