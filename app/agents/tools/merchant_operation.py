import logging

from typing import Any



from langchain.tools import tool



from app.services.eos_merchant_service import fetch_merchant_info



logger = logging.getLogger(__name__)





@tool(description="获取商户信息，包括商户ID、商户名称、状态、秘钥、公钥等详细信息。参数merchant_id为商户ID，例如MT200010000003605")

def get_merchant_info(merchant_id: str = "") -> dict[str, Any]:

    """获取商户详细信息。"""

    logger.info("[Tool] get_merchant_info 调用 - merchant_id: %s", merchant_id)

    result = fetch_merchant_info(merchant_id)

    if result.get("error"):

        logger.warning(

            "[Tool] get_merchant_info 失败 - merchant_id=%s, error=%s",

            merchant_id,

            result["error"],

        )

    else:

        logger.info("[Tool] get_merchant_info 成功 - merchant_id: %s", merchant_id)

    return result

