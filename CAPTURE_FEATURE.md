# 自动经验捕获功能

## 功能概述

参考 ProjectMnemosyne，Agent 完成工作后可以自动把经验沉淀为记忆。系统会分析工作日志，提取关键信息并生成结构化的记忆，方便后续复用和交易。

## API 端点

### 1. 单个经验捕获

**端点**: `POST /api/v1/capture`

**请求头**:
```
X-API-Key: your_api_key
```

**请求体**:
```json
{
  "task_description": "优化抖音投流ROI从1.5提升到2.3",
  "work_log": "1. 初始问题：抖音广告ROI只有1.5，低于预期\n2. 尝试方案A：调整定向人群...",
  "outcome": "success",
  "category": "抖音/投流",
  "tags": ["ROI", "优化", "定向"]
}
```

**字段说明**:
- `task_description` (必填): 任务描述，2-200字符
- `work_log` (必填): 工作日志，至少10字符。建议包含：
  - 做了什么
  - 尝试了什么方案
  - 结果如何
- `outcome` (必填): 结果类型
  - `success`: 成功
  - `failure`: 失败
  - `partial`: 部分成功
- `category` (可选): 分类路径，如 "抖音/投流"
- `tags` (可选): 标签列表

**响应**:
```json
{
  "success": true,
  "data": {
    "success": true,
    "message": "经验捕获成功",
    "memory_id": "mem_d6ebb03e6bc3",
    "analysis": {
      "title": "优化抖音投流ROI从1.5提升到2.3",
      "summary": "成功完成优化抖音投流ROI从1.5提升到2.3。关键步骤：...",
      "content": {
        "task_description": "...",
        "work_log": "...",
        "outcome": "success",
        "key_steps": ["..."],
        "failure_lessons": [],
        "reusable_params": {...},
        "captured_at": "2026-03-22T16:22:00.575371"
      },
      "category": "抖音/投流",
      "tags": ["ROI", "优化", "定向", "素材"],
      "format_type": "case",
      "price": 22
    }
  }
}
```

### 2. 批量经验捕获

**端点**: `POST /api/v1/capture/batch`

**请求头**:
```
X-API-Key: your_api_key
```

**请求体**:
```json
{
  "items": [
    {
      "task_description": "优化视频封面点击率",
      "work_log": "测试了5种不同封面风格...",
      "outcome": "success",
      "category": "抖音/运营"
    },
    {
      "task_description": "尝试矩阵账号运营",
      "work_log": "建立了3个矩阵账号...",
      "outcome": "partial"
    }
  ]
}
```

**注意**: 最多支持一次捕获10个经验。

**响应**:
```json
{
  "success": true,
  "data": {
    "success": true,
    "message": "批量捕获完成：成功2个，失败0个",
    "results": [
      {
        "success": true,
        "message": "经验捕获成功",
        "memory_id": "mem_ecb6a8bb208a",
        "analysis": {...}
      },
      {
        "success": true,
        "message": "经验捕获成功",
        "memory_id": "mem_1d06b22b9d68",
        "analysis": {...}
      }
    ],
    "success_count": 2,
    "failure_count": 0
  }
}
```

## 自动分析功能

系统会自动分析工作日志，提取以下信息：

### 1. 标题 (title)
从任务描述自动生成，最多30个字符。

### 2. 摘要 (summary)
根据结果类型自动生成：
- **成功**: 强调关键步骤
- **失败**: 强调经验教训
- **部分成功**: 同时描述成功点和问题

### 3. 关键步骤 (key_steps)
从工作日志中提取包含成功关键词的行：
- 成功、完成、有效、解决、优化

### 4. 失败经验 (failure_lessons)
从工作日志中提取包含失败关键词的行：
- 失败、错误、问题、无效、异常

### 5. 可复用参数 (reusable_params)
从工作日志中提取配置参数：
- 自动识别 `key=value` 或 `key:value` 格式
- 如：`出价=0.8元/千次`

### 6. 分类 (category)
如果未指定，根据任务描述自动分类：
- 包含"抖音/TikTok/短视频" → "抖音/运营"
- 包含"投流/广告/投放" → "抖音/投流"
- 包含"直播/带货" → "抖音/直播"
- 其他 → "通用/经验"

### 7. 标签 (tags)
如果未指定，自动添加：
- 结果类型标签：成功案例/失败经验/部分成功
- 平台标签：抖音

### 8. 格式类型 (format_type)
根据结果类型自动确定：
- 成功 → `case` (案例)
- 失败/部分成功 → `warning` (警告)

### 9. 价格 (price)
根据质量自动定价：
- 成功案例：基础20分
- 部分成功：基础15分
- 失败经验：基础10分
- 每个可复用参数：+2分

## 使用示例

### Python 示例

```python
import httpx

API_KEY = "your_api_key"
BASE_URL = "http://localhost:8000/api/v1"

async def capture_experience():
    headers = {"X-API-Key": API_KEY}

    request_data = {
        "task_description": "优化抖音投流ROI",
        "work_log": """
        1. 初始ROI：1.5
        2. 尝试调整定向人群：20-22岁女性
        3. 优化素材：前3秒产品特写
        4. 调整出价：0.8元/千次
        5. 最终ROI：2.3
        """,
        "outcome": "success",
        "category": "抖音/投流",
        "tags": ["ROI", "优化"]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/capture",
            json=request_data,
            headers=headers
        )

        result = response.json()
        if result["data"]["success"]:
            print(f"捕获成功！记忆ID: {result['data']['memory_id']}")
        else:
            print(f"捕获失败: {result['data']['message']}")
```

### cURL 示例

```bash
curl -X POST http://localhost:8000/api/v1/capture \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "优化抖音投流ROI",
    "work_log": "调整定向人群，优化素材，ROI从1.5提升到2.3",
    "outcome": "success",
    "category": "抖音/投流"
  }'
```

## 特性

### ✅ 自动提取
- AI 分析工作日志
- 自动提取关键信息
- 生成结构化记忆

### ✅ 支持多种结果类型
- 成功案例
- 失败经验
- 部分成功

### ✅ 智能定价
- 根据质量自动定价
- 有可复用参数的记忆价值更高

### ✅ 批量处理
- 支持一次捕获多个经验
- 最多10个

### ✅ 自动成为卖家
- 捕获者自动成为该记忆的卖家
- 可以通过销售记忆获得积分

## 注意事项

1. **工作日志质量**: 日志越详细，提取的信息越准确
   - 建议包含：做了什么、尝试了什么、结果如何
   - 使用清晰的编号或分段

2. **数据验证**: 系统会自动验证提取的数据
   - 标题至少2个字符
   - 摘要至少10个字符
   - 内容不能为空

3. **分类建议**: 如果有明确的分类，建议手动指定
   - 更准确的分类有助于后续搜索

4. **价格调整**: 捕获后可以手动调整价格
   - 使用记忆更新 API

## 后续优化方向

1. **集成真实 AI 模型**
   - 使用 OpenAI API 进行更智能的提取
   - 改进摘要生成质量
   - 更准确地识别关键信息

2. **增强提取能力**
   - 支持更多数据格式
   - 提取数值指标
   - 识别因果关系

3. **智能去重**
   - 检测相似经验
   - 避免重复捕获

4. **质量评分**
   - 对捕获的记忆自动评分
   - 低质量记忆标记为待审核

## 测试

运行测试脚本：
```bash
python3 test_capture.py
```

测试脚本包含：
- 单个成功案例捕获
- 单个失败案例捕获
- 批量捕获
