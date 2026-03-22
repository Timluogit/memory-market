#!/usr/bin/env python
"""快速测试语义搜索 API

启动服务器后运行此脚本测试搜索功能
"""
import httpx
import asyncio
import json


BASE_URL = "http://localhost:8000"


async def test_search_api():
    """测试搜索 API"""
    print("=" * 60)
    print("语义搜索 API 测试")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        # 测试三种搜索模式
        test_cases = [
            {
                "name": "关键词搜索",
                "params": {"search_type": "keyword", "query": "Python", "page_size": 5}
            },
            {
                "name": "语义搜索",
                "params": {"search_type": "semantic", "query": "API开发", "page_size": 5}
            },
            {
                "name": "混合搜索",
                "params": {"search_type": "hybrid", "query": "web安全", "page_size": 5}
            },
            {
                "name": "带筛选的混合搜索",
                "params": {
                    "search_type": "hybrid",
                    "query": "Python",
                    "category": "编程/Python",
                    "page_size": 5
                }
            }
        ]

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n测试 {i}: {test_case['name']}")
            print("-" * 60)

            try:
                response = await client.get(
                    f"{BASE_URL}/memories",
                    params=test_case['params'],
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        result = data['data']
                        print(f"✓ 成功: 找到 {result['total']} 条结果")

                        if result['items']:
                            print("  结果:")
                            for j, item in enumerate(result['items'][:3], 1):
                                print(f"    {j}. {item['title']}")
                                print(f"       分类: {item['category']}")
                                print(f"       评分: {item['avg_score']}")
                        else:
                            print("  (无结果)")
                    else:
                        print(f"✗ 失败: {data.get('message', '未知错误')}")
                else:
                    print(f"✗ HTTP {response.status_code}")
                    print(f"  {response.text}")

            except httpx.ConnectError:
                print(f"✗ 连接失败: 请确保服务器运行在 {BASE_URL}")
                break
            except Exception as e:
                print(f"✗ 错误: {e}")

        # 测试错误处理
        print("\n\n错误处理测试")
        print("-" * 60)

        # 无效的 search_type
        print("\n1. 无效的 search_type:")
        response = await client.get(
            f"{BASE_URL}/memories",
            params={"search_type": "invalid", "query": "test"},
            timeout=10.0
        )
        print(f"   状态码: {response.status_code} (期望 400)")
        if response.status_code == 400:
            print("   ✓ 正确返回错误")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    print("\n提示: 请先启动服务器: uvicorn app.main:app --reload\n")
    asyncio.run(test_search_api())
