"""数字签名服务"""
import hashlib
import json
from datetime import datetime
from typing import Tuple, Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

class DigitalSignatureService:
    """数字签名服务 - 使用 RSA-2048 + SHA-256"""

    def __init__(self):
        self.algorithm_name = "RSA-SHA256"
        self.key_size = 2048

    def generate_key_pair(self) -> Tuple[bytes, bytes]:
        """
        生成 RSA 密钥对

        Returns:
            (private_key_pem, public_key_pem): 私钥和公钥的 PEM 格式字节
        """
        # 生成私钥
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.key_size,
            backend=default_backend()
        )

        # 导出私钥（PKCS8 格式）
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        # 导出公钥
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        return private_pem, public_pem

    def sign(self, data: dict, private_key_pem: bytes) -> Tuple[str, datetime]:
        """
        对数据进行签名

        Args:
            data: 要签名的数据字典
            private_key_pem: 私钥 PEM 格式字节

        Returns:
            (signature_hex, timestamp): 签名的十六进制字符串和签名时间戳
        """
        # 将数据转换为规范化的 JSON 字符串
        canonical_data = self._canonicalize(data)

        # 计算数据哈希
        data_hash = hashlib.sha256(canonical_data.encode('utf-8')).digest()

        # 加载私钥
        private_key = serialization.load_pem_private_key(
            private_key_pem,
            password=None,
            backend=default_backend()
        )

        # 使用私钥签名
        signature = private_key.sign(
            data_hash,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

        # 记录签名时间戳
        timestamp = datetime.utcnow()

        return signature.hex(), timestamp

    def verify(self, data: dict, signature_hex: str, public_key_pem: bytes) -> bool:
        """
        验证签名

        Args:
            data: 原始数据字典
            signature_hex: 签名的十六进制字符串
            public_key_pem: 公钥 PEM 格式字节

        Returns:
            验证是否成功
        """
        try:
            # 将数据转换为规范化的 JSON 字符串
            canonical_data = self._canonicalize(data)

            # 计算数据哈希
            data_hash = hashlib.sha256(canonical_data.encode('utf-8')).digest()

            # 将十六进制签名转换为字节
            signature = bytes.fromhex(signature_hex)

            # 加载公钥
            public_key = serialization.load_pem_public_key(
                public_key_pem,
                backend=default_backend()
            )

            # 验证签名
            public_key.verify(
                signature,
                data_hash,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )

            return True
        except Exception as e:
            # 签名验证失败
            return False

    def _canonicalize(self, data: dict) -> str:
        """
        将字典转换为规范化的 JSON 字符串
        确保相同的字典总是产生相同的字符串表示

        Args:
            data: 数据字典

        Returns:
            规范化的 JSON 字符串
        """
        # 排序键并确保字符串的一致性
        # 移除 None 值，因为 None 会被 JSON 转换为 null
        filtered_data = {k: v for k, v in sorted(data.items()) if v is not None}

        # 使用 ensure_ascii=False 保持 Unicode 字符
        # 使用 separators 减少空格
        return json.dumps(filtered_data, ensure_ascii=False, separators=(',', ':'))

    def export_public_key_pem(self, public_key_pem: bytes) -> str:
        """
        导出公钥为 PEM 格式字符串

        Args:
            public_key_pem: 公钥 PEM 格式字节

        Returns:
            PEM 格式字符串
        """
        return public_key_pem.decode('utf-8')

    def get_algorithm_info(self) -> dict:
        """
        获取算法信息

        Returns:
            算法信息字典
        """
        return {
            "algorithm": self.algorithm_name,
            "key_size": self.key_size,
            "hash_function": "SHA-256",
            "padding": "PSS",
            "compliance": ["FIPS 140-2", "eIDAS"]
        }


# 全局实例
signature_service = DigitalSignatureService()
