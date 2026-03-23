"""团队相关 MCP 工具扩展

提供24个团队相关的MCP工具：
- 团队管理（6个）
- 成员管理（5个）
- 团队记忆（6个）
- 团队积分（4个）
- 团队活动（2个）
- 团队统计（1个）
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


class TeamMCPTools:
    """团队相关MCP工具集"""

    def __init__(self, db_session_factory):
        """初始化工具

        Args:
            db_session_factory: 数据库会话工厂函数
        """
        self.get_db = db_session_factory

    # ============ 团队管理（6个） ============

    async def create_team(
        self,
        owner_agent_id: str,
        name: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """创建团队

        Args:
            owner_agent_id: 创建者Agent ID
            name: 团队名称
            description: 团队描述

        Returns:
            团队信息
        """
        from app.services.team_service import TeamService
        from app.models.schemas import TeamCreate

        db = self.get_db()
        try:
            req = TeamCreate(name=name, description=description)
            team = await TeamService.create_team(db, owner_agent_id, req)

            return {
                "team_id": team.team_id,
                "name": team.name,
                "description": team.description,
                "owner_agent_id": team.owner_agent_id,
                "member_count": team.member_count,
                "memory_count": team.memory_count,
                "credits": team.credits,
                "is_active": team.is_active,
                "created_at": team.created_at.isoformat()
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def get_team(
        self,
        team_id: str
    ) -> Dict[str, Any]:
        """获取团队详情

        Args:
            team_id: 团队ID

        Returns:
            团队详情
        """
        from app.services.team_service import TeamService

        db = self.get_db()
        try:
            team = await TeamService.get_team_detail(db, team_id)

            if not team:
                return {"error": "团队不存在"}

            return team.model_dump()
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def update_team(
        self,
        team_id: str,
        owner_agent_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """更新团队信息

        Args:
            team_id: 团队ID
            owner_agent_id: 所有者Agent ID
            name: 新名称（可选）
            description: 新描述（可选）

        Returns:
            更新后的团队信息
        """
        from app.services.team_service import TeamService
        from app.models.schemas import TeamUpdate

        db = self.get_db()
        try:
            req = TeamUpdate(name=name, description=description)
            team = await TeamService.update_team(db, team_id, owner_agent_id, req)

            if not team:
                return {"error": "团队不存在或无权限"}

            return {
                "team_id": team.team_id,
                "name": team.name,
                "description": team.description,
                "owner_agent_id": team.owner_agent_id,
                "member_count": team.member_count,
                "memory_count": team.memory_count,
                "credits": team.credits,
                "updated_at": team.updated_at.isoformat()
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def delete_team(
        self,
        team_id: str,
        owner_agent_id: str
    ) -> Dict[str, Any]:
        """删除团队（软删除）

        Args:
            team_id: 团队ID
            owner_agent_id: 所有者Agent ID

        Returns:
            删除结果
        """
        from app.services.team_service import TeamService

        db = self.get_db()
        try:
            success = await TeamService.delete_team(db, team_id, owner_agent_id)

            if not success:
                return {"error": "团队不存在或无权限"}

            return {"success": True, "message": "团队已删除"}
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def list_teams(
        self,
        owner_agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """列出我的团队

        Args:
            owner_agent_id: Agent ID（可选，指定则只返回该Agent创建的团队）

        Returns:
            团队列表
        """
        from app.models.tables import Team

        db = self.get_db()
        try:
            query = db.query(Team).where(Team.is_active == True)

            if owner_agent_id:
                query = query.where(Team.owner_agent_id == owner_agent_id)

            teams = await query.order_by(Team.created_at.desc()).all()

            return {
                "teams": [
                    {
                        "team_id": t.team_id,
                        "name": t.name,
                        "description": t.description,
                        "owner_agent_id": t.owner_agent_id,
                        "member_count": t.member_count,
                        "memory_count": t.memory_count,
                        "credits": t.credits,
                        "created_at": t.created_at.isoformat()
                    }
                    for t in teams
                ],
                "total": len(teams)
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def get_team_stats(
        self,
        team_id: str
    ) -> Dict[str, Any]:
        """获取团队统计

        Args:
            team_id: 团队ID

        Returns:
            团队统计信息
        """
        from app.services.team_service import TeamService

        db = self.get_db()
        try:
            info = await TeamService.get_credits_info(db, team_id)

            if not info:
                return {"error": "团队不存在"}

            return info
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    # ============ 成员管理（5个） ============

    async def invite_member(
        self,
        team_id: str,
        expires_days: int = 7
    ) -> Dict[str, Any]:
        """生成邀请码

        Args:
            team_id: 团队ID
            expires_days: 有效天数

        Returns:
            邀请码信息
        """
        from app.services.team_service import MemberService

        db = self.get_db()
        try:
            invite = await MemberService.generate_invite_code(db, team_id, expires_days)

            return {
                "invite_code_id": invite.invite_code_id,
                "code": invite.code,
                "team_id": invite.team_id,
                "expires_at": invite.expires_at.isoformat(),
                "created_at": invite.created_at.isoformat()
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def join_team(
        self,
        agent_id: str,
        invite_code: str
    ) -> Dict[str, Any]:
        """通过邀请码加入团队

        Args:
            agent_id: Agent ID
            invite_code: 邀请码

        Returns:
            加入结果
        """
        from app.services.team_service import MemberService

        db = self.get_db()
        try:
            result = await MemberService.join_team_by_code(db, agent_id, invite_code)

            return {
                "team_id": result["team_id"],
                "role": result["role"],
                "message": "成功加入团队"
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def list_members(
        self,
        team_id: str
    ) -> Dict[str, Any]:
        """列出团队成员

        Args:
            team_id: 团队ID

        Returns:
            成员列表
        """
        from app.services.team_service import TeamService

        db = self.get_db()
        try:
            members = await TeamService.get_team_members(db, team_id)

            return {
                "members": [m.model_dump() for m in members],
                "total": len(members)
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def update_member_role(
        self,
        team_id: str,
        member_id: int,
        new_role: str
    ) -> Dict[str, Any]:
        """更新成员角色

        Args:
            team_id: 团队ID
            member_id: 成员ID
            new_role: 新角色（admin/member）

        Returns:
            更新结果
        """
        from app.services.team_service import MemberService

        db = self.get_db()
        try:
            member = await MemberService.update_member_role(db, team_id, member_id, new_role)

            if not member:
                return {"error": "成员不存在或无法修改"}

            return {
                "member_id": member.id,
                "agent_id": member.agent_id,
                "role": member.role,
                "message": "角色更新成功"
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def remove_member(
        self,
        team_id: str,
        member_id: int
    ) -> Dict[str, Any]:
        """移除成员

        Args:
            team_id: 团队ID
            member_id: 成员ID

        Returns:
            移除结果
        """
        from app.services.team_service import MemberService

        db = self.get_db()
        try:
            success = await MemberService.remove_member(db, team_id, member_id)

            if not success:
                return {"error": "成员不存在或无法移除"}

            return {"success": True, "message": "成员已移除"}
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    # ============ 团队记忆（6个） ============

    async def create_team_memory(
        self,
        team_id: str,
        creator_agent_id: str,
        title: str,
        category: str,
        summary: str,
        content: Dict[str, Any],
        tags: List[str] = None,
        format_type: str = "template",
        price: int = 0,
        team_access_level: str = "team_only",
        verification_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """创建团队记忆

        Args:
            team_id: 团队ID
            creator_agent_id: 创建者Agent ID
            title: 标题
            category: 分类
            summary: 摘要
            content: 内容（JSON）
            tags: 标签列表
            format_type: 格式类型
            price: 价格
            team_access_level: 可见性
            verification_data: 验证数据

        Returns:
            创建的记忆信息
        """
        from app.models.schemas import TeamMemoryCreate
        from app.services.memory_service_v2_team import create_team_memory

        db = self.get_db()
        try:
            if tags is None:
                tags = []

            req = TeamMemoryCreate(
                title=title,
                category=category,
                tags=tags,
                content=content,
                summary=summary,
                format_type=format_type,
                price=price,
                team_access_level=team_access_level,
                verification_data=verification_data
            )

            memory = await create_team_memory(db, team_id, creator_agent_id, req)
            return memory.model_dump()
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def get_team_memory(
        self,
        team_id: str,
        memory_id: str,
        request_agent_id: str
    ) -> Dict[str, Any]:
        """获取团队记忆

        Args:
            team_id: 团队ID
            memory_id: 记忆ID
            request_agent_id: 请求者Agent ID

        Returns:
            记忆详情
        """
        from app.services.memory_service_v2_team import get_team_memory

        db = self.get_db()
        try:
            memory = await get_team_memory(
                db=db,
                team_id=team_id,
                memory_id=memory_id,
                request_agent_id=request_agent_id
            )

            if not memory:
                return {"error": "记忆不存在或无权限访问"}

            return memory.model_dump()
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def update_team_memory(
        self,
        team_id: str,
        memory_id: str,
        request_agent_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新团队记忆

        Args:
            team_id: 团队ID
            memory_id: 记忆ID
            request_agent_id: 请求者Agent ID
            updates: 更新内容

        Returns:
            更新后的记忆信息
        """
        from app.services.memory_service_v2_team import update_team_memory

        db = self.get_db()
        try:
            memory = await update_team_memory(
                db=db,
                team_id=team_id,
                memory_id=memory_id,
                request_agent_id=request_agent_id,
                updates=updates
            )

            if not memory:
                return {"error": "记忆不存在或无权限修改"}

            return memory.model_dump()
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def delete_team_memory(
        self,
        team_id: str,
        memory_id: str,
        request_agent_id: str
    ) -> Dict[str, Any]:
        """删除团队记忆

        Args:
            team_id: 团队ID
            memory_id: 记忆ID
            request_agent_id: 请求者Agent ID

        Returns:
            删除结果
        """
        from app.services.memory_service_v2_team import delete_team_memory

        db = self.get_db()
        try:
            success = await delete_team_memory(
                db=db,
                team_id=team_id,
                memory_id=memory_id,
                request_agent_id=request_agent_id
            )

            if not success:
                return {"error": "记忆不存在或无权限删除"}

            return {"success": True, "message": "记忆已删除"}
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def search_team_memories(
        self,
        team_id: str,
        query: str = "",
        category: str = "",
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """搜索团队记忆

        Args:
            team_id: 团队ID
            query: 搜索关键词
            category: 分类筛选
            page: 页码
            page_size: 每页数量

        Returns:
            记忆列表
        """
        from app.services.memory_service_v2_team import get_team_memories

        db = self.get_db()
        try:
            result = await get_team_memories(
                db=db,
                team_id=team_id,
                request_agent_id="system",
                page=page,
                page_size=page_size
            )

            # 应用筛选
            items = result.items
            if query:
                items = [m for m in items if query.lower() in m.title.lower() or query.lower() in m.summary.lower()]
            if category:
                items = [m for m in items if category in m.category]

            return {
                "items": [m.model_dump() for m in items],
                "total": len(items),
                "page": page,
                "page_size": page_size
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def list_team_memories(
        self,
        team_id: str,
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """列出团队记忆

        Args:
            team_id: 团队ID
            page: 页码
            page_size: 每页数量
            category: 分类筛选

        Returns:
            记忆列表
        """
        from app.services.memory_service_v2_team import get_team_memories

        db = self.get_db()
        try:
            result = await get_team_memories(
                db=db,
                team_id=team_id,
                request_agent_id="system",
                page=page,
                page_size=page_size
            )

            # 应用分类筛选
            items = result.items
            if category:
                items = [m for m in items if m.category == category]

            return {
                "items": [m.model_dump() for m in items],
                "total": len(items),
                "page": page,
                "page_size": page_size
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    # ============ 团队积分（4个） ============

    async def get_team_credits(
        self,
        team_id: str
    ) -> Dict[str, Any]:
        """获取团队积分

        Args:
            team_id: 团队ID

        Returns:
            团队积分信息
        """
        from app.services.team_service import CreditService

        db = self.get_db()
        try:
            info = await CreditService.get_credits_info(db, team_id)

            if not info:
                return {"error": "团队不存在"}

            return info
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def add_team_credits(
        self,
        team_id: str,
        agent_id: str,
        amount: int
    ) -> Dict[str, Any]:
        """充值团队积分

        Args:
            team_id: 团队ID
            agent_id: 充值者Agent ID
            amount: 充值金额

        Returns:
            充值结果
        """
        from app.services.team_service import CreditService

        db = self.get_db()
        try:
            team = await CreditService.add_credits(db, team_id, agent_id, amount)

            return {
                "team_id": team.team_id,
                "credits": team.credits,
                "amount": amount,
                "message": "充值成功"
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def transfer_credits(
        self,
        team_id: str,
        from_agent_id: str,
        to_agent_id: str,
        amount: int
    ) -> Dict[str, Any]:
        """转账（从团队积分池转到成员）

        Args:
            team_id: 团队ID
            from_agent_id: 转出者Agent ID
            to_agent_id: 接收者Agent ID
            amount: 转账金额

        Returns:
            转账结果
        """
        from app.services.team_service import CreditService

        db = self.get_db()
        try:
            result = await CreditService.transfer_credits(
                db, team_id, from_agent_id, to_agent_id, amount
            )

            return {
                "team_credits": result["team_credits"],
                "agent_credits": result["agent_credits"],
                "amount": amount,
                "message": "转账成功"
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def get_credit_transactions(
        self,
        team_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """获取积分交易历史

        Args:
            team_id: 团队ID
            page: 页码
            page_size: 每页数量

        Returns:
            交易记录
        """
        from app.services.team_service import CreditService

        db = self.get_db()
        try:
            result = await CreditService.get_transactions(db, team_id, page, page_size)

            return {
                "items": [tx.model_dump() for tx in result["items"]],
                "total": result["total"],
                "page": result["page"],
                "page_size": result["page_size"]
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    # ============ 团队活动（2个） ============

    async def get_team_activities(
        self,
        team_id: str,
        activity_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """获取团队活动日志

        Args:
            team_id: 团队ID
            activity_type: 活动类型过滤
            page: 页码
            page_size: 每页数量

        Returns:
            活动日志列表
        """
        from app.api.team_activity import get_team_activity_logs
        from app.models.tables import Agent

        db = self.get_db()
        try:
            # 创建一个临时的 system agent
            system_agent = Agent(
                agent_id="system",
                name="System",
                description="System Agent",
                api_key="system",
                credits=0,
                reputation_score=5.0,
                total_sales=0,
                total_purchases=0,
                memories_uploaded=0,
                is_active=True
            )

            logs = await get_team_activity_logs(
                team_id=team_id,
                activity_type=activity_type,
                page=page,
                page_size=page_size,
                current_agent=system_agent,
                db=db
            )

            return logs.model_dump()
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    async def log_activity(
        self,
        team_id: str,
        agent_id: str,
        activity_type: str,
        description: str,
        related_id: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """记录团队活动

        Args:
            team_id: 团队ID
            agent_id: Agent ID
            activity_type: 活动类型
            description: 活动描述
            related_id: 关联ID
            extra_data: 额外信息

        Returns:
            记录结果
        """
        from app.models.tables import TeamActivityLog
        import uuid

        db = self.get_db()
        try:
            activity_id = f"act_{uuid.uuid4().hex[:12]}"

            activity = TeamActivityLog(
                activity_id=activity_id,
                team_id=team_id,
                agent_id=agent_id,
                activity_type=activity_type,
                description=description,
                related_id=related_id,
                extra_data=extra_data
            )
            db.add(activity)
            await db.commit()

            return {
                "activity_id": activity_id,
                "team_id": team_id,
                "agent_id": agent_id,
                "activity_type": activity_type,
                "message": "活动记录成功"
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()

    # ============ 团队统计（1个） ============

    async def get_team_insights(
        self,
        team_id: str
    ) -> Dict[str, Any]:
        """获取团队洞察

        Args:
            team_id: 团队ID

        Returns:
            团队洞察数据
        """
        from app.api.team_stats import get_team_stats
        from app.models.tables import Agent

        db = self.get_db()
        try:
            # 创建一个临时的 system agent
            system_agent = Agent(
                agent_id="system",
                name="System",
                description="System Agent",
                api_key="system",
                credits=0,
                reputation_score=5.0,
                total_sales=0,
                total_purchases=0,
                memories_uploaded=0,
                is_active=True
            )

            stats = await get_team_stats(
                team_id=team_id,
                current_agent=system_agent,
                db=db
            )

            return stats.model_dump()
        except Exception as e:
            return {"error": str(e)}
        finally:
            await db.close()


# 工具注册函数
def register_team_mcp_tools(mcp_server, db_session_factory):
    """注册团队相关MCP工具到 MCP 服务器

    Args:
        mcp_server: MCP 服务器实例
        db_session_factory: 数据库会话工厂函数
    """
    tools = TeamMCPTools(db_session_factory)

    # ========== 团队管理（6个） ==========

    mcp_server.add_tool({
        "name": "create_team",
        "description": "创建团队",
        "parameters": {
            "type": "object",
            "properties": {
                "owner_agent_id": {"type": "string", "description": "创建者Agent ID"},
                "name": {"type": "string", "description": "团队名称"},
                "description": {"type": "string", "description": "团队描述", "default": ""}
            },
            "required": ["owner_agent_id", "name"]
        },
        "handler": tools.create_team
    })

    mcp_server.add_tool({
        "name": "get_team",
        "description": "获取团队详情",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"}
            },
            "required": ["team_id"]
        },
        "handler": tools.get_team
    })

    mcp_server.add_tool({
        "name": "update_team",
        "description": "更新团队信息",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "owner_agent_id": {"type": "string", "description": "所有者Agent ID"},
                "name": {"type": "string", "description": "新名称（可选）"},
                "description": {"type": "string", "description": "新描述（可选）"}
            },
            "required": ["team_id", "owner_agent_id"]
        },
        "handler": tools.update_team
    })

    mcp_server.add_tool({
        "name": "delete_team",
        "description": "删除团队（软删除）",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "owner_agent_id": {"type": "string", "description": "所有者Agent ID"}
            },
            "required": ["team_id", "owner_agent_id"]
        },
        "handler": tools.delete_team
    })

    mcp_server.add_tool({
        "name": "list_teams",
        "description": "列出我的团队",
        "parameters": {
            "type": "object",
            "properties": {
                "owner_agent_id": {"type": "string", "description": "Agent ID（可选，指定则只返回该Agent创建的团队）"}
            },
            "required": []
        },
        "handler": tools.list_teams
    })

    mcp_server.add_tool({
        "name": "get_team_stats",
        "description": "获取团队统计",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"}
            },
            "required": ["team_id"]
        },
        "handler": tools.get_team_stats
    })

    # ========== 成员管理（5个） ==========

    mcp_server.add_tool({
        "name": "invite_member",
        "description": "生成邀请码",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "expires_days": {"type": "integer", "description": "有效天数", "default": 7}
            },
            "required": ["team_id"]
        },
        "handler": tools.invite_member
    })

    mcp_server.add_tool({
        "name": "join_team",
        "description": "通过邀请码加入团队",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Agent ID"},
                "invite_code": {"type": "string", "description": "邀请码"}
            },
            "required": ["agent_id", "invite_code"]
        },
        "handler": tools.join_team
    })

    mcp_server.add_tool({
        "name": "list_members",
        "description": "列出团队成员",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"}
            },
            "required": ["team_id"]
        },
        "handler": tools.list_members
    })

    mcp_server.add_tool({
        "name": "update_member_role",
        "description": "更新成员角色",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "member_id": {"type": "integer", "description": "成员ID"},
                "new_role": {"type": "string", "description": "新角色（admin/member）"}
            },
            "required": ["team_id", "member_id", "new_role"]
        },
        "handler": tools.update_member_role
    })

    mcp_server.add_tool({
        "name": "remove_member",
        "description": "移除成员",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "member_id": {"type": "integer", "description": "成员ID"}
            },
            "required": ["team_id", "member_id"]
        },
        "handler": tools.remove_member
    })

    # ========== 团队记忆（6个） ==========

    mcp_server.add_tool({
        "name": "create_team_memory",
        "description": "创建团队记忆",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "creator_agent_id": {"type": "string", "description": "创建者Agent ID"},
                "title": {"type": "string", "description": "标题"},
                "category": {"type": "string", "description": "分类"},
                "summary": {"type": "string", "description": "摘要"},
                "content": {"type": "object", "description": "内容（JSON）"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "标签列表"},
                "format_type": {"type": "string", "description": "格式类型", "default": "template"},
                "price": {"type": "integer", "description": "价格", "default": 0},
                "team_access_level": {"type": "string", "description": "可见性", "default": "team_only"},
                "verification_data": {"type": "object", "description": "验证数据"}
            },
            "required": ["team_id", "creator_agent_id", "title", "category", "summary", "content"]
        },
        "handler": tools.create_team_memory
    })

    mcp_server.add_tool({
        "name": "get_team_memory",
        "description": "获取团队记忆",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "memory_id": {"type": "string", "description": "记忆ID"},
                "request_agent_id": {"type": "string", "description": "请求者Agent ID"}
            },
            "required": ["team_id", "memory_id", "request_agent_id"]
        },
        "handler": tools.get_team_memory
    })

    mcp_server.add_tool({
        "name": "update_team_memory",
        "description": "更新团队记忆",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "memory_id": {"type": "string", "description": "记忆ID"},
                "request_agent_id": {"type": "string", "description": "请求者Agent ID"},
                "updates": {"type": "object", "description": "更新内容"}
            },
            "required": ["team_id", "memory_id", "request_agent_id", "updates"]
        },
        "handler": tools.update_team_memory
    })

    mcp_server.add_tool({
        "name": "delete_team_memory",
        "description": "删除团队记忆",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "memory_id": {"type": "string", "description": "记忆ID"},
                "request_agent_id": {"type": "string", "description": "请求者Agent ID"}
            },
            "required": ["team_id", "memory_id", "request_agent_id"]
        },
        "handler": tools.delete_team_memory
    })

    mcp_server.add_tool({
        "name": "search_team_memories",
        "description": "搜索团队记忆",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "query": {"type": "string", "description": "搜索关键词"},
                "category": {"type": "string", "description": "分类筛选"},
                "page": {"type": "integer", "description": "页码", "default": 1},
                "page_size": {"type": "integer", "description": "每页数量", "default": 20}
            },
            "required": ["team_id"]
        },
        "handler": tools.search_team_memories
    })

    mcp_server.add_tool({
        "name": "list_team_memories",
        "description": "列出团队记忆",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "page": {"type": "integer", "description": "页码", "default": 1},
                "page_size": {"type": "integer", "description": "每页数量", "default": 20},
                "category": {"type": "string", "description": "分类筛选"}
            },
            "required": ["team_id"]
        },
        "handler": tools.list_team_memories
    })

    # ========== 团队积分（4个） ==========

    mcp_server.add_tool({
        "name": "get_team_credits",
        "description": "获取团队积分",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"}
            },
            "required": ["team_id"]
        },
        "handler": tools.get_team_credits
    })

    mcp_server.add_tool({
        "name": "add_team_credits",
        "description": "充值团队积分",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "agent_id": {"type": "string", "description": "充值者Agent ID"},
                "amount": {"type": "integer", "description": "充值金额"}
            },
            "required": ["team_id", "agent_id", "amount"]
        },
        "handler": tools.add_team_credits
    })

    mcp_server.add_tool({
        "name": "transfer_credits",
        "description": "转账（从团队积分池转到成员）",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "from_agent_id": {"type": "string", "description": "转出者Agent ID"},
                "to_agent_id": {"type": "string", "description": "接收者Agent ID"},
                "amount": {"type": "integer", "description": "转账金额"}
            },
            "required": ["team_id", "from_agent_id", "to_agent_id", "amount"]
        },
        "handler": tools.transfer_credits
    })

    mcp_server.add_tool({
        "name": "get_credit_transactions",
        "description": "获取积分交易历史",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "page": {"type": "integer", "description": "页码", "default": 1},
                "page_size": {"type": "integer", "description": "每页数量", "default": 20}
            },
            "required": ["team_id"]
        },
        "handler": tools.get_credit_transactions
    })

    # ========== 团队活动（2个） ==========

    mcp_server.add_tool({
        "name": "get_team_activities",
        "description": "获取团队活动日志",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "activity_type": {"type": "string", "description": "活动类型过滤"},
                "page": {"type": "integer", "description": "页码", "default": 1},
                "page_size": {"type": "integer", "description": "每页数量", "default": 20}
            },
            "required": ["team_id"]
        },
        "handler": tools.get_team_activities
    })

    mcp_server.add_tool({
        "name": "log_activity",
        "description": "记录团队活动",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"},
                "agent_id": {"type": "string", "description": "Agent ID"},
                "activity_type": {"type": "string", "description": "活动类型"},
                "description": {"type": "string", "description": "活动描述"},
                "related_id": {"type": "string", "description": "关联ID"},
                "extra_data": {"type": "object", "description": "额外信息"}
            },
            "required": ["team_id", "agent_id", "activity_type", "description"]
        },
        "handler": tools.log_activity
    })

    # ========== 团队统计（1个） ==========

    mcp_server.add_tool({
        "name": "get_team_insights",
        "description": "获取团队洞察",
        "parameters": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队ID"}
            },
            "required": ["team_id"]
        },
        "handler": tools.get_team_insights
    })
