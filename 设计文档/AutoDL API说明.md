# Hunyuan-DiT 文生图 API 网关

OpenAI 兼容的文生图 HTTP 接口，内部回环调用本机 ComfyUI（`127.0.0.1:8188`）跑 Hunyuan-DiT-v1.1。
代码：`/root/autodl-tmp/hunyuan_gateway/app.py`，启动脚本 `start_gateway.sh`。

## 公网入口

```
https://u1121132-9a6c-aa6aa883.bjb2.seetacloud.com:8443
```

（AutoDL 自定义服务 6006→8443。本地改自己实例的域名即可。）

## 主接口：`POST /v1/images/generations`

### 请求参数（JSON body）

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `prompt` | str | — | **必填**，空则 400 |
| `model` | str | `hunyuan-dit-v1.1` | 固定值 |
| `n` | int | 1 | 生成数量，被 clamp 到 **1..4** |
| `size` | str | `1024x1024` | 目标输出尺寸 `WxH`，对 8 取整，限制 **256..1536**。这是最终输出尺寸；实际 latent 会在 ≥1024² 内部采样再降采样到该尺寸（避免小图花屏） |
| `response_format` | str | `b64_json` | `b64_json` / `url` / `raw` |
| `negative_prompt` | str | 服务端 `NEG` | 负面提示词 |
| `steps` | int | 30 | 采样步数，clamp **1..50** |
| `cfg` | float | 6.0 | CFG，clamp **1.0..20.0** |
| `seed` | int | 随机 | 固定种子时多张图按 `seed+i` 递增；不指定则每张独立随机 |
| `sampler_name` | str | `dpmpp_2m` | 采样器 |
| `scheduler` | str | `karras` | 调度器 |

### 返回结果（按 `response_format`）

- **`b64_json`**（默认，OpenAI 标准）：`{"created": <ts>, "data": [{"b64_json": "<base64 PNG>"}]}`，图片已取走并清理 output 文件。
- **`url`**（OpenAI 标准）：`{"created": <ts>, "data": [{"url": "<PUBLIC_BASE>/v1/files/<filename>"}]}`，**保留** output 文件供后续 `GET /v1/files/{filename}` 下载。
- **`raw`**（本服务扩展，要求 **n=1**）：直接返回 `image/png` 二进制，文件取走后即清理。

### 错误（OpenAI 风格 `{"error": {...}}`）

| HTTP | 触发条件 |
|------|----------|
| 400 | prompt 必填 / response_format 非法 / raw 时 n≠1 / size 解析失败 |
| 503 | 排队超时（`QUEUE_TIMEOUT=120s`，串行锁被占），带 `Retry-After: 30` |
| 504 | 单次生成超时（`GEN_TIMEOUT=180s`） |
| 502 | ComfyUI 执行失败或下载失败 |

## 并发约束

Hunyuan 单次出图峰值显存 ~31GB（5090 共 32GB），**全局 `asyncio.Lock` 串行化所有生成**，uvicorn 必须 `--workers 1`（锁是进程内的）。并发请求排队。

## 其他端点

- `GET /health` → `{"status":"ok","comfyui":"up","vram_used_mib":N}`，ComfyUI 挂了返 502
- `GET /v1/models` → 模型列表
- `GET /v1/files/{filename}?subfolder=` → 下载已生成的 PNG

## 调用示例

### curl（b64_json）

```bash
curl -s https://u1121132-9a6c-aa6aa883.bjb2.seetacloud.com:8443/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-anything" \
  -d '{
    "prompt": "一只柴犬穿着宇航服在月球表面奔跑，背景是蓝色的地球，电影级光影",
    "size": "1024x1024",
    "steps": 30,
    "cfg": 6.0,
    "seed": 42,
    "negative_prompt": "blurry, watermark, low quality"
  }' | jq -r '.data[0].b64_json' | base64 -d > out.png
```

### curl（raw，直接拿 PNG 二进制，要求 n=1）

```bash
curl -s https://u1121132-9a6c-aa6aa883.bjb2.seetacloud.com:8443/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-anything" \
  -d '{
    "prompt": "一只柴犬穿着宇航服在月球表面奔跑，背景是蓝色的地球",
    "response_format": "raw",
    "size": "1024x1024",
    "steps": 30,
    "cfg": 6.0,
    "seed": 42
  }' --output out.png
```

### Python · OpenAI SDK（b64_json）

网关忽略 API key，但 SDK 需要非空值；自定义字段（negative_prompt/steps/cfg/seed）必须走 `extra_body`。

```python
# pip install openai
from openai import OpenAI
import base64

BASE_URL = "https://u1121132-9a6c-aa6aa883.bjb2.seetacloud.com:8443/v1"
client = OpenAI(base_url=BASE_URL, api_key="sk-anything")

resp = client.images.generate(
    model="hunyuan-dit-v1.1",
    prompt="一只柴犬穿着宇航服在月球表面奔跑，背景是蓝色的地球，电影级光影，8k壁纸",
    n=1,
    size="1024x1024",
    response_format="b64_json",
    extra_body={
        "negative_prompt": "worst quality, low quality, blurry, deformed, watermark, text",
        "steps": 30,
        "cfg": 6.0,
        "seed": 42,
    },
)

with open("out_openai.png", "wb") as f:
    f.write(base64.b64decode(resp.data[0].b64_json))
```

### Python · requests（raw，直接拿二进制）

无需 OpenAI SDK，响应体直接是 PNG 字节。生成耗时 10–30s，`timeout` 留足。

```python
# pip install requests
import requests

URL = "https://u1121132-9a6c-aa6aa883.bjb2.seetacloud.com:8443/v1/images/generations"

r = requests.post(
    URL,
    json={
        "prompt": "一只柴犬穿着宇航服在月球表面奔跑，背景是蓝色的地球，电影级光影，8k壁纸",
        "response_format": "raw",        # 本服务扩展：直接返回 PNG 二进制
        "size": "1024x1024",
        "negative_prompt": "blurry, watermark, low quality",
        "steps": 30,
        "cfg": 6.0,
        "seed": 42,
    },
    headers={"Authorization": "Bearer sk-anything"},
    timeout=180,
)
r.raise_for_status()

with open("out_raw.png", "wb") as f:
    f.write(r.content)                    # 已是 PNG 字节，无需 base64
```

## 性能参考

- 模型已缓存时出图 ~3–10s；首次含模型加载 ~25s。
- Hunyuan 出图显存峰值 ~28–31GB。
- 30 步真实出图约 9.4s。

## 启动 / 依赖

```bash
# 1. 先起 ComfyUI（依赖其在 8188）
bash /root/autodl-tmp/start.sh

# 2. 起网关
bash /root/autodl-tmp/hunyuan_gateway/start_gateway.sh
# 后台: nohup ... > gateway.log 2>&1 &
```

依赖：fastapi 0.141.1 + uvicorn 0.52.1（清华源装，需 `unset` 代理绕开阿里云 403）。openai SDK 仅本地机器需装。
