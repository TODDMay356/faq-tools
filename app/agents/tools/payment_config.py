from langchain.tools import tool
from typing import Dict, List

from app.core.eos_config import BANK_AISLE_MID_MAP

# 支付方式配置
PAYMENT_STYLES = [
    {"payStyle": "PS0001", "payStyleName": "VISA", "bankAisleId": "B016", "bankAisleName": "worldPay"},
    {"payStyle": "PS0007", "payStyleName": "DINERS", "bankAisleId": "B008", "bankAisleName": "ONERWAY"},
    {"payStyle": "PS0009", "payStyleName": "American Express", "bankAisleId": "B010", "bankAisleName": "EBANX"},
    {"payStyle": "PS0010", "payStyleName": "ELO", "bankAisleId": "B010", "bankAisleName": "EBANX"},
    {"payStyle": "PS0011", "payStyleName": "HIPERCARD", "bankAisleId": "B010", "bankAisleName": "EBANX"},
    {"payStyle": "PS0103", "payStyleName": "GIROPAY", "bankAisleId": "B009", "bankAisleName": "PPRO"},
    {"payStyle": "PS0104", "payStyleName": "IDEAL", "bankAisleId": "B008", "bankAisleName": "ONERWAY"},
    {"payStyle": "PS0106", "payStyleName": "MB_WAY", "bankAisleId": "B009", "bankAisleName": "PPRO"},
    {"payStyle": "PS0109", "payStyleName": "BANCONTACT", "bankAisleId": "B009", "bankAisleName": "PPRO"},
    {"payStyle": "PS0110", "payStyleName": "PRZELEWY24", "bankAisleId": "B009", "bankAisleName": "PPRO"},
    {"payStyle": "PS0111", "payStyleName": "EPS", "bankAisleId": "B009", "bankAisleName": "PPRO"},
    {"payStyle": "PS0112", "payStyleName": "MULTIBANCO", "bankAisleId": "B009", "bankAisleName": "PPRO"},
    {"payStyle": "PS0113", "payStyleName": "BLIK", "bankAisleId": "B009", "bankAisleName": "PPRO"},
    {"payStyle": "PS0117", "payStyleName": "Ozow", "bankAisleId": "B010", "bankAisleName": "EBANX"},
    {"payStyle": "PS0118", "payStyleName": "Servipag", "bankAisleId": "B010", "bankAisleName": "EBANX"},
    {"payStyle": "PS0119", "payStyleName": "PSE", "bankAisleId": "B010", "bankAisleName": "EBANX"},
    {"payStyle": "PS0120", "payStyleName": "SPEI", "bankAisleId": "B010", "bankAisleName": "EBANX"},
    {"payStyle": "PS0301", "payStyleName": "BOLETO", "bankAisleId": "B010", "bankAisleName": "EBANX"},
    {"payStyle": "PS0302", "payStyleName": "PIX", "bankAisleId": "B010", "bankAisleName": "EBANX"},
    {"payStyle": "PS0303", "payStyleName": "OXXO", "bankAisleId": "B010", "bankAisleName": "EBANX"},
    {"payStyle": "PS0304", "payStyleName": "KONBINI", "bankAisleId": "B009", "bankAisleName": "PPRO"},
    {"payStyle": "PS0401", "payStyleName": "BANCOMATPAY", "bankAisleId": "B009", "bankAisleName": "PPRO"},
    {"payStyle": "PS0405", "payStyleName": "PAYCONIQ", "bankAisleId": "B009", "bankAisleName": "PPRO"},
    {"payStyle": "PS0406", "payStyleName": "SATISPAY", "bankAisleId": "B009", "bankAisleName": "PPRO"},
    {"payStyle": "PS0421", "payStyleName": "payPal", "bankAisleId": "B014", "bankAisleName": "Paypal"},
    {"payStyle": "PS0422", "payStyleName": "Mercado Pago", "bankAisleId": "B010", "bankAisleName": "EBANX"},
    {"payStyle": "PS0423", "payStyleName": "Nequi", "bankAisleId": "B010", "bankAisleName": "EBANX"},
    {"payStyle": "PS0602", "payStyleName": "KLARNA_LATER", "bankAisleId": "B009", "bankAisleName": "PPRO"},
]


@tool(description="查询支付方式列表，返回支付方式ID、名称、银行通道ID和通道名称")
def get_payment_styles() -> List[Dict[str, str]]:
    """查询支付方式列表"""
    return PAYMENT_STYLES


# @tool(description="根据银行通道ID获取对应的商户名称")
# def get_mid_name_by_bank_aisle(bank_aisle_id: str) -> str:
#     """根据银行通道ID获取商户名称"""
#     return BANK_AISLE_MID_MAP.get(bank_aisle_id, "")
