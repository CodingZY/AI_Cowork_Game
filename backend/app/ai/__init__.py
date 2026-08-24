"""Phase 2 AI 图像生成与后处理。

- image_client.ImageGenClient：封装 AutoDL Hunyuan-DiT 生图 API；未配置时返占位图。
- image_pipeline.run_image_pipeline：rembg + crop + padding + resize + format 标准化。
"""
