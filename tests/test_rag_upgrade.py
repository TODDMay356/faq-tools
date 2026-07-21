import sys
sys.path.insert(0, r"d:\rag-system\faq-tools-v3\faq-tools-test")

import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_ENDPOINT"] = "https://hf-mirror.com"

print("=== Phase 4: Runtime Verification Test (Chinese) ===\n")

print("1. Testing IntentType enum...")
try:
    from app.retrieval.reranker import IntentType
    print("   [OK] IntentType imported successfully")
    print(f"   - IntentType members: {[e.value for e in IntentType]}")
except Exception as e:
    print(f"   [FAIL] {e}")
    sys.exit(1)

print("\n2. Testing intent classification (regex-based, Chinese queries)...")
try:
    from app.retrieval.reranker import Reranker
    reranker = Reranker()
    test_queries = [
        ("报错E1234怎么解决", IntentType.ERROR_CODE),
        ("如何调用支付接口", IntentType.API_USAGE),
        ("能不能支持分期付款", IntentType.FAQ),
        ("费率是多少", IntentType.POLICY),
        ("你们公司在哪里", IntentType.GENERAL),
        ("E1001错误", IntentType.ERROR_CODE),
        ("API接口参数说明", IntentType.API_USAGE),
        ("常见问题FAQ", IntentType.FAQ),
        ("结算周期多久", IntentType.POLICY),
        ("帮助信息", IntentType.GENERAL),
    ]
    passed = 0
    for query, expected in test_queries:
        result = reranker.classify_intent(query)
        status = "[OK]" if result == expected else "[??]"
        if result == expected:
            passed += 1
        print(f"   {status} '{query}' -> {result.value} (expected: {expected.value})")
    print(f"\n   Pass rate: {passed}/{len(test_queries)}")
    if passed >= 8:
        print("   [OK] Intent classification passes >= 80% threshold")
except Exception as e:
    print(f"   [FAIL] {e}")
    import traceback
    traceback.print_exc()

print("\n=== Verification Complete ===")
