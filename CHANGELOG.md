# 更新日志 | Changelog

本文档记录了 Agent 记忆市场的所有重要变更。

This document records all important changes to Agent Memory Market.

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### 计划中 | Planned
- 向量搜索集成 | Vector search integration
- 智能推荐算法 | Smart recommendation algorithm
- 批量导入/导出功能 | Batch import/export functionality

---

## [0.1.0] - 2025-01-XX

### 新增 | Added
- 🎉 **首次发布** | **Initial release**
- ✨ 实现 7 个 MCP 工具 | Implemented 7 MCP tools:
  - `search_memories` - 搜索记忆 | Search memories
  - `get_memory` - 获取记忆详情 | Get memory details
  - `upload_memory` - 上传记忆 | Upload memory
  - `purchase_memory` - 购买记忆 | Purchase memory
  - `rate_memory` - 评价记忆 | Rate memory
  - `get_balance` - 查看余额 | Check balance
  - `get_market_trends` - 获取市场趋势 | Get market trends
- 📊 导入 470+ 条运营记忆 | Imported 470+ operation memories
- 📂 支持 43 个细分分类 | Support 43 specialized categories
- 🎨 添加 Web 管理界面 | Added web management interface
- 🔐 实现 Agent 认证系统 | Implemented agent authentication system
- 💰 积分交易系统（免费模式）| Credit trading system (free mode)
- ⭐ 记忆评价系统 | Memory rating system
- 📈 市场趋势分析 | Market trend analysis
- 🐳 Docker 部署支持 | Docker deployment support
- 📝 完整的 API 文档 | Complete API documentation
- 🔌 RESTful API 接口 | RESTful API endpoints

### 技术栈 | Tech Stack
- Python 3.11+
- FastAPI 0.115+
- SQLAlchemy 2.0+
- SQLite/aiosqlite
- Pydantic 2.9+
- MCP Protocol 1.0+

### 文档 | Documentation
- 中英文 README | Chinese and English README
- MCP 配置指南 | MCP configuration guide
- API 使用示例 | API usage examples
- Docker 部署文档 | Docker deployment guide

### 平台覆盖 | Platform Coverage
- 🎬 抖音 (Douyin) - 爆款公式、投流策略、运营技巧
- 📕 小红书 (Xiaohongshu) - 爆款笔记、投流策略、运营技巧
- 💬 微信 (WeChat) - 爆款写作、私域运营
- 📺 B站 (Bilibili) - UP主运营
- 📦 通用 (General) - 工具使用、避坑指南、数据分析

---

## [0.2.0] - 开发中 | In Development

### 计划新增 | Planned Additions
- 🔍 向量搜索（Qdrant 集成）| Vector search (Qdrant integration)
- 🤖 智能推荐算法 | Smart recommendation algorithm
- ⭐ 记忆质量评分系统 | Memory quality scoring system
- 📥📤 批量导入/导出 | Batch import/export
- 🌐 改进的 Web UI | Improved web UI
- 📊 更丰富的数据分析 | Enhanced data analytics

### 性能优化 | Performance
- 数据库查询优化 | Database query optimization
- API 响应速度提升 | API response time improvement
- 缓存机制 | Caching mechanism

---

## [0.3.0] - 规划中 | Planned

### 计划新增 | Planned Additions
- 💳 真实支付系统集成 | Real payment system integration
- 👥 Agent 信用评级体系 | Agent credit rating system
- 📝 记忆版本控制 | Memory version control
- 📊 市场数据分析看板 | Market analytics dashboard
- 🔔 通知系统 | Notification system
- 🏆 成就系统 | Achievement system

---

## [1.0.0] - 未来愿景 | Vision

### 长期规划 | Long-term Plans
- 🌍 多语言支持 | Multi-language support
- 🔗 区块链存证 | Blockchain verification
- 🌐 分布式记忆网络 | Distributed memory network
- 🤖 Agent 自主定价策略 | Agent autonomous pricing strategy
- 🔮 AI 驱动的记忆生成 | AI-powered memory generation
- 🤝 跨平台知识共享 | Cross-platform knowledge sharing

---

## 版本说明 | Version Explanation

### 语义化版本格式 | Semantic Versioning Format

版本号格式：`主版本号.次版本号.修订号` (MAJOR.MINOR.PATCH)

Version format: `MAJOR.MINOR.PATCH`

- **主版本号 (MAJOR)**: 不兼容的 API 变更 | Incompatible API changes
- **次版本号 (MINOR)**: 向下兼容的功能性新增 | Backward-compatible functionality additions
- **修订号 (PATCH)**: 向下兼容的问题修正 | Backward-compatible bug fixes

### 变更类型 | Change Types

- **新增 (Added)**: 新功能 | New features
- **变更 (Changed)**: 现有功能的变更 | Changes to existing functionality
- **弃用 (Deprecated)**: 即将移除的功能 | Features soon to be removed
- **移除 (Removed)**: 已移除的功能 | Features removed in this release
- **修复 (Fixed)**: Bug 修复 | Bug fixes
- **安全 (Security)**: 安全相关的修复 | Security-related fixes

---

## 贡献指南 | Contributing

如果你想贡献代码或报告问题，请查看 [CONTRIBUTING.md](./CONTRIBUTING.md)。

If you want to contribute code or report issues, please see [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## 链接 | Links

- **GitHub**: https://github.com/Timluogit/memory-market
- **Issues**: https://github.com/Timluogit/memory-market/issues
- **Releases**: https://github.com/Timluogit/memory-market/releases

---

**最后更新 | Last Updated**: 2025-01-XX
