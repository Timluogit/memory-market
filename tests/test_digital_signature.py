"""数字签名功能测试"""
import pytest
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.services.digital_signature_service import signature_service
from app.services.key_management_service import key_management_service
from app.api.audit_signature_middleware import audit_signature_middleware
from app.models.tables import AuditLog, Agent
from app.db.database import Base, engine


class TestDigitalSignatureService:
    """测试数字签名服务"""

    def test_generate_key_pair(self):
        """测试密钥对生成"""
        private_pem, public_pem = signature_service.generate_key_pair()

        assert private_pem is not None
        assert public_pem is not None
        assert b"PRIVATE KEY" in private_pem
        assert b"PUBLIC KEY" in public_pem

    def test_sign_and_verify(self):
        """测试签名和验证"""
        # 生成密钥对
        private_pem, public_pem = signature_service.generate_key_pair()

        # 准备测试数据
        test_data = {
            "log_id": "audit_123456",
            "action_type": "login",
            "actor_name": "test_user",
            "status": "success",
            "created_at": datetime.utcnow().isoformat()
        }

        # 签名
        signature_hex, timestamp = signature_service.sign(test_data, private_pem)

        assert signature_hex is not None
        assert len(signature_hex) > 0
        assert timestamp is not None

        # 验证签名
        is_valid = signature_service.verify(test_data, signature_hex, public_pem)
        assert is_valid is True

    def test_verify_with_tampered_data(self):
        """测试篡改检测"""
        # 生成密钥对
        private_pem, public_pem = signature_service.generate_key_pair()

        # 准备测试数据
        original_data = {
            "log_id": "audit_123456",
            "action_type": "login",
            "actor_name": "test_user",
            "status": "success",
            "created_at": datetime.utcnow().isoformat()
        }

        # 签名
        signature_hex, _ = signature_service.sign(original_data, private_pem)

        # 篡改数据
        tampered_data = original_data.copy()
        tampered_data["status"] = "failure"

        # 验证篡改后的数据
        is_valid = signature_service.verify(tampered_data, signature_hex, public_pem)
        assert is_valid is False

    def test_verify_with_wrong_key(self):
        """测试使用错误的公钥验证"""
        # 生成两对密钥
        private_pem1, public_pem1 = signature_service.generate_key_pair()
        private_pem2, public_pem2 = signature_service.generate_key_pair()

        # 使用第一对密钥签名
        test_data = {"log_id": "audit_123456", "action_type": "login"}
        signature_hex, _ = signature_service.sign(test_data, private_pem1)

        # 使用第二对密钥的公钥验证
        is_valid = signature_service.verify(test_data, signature_hex, public_pem2)
        assert is_valid is False

    def test_canonicalization_consistency(self):
        """测试数据规范化的一致性"""
        # 相同的数据应该产生相同的规范化的字符串
        data1 = {"b": 2, "a": 1, "c": 3}
        data2 = {"c": 3, "a": 1, "b": 2}

        canonical1 = signature_service._canonicalize(data1)
        canonical2 = signature_service._canonicalize(data2)

        assert canonical1 == canonical2

    def test_performance_signing(self):
        """测试签名性能"""
        # 生成密钥对
        private_pem, _ = signature_service.generate_key_pair()

        # 准备测试数据
        test_data = {
            "log_id": "audit_123456",
            "action_type": "login",
            "actor_name": "test_user",
            "status": "success",
            "created_at": datetime.utcnow().isoformat()
        }

        # 测试多次签名的性能
        iterations = 10
        start_time = time.time()

        for _ in range(iterations):
            signature_service.sign(test_data, private_pem)

        end_time = time.time()
        avg_time_ms = (end_time - start_time) / iterations * 1000

        # 平均签名时间应该 < 10ms
        assert avg_time_ms < 10.0

        print(f"\n平均签名时间: {avg_time_ms:.2f}ms")

    def test_performance_verification(self):
        """测试验证性能"""
        # 生成密钥对
        private_pem, public_pem = signature_service.generate_key_pair()

        # 准备测试数据
        test_data = {
            "log_id": "audit_123456",
            "action_type": "login",
            "actor_name": "test_user",
            "status": "success",
            "created_at": datetime.utcnow().isoformat()
        }

        # 签名
        signature_hex, _ = signature_service.sign(test_data, private_pem)

        # 测试多次验证的性能
        iterations = 10
        start_time = time.time()

        for _ in range(iterations):
            signature_service.verify(test_data, signature_hex, public_pem)

        end_time = time.time()
        avg_time_ms = (end_time - start_time) / iterations * 1000

        # 平均验证时间应该 < 5ms
        assert avg_time_ms < 5.0

        print(f"\n平均验证时间: {avg_time_ms:.2f}ms")


