import logging

from typing import Any, Optional



from langchain.tools import tool

from pydantic import BaseModel, Field



from app.services.eos_merchant_service import fetch_merchant_websites



logger = logging.getLogger(__name__)





class MerchantWebsiteInput(BaseModel):

    """商户网站查询参数。"""



    txb_acc_id: Optional[str] = Field(default=None, description="商户信息中的账号txbAccId")

    web_site: Optional[str] = Field(default=None, description="网站地址")





@tool(

    args_schema=MerchantWebsiteInput,

    description=(

        "查询商户网站信息列表，可查询商户网站ID、网站地址、网站名称、"

        "网站状态、账单名称、贸易类型、贸易子类型、是否开通MIT支付等信息"

    ),

)

def query_merchant_websites(

    txb_acc_id: Optional[str] = None,

    web_site: Optional[str] = None,

) -> dict[str, Any]:

    """查询商户网站信息。"""

    logger.info(

        "[Tool] query_merchant_websites 调用 - txb_acc_id=%s, web_site=%s",

        txb_acc_id,

        web_site,

    )

    result = fetch_merchant_websites(txb_acc_id=txb_acc_id, web_site=web_site)

    if result.get("error"):

        logger.exception("[Tool] query_merchant_websites 失败 - error=%s", result["error"])

    else:

        logger.info(

            "[Tool] query_merchant_websites 成功 - 返回数据量: %s",

            len(result.get("data", {}).get("data", [])),

        )

    return result

