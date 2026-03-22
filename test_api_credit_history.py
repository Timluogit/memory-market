"""测试积分流水 API"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_credit_history_api():
    """测试积分流水 API"""
    print("=== 测试积分流水 API ===\n")

    # 1. 注册一个新Agent
    print("1. 注册新Agent...")
    register_data = {
        "name": "流水测试Agent",
        "description": "测试积分流水API"
    }
    resp = requests.post(f"{BASE_URL}/agents", json=register_data)
    if resp.status_code != 200:
        print(f"✗ 注册失败: {resp.status_code}")
        print(resp.text)
        return

    agent = resp.json()["data"]
    api_key = agent["api_key"]
    agent_id = agent["agent_id"]
    print(f"✓ 注册成功")
    print(f"  Agent ID: {agent_id}")
    print(f"  API Key: {api_key[:20]}...")
    print(f"  初始积分: {agent['credits']}")

    # 2. 获取积分流水
    print("\n2. 获取积分流水...")
    headers = {"X-API-Key": api_key}
    resp = requests.get(f"{BASE_URL}/agents/me/credits/history", headers=headers)

    if resp.status_code != 200:
        print(f"✗ 获取流水失败: {resp.status_code}")
        print(resp.text)
        return

    result = resp.json()["data"]
    print(f"✓ 获取成功")
    print(f"  总记录数: {result['total']}")
    print(f"  当前页: {result['page']}")
    print(f"  每页数量: {result['page_size']}")

    # 3. 打印流水详情
    print("\n3. 流水详情:")
    for idx, tx in enumerate(result["items"], 1):
        print(f"\n记录 #{idx}:")
        print(f"  交易ID: {tx['tx_id']}")
        print(f"  类型: {tx['tx_type']}")
        print(f"  金额: {tx['amount']}")
        print(f"  变动后余额: {tx['balance_after']}")
        print(f"  描述: {tx['description']}")
        print(f"  时间: {tx['created_at']}")

    # 4. 测试分页
    print("\n4. 测试分页（page=1, page_size=5）...")
    resp = requests.get(
        f"{BASE_URL}/agents/me/credits/history",
        headers=headers,
        params={"page": 1, "page_size": 5}
    )
    if resp.status_code == 200:
        result = resp.json()["data"]
        print(f"✓ 分页请求成功")
        print(f"  返回记录数: {len(result['items'])}")
    else:
        print(f"✗ 分页请求失败: {resp.status_code}")

    print("\n✓ 所有测试完成！")

if __name__ == "__main__":
    test_credit_history_api()
