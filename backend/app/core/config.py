# -*- coding: utf-8 -*-
"""全局配置模块。

基于 pydantic-settings 从 .env 加载运行配置，
提供数据库、大模型、安全密钥等全部配置项的单一真源。
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类。

    属性均为环境变量映射；pydantic-settings 读取顺序为环境变量优先、
    其次 env_file（.env）——注意 .env 文件值只进入本类字段，不写入
    os.environ（需进程环境变量的场景须显式设置环境变量）。
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- 数据库 ---
    database_url: str = (
        "postgresql+psycopg2://postgres:change-me-strong-password@localhost:5432/jiaban"
    )

    # --- 大模型（DeepSeek，OpenAI 兼容） ---
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
    llm_model: str = "deepseek-flash"
    llm_mock: bool = False

    # --- Embedding 通道（spec rag-llamaindex-migration：检索层向量表征） ---
    # zhipu = 智谱 BigModel embedding-3（OpenAI 兼容，境内已备案）；
    # mock  = 确定性本地 mock（联调/CI/测试，conftest 强制 mock 不触网）
    embedding_provider: str = "zhipu"
    zhipu_model: str = "embedding-3"
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    # 真实 key 只存 backend/.env（已 gitignore）；为空时 embed_client 告警并降级 mock
    zhipu_api_key: str = ""
    embedding_dimensions: int = 2048

    # --- JWT ---
    jwt_secret: str = "change-me-strong-jwt-secret"
    jwt_issuer: str = "jiaban"

    # --- 字段加密（本地 Fernet；生产替换为 KMS KeyProvider 实现） ---
    field_enc_key: str = "change-me-strong-fernet-key"

    # --- 模拟支付验签密钥 ---
    pay_mock_sign_key: str = "jiaban-pay-mock-sign-key"

    # --- 免费额度 ---
    free_quota_daily: int = 4

    # --- 档案媒体（头像/相册，甲方需求 2026-10-14） ---
    # 上传文件根目录：相对路径锚定 backend 目录（services.media_store.media_root()）；
    # 生产演进替换为 OSS/对象存储时仅改本配置与 media_store 实现
    upload_dir: str = "data/uploads"
    # 每个档案相册照片上限（头像不计入）
    profile_photo_limit: int = 30

    # --- 缓存后端（spec D2：可选 Redis，缺省回退进程内） ---
    redis_url: str = ""  # 形如 redis://localhost:6379/0；空 = 进程内缓存

    # --- 向量库（spec milvus-vector-store：独立向量库 Milvus standalone） ---
    # 空 = 主通道禁用（检索走 hashing 降级链）；compose 注入 http://milvus:19530，
    # 本地开发 backend/.env 用 http://localhost:19531（宿主端口避让映射）
    milvus_uri: str = ""
    # 可选鉴权 token（standalone 默认无鉴权）
    milvus_token: str = ""

    # --- 通道抽象配置（spec D1：外部凭据留位，缺省用本地实现） ---
    auth_provider: str = "dev"  # dev / wx（wx 需 WX_APPID + WX_SECRET）
    wx_appid: str = ""  # 待业务方提供（留位，不伪造）
    wx_secret: str = ""  # 待业务方提供（留位，不伪造）
    pay_provider: str = "mock"  # mock / wxpay（wxpay 需商户配置）
    wxpay_mch_id: str = ""  # 微信支付商户号（留位）
    wxpay_serial_no: str = ""  # 商户证书序列号（留位）
    wxpay_private_key_path: str = ""  # 商户私钥路径（留位）
    wxpay_api_v3_key: str = ""  # APIv3 密钥（留位，32 字符）
    wxpay_platform_cert_path: str = ""  # 微信支付平台证书/公钥 PEM 路径（回调验签用，留位）
    wxpay_notify_url: str = ""  # 微信支付 V3 回调通知地址（https，JSAPI 下单必填，留位）

    # --- 敏感字段加密 Provider（Task 3.3：配置即切） ---
    # local = 本地 Fernet（默认，v{N}: 前缀多密钥轮换，输出格式不变）；
    # kms = KMS 信封加密（KEK 包裹 DEK，密文头带 provider 标记与 DEK id）
    crypto_provider: str = "local"
    # KMS 主密钥：本地实现下为环境变量主密钥（KEK 派生源）；kms 通道必填
    kms_master_key: str = ""

    # --- 内容安全平台回调（送检异步回调闭环） ---
    # 平台回调共享密钥：配置后 /safety-scan/callback 才接受回调（HMAC-SHA256 验签）
    safety_scan_callback_secret: str = ""

    # --- 字段加密密钥轮换（spec D4） ---
    # field_enc_key = 当前（最新版）密钥；历史密钥以逗号分隔，顺序即 v1..v{n-1}
    field_enc_keys_old: str = ""  # 例: "oldkey1,oldkey2" 对应 v1,v2

    # --- 告警通知（告警闭环：alert_watch 任务超阈值留痕后推送） ---
    alert_webhook_url: str = ""  # 告警 webhook 通知地址，留空=不通知

    # --- 服务 ---
    app_port: int = 8000

    # --- 模型白名单（spec D2：启动时校验，未登记 provider 拒绝启动） ---
    @property
    def model_whitelist(self) -> List[dict]:
        """返回已备案模型白名单快照。

        Returns:
            白名单条目列表，每条含 provider/model/base_url。
        """
        return [
            {
                "provider": "deepseek",
                "model": self.llm_model,
                "base_url": self.llm_base_url,
            },
            {
                "provider": "zhipu",
                "model": self.zhipu_model,
                "base_url": self.zhipu_base_url,
            },
        ]


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例。

    Returns:
        Settings: 全局唯一配置实例。
    """
    return Settings()