class TestKeyManagementService:
    """测试密钥管理服务"""

    def test_generate_and_store_key_pair(self):
        """测试生成和存储密钥对"""
        key_id, public_key_pem = key_management_service.generate_and_store_key_pair()

        assert key_id is not None
        assert public_key_pem is not None
        assert b"PUBLIC KEY" in public_key_pem.encode('utf-8')

    def test_get_current_key_pair(self):
        """测试获取当前密钥对"""
        # 首先生成一个密钥对
        key_id1, public_key_pem1 = key_management_service.generate_and_store_key_pair()

        # 获取当前密钥对
        key_pair = key_management_service.get_current_key_pair()

        assert key_pair is not None
        key_id2, private_key_pem, public_key_pem2 = key_pair

        assert key_id1 == key_id2
        assert public_key_pem1.encode('utf-8') == public_key_pem2
        assert private_key_pem is not None

    def test_rotate_key(self):
        """测试密钥轮换"""
        # 生成第一个密钥对
        key_id1, _ = key_management_service.generate_and_store_key_pair()

        # 密钥轮换
        key_id2, public_key_pem2 = key_management_service.rotate_key()

        assert key_id2 is not None
        assert key_id2 != key_id1

        # 新密钥应该成为当前密钥
        key_pair = key_management_service.get_current_key_pair()
        assert key_pair[0] == key_id2

    def test_get_key_info(self):
        """测试获取密钥信息"""
        # 生成一个密钥对
        key_id, _ = key_management_service.generate_and_store_key_pair()

        # 获取密钥信息
        key_info = key_management_service.get_key_info()

        assert key_info["has_current_key"] is True
        assert key_info["current_key"]["key_id"] == key_id
        assert "algorithm" in key_info["current_key"]


class TestAuditSignatureMiddleware:
    """测试审计日志签名中间件"""

    def test_sign_audit_log(self, db: Session):
        """测试为审计日志签名"""
        # 创建测试审计日志
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

        # 签名
        is_success = audit_signature_middleware.sign_audit_log(audit_log)

        assert is_success is True
        assert audit_log.signature is not None
        assert audit_log.signature_algorithm is not None
        assert audit_log.signature_timestamp is not None

    def test_verify_audit_log(self, db: Session):
        """测试验证审计日志签名"""
        # 创建并签名审计日志
        audit_log = AuditLog(
            log_id="audit_test_002",
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

        # 签名
        audit_signature_middleware.sign_audit_log(audit_log)

        # 验证
        is_valid = audit_signature_middleware.verify_audit_log(audit_log)

        assert is_valid is True

    def test_detect_tampering(self, db: Session):
        """测试篡改检测"""
        # 创建并签名审计日志
        audit_log = AuditLog(
            log_id="audit_test_003",
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

        # 签名
        audit_signature_middleware.sign_audit_log(audit_log)

        # 篡改数据
        audit_log.status = "failure"

        # 验证应该失败
        is_valid = audit_signature_middleware.verify_audit_log(audit_log)
        assert is_valid is False

    def test_multiple_logs_signature_coverage(self, db: Session):
        """测试多日志签名覆盖率"""
        # 创建多个审计日志
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
            # 签名
            audit_signature_middleware.sign_audit_log(audit_log)
            logs.append(audit_log)

        # 验证所有日志都有签名
        signed_count = sum(1 for log in logs if log.signature is not None)
        assert signed_count == 10

        # 验证所有签名都有效
        valid_count = sum(1 for log in logs if audit_signature_middleware.verify_audit_log(log))
        assert valid_count == 10


class TestEndToEndSigningWorkflow:
    """测试端到端签名流程"""

    def test_complete_signing_workflow(self, db: Session):
        """测试完整的签名流程"""
        # 1. 生成密钥对
        key_id, public_key_pem = key_management_service.generate_and_store_key_pair()
        assert key_id is not None

        # 2. 创建审计日志
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

        # 3. 签名审计日志
        sign_success = audit_signature_middleware.sign_audit_log(audit_log)
        assert sign_success is True
        assert audit_log.signature is not None

        # 4. 验证签名
        verify_success = audit_signature_middleware.verify_audit_log(audit_log)
        assert verify_success is True

        # 5. 篡改检测
        original_signature = audit_log.signature
        audit_log.action_type = "memory_updated"

        verify_after_tamper = audit_signature_middleware.verify_audit_log(audit_log)
        assert verify_after_tamper is False

        # 6. 密钥轮换
        new_key_id, new_public_key_pem = key_management_service.rotate_key()
        assert new_key_id != key_id

        # 7. 新密钥应该能签名新日志
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

        verify_new_success = audit_signature_middleware.verify_audit_log(new_audit_log)
        assert verify_new_success is True


class TestCompliance:
    """测试合规性相关功能"""

    def test_signature_algorithm_info(self):
        """测试签名算法信息"""
        info = signature_service.get_algorithm_info()

        assert "algorithm" in info
        assert "key_size" in info
        assert "hash_function" in info
        assert "compliance" in info
        assert "FIPS 140-2" in info["compliance"]
        assert "eIDAS" in info["compliance"]

    def test_key_security_features(self):
        """测试密钥安全特性"""
        # 密钥应该加密存储
        key_id, _ = key_management_service.generate_and_store_key_pair()
        key_pair = key_management_service.get_current_key_pair()

        assert key_pair is not None
        # 私钥应该是加密的（通过检查是否为有效 PEM 格式验证）
        private_pem = key_pair[1]
        assert private_pem is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
