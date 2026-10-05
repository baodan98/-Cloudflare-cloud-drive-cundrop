"""Cloudflare R2 客户端（S3 兼容协议）。"""
import os
from urllib.parse import quote

import boto3
from botocore.config import Config


class R2Client:
    def __init__(self):
        account = os.environ["R2_ACCOUNT_ID"]
        self.bucket = os.environ["R2_BUCKET"]
        endpoint = os.environ.get(
            "R2_ENDPOINT", f"https://{account}.r2.cloudflarestorage.com"
        )
        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    def presigned_put(self, key, mime, expires=3600):
        """浏览器直传 R2 用的预签名 PUT URL。"""
        return self.s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": mime},
            ExpiresIn=expires,
        )

    def presigned_get(self, key, filename="", expires=4 * 3600, download=False):
        """分享页用的预签名 GET URL（支持 Range，视频可拖进度）。
        download=False 用于在线预览/播放；True 则强制下载并携带中文文件名。"""
        params = {"Bucket": self.bucket, "Key": key}
        if download and filename:
            safe = quote(filename)
            params["ResponseContentDisposition"] = (
                f"attachment; filename*=UTF-8''{safe}"
            )
        return self.s3.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=expires
        )

    def head(self, key):
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def delete(self, key):
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
        except Exception:
            pass

    def ping(self):
        """连通性检查：列一下 bucket（只需要 ListBucket 权限）。"""
        self.s3.list_objects_v2(Bucket=self.bucket, MaxKeys=1)
        return True
