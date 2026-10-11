#!/usr/bin/env python3
"""Playwright Edge 原生极速无头渲染管道。
利用 Windows 原生 Microsoft Edge 无头实例，逐帧抓取 Web 画面，直推 FFmpeg 管道压制。
"""
import argparse
import base64
from pathlib import Path
import subprocess
import sys
import time
import os
import shutil
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import threading
from playwright.sync_api import sync_playwright
from runtime_tools import executable, browser_launch_options


@contextmanager
def local_server(root):
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(Path(root).resolve())))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:' + str(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def render_html_to_video(html_path, out_video, duration, fps=30, width=1920, height=1080,
                         crf=18, preset='fast', stills=None, serve_root=None, start_time=0):
    from production_stage import owner, require
    location = Path(serve_root).resolve() if serve_root else Path(html_path).resolve().parent
    if (owner(location)/'production.json').exists() or (owner(location)/'episode.json').exists():
        require(location)
    if serve_root is None:
        return _render_html_to_video(html_path, out_video, duration, fps, width, height, crf, preset, stills, start_time=start_time)
    root = Path(serve_root).resolve()
    relative = Path(html_path).resolve().relative_to(root).as_posix()
    from urllib.parse import quote
    with local_server(root) as base:
        return _render_html_to_video(html_path, out_video, duration, fps, width, height, crf, preset, stills,
                                    base + '/' + quote(relative),start_time=start_time)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def _render_html_to_video(
    html_path: Path,
    out_video: Path,
    duration: float,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    crf: int = 18,
    preset: str = "fast",
    stills: list = None,
    browser_url: str = None,
    start_time: float = 0
):
    out_video = Path(out_video).resolve()
    out_video.parent.mkdir(parents=True, exist_ok=True)
    html_url = browser_url or html_path.resolve().as_uri()

    total_frames = int(round(duration * fps))

    with sync_playwright() as p:
        # 使用本地 Windows 原生 Edge 内核，免去额外下载 Chromium
        browser = p.chromium.launch(
            **browser_launch_options(),
            args=[
                "--disable-web-security",
                "--enable-gpu-rasterization",
                "--ignore-gpu-blocklist",
                "--allow-file-access-from-files"
            ]
        )
        page = browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=1
        )

        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(html_url)
        page.wait_for_load_state("domcontentloaded")
        page.evaluate("document.fonts && document.fonts.ready")
        page.evaluate("window.ready || Promise.resolve()")
        actual=page.evaluate("(()=>{const c=document.querySelector('canvas');return c?[c.width,c.height]:null})()")
        if actual != [width,height]:
            browser.close()
            raise ValueError(f"模板画布{actual}与输出{width}x{height}不一致；需要按目标画幅重排，不能只改FFmpeg尺寸")
        if errors:
            browser.close()
            raise RuntimeError("模板加载错误: "+"; ".join(errors))

        # 如果是导出静帧模式
        if stills:
            stills_dir = out_video.parent / "stills"
            stills_dir.mkdir(parents=True, exist_ok=True)
            for sec in stills:
                t = float(sec)
                page.evaluate("async t=>{if(window.prepareFrame)await window.prepareFrame(t)}", t)
                frame_data = page.evaluate(f"window.renderFrame ? window.renderFrame({t}) : document.querySelector('canvas').toDataURL('image/png').split(',')[1]")
                png_bytes = base64.b64decode(frame_data)
                img_path = stills_dir / f"frame_{t:06.2f}s.png"
                img_path.write_bytes(png_bytes)
                print(f"[STILL] 导出静帧: {img_path}")
            browser.close()
            return

        # 启动 FFmpeg 管道推流
        ffmpeg_cmd = [
            executable('ffmpeg'), "-y", "-v", "error",
            "-f", "image2pipe",
            "-framerate", str(fps),
            "-c:v", "png",
            "-i", "-",
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            str(out_video)
        ]

        proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

        wall_started = time.time()
        print(f"[RENDER] 开始渲染: 总帧数 {total_frames} 帧, {fps}fps, {width}x{height} -> {out_video.name}")

        try:
            for frame_idx in range(total_frames):
                t = start_time + frame_idx / fps
                page.evaluate("async t=>{if(window.prepareFrame)await window.prepareFrame(t)}", t)
                frame_data = page.evaluate(f"window.renderFrame ? window.renderFrame({t}) : document.querySelector('canvas').toDataURL('image/png').split(',')[1]")
                proc.stdin.write(base64.b64decode(frame_data))
                if frame_idx % 30 == 0 or frame_idx == total_frames - 1:
                    progress = (frame_idx + 1) / total_frames * 100
                    sys.stdout.write(f"\r[RENDER] 进度: {progress:5.1f}% ({frame_idx+1}/{total_frames})")
                    sys.stdout.flush()
            print()
            proc.stdin.close()
            result=proc.wait()
        finally:
            browser.close()
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        if result or errors:
            raise RuntimeError(f"渲染失败: ffmpeg={result}, browser_errors={errors}")

        elapsed = time.time() - wall_started
        fps_real = total_frames / max(0.001, elapsed)
        print(f"[OK] 渲染完成！总耗时: {elapsed:.2f}秒 (平均 {fps_real:.1f} fps) -> {out_video}")

def main():
    parser = argparse.ArgumentParser(description="Playwright Edge 极速渲染器")
    parser.add_argument("--html", required=True, help="要渲染的 HTML 文件绝对或相对路径")
    parser.add_argument("--out", required=True, help="输出 MP4 文件路径")
    parser.add_argument("--duration", type=float, required=True, help="视频总时长（秒）")
    parser.add_argument("--fps", type=int, default=30, help="帧率，默认 30")
    parser.add_argument("--width", type=int, default=1920, help="画布宽度，默认 1920")
    parser.add_argument("--height", type=int, default=1080, help="画布高度，默认 1080")
    parser.add_argument("--stills", help="仅导出逗号分隔秒数的静帧图片，如: 0.5,2.0,4.5")
    args = parser.parse_args()

    stills_list = [float(s.strip()) for s in args.stills.split(",")] if args.stills else None
    render_html_to_video(
        html_path=Path(args.html),
        out_video=Path(args.out),
        duration=args.duration,
        fps=args.fps,
        width=args.width,
        height=args.height,
        stills=stills_list
    )

if __name__ == "__main__":
    main()
