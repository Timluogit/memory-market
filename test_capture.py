"""测试经验捕获功能"""
import asyncio
import httpx

BASE_URL = "http://localhost:8000/api/v1"

# 测试 Agent 的 API Key
API_KEY = "mk_675aece90791ed00ffadb72e297706f86df254bd16cfda67"


async def test_single_capture():
    """测试单个经验捕获"""
    print("\n=== 测试单个经验捕获 ===\n")

    headers = {"X-API-Key": API_KEY}

    # 成功案例
    success_request = {
        "task_description": "优化抖音投流ROI从1.5提升到2.3",
        "work_log": """
1. 初始问题：抖音广告ROI只有1.5，低于预期
2. 尝试方案A：调整定向人群，年龄从18-24缩小到20-22，兴趣标签增加"美妆教程"
3. 尝试方案B：优化素材，前3秒增加产品特写镜头
4. 尝试方案C：调整出价策略，从oCPM改为手动出价，降低20%
5. 最终结果：组合方案A+B+C后，ROI提升到2.3，转化率提升35%
6. 关键配置：出价=0.8元/千次，定向=20-22岁女性+美妆兴趣，素材开头=产品特写3秒
        """.strip(),
        "outcome": "success",
        "category": "抖音/投流",
        "tags": ["ROI", "优化", "定向", "素材"]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/capture",
            json=success_request,
            headers=headers,
            timeout=30.0
        )

        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")

        if response.status_code == 200:
            data = response.json()["data"]
            if data["success"]:
                print(f"\n✅ 捕获成功！")
                print(f"记忆ID: {data['memory_id']}")
                print(f"分析结果: {data['analysis']}")
            else:
                print(f"\n❌ 捕获失败: {data['message']}")
        else:
            print(f"\n❌ 请求失败: {response.text}")


async def test_failure_capture():
    """测试失败经验捕获"""
    print("\n=== 测试失败经验捕获 ===\n")

    headers = {"X-API-Key": API_KEY}

    # 失败案例
    failure_request = {
        "task_description": "尝试直播带货新话术",
        "work_log": """
1. 目标：测试新的互动话术提升直播间转化率
2. 新话术内容：增加紧迫感表述"最后50个名额"
3. 执行结果：观众反映被冒犯，停留时长下降40%
4. 问题分析：话术过于激进，与品牌调性不符
5. 经验教训：真诚比套路更重要，需要根据品牌调性调整话术风格
        """.strip(),
        "outcome": "failure",
        "category": "抖音/直播",
        "tags": ["直播", "话术", "失败经验"]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/capture",
            json=failure_request,
            headers=headers,
            timeout=30.0
        )

        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")

        if response.status_code == 200:
            data = response.json()["data"]
            if data["success"]:
                print(f"\n✅ 捕获成功！")
                print(f"记忆ID: {data['memory_id']}")
            else:
                print(f"\n❌ 捕获失败: {data['message']}")


async def test_batch_capture():
    """测试批量捕获"""
    print("\n=== 测试批量经验捕获 ===\n")

    headers = {"X-API-Key": API_KEY}

    batch_request = {
        "items": [
            {
                "task_description": "优化视频封面点击率",
                "work_log": "测试了5种不同封面风格，发现高对比度色彩+产品特写效果最好，CTR提升50%",
                "outcome": "success",
                "category": "抖音/运营"
            },
            {
                "task_description": "尝试矩阵账号运营",
                "work_log": "建立了3个矩阵账号，互相导流，总粉丝增长2倍，但维护成本较高",
                "outcome": "partial",
                "category": "抖音/运营"
            },
            {
                "task_description": "测试新的带货产品",
                "work_log": "选品失误，产品定价过高，转化率极低，库存积压",
                "outcome": "failure",
                "category": "抖音/选品"
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/capture/batch",
            json=batch_request,
            headers=headers,
            timeout=60.0
        )

        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")

        if response.status_code == 200:
            data = response.json()["data"]
            print(f"\n✅ 批量捕获完成！")
            print(f"成功: {data['success_count']}个")
            print(f"失败: {data['failure_count']}个")
            print(f"\n详细结果:")
            for i, result in enumerate(data["results"], 1):
                print(f"  {i}. {result['message']}")
                if result['memory_id']:
                    print(f"     记忆ID: {result['memory_id']}")


async def main():
    """运行所有测试"""
    print("开始测试经验捕获功能...")

    try:
        await test_single_capture()
        await test_failure_capture()
        await test_batch_capture()

        print("\n" + "="*50)
        print("测试完成！")
        print("="*50)

    except Exception as e:
        print(f"\n❌ 测试出错: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
