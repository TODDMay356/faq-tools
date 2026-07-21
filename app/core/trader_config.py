"""Merchant Trader 接口相关配置。"""

MERCHANT_TRADER_BASE_URL = "https://merchanttrader-test.inflyway.com"
ORDER_TRACE_OPEN_BASE_URL = "https://cashier-test.inflyway.com"

TRACE_LOG_LIST_URL = (
    f"{ORDER_TRACE_OPEN_BASE_URL}/notice/api/open/trace-pc-log/list"
)
TRACE_LOG_DETAIL_URL = (
    f"{ORDER_TRACE_OPEN_BASE_URL}/notice/api/open/trace-pc-log/detail"
)
MERCHANT_ROUTE_URL = f"{MERCHANT_TRADER_BASE_URL}/dhpayservice/merchant/getRoute"

TARGET_TRACE_URLS: tuple[str, ...] = (
    "https://payapi-test.inflyway.com/paycenter/api/v2/order/payment/create",
    "https://payapi-test.inflyway.com/paycenter/api/pay",
)

REQUIRED_SOURCE_VALUE = "S004"
