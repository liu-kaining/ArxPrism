"""
Cloudflare R2 对象存储服务

用于存储和访问论文 PDF 文件。

配置项 (环境变量):
- R2_ENABLED: 是否启用 R2 存储
- R2_ACCOUNT_ID: R2 Account ID
- R2_ACCESS_KEY_ID: R2 Access Key ID
- R2_SECRET_ACCESS_KEY: R2 Secret Access Key
- R2_BUCKET_NAME: Bucket 名称
- R2_PUBLIC_URL: 公开访问 URL 前缀
"""

import logging
import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from pathlib import Path
from typing import Optional

from src.core.config import settings

logger = logging.getLogger(__name__)


class R2Storage:
    """Cloudflare R2 存储服务客户端."""

    def __init__(self) -> None:
        self.enabled = settings.r2_enabled
        self.bucket_name = settings.r2_bucket_name
        self.public_url = settings.r2_public_url.rstrip("/")

        if not self.enabled:
            logger.info("R2 storage is disabled, using local storage only")
            self._client = None
            return

        if not all([settings.r2_account_id, settings.r2_access_key_id, settings.r2_secret_access_key]):
            logger.warning("R2 credentials not fully configured, falling back to local storage")
            self.enabled = False
            self._client = None
            return

        # 创建 S3 兼容客户端 (R2 使用 S3 API)
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            config=BotoConfig(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"}
            )
        )
        logger.info(f"R2 storage initialized: bucket={self.bucket_name}")

    def upload_pdf(self, local_path: str, arxiv_id: str) -> Optional[str]:
        """
        上传 PDF 文件到 R2.

        Args:
            local_path: 本地 PDF 文件路径
            arxiv_id: arXiv 论文 ID (用于 R2 对象键)

        Returns:
            R2 公开访问 URL，失败返回 None
        """
        if not self.enabled or not self._client:
            logger.warning("R2 not enabled, skipping upload")
            return None

        local_file = Path(local_path)
        if not local_file.exists():
            logger.error(f"Local PDF file not found: {local_path}")
            return None

        object_key = f"papers/{arxiv_id}.pdf"

        try:
            self._client.upload_file(
                str(local_file),
                self.bucket_name,
                object_key,
                ExtraArgs={
                    "ContentType": "application/pdf",
                    "Metadata": {
                        "arxiv_id": arxiv_id,
                        "source": "arxprism"
                    }
                }
            )
            logger.info(f"Uploaded PDF to R2: {object_key}")

            # 返回公开访问 URL
            public_url = f"{self.public_url}/{object_key}"
            return public_url

        except ClientError as e:
            logger.error(f"Failed to upload PDF to R2: {e}")
            return None

    def get_pdf_url(self, arxiv_id: str) -> Optional[str]:
        """
        获取 PDF 的公开访问 URL.

        Args:
            arxiv_id: arXiv 论文 ID

        Returns:
            公开访问 URL
        """
        if not self.enabled:
            return None

        object_key = f"papers/{arxiv_id}.pdf"
        return f"{self.public_url}/{object_key}"

    def delete_pdf(self, arxiv_id: str) -> bool:
        """
        从 R2 删除 PDF 文件.

        Args:
            arxiv_id: arXiv 论文 ID

        Returns:
            是否删除成功
        """
        if not self.enabled or not self._client:
            return False

        object_key = f"papers/{arxiv_id}.pdf"

        try:
            self._client.delete_object(Bucket=self.bucket_name, Key=object_key)
            logger.info(f"Deleted PDF from R2: {object_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete PDF from R2: {e}")
            return False

    def pdf_exists(self, arxiv_id: str) -> bool:
        """
        检查 PDF 是否已存在于 R2.

        Args:
            arxiv_id: arXiv 论文 ID

        Returns:
            是否存在
        """
        if not self.enabled or not self._client:
            return False

        object_key = f"papers/{arxiv_id}.pdf"

        try:
            self._client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError:
            return False


# 全局实例
r2_storage = R2Storage()


def get_r2_storage() -> R2Storage:
    """获取 R2 存储实例."""
    return r2_storage
