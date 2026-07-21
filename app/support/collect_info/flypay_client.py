"""FlyPay API客户端"""
import httpx
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class FlyPayClient:
    """FlyPay API客户端"""
    
    def __init__(self, base_url: str = "https://cashier-test.inflyway.com"):
        self.base_url = base_url
    
    async def create_merchant(
        self,
        id: str,
        person: str,
        email: str,
        website: str,
        trade_type: str
    ) -> Dict[str, Any]:
        """创建商户账号"""
        url = f"{self.base_url}/messager/lark/app/merchant/add"
        
        params = {
            "id": id,
            "person": person,
            "email": email,
            "website": website,
            "tradeType": trade_type
        }
        logger.info(f"创建商户请求: {params}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, params=params)
            data = response.json()
            logger.info(f"创建商户响应: {data}")
            return data
