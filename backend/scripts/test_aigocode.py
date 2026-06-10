#!/usr/bin/env python3
"""测试 AIGoCode API 响应速度"""
import asyncio
import time
import os

async def main():
    api_key = os.environ.get("AIGOCODE_API_KEY", "")
    base_url = os.environ.get("AIGOCODE_API_BASE", "https://api.aigocode.com")
    model = os.environ.get("AIGOCODE_MODEL", "claude-opus-4-6")

    if not api_key:
        print("ERROR: AIGOCODE_API_KEY 未设置")
        return

    print(f"API Base: {base_url}")
    print(f"Model:    {model}")
    print(f"Key:      {api_key[:12]}...{api_key[-4:]}")
    print("-" * 50)

    try:
        from anthropic import AsyncAnthropic
        import httpx
    except ImportError:
        print("ERROR: pip install anthropic httpx")
        return

    client = AsyncAnthropic(
        api_key=api_key,
        base_url=base_url,
        timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
        max_retries=0,
    )

    # 测试 1: 短请求
    print("\n[测试 1] 短请求（50字以内）...")
    t0 = time.time()
    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=100,
            messages=[{"role": "user", "content": "用一句话介绍微信公众号"}],
        )
        elapsed = time.time() - t0
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        print(f"  耗时: {elapsed:.1f}s")
        print(f"  输出: {text[:80]}")
        if resp.usage:
            print(f"  Token: prompt={resp.usage.input_tokens} completion={resp.usage.output_tokens}")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  失败 ({elapsed:.1f}s): {type(e).__name__}: {e}")

    # 测试 2: 模拟标题生成（JSON 输出）
    print("\n[测试 2] JSON 输出（模拟标题生成）...")
    t0 = time.time()
    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=500,
            temperature=0.7,
            messages=[{
                "role": "user",
                "content": '为"AI如何改变内容创作"这个主题生成3个公众号标题，输出JSON格式：{"titles": [{"title": "...", "word_count": N}]}'
            }],
        )
        elapsed = time.time() - t0
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        print(f"  耗时: {elapsed:.1f}s")
        print(f"  输出: {text[:120]}")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  失败 ({elapsed:.1f}s): {type(e).__name__}: {e}")

    # 测试 3: 连接耗时（不发请求，只建连）
    print("\n[测试 3] 纯连接测试（DNS+TLS）...")
    t0 = time.time()
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(base_url, timeout=10.0)
            elapsed = time.time() - t0
            print(f"  HTTP {resp.status_code} - {elapsed:.2f}s")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  连接失败 ({elapsed:.1f}s): {type(e).__name__}: {e}")

    print("\n" + "=" * 50)
    print("如果测试1超过30s或测试2超过60s，说明API本身慢")
    print("如果测试3超过5s，说明网络不通或需要配代理")

if __name__ == "__main__":
    asyncio.run(main())
