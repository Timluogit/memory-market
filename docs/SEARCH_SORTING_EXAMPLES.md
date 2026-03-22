#!/usr/bin/env python3
"""搜索排序功能示例

演示如何使用新的搜索排序API
"""

import requests
from typing import Dict, Any

BASE_URL = "http://localhost:8000/api"


def print_results(title: str, data: Dict[str, Any]):
    """格式化打印搜索结果"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"总数: {data['total']} | 页码: {data['page']}/{(data['total']+data['page_size']-1)//data['page_size']}")

    for i, item in enumerate(data['items'][:5], 1):  # 只显示前5个
        print(f"\n{i}. {item['title']}")
        print(f"   评分: {item['avg_score']:.1f} | 购买: {item['purchase_count']}次 | 收藏: {item['favorite_count']}次")
        print(f"   验证: {item['verification_score'] or 'N/A'} | 价格: {item['price']}分")
        print(f"   分类: {item['category']}")


def example_1_relevance_sorting():
    """示例1: 综合评分排序（默认）"""
    response = requests.get(f"{BASE_URL}/memories", params={
        "sort_by": "relevance",
        "page": 1,
        "page_size": 10
    })
    data = response.json()["data"]
    print_results("综合评分排序（默认）", data)


def example_2_search_with_relevance():
    """示例2: 搜索关键词 + 综合评分"""
    response = requests.get(f"{BASE_URL}/memories", params={
        "query": "agent",
        "sort_by": "relevance",
        "page": 1,
        "page_size": 10
    })
    data = response.json()["data"]
    print_results("搜索 'agent' + 综合评分", data)


def example_3_sort_by_created_at():
    """示例3: 按创建时间排序"""
    response = requests.get(f"{BASE_URL}/memories", params={
        "sort_by": "created_at",
        "page": 1,
        "page_size": 10
    })
    data = response.json()["data"]
    print_results("按创建时间排序", data)


def example_4_sort_by_popularity():
    """示例4: 按购买次数排序（热门）"""
    response = requests.get(f"{BASE_URL}/memories", params={
        "sort_by": "purchase_count",
        "page": 1,
        "page_size": 10
    })
    data = response.json()["data"]
    print_results("按购买次数排序（热门）", data)


def example_5_sort_by_price():
    """示例5: 按价格排序（从低到高）"""
    response = requests.get(f"{BASE_URL}/memories", params={
        "sort_by": "price",
        "page": 1,
        "page_size": 10
    })
    data = response.json()["data"]
    print_results("按价格排序（从低到高）", data)


def example_6_filter_and_sort():
    """示例6: 筛选 + 排序组合"""
    response = requests.get(f"{BASE_URL}/memories", params={
        "category": "OpenAI",
        "min_score": 4.0,
        "max_price": 1000,
        "sort_by": "relevance",
        "page": 1,
        "page_size": 10
    })
    data = response.json()["data"]
    print_results("筛选: OpenAI分类, 评分≥4.0, 价格≤1000分 + 综合评分", data)


def main():
    """运行所有示例"""
    examples = [
        ("综合评分排序（默认）", example_1_relevance_sorting),
        ("搜索关键词 + 综合评分", example_2_search_with_relevance),
        ("按创建时间排序", example_3_sort_by_created_at),
        ("按购买次数排序（热门）", example_4_sort_by_popularity),
        ("按价格排序（从低到高）", example_5_sort_by_price),
        ("筛选 + 排序组合", example_6_filter_and_sort),
    ]

    print("搜索排序功能示例")
    print("=" * 60)

    for title, example_func in examples:
        try:
            example_func()
        except requests.exceptions.ConnectionError:
            print(f"\n⚠️  无法连接到服务器 {BASE_URL}")
            print("请确保服务器正在运行: uvicorn app.main:app --reload")
            break
        except Exception as e:
            print(f"\n❌ 执行示例 '{title}' 时出错: {e}")

    print("\n" + "=" * 60)
    print("示例运行完成！")


if __name__ == "__main__":
    main()
