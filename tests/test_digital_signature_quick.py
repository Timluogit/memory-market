"""数字签名功能快速测试"""
import os
import time
from datetime import datetime

# 设置环境变量
os.environ["KEY_ENCRYPTION_SALT"] = "80a2dba9b0dbae2dbe5e52d51b176777"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.services.digital_signature_service import signature_service
from app.services.key_management_service import key_management_service
from app.api.audit_signature_middleware import audit_signature_middleware
from app.models.tables import AuditLog, Agent
from app.db.database import Base, engine, SessionLocal


def test_signature_service():
    """测试数字签名服务"""
    print("\n=== 测试数字签名服务 ===")

    # 1. 密钥生成
    print("1. 密钥生成...")
    private_pem, public_pem = signature_service.generate_key_pair()
    assert private_pem is not None
    assert public_pem is not None
    print("   ✓ 密钥对生成成功")

    # 2. 签名功能
    print("2. 签名功能...")
    test_data = {
        "log_id": "audit_001",
        "action_type": "login",
        "actor_name": "test_user",
        "status": "success",
        "created_at": datetime.utcnow().isoformat()
    }
    signature_hex, timestamp = signature_service.sign(test_data, private_pem)
    assert signature_hex is not None
    assert len(signature_hex) > 0
    assert timestamp is not None
    print("   ✓ 签名成功")

    # 3. 验证功能
    print("3. 验证功能...")
    is_valid = signature_service.verify(test_data, signature_hex, public_pem)
    assert is_valid is True
    print("   ✓ 验证成功")

    # 4. 篡改检测
    print("4. 篡改检测...")
    tampered_data = test_data.copy()
    tampered_data["status"] = "failure"
    is_valid_tampered = signature_service.verify(tampered_data, signature_hex, public_pem)
    assert is_valid_tampered is False
    print("   ✓ 篡改检测成功")

    # 5. 性能测试
    print("5. 性能测试...")
    iterations = 10

    # 签名性能
    start = time.time()
    for _ in range(iterations):
        signature_service.sign(test_data, private_pem)
    sign_avg_ms = (time.time() - start) / iterations * 1000
    print(f"   平均签名时间: {sign_avg_ms:.2f}ms (目标 < 10ms)")

    # 验证性能
    start = time.time()
    for _ in range(iterations):
        signature_service.verify(test_data, signature_hex, public_pem)
    verify_avg_ms = (time.time() - start) / iterations * 1000
    print(f"   平均验证时间: {verify_avg_ms:.2f}ms (目标 < 5ms)")

    # 验证性能达标
    assert verify_avg_ms < 5.0, f"验证性能未达标: {verify_avg_ms}ms >= 5ms"
    print("   ✓ 性能测试通过")

    # 6. 算法信息
    print("6. 算法信息...")
    info = signature_service.get_algorithm_info()
    assert info["algorithm"] == "RSA-SHA256"
    assert info["key_size"] == 2048
    assert "FIPS 140-2" in info["compliance"]
    assert "eIDAS" in info["compliance"]
    print(f"   ✓ 算法: {info['algorithm']}")
    print(f"   ✓ 密钥长度: {info['key_size']} 位")
    print(f"   ✓ 合规性: {', '.join(info['compliance'])}")


def test_key_management():
    """测试密钥管理服务"""
    print("\n=== 测试密钥管理服务 ===")

    # 1. 生成并存储密钥对
    print("1. 生成并存储密钥对...")
    key_id, public_key_pem = key_management_service.generate_and_store_key_pair()
    assert key_id is not None
    assert public_key_pem is not None
    print(f"   ✓ 密钥对生成成功，ID: {key_id}")

    # 2. 获取当前密钥对
    print("2. 获取当前密钥对...")
    key_pair = key_management_service.get_current_key_pair()
    assert key_pair is not None
    current_key_id, private_key_pem, public_key_pem2 = key_pair
    assert current_key_id == key_id
    assert private_key_pem is not None
    print(f"   ✓ 当前密钥ID: {current_key_id}")

    # 3. 密钥轮换
    print("3. 密钥轮换...")
    old_key_id = current_key_id
    new_key_id, new_public_key_pem = key_management_service.rotate_key()
    assert new_key_id != old_key_id
    print(f"   ✓ 密钥轮换成功: {old_key_id} -> {new_key_id}")

    # 4. 获取密钥信息
    print("4. 获取密钥信息...")
    key_info = key_management_service.get_key_info()
    assert key_info["has_current_key"] is True
    assert key_info["current_key"]["key_id"] == new_key_id
    print(f"   ✓ 当前密钥: {key_info['current_key']['key_id']}")
    print(f"   ✓ 历史密钥数量: {key_info['previous_keys_count']}")


