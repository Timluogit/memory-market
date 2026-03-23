"""
MCP 工具使用示例

本文件提供了所有34个MCP工具的使用示例，每个工具至少包含2个示例。
"""
import asyncio
from unittest.mock import AsyncMock
from mcp_tools.team_mcp import TeamMCPTools


# 创建模拟数据库工厂
def create_mock_db():
    """创建模拟数据库会话"""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.close = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock()
    return db


def create_mock_db_factory():
    """创建模拟数据库工厂"""
    return lambda: create_mock_db()


async def main():
    """主函数 - 运行所有示例"""
    # 初始化工具
    db_factory = create_mock_db_factory()
    tools = TeamMCPTools(db_factory)

    print("=" * 60)
    print("MCP 工具使用示例")
    print("=" * 60)

    # ========== 团队管理（6个） ==========
    print("\n【团队管理示例】")

    # 示例1: create_team - 创建团队
    print("\n1. create_team - 创建团队")
    print("示例1-1: 创建简单团队")
    print("""
    result = await tools.create_team(
        owner_agent_id="agent_001",
        name="我的团队",
        description="这是一个测试团队"
    )
    print(f"团队ID: {result['team_id']}")
    print(f"团队名称: {result['name']}")
    """)

    print("示例1-2: 创建带详细描述的团队")
    print("""
    result = await tools.create_team(
        owner_agent_id="agent_001",
        name="开发团队",
        description="专注于AI开发的技术团队"
    )
    print(f"团队创建成功: {result['name']}")
    """)

    # 示例2: get_team - 获取团队详情
    print("\n2. get_team - 获取团队详情")
    print("示例2-1: 获取基本信息")
    print("""
    team = await tools.get_team(team_id="team_001")
    print(f"团队: {team['name']}")
    print(f"所有者: {team['owner_name']}")
    print(f"成员数: {team['member_count']}")
    """)

    print("示例2-2: 获取完整团队信息")
    print("""
    team = await tools.get_team(team_id="team_001")
    print(f"团队ID: {team['team_id']}")
    print(f"名称: {team['name']}")
    print(f"描述: {team['description']}")
    print(f"积分: {team['credits']}")
    print(f"总收入: {team['total_earned']}")
    print(f"总支出: {team['total_spent']}")
    """)

    # 示例3: update_team - 更新团队信息
    print("\n3. update_team - 更新团队信息")
    print("示例3-1: 更新团队名称")
    print("""
    result = await tools.update_team(
        team_id="team_001",
        owner_agent_id="agent_001",
        name="新团队名称"
    )
    print(f"更新后的名称: {result['name']}")
    """)

    print("示例3-2: 更新团队描述")
    print("""
    result = await tools.update_team(
        team_id="team_001",
        owner_agent_id="agent_001",
        description="更新后的团队描述"
    )
    print(f"更新后的描述: {result['description']}")
    """)

    # 示例4: delete_team - 删除团队
    print("\n4. delete_team - 删除团队")
    print("示例4-1: 删除测试团队")
    print("""
    result = await tools.delete_team(
        team_id="team_001",
        owner_agent_id="agent_001"
    )
    print(result['message'])
    """)

    print("示例4-2: 删除临时团队")
    print("""
    result = await tools.delete_team(
        team_id="temp_team_123",
        owner_agent_id="agent_001"
    )
    if result['success']:
        print("团队已成功删除")
    """)

    # 示例5: list_teams - 列出团队
    print("\n5. list_teams - 列出团队")
    print("示例5-1: 获取所有团队")
    print("""
    result = await tools.list_teams()
    print(f"共有 {result['total']} 个团队:")
    for team in result['teams']:
        print(f"  - {team['name']} ({team['member_count']} 成员)")
    """)

    print("示例5-2: 获取特定Agent创建的团队")
    print("""
    result = await tools.list_teams(owner_agent_id="agent_001")
    print(f"Agent001 创建了 {result['total']} 个团队:")
    for team in result['teams']:
        print(f"  - {team['name']}")
    """)

    # 示例6: get_team_stats - 获取团队统计
    print("\n6. get_team_stats - 获取团队统计")
    print("示例6-1: 查看团队积分")
    print("""
    stats = await tools.get_team_stats(team_id="team_001")
    print(f"团队积分: {stats['credits']}")
    print(f"总收入: {stats['total_earned']}")
    print(f"总支出: {stats['total_spent']}")
    """)

    print("示例6-2: 分析团队财务状况")
    print("""
    stats = await tools.get_team_stats(team_id="team_001")
    net_profit = stats['total_earned'] - stats['total_spent']
    print(f"净利润: {net_profit}")
    print(f"当前余额: {stats['credits']}")
    """)

    # ========== 成员管理（5个） ==========
    print("\n【成员管理示例】")

    # 示例7: invite_member - 生成邀请码
    print("\n7. invite_member - 生成邀请码")
    print("示例7-1: 生成7天有效邀请码")
    print("""
    invite = await tools.invite_member(
        team_id="team_001",
        expires_days=7
    )
    print(f"邀请码: {invite['code']}")
    print(f"过期时间: {invite['expires_at']}")
    """)

    print("示例7-2: 生成30天长期邀请码")
    print("""
    invite = await tools.invite_member(
        team_id="team_001",
        expires_days=30
    )
    print(f"长期邀请码: {invite['code']}")
    print(f"有效期: 30天")
    """)

    # 示例8: join_team - 加入团队
    print("\n8. join_team - 加入团队")
    print("示例8-1: 使用邀请码加入团队")
    print("""
    result = await tools.join_team(
        agent_id="agent_002",
        invite_code="ABC12345"
    )
    print(result['message'])
    print(f"角色: {result['role']}")
    """)

    print("示例8-2: 批量加入多个团队")
    print("""
    codes = ["ABC12345", "XYZ67890"]
    for code in codes:
        result = await tools.join_team(
            agent_id="agent_002",
            invite_code=code
        )
        print(f"加入团队: {result['team_id']}")
    """)

    # 示例9: list_members - 列出成员
    print("\n9. list_members - 列出成员")
    print("示例9-1: 获取所有成员")
    print("""
    result = await tools.list_members(team_id="team_001")
    print(f"团队成员 ({result['total']} 人):")
    for member in result['members']:
        print(f"  - {member['agent_name']} ({member['role']})")
    """)

    print("示例9-2: 统计各角色人数")
    print("""
    result = await tools.list_members(team_id="team_001")
    role_count = {}
    for member in result['members']:
        role = member['role']
        role_count[role] = role_count.get(role, 0) + 1

    print("角色分布:")
    for role, count in role_count.items():
        print(f"  {role}: {count} 人")
    """)

    # 示例10: update_member_role - 更新成员角色
    print("\n10. update_member_role - 更新成员角色")
    print("示例10-1: 提升为管理员")
    print("""
    result = await tools.update_member_role(
        team_id="team_001",
        member_id=2,
        new_role="admin"
    )
    print(f"{result['agent_id']} 现在是 {result['role']}")
    """)

    print("示例10-2: 降级为普通成员")
    print("""
    result = await tools.update_member_role(
        team_id="team_001",
        member_id=2,
        new_role="member"
    )
    print(f"成员角色已更新为 {result['role']}")
    """)

    # 示例11: remove_member - 移除成员
    print("\n11. remove_member - 移除成员")
    print("示例11-1: 移除不活跃成员")
    print("""
    result = await tools.remove_member(
        team_id="team_001",
        member_id=3
    )
    print(result['message'])
    """)

    print("示例11-2: 批量清理成员")
    print("""
    member_ids = [4, 5, 6]
    for member_id in member_ids:
        result = await tools.remove_member(
            team_id="team_001",
            member_id=member_id
        )
        print(f"成员 {member_id}: {result['message']}")
    """)

    # ========== 团队记忆（6个） ==========
    print("\n【团队记忆示例】")

    # 示例12: create_team_memory - 创建团队记忆
    print("\n12. create_team_memory - 创建团队记忆")
    print("示例12-1: 创建项目文档")
    print("""
    memory = await tools.create_team_memory(
        team_id="team_001",
        creator_agent_id="agent_001",
        title="项目文档",
        category="文档",
        summary="项目相关文档",
        content={
            "sections": [
                {"title": "概述", "content": "项目概述..."},
                {"title": "技术栈", "content": "Python + FastAPI"}
            ]
        },
        tags=["项目", "文档"]
    )
    print(f"记忆ID: {memory['memory_id']}")
    """)

    print("示例12-2: 创建会议记录")
    print("""
    memory = await tools.create_team_memory(
        team_id="team_001",
        creator_agent_id="agent_001",
        title="2024-01-01 团队会议",
        category="会议记录",
        summary="周例会记录",
        content={
            "attendees": ["Agent001", "Agent002"],
            "agenda": ["项目进度", "下周计划"],
            "decisions": ["决定使用FastAPI"]
        },
        tags=["会议", "周会"],
        format_type="meeting"
    )
    print(f"会议记录已创建: {memory['title']}")
    """)

    # 示例13: get_team_memory - 获取团队记忆
    print("\n13. get_team_memory - 获取团队记忆")
    print("示例13-1: 获取完整记忆")
    print("""
    memory = await tools.get_team_memory(
        team_id="team_001",
        memory_id="mem_001",
        request_agent_id="agent_001"
    )
    print(f"标题: {memory['title']}")
    print(f"分类: {memory['category']}")
    print(f"内容: {memory['content']}")
    """)

    print("示例13-2: 获取并处理记忆内容")
    print("""
    memory = await tools.get_team_memory(
        team_id="team_001",
        memory_id="mem_001",
        request_agent_id="agent_001"
    )
    # 处理内容
    for section in memory['content']['sections']:
        print(f"{section['title']}: {section['content']}")
    """)

    # 示例14: update_team_memory - 更新团队记忆
    print("\n14. update_team_memory - 更新团队记忆")
    print("示例14-1: 更新标题和摘要")
    print("""
    memory = await tools.update_team_memory(
        team_id="team_001",
        memory_id="mem_001",
        request_agent_id="agent_001",
        updates={
            "title": "新标题",
            "summary": "更新后的摘要"
        }
    )
    print(f"记忆已更新: {memory['title']}")
    """)

    print("示例14-2: 追加内容")
    print("""
    memory = await tools.get_team_memory(
        team_id="team_001",
        memory_id="mem_001",
        request_agent_id="agent_001"
    )
    original_content = memory['content']
    original_content['sections'].append({
        "title": "新增章节",
        "content": "新内容..."
    })

    updated = await tools.update_team_memory(
        team_id="team_001",
        memory_id="mem_001",
        request_agent_id="agent_001",
        updates={"content": original_content}
    )
    print("内容已追加")
    """)

    # 示例15: delete_team_memory - 删除团队记忆
    print("\n15. delete_team_memory - 删除团队记忆")
    print("示例15-1: 删除过期文档")
    print("""
    result = await tools.delete_team_memory(
        team_id="team_001",
        memory_id="mem_001",
        request_agent_id="agent_001"
    )
    print(result['message'])
    """)

    print("示例15-2: 批量删除测试数据")
    print("""
    memory_ids = ["mem_test_1", "mem_test_2", "mem_test_3"]
    for memory_id in memory_ids:
        result = await tools.delete_team_memory(
            team_id="team_001",
            memory_id=memory_id,
            request_agent_id="agent_001"
        )
        print(f"记忆 {memory_id}: {result['message']}")
    """)

    # 示例16: search_team_memories - 搜索团队记忆
    print("\n16. search_team_memories - 搜索团队记忆")
    print("示例16-1: 关键词搜索")
    print("""
    result = await tools.search_team_memories(
        team_id="team_001",
        query="项目"
    )
    print(f"找到 {result['total']} 条相关记忆:")
    for item in result['items']:
        print(f"  - {item['title']}")
    """)

    print("示例16-2: 分类搜索")
    print("""
    result = await tools.search_team_memories(
        team_id="team_001",
        category="会议记录"
    )
    print(f"会议记录 ({result['total']} 条):")
    for item in result['items']:
        print(f"  - {item['title']} - {item['summary']}")
    """)

    # 示例17: list_team_memories - 列出团队记忆
    print("\n17. list_team_memories - 列出团队记忆")
    print("示例17-1: 获取所有记忆")
    print("""
    result = await tools.list_team_memories(team_id="team_001")
    print(f"团队记忆 ({result['total']} 条):")
    for item in result['items']:
        print(f"  - {item['title']} ({item['category']})")
    """)

    print("示例17-2: 分页获取记忆")
    print("""
    page = 1
    while True:
        result = await tools.list_team_memories(
            team_id="team_001",
            page=page,
            page_size=10
        )
        if not result['items']:
            break
        print(f"第 {page} 页:")
        for item in result['items']:
            print(f"  - {item['title']}")
        page += 1
    """)

    # ========== 团队积分（4个） ==========
    print("\n【团队积分示例】")

    # 示例18: get_team_credits - 获取团队积分
    print("\n18. get_team_credits - 获取团队积分")
    print("示例18-1: 查看当前积分")
    print("""
    info = await tools.get_team_credits(team_id="team_001")
    print(f"团队积分: {info['credits']}")
    print(f"总收入: {info['total_earned']}")
    print(f"总支出: {info['total_spent']}")
    """)

    print("示例18-2: 计算净收入")
    print("""
    info = await tools.get_team_credits(team_id="team_001")
    net_income = info['total_earned'] - info['total_spent']
    print(f"净收入: {net_income}")
    print(f"当前余额: {info['credits']}")
    """)

    # 示例19: add_team_credits - 充值团队积分
    print("\n19. add_team_credits - 充值团队积分")
    print("示例19-1: 充值1000积分")
    print("""
    result = await tools.add_team_credits(
        team_id="team_001",
        agent_id="agent_001",
        amount=1000
    )
    print(f"充值成功: {result['amount']} 积分")
    print(f"当前余额: {result['credits']}")
    """)

    print("示例19-2: 多次充值")
    print("""
    amounts = [500, 1000, 2000]
    for amount in amounts:
        result = await tools.add_team_credits(
            team_id="team_001",
            agent_id="agent_001",
            amount=amount
        )
        print(f"充值 {amount} 积分, 余额: {result['credits']}")
    """)

    # 示例20: transfer_credits - 转账
    print("\n20. transfer_credits - 转账")
    print("示例20-1: 转账给成员")
    print("""
    result = await tools.transfer_credits(
        team_id="team_001",
        from_agent_id="agent_001",
        to_agent_id="agent_002",
        amount=500
    )
    print(f"转账成功: {result['amount']} 积分")
    print(f"团队余额: {result['team_credits']}")
    print(f"成员余额: {result['agent_credits']}")
    """)

    print("示例20-2: 团队分红")
    print("""
    members = ["agent_002", "agent_003", "agent_004"]
    bonus = 300  # 每人分红300积分

    for member_id in members:
        result = await tools.transfer_credits(
            team_id="team_001",
            from_agent_id="agent_001",
            to_agent_id=member_id,
            amount=bonus
        )
        print(f"给 {member_id} 分红 {bonus} 积分")
    """)

    # 示例21: get_credit_transactions - 获取交易历史
    print("\n21. get_credit_transactions - 获取交易历史")
    print("示例21-1: 查看最近交易")
    print("""
    history = await tools.get_credit_transactions(team_id="team_001")
    print(f"最近 {history['total']} 笔交易:")
    for tx in history['items']:
        print(f"  {tx['tx_type']}: {tx['amount']} - {tx['description']}")
    """)

    print("示例21-2: 统计交易类型")
    print("""
    history = await tools.get_credit_transactions(team_id="team_001")
    tx_stats = {}
    for tx in history['items']:
        tx_type = tx['tx_type']
        tx_stats[tx_type] = tx_stats.get(tx_type, 0) + 1

    print("交易统计:")
    for tx_type, count in tx_stats.items():
        print(f"  {tx_type}: {count} 笔")
    """)

    # ========== 团队活动（2个） ==========
    print("\n【团队活动示例】")

    # 示例22: get_team_activities - 获取团队活动
    print("\n22. get_team_activities - 获取团队活动")
    print("示例22-1: 查看所有活动")
    print("""
    activities = await tools.get_team_activities(team_id="team_001")
    print(f"团队活动 ({activities['total']} 条):")
    for activity in activities['items']:
        print(f"  {activity['agent_name']} - {activity['activity_type']}")
    print(f"    {activity['description']}")
    """)

    print("示例22-2: 查看特定类型活动")
    print("""
    activities = await tools.get_team_activities(
        team_id="team_001",
        activity_type="create_memory"
    )
    print(f"创建记忆活动 ({activities['total']} 条):")
    for activity in activities['items']:
        print(f"  {activity['agent_name']}: {activity['description']}")
    """)

    # 示例23: log_activity - 记录活动
    print("\n23. log_activity - 记录活动")
    print("示例23-1: 记录任务完成")
    print("""
    result = await tools.log_activity(
        team_id="team_001",
        agent_id="agent_001",
        activity_type="task_complete",
        description="完成项目里程碑"
    )
    print(f"活动已记录: {result['activity_id']}")
    """)

    print("示例23-2: 记录带额外信息的活动")
    print("""
    result = await tools.log_activity(
        team_id="team_001",
        agent_id="agent_001",
        activity_type="milestone",
        description="达成里程碑",
        related_id="project_001",
        extra_data={
            "progress": "50%",
            "milestone": "Alpha版本发布"
        }
    )
    print(f"里程碑活动已记录")
    """)

    # ========== 团队统计（1个） ==========
    print("\n【团队统计示例】")

    # 示例24: get_team_insights - 获取团队洞察
    print("\n24. get_team_insights - 获取团队洞察")
    print("示例24-1: 查看团队概况")
    print("""
    insights = await tools.get_team_insights(team_id="team_001")
    print(f"团队名称: {insights['name']}")
    print(f"成员数: {insights['member_count']}")
    print(f"记忆数: {insights['memory_count']}")
    print(f"积分: {insights['credits']}")
    """)

    print("示例24-2: 分析团队活跃度")
    print("""
    insights = await tools.get_team_insights(team_id="team_001")
    active_ratio_7d = insights['active_members_7d'] / insights['member_count']
    active_ratio_30d = insights['active_members_30d'] / insights['member_count']

    print(f"7天活跃率: {active_ratio_7d:.1%}")
    print(f"30天活跃率: {active_ratio_30d:.1%}")

    if active_ratio_7d < 0.5:
        print("提醒: 7天活跃率较低，建议激活团队成员")
    """)

    # ========== 总结 ==========
    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)
    print("\n工具统计:")
    print("  团队管理: 6 个")
    print("  成员管理: 5 个")
    print("  团队记忆: 6 个")
    print("  团队积分: 4 个")
    print("  团队活动: 2 个")
    print("  团队统计: 1 个")
    print("  总计: 24 个新工具")
    print("\n每个工具都提供了至少2个使用示例。")
    print("更多详情请参考 docs/mcp-tools-guide.md")


