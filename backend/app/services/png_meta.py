# -*- coding: utf-8 -*-
"""PNG 隐式标识（`tEXt` chunk）读写服务（RQ-01 AC-RQ01-3 / NFR-C13）。

设计取舍：**纯标准库实现，不依赖 Pillow**。原因有二：

1. 隐式标识必须能覆盖**客户端 canvas 导出的 PNG**（H5 / 小程序
   `canvasToTempFilePath` 产物），此时服务端拿到的是既有 PNG 字节，只能做
   chunk 级改写，不能重新编码（重编码会丢画质、放大体积、破坏原图）；
2. 元数据断言（AC-RQ01-4 程序化校验）需要在无图像库的环境下也能跑通。

PNG 结构（ISO/IEC 15948）：8 字节签名 + 若干 chunk，chunk 格式为
`length(4, 大端) | type(4) | data(length) | crc32(4)`，CRC 覆盖 `type + data`。
`tEXt` chunk 的 data 为 `keyword\\0text`，两者均为 Latin-1；因此本模块写入的
元数据值必须是 ASCII 安全字符串（`ai_label` 模块已按此口径构造）。
"""
import struct
import zlib
from typing import Dict, List, Optional, Tuple

# PNG 文件签名
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# 需要写入 / 校验的 chunk 类型（tEXt 为 Latin-1 文本，兼容性最好）
CHUNK_TEXT = b"tEXt"
CHUNK_IEND = b"IEND"

# 单个 tEXt chunk 的 safety 上限（keyword ≤79，text 无硬上限但避免超长）
MAX_TEXT_LEN = 4096


class PngMetadataError(ValueError):
    """PNG 元数据读写失败（非法 PNG / 写入后回读不一致）。"""


def is_png(data: bytes) -> bool:
    """判断字节是否为 PNG（签名比对）。

    Args:
        data: 待判定字节。

    Returns:
        True 表示是 PNG。
    """
    return bool(data) and data[:8] == PNG_SIGNATURE


def _iter_chunks(data: bytes) -> List[Tuple[bytes, bytes]]:
    """解析 PNG 全部 chunk。

    Args:
        data: PNG 字节。

    Returns:
        [(type, data), ...] 列表（顺序与文件一致）。

    Raises:
        PngMetadataError: 签名不符或 chunk 结构损坏。
    """
    if not is_png(data):
        raise PngMetadataError("not a png file")
    chunks: List[Tuple[bytes, bytes]] = []
    pos = 8
    total = len(data)
    while pos + 8 <= total:
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        start = pos + 8
        end = start + length
        if end + 4 > total:
            raise PngMetadataError("truncated png chunk")
        payload = data[start:end]
        chunks.append((ctype, payload))
        pos = end + 4  # 跳过 CRC
        if ctype == CHUNK_IEND:
            break
    if not chunks:
        raise PngMetadataError("no png chunk found")
    return chunks


