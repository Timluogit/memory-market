"""密钥管理服务"""
import os
import json
from datetime import datetime
from typing import Tuple, Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64

from app.services.digital_signature_service import signature_service
from app.core.config import settings


class KeyManagementService:
    """密钥管理服务 - 负责密钥的生成、存储、轮换和导出"""

    def __init__(self):
        # 密钥存储路径
        self.keys_dir = os.path.join(os.path.dirname(settings.DATABASE_URL.replace("sqlite:///", "")), "keys")
        self.ensure_keys_directory()

        # 主密钥（用于加密存储的密钥）
        self.master_key = self._get_or_create_master_key()

        # 密钥文件名
        self.current_key_file = os.path.join(self.keys_dir, "current_key.json")
        self.previous_keys_dir = os.path.join(self.keys_dir, "previous")
        self.ensure_previous_keys_directory()

    def ensure_keys_directory(self):
        """确保密钥目录存在"""
        os.makedirs(self.keys_dir, mode=0o700, exist_ok=True)

    def ensure_previous_keys_directory(self):
        """确保历史密钥目录存在"""
        os.makedirs(self.previous_keys_dir, mode=0o700, exist_ok=True)

    def _get_or_create_master_key(self) -> bytes:
        """
        获取或创建主密钥

        Returns:
            主密钥字节（32字节，用于 AES-256）
        """
        master_key_file = os.path.join(self.keys_dir, ".master_key")

        if os.path.exists(master_key_file):
            # 读取现有主密钥
            with open(master_key_file, 'rb') as f:
                encrypted_key = f.read()

            # 从环境变量获取盐值
            salt_hex = os.getenv("KEY_ENCRYPTION_SALT", "")
            if not salt_hex:
                raise ValueError("KEY_ENCRYPTION_SALT environment variable is required")

            salt = bytes.fromhex(salt_hex)

            # 使用 PBKDF2 派生密钥
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )

            key = kdf.derive(settings.JWT_SECRET.encode('utf-8'))

            # 解密主密钥
            iv = encrypted_key[:16]
            ciphertext = encrypted_key[16:]
            cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            return decryptor.update(ciphertext) + decryptor.finalize()
        else:
            # 创建新的主密钥
            master_key = os.urandom(32)

            # 加密并保存主密钥
            key = os.urandom(32)
            iv = os.urandom(16)

            cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
            encryptor = cipher.encryptor()
            encrypted_key = encryptor.update(master_key) + encryptor.finalize()

            # 保存加密后的主密钥
            with open(master_key_file, 'wb') as f:
                f.write(iv + encrypted_key)

            # 保存盐值（实际部署中应该从安全配置管理服务获取）
            salt_hex = os.getenv("KEY_ENCRYPTION_SALT", "")
            if not salt_hex:
                salt_hex = os.urandom(16).hex()
                # 注意：实际部署中应该从安全配置管理服务获取盐值
                # 这里只是示例，不应该在生产环境中这样使用

            return master_key

    def generate_and_store_key_pair(self) -> Tuple[str, str]:
        """
        生成并存储新的密钥对

        Returns:
            (key_id, public_key_pem): 密钥ID和公钥PEM字符串
        """
        # 生成密钥对
        private_pem, public_pem = signature_service.generate_key_pair()

        # 创建密钥ID
        key_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        # 加密私钥
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(self.master_key), modes.CFB(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_private_key = encryptor.update(private_pem) + encryptor.finalize()

        # 保存密钥信息
        key_info = {
            "key_id": key_id,
            "public_key": public_pem.decode('utf-8'),
            "encrypted_private_key": base64.b64encode(iv + encrypted_private_key).decode('utf-8'),
            "algorithm": signature_service.algorithm_name,
            "created_at": datetime.utcnow().isoformat()
        }

        # 如果存在当前密钥，先归档
        if os.path.exists(self.current_key_file):
            self._archive_current_key()

        # 保存为新当前密钥
        with open(self.current_key_file, 'w') as f:
            json.dump(key_info, f, indent=2)

        return key_id, key_info["public_key"]

    def get_current_key_pair(self) -> Optional[Tuple[str, bytes, bytes]]:
        """
        获取当前密钥对

        Returns:
            (key_id, private_key_pem, public_key_pem) 或 None
        """
        if not os.path.exists(self.current_key_file):
            return None

        with open(self.current_key_file, 'r') as f:
            key_info = json.load(f)

        # 解密私钥
        encrypted_data = base64.b64decode(key_info["encrypted_private_key"])
        iv = encrypted_data[:16]
        ciphertext = encrypted_data[16:]

        cipher = Cipher(algorithms.AES(self.master_key), modes.CFB(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        private_pem = decryptor.update(ciphertext) + decryptor.finalize()

        public_pem = key_info["public_key"].encode('utf-8')

        return key_info["key_id"], private_pem, public_pem

    def get_public_key_by_id(self, key_id: str) -> Optional[bytes]:
        """
        根据 key_id 获取公钥

        Args:
            key_id: 密钥ID

        Returns:
            公钥 PEM 格式字节，如果不存在则返回 None
        """
        # 首先检查当前密钥
        if os.path.exists(self.current_key_file):
            with open(self.current_key_file, 'r') as f:
                key_info = json.load(f)
                if key_info["key_id"] == key_id:
                    return key_info["public_key"].encode('utf-8')

        # 检查历史密钥
        key_file = os.path.join(self.previous_keys_dir, f"{key_id}.json")
        if os.path.exists(key_file):
            with open(key_file, 'r') as f:
                key_info = json.load(f)
                return key_info["public_key"].encode('utf-8')

        return None

    def rotate_key(self) -> Tuple[str, str]:
        """
        密钥轮换：生成新密钥并归档旧密钥

        Returns:
            (new_key_id, new_public_key_pem): 新密钥ID和公钥
        """
        return self.generate_and_store_key_pair()

    def _archive_current_key(self):
        """归档当前密钥"""
        if not os.path.exists(self.current_key_file):
            return

        with open(self.current_key_file, 'r') as f:
            key_info = json.load(f)

        key_id = key_info["key_id"]
        archive_file = os.path.join(self.previous_keys_dir, f"{key_id}.json")

        # 移动到历史目录
        os.rename(self.current_key_file, archive_file)

    def export_key_pair_pkcs12(self, key_id: str, password: str) -> Optional[bytes]:
        """
        导出密钥对为 PKCS#12 格式

        Args:
            key_id: 密钥ID
            password: 导出密码

        Returns:
            PKCS#12 格式的字节数据，如果密钥不存在则返回 None
        """
        # 获取私钥和公钥
        private_key = None
        public_key = None

        # 检查当前密钥
        if os.path.exists(self.current_key_file):
            with open(self.current_key_file, 'r') as f:
                key_info = json.load(f)
                if key_info["key_id"] == key_id:
                    encrypted_data = base64.b64decode(key_info["encrypted_private_key"])
                    iv = encrypted_data[:16]
                    ciphertext = encrypted_data[16:]

                    cipher = Cipher(algorithms.AES(self.master_key), modes.CFB(iv), backend=default_backend())
                    decryptor = cipher.decryptor()
                    private_key = decryptor.update(ciphertext) + decryptor.finalize()
                    public_key = key_info["public_key"].encode('utf-8')

        if private_key is None:
            return None

        # 加载私钥对象
        private_key_obj = serialization.load_pem_private_key(
            private_key,
            password=None,
            backend=default_backend()
        )

        # 导出为 PKCS#12
        from cryptography.hazmat.primitives.serialization.pkcs12 import (
            serialize_key_and_certificates,
            PKCS12CertificateOptions,
            load_key_and_certificates
        )

        # 注意：这里简化处理，实际应该使用完整的证书链
        # 在实际应用中，应该使用证书而不仅仅是公钥
        return None  # 需要完整的证书链实现

    def get_key_info(self) -> dict:
        """
        获取当前密钥信息

        Returns:
            密钥信息字典
        """
        if not os.path.exists(self.current_key_file):
            return {
                "has_current_key": False,
                "message": "No current key found"
            }

        with open(self.current_key_file, 'r') as f:
            key_info = json.load(f)

        # 统计历史密钥数量
        previous_keys = []
        if os.path.exists(self.previous_keys_dir):
            for filename in os.listdir(self.previous_keys_dir):
                if filename.endswith('.json'):
                    key_file = os.path.join(self.previous_keys_dir, filename)
                    with open(key_file, 'r') as f:
                        prev_key_info = json.load(f)
                        previous_keys.append({
                            "key_id": prev_key_info["key_id"],
                            "created_at": prev_key_info["created_at"]
                        })

        return {
            "has_current_key": True,
            "current_key": {
                "key_id": key_info["key_id"],
                "algorithm": key_info["algorithm"],
                "created_at": key_info["created_at"]
            },
            "previous_keys_count": len(previous_keys),
            "previous_keys": sorted(previous_keys, key=lambda x: x["created_at"], reverse=True)[:10]  # 最近10个
        }


# 全局实例
key_management_service = KeyManagementService()
