#!/bin/bash

# 缓存系统验证脚本

echo "==================================="
echo "缓存系统文件验证"
echo "==================================="
echo ""

echo "1. 核心缓存模块"
echo "-------------------"
ls -lh app/cache/*.py
echo ""

echo "2. 搜索缓存中间件"
echo "-------------------"
ls -lh app/api/*cache*.py
echo ""

echo "3. 缓存失效服务"
echo "-------------------"
ls -lh app/services/*invalidation*.py
echo ""

echo "4. 测试文件"
echo "-------------------"
ls -lh tests/*cache*.py
echo ""

echo "5. 配置文件"
echo "-------------------"
ls -lh docker-compose.cache.yml redis/redis.conf
echo ""

echo "6. Grafana仪表板"
echo "-------------------"
ls -lh grafana/dashboards/*cache*.json
echo ""

echo "7. 文档"
echo "-------------------"
ls -lh docs/*cache*.md
echo ""

echo "8. Python语法检查"
echo "-------------------"
python3 -m py_compile app/cache/redis_client.py
python3 -m py_compile app/cache/cache_keys.py
python3 -m py_compile app/api/search_cache_middleware.py
python3 -m py_compile app/services/cache_invalidation_service.py
python3 -m py_compile app/api/cache_stats.py
python3 -m py_compile tests/test_search_cache.py

if [ $? -eq 0 ]; then
    echo "✅ 所有Python文件语法检查通过"
else
    echo "❌ Python语法检查失败"
    exit 1
fi

echo ""
echo "==================================="
echo "验证完成"
echo "==================================="