def _make_chunk(ctype: bytes, payload: bytes) -> bytes:
    """构造一个 PNG chunk（含长度与 CRC32）。

    Args:
        ctype: chunk 类型（4 字节）。
        payload: chunk 数据。

    Returns:
        完整 chunk 字节（length + type + data + crc）。
    """
    crc = zlib.crc32(ctype + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + ctype + payload + struct.pack(">I", crc)


def _text_payload(keyword: str, value: str) -> bytes:
    """构造 tEXt chunk 的数据段（`keyword\\0text`，Latin-1）。

    Args:
        keyword: 键（≤79 字节 ASCII）。
        value: 值（ASCII 安全字符串）。

    Returns:
        Latin-1 编码的数据段。

    Raises:
        PngMetadataError: 键过长、值为空、含 NUL 或无法以 Latin-1 编码。
    """
    if not keyword or len(keyword.encode("latin-1", "ignore")) > 79:
        raise PngMetadataError(f"invalid tEXt keyword: {keyword!r}")
    if "\x00" in keyword or "\x00" in str(value):
        raise PngMetadataError("tEXt keyword/value must not contain NUL")
    try:
        encoded_key = keyword.encode("latin-1")
        encoded_val = str(value).encode("latin-1")
    except UnicodeEncodeError as exc:
        raise PngMetadataError(
            f"tEXt value must be latin-1 encodable (keyword={keyword!r})"
        ) from exc
    if len(encoded_val) > MAX_TEXT_LEN:
        raise PngMetadataError(f"tEXt value too long for keyword={keyword!r}")
    return encoded_key + b"\x00" + encoded_val


def embed_text_metadata(png: bytes, metadata: Dict[str, str]) -> bytes:
    """把元数据写入 PNG 的 `tEXt` chunk（插在 IHDR 之后、IDAT 之前）。

    幂等口径：同名 keyword 的既有 tEXt chunk 会被剔除后重写，保证重复导出
    时元数据一致（AC-RQ01-6「同一长图重复导出元数据一致」）。

    Args:
        png: 原始 PNG 字节（服务端渲染产物或客户端 canvas 产物）。
        metadata: 待写入元数据（键值均须 ASCII / Latin-1 安全）。

    Returns:
        写入后的新 PNG 字节。

    Raises:
        PngMetadataError: 非 PNG / 结构损坏 / 元数据不合法。
    """
    chunks = _iter_chunks(png)
    keywords = set(metadata.keys())
    out = bytearray(PNG_SIGNATURE)
    inserted = False
    for ctype, payload in chunks:
        if ctype == CHUNK_TEXT:
            # 剔除同名 keyword 的旧 chunk（幂等重写）
            name = payload.split(b"\x00", 1)[0].decode("latin-1", "ignore")
            if name in keywords:
                continue
            out += _make_chunk(ctype, payload)
            continue
        out += _make_chunk(ctype, payload)
        if ctype == b"IHDR" and not inserted:
            for key, value in metadata.items():
                out += _make_chunk(CHUNK_TEXT, _text_payload(key, value))
            inserted = True
    if not inserted:
        raise PngMetadataError("IHDR chunk not found, refuse to write metadata")
    return bytes(out)


def read_text_metadata(png: bytes) -> Dict[str, str]:
    """读取 PNG 的全部 `tEXt` 元数据（程序化断言入口）。

    Args:
        png: PNG 字节。

    Returns:
        {keyword: value} 字典（同键取首个）。

    Raises:
        PngMetadataError: 非 PNG 或结构损坏。
    """
    out: Dict[str, str] = {}
    for ctype, payload in _iter_chunks(png):
        if ctype != CHUNK_TEXT:
            continue
        if b"\x00" not in payload:
            continue
        raw_key, raw_val = payload.split(b"\x00", 1)
        key = raw_key.decode("latin-1", "ignore")
        if key and key not in out:
            out[key] = raw_val.decode("latin-1", "ignore")
    return out


def verify_ai_metadata(png: bytes, required_keys: List[str]) -> Tuple[bool, Dict[str, str], List[str]]:
    """校验 PNG 是否带齐隐式标识（AC-RQ01-3 / AC-RQ01-4 门禁断言）。

    Args:
        png: PNG 字节。
        required_keys: 必需元数据键清单。

    Returns:
        (是否通过, 实际元数据, 缺失键列表)。

    Raises:
        PngMetadataError: 非 PNG 或结构损坏（调用方按渲染失败处理）。
    """
    metadata = read_text_metadata(png)
    missing = [key for key in required_keys if not metadata.get(key)]
    return (not missing, metadata, missing)


def strip_text_metadata(png: bytes) -> bytes:
    """剔除全部 `tEXt` chunk（测试与「纯净版」防御校验用）。

    产品不提供「纯净版」导出选项（AC-RQ01-6），本函数仅供测试断言
    「剔除标识后校验必然失败」这一 fail-closed 语义。

    Args:
        png: PNG 字节。

    Returns:
        不含 tEXt chunk 的 PNG 字节。

    Raises:
        PngMetadataError: 非 PNG 或结构损坏。
    """
    out = bytearray(PNG_SIGNATURE)
    for ctype, payload in _iter_chunks(png):
        if ctype == CHUNK_TEXT:
            continue
        out += _make_chunk(ctype, payload)
    return bytes(out)


def describe(png: Optional[bytes]) -> Dict[str, object]:
    """生成 PNG 元数据可读摘要（后台抽检 / 日志用）。

    Args:
        png: PNG 字节或 None。

    Returns:
        {is_png, byte_size, metadata} 字典；None 输入返回 is_png=False。
    """
    if not png:
        return {"is_png": False, "byte_size": 0, "metadata": {}}
    try:
        return {
            "is_png": is_png(png),
            "byte_size": len(png),
            "metadata": read_text_metadata(png),
        }
    except PngMetadataError as exc:
        return {"is_png": False, "byte_size": len(png), "metadata": {}, "error": str(exc)}