# 最佳实践示例
async def best_practices():
    """最佳实践示例"""
    print("\n【最佳实践】")

    # 1. 错误处理
    print("\n1. 错误处理")
    print("""
    result = await tools.create_team(
        owner_agent_id="agent_001",
        name="测试团队"
    )

    if "error" in result:
        print(f"操作失败: {result['error']}")
        # 处理错误
    else:
        print(f"操作成功: {result['team_id']}")
        # 继续处理
    """)

    # 2. 批量操作
    print("\n2. 批量操作")
    print("""
    # 批量创建记忆
    memories_data = [
        {"title": "文档1", "category": "文档", "summary": "摘要1"},
        {"title": "文档2", "category": "文档", "summary": "摘要2"},
        {"title": "文档3", "category": "文档", "summary": "摘要3"},
    ]

    created = []
    failed = []

    for data in memories_data:
        result = await tools.create_team_memory(
            team_id="team_001",
            creator_agent_id="agent_001",
            content={},
            **data
        )
        if "error" in result:
            failed.append(data)
        else:
            created.append(result)

    print(f"成功: {len(created)}, 失败: {len(failed)}")
    """)

    # 3. 分页处理
    print("\n3. 分页处理")
    print("""
    async def fetch_all_memories(team_id):
        all_memories = []
        page = 1

        while True:
            result = await tools.list_team_memories(
                team_id=team_id,
                page=page,
                page_size=50
            )
            if not result['items']:
                break
            all_memories.extend(result['items'])
            page += 1

        return all_memories

    memories = await fetch_all_memories("team_001")
    print(f"总共获取 {len(memories)} 条记忆")
    """)

    # 4. 权限验证
    print("\n4. 权限验证")
    print("""
    async def ensure_owner(team_id, agent_id):
        team = await tools.get_team(team_id=team_id)

        if "error" in team:
            raise Exception("团队不存在")

        if team['owner_agent_id'] != agent_id:
            raise Exception("只有Owner可以执行此操作")

        return True

    # 使用
    await ensure_owner("team_001", "agent_001")
    result = await tools.delete_team(
        team_id="team_001",
        owner_agent_id="agent_001"
    )
    """)

    # 5. 数据分析
    print("\n5. 数据分析")
    print("""
    async def analyze_team_activity(team_id, days=7):
        """分析团队最近活动"""
        from datetime import datetime, timedelta

        activities = await tools.get_team_activities(team_id=team_id)
        cutoff_date = datetime.now() - timedelta(days=days)

        recent_activities = [
            a for a in activities['items']
            if a['created_at'] >= cutoff_date
        ]

        # 统计活动类型
        type_stats = {}
        for activity in recent_activities:
            atype = activity['activity_type']
            type_stats[atype] = type_stats.get(atype, 0) + 1

        # 统计活跃成员
        active_members = set(a['agent_id'] for a in recent_activities)

        return {
            "total_activities": len(recent_activities),
            "activity_types": type_stats,
            "active_members": len(active_members),
            "avg_per_day": len(recent_activities) / days
        }

    stats = await analyze_team_activity("team_001", days=7)
    print(f"最近7天活动: {stats['total_activities']}")
    print(f"活跃成员: {stats['active_members']}")
    print(f"日均活动: {stats['avg_per_day']:.1f}")
    """)


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())

    # 运行最佳实践
    print("\n\n" + "=" * 60)
    asyncio.run(best_practices())
