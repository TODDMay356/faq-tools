"""EOS 接口相关配置。"""

EOS_PAYCENTER_BASE_URL = "https://test.inflyway.com/paycenter/eos"

# 银行通道 ID 与商户名称映射
BANK_AISLE_MID_MAP: dict[str, str] = {
    "B009": "PUB_PPRO",
    "B010": "PUB_EBANX",
    "B008": "PRI_ONERWAY_everis.me",
    "B016": "PRI_WORLDPAY_CAMELPAYRDR1",
    "B014": "PUB_PAYPAL",
}

# 默认支付路由配置（按通道批量添加）
DEFAULT_PAYMENT_ROUTE_CONFIGS: list[dict[str, object]] = [
    {
        "bank_aisle_id": "B009",
        "mid_name": "PUB_PPRO",
        "pay_style_ids": [
            "PS0103",
            "PS0106",
            "PS0109",
            "PS0110",
            "PS0111",
            "PS0112",
            "PS0113",
            "PS0304",
            "PS0401",
            "PS0405",
            "PS0406",
            "PS0121",
            "PS0602",
        ],
    },
    {
        "bank_aisle_id": "B010",
        "mid_name": "PUB_EBANX",
        "pay_style_ids": [
            "PS0009",
            "PS0010",
            "PS0011",
            "PS0110",
            "PS0117",
            "PS0118",
            "PS0119",
            "PS0120",
            "PS0301",
            "PS0302",
            "PS0303",
            "PS0422",
            "PS0423",
        ],
    },
    {
        "bank_aisle_id": "B008",
        "mid_name": "PRI_ONERWAY_everis.me",
        "pay_style_ids": ["PS0104", "PS0007"],
    },
]

PARTNER_BIND_PARTNER_CODE = "EBANX"