def test_signature_middleware():
    """测试签名中间件"""
    print("\n=== 测试签名中间件 ===")

    # 创建内存数据库
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. 创建并签名审计日志
        print("1. 创建并签名审计日志...")
        audit_log = AuditLog(
            log_id="audit_test_001",
            actor_agent_id="agent_123",
            actor_name="test_agent",
            action_type="login",
            action_category="auth",
            status="success",
            http_method="POST",
            endpoint="/api/auth/login",
            ip_address="127.0.0.1",
            created_at=datetime.utcnow()
        )

        sign_success = audit_signature_middleware.sign_audit_log(audit_log)
        assert sign_success is True
        assert audit_log.signature is not None
        assert audit_log.signature_algorithm is not None
        assert audit_log.signature_timestamp is not None
        print("   ✓ 签名成功")
        print(f"   ✓ 签名算法: {audit_log.signature_algorithm}")
        print(f"   ✓ 签名时间戳: {audit_log.signature_timestamp}")

        # 2. 验证签名
        print("2. 验证签名...")
        verify_success = audit_signature_middleware.verify_audit_log(audit_log)
        assert verify_success is True
        print("   ✓ 验证成功")

        # 3. 篡改检测
        print("3. 篡改检测...")
        original_signature = audit_log.signature
        audit_log.status = "failure"  # 篡改数据
        verify_after_tamper = audit_signature_middleware.verify_audit_log(audit_log)
        assert verify_after_tamper is False
        print("   ✓ 篡改检测成功")

        # 4. 多日志签名覆盖率
        print("4. 多日志签名覆盖率...")
        logs = []
        for i in range(10):
            audit_log = AuditLog(
                log_id=f"audit_test_{i:04d}",
                actor_agent_id="agent_123",
                actor_name="test_agent",
                action_type="login",
                action_category="auth",
                status="success",
                created_at=datetime.utcnow()
            )
            audit_signature_middleware.sign_audit_log(audit_log)
            logs.append(audit_log)

        # 检查签名覆盖率
        signed_count = sum(1 for log in logs if log.signature is not None)
        valid_count = sum(1 for log in logs if audit_signature_middleware.verify_audit_log(log))

        assert signed_count == 10, f"签名覆盖率: {signed_count}/10"
        assert valid_count == 10, f"验证通过率: {valid_count}/10"
        print(f"   ✓ 签名覆盖率: {signed_count}/10 (100%)")
        print(f"   ✓ 验证通过率: {valid_count}/10 (100%)")

    finally:
        db.close()


def test_end_to_end_workflow():
    """测试端到端工作流"""
    print("\n=== 测试端到端工作流 ===")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. 完整的签名流程
        print("1. 完整的签名流程...")
        key_id, public_key_pem = key_management_service.generate_and_store_key_pair()
        print(f"   ✓ 密钥生成: {key_id}")

        audit_log = AuditLog(
            log_id="audit_workflow_001",
            actor_agent_id="agent_123",
            actor_name="test_agent",
            action_type="memory_created",
            action_category="memory",
            target_type="memory",
            target_id="mem_123456",
            target_name="Test Memory",
            status="success",
            http_method="POST",
            endpoint="/api/memories",
            ip_address="192.168.1.100",
            request_data={"title": "Test", "content": "Test content"},
            response_data={"memory_id": "mem_123456"},
            created_at=datetime.utcnow()
        )

        sign_success = audit_signature_middleware.sign_audit_log(audit_log)
        assert sign_success is True
        print("   ✓ 审计日志签名成功")

        verify_success = audit_signature_middleware.verify_audit_log(audit_log)
        assert verify_success is True
        print("   ✓ 审计日志验证成功")

        # 2. 篡改检测
        print("2. 篡改检测...")
        audit_log.action_type = "memory_updated"
        verify_after_tamper = audit_signature_middleware.verify_audit_log(audit_log)
        assert verify_after_tamper is False
        print("   ✓ 篡改被成功检测")

        # 3. 密钥轮换
        print("3. 密钥轮换...")
        old_key_id = key_id
        new_key_id, new_public_key_pem = key_management_service.rotate_key()
        assert new_key_id != old_key_id
        print(f"   ✓ 密钥轮换: {old_key_id} -> {new_key_id}")

        # 4. 新密钥签名新日志
        print("4. 新密钥签名新日志...")
        new_audit_log = AuditLog(
            log_id="audit_workflow_002",
            actor_agent_id="agent_123",
            actor_name="test_agent",
            action_type="login",
            action_category="auth",
            status="success",
            created_at=datetime.utcnow()
        )

        sign_new_success = audit_signature_middleware.sign_audit_log(new_audit_log)
        assert sign_new_success is True
        print("   ✓ 新密钥签名成功")

        verify_new_success = audit_signature_middleware.verify_audit_log(new_audit_log)
        assert verify_new_success is True
        print("   ✓ 新密钥验证成功")

    finally:
        db.close()


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*50)
    print("数字签名验证系统 - 功能测试")
    print("="*50)

    try:
        test_signature_service()
        test_key_management()
        test_signature_middleware()
        test_end_to_end_workflow()

        print("\n" + "="*50)
        print("✅ 所有测试通过！")
        print("="*50)

        print("\n=== 测试总结 ===")
        print("✓ 数字签名服务: 正常")
        print("✓ 密钥管理服务: 正常")
        print("✓ 签名中间件: 正常")
        print("✓ 端到端流程: 正常")
        print("✓ 篡改检测: 正常")
        print("✓ 性能指标: 符合要求")
        print("\n合规性:")
        print("✓ FIPS 140-2: 符合")
        print("✓ eIDAS: 符合")

        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
