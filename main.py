import asyncio
import json
import os
import random
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from astrbot.api import logger
from astrbot.api import message_components as Comp
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

SUPPORTED_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

# Quart imports for web API handlers (fallback if astrbot.api.web unavailable)
try:
    from astrbot.api.web import request as web_request
    _HAVE_ASTRBOT_WEB = True
except ImportError:
    _HAVE_ASTRBOT_WEB = False


class RandomKitaPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.plugin_name = "astrbot_plugin_random_kita"

        data_root = self._get_data_root()
        self.data_path = data_root / "plugin_data" / self.plugin_name
        self.images_dir = self.data_path / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

        self.image_files = self._scan_images()
        logger.info(f"随机喜多插件加载成功，当前图片数量: {len(self.image_files)}")

        context.register_web_api(
            f"/{self.plugin_name}/download",
            self.handle_download,
            ["POST"],
            "从 GitHub Release 下载预设图片包",
        )
        context.register_web_api(
            f"/{self.plugin_name}/count",
            self.handle_count,
            ["GET"],
            "获取当前图片数量",
        )
        context.register_web_api(
            f"/{self.plugin_name}/images",
            self.handle_list_images,
            ["GET"],
            "列出所有图片",
        )
        context.register_web_api(
            f"/{self.plugin_name}/image/<path:filename>",
            self.handle_serve_image,
            ["GET"],
            "获取图片文件",
        )
        context.register_web_api(
            f"/{self.plugin_name}/images/delete",
            self.handle_delete_image,
            ["POST"],
            "删除单张图片",
        )
        context.register_web_api(
            f"/{self.plugin_name}/images/batch-delete",
            self.handle_batch_delete,
            ["POST"],
            "批量删除图片",
        )

    def _get_data_root(self) -> Path:
        try:
            from astrbot.core.utils.astrbot_path import get_astrbot_data_path
            return Path(get_astrbot_data_path())
        except ImportError:
            return Path("data")

    def _scan_images(self) -> list[Path]:
        if not self.images_dir.exists():
            return []
        return sorted([
            f for f in self.images_dir.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS
        ])

    def _get_config_url(self) -> str:
        try:
            return getattr(self, 'config', {}).get("github_release_url", "")
        except Exception:
            return ""

    async def _get_request_json(self):
        if _HAVE_ASTRBOT_WEB:
            return await web_request.json(default={})
        from quart import request
        return await request.get_json(force=True, silent=True) or {}

    def _safe_filename(self, name: str) -> str:
        return os.path.basename(name)

    async def _download_images(self, url: str) -> bool:
        try:
            logger.info(f"正在从 {url} 下载喜多图片...")
            loop = asyncio.get_event_loop()

            def _dl():
                with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
                    tmp_path = tmp.name
                urllib.request.urlretrieve(url, tmp_path)
                return tmp_path

            tmp_path = await loop.run_in_executor(None, _dl)

            def _extract():
                with zipfile.ZipFile(tmp_path, 'r') as zf:
                    zf.extractall(self.images_dir)
                os.unlink(tmp_path)

            await loop.run_in_executor(None, _extract)
            self.image_files = self._scan_images()
            logger.info(f"下载完成，当前共 {len(self.image_files)} 张图片")
            return True

        except Exception as e:
            logger.error(f"下载图片失败: {e}")
            return False

    async def handle_download(self):
        url = self._get_config_url()
        if not url:
            logger.warning("下载失败: github_release_url 未配置")
            return {"status": "error", "message": "请先在插件配置中设置「预设图片包下载地址」"}
        ok = await self._download_images(url)
        if ok:
            return {"status": "ok", "data": {"count": len(self.image_files)}}
        logger.error("下载失败，检查 URL 或网络")
        return {"status": "error", "message": "下载失败，请检查 URL 是否正确且服务器能访问该地址"}

    async def handle_count(self):
        self.image_files = self._scan_images()
        return {"count": len(self.image_files)}

    async def handle_list_images(self):
        self.image_files = self._scan_images()
        files = []
        for f in self.image_files:
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "ext": f.suffix.lower(),
            })
        return {"images": files}

    async def handle_serve_image(self, filename: str):
        safe = self._safe_filename(filename)
        filepath = self.images_dir / safe
        if not filepath.exists() or not filepath.is_file():
            return {"error": "not found"}, 404
        from quart import send_file
        return await send_file(str(filepath))

    async def handle_delete_image(self):
        data = await self._get_request_json()
        name = self._safe_filename(data.get("filename", ""))
        if not name:
            return {"status": "error", "message": "缺少文件名"}
        filepath = self.images_dir / name
        if filepath.exists() and filepath.is_file():
            filepath.unlink()
            self.image_files = self._scan_images()
            logger.info(f"删除图片: {name}")
            return {"status": "ok", "data": {"count": len(self.image_files)}}
        return {"status": "error", "message": "文件不存在"}

    async def handle_batch_delete(self):
        data = await self._get_request_json()
        names = data.get("filenames", [])
        if not names:
            return {"status": "error", "message": "缺少文件名列表"}
        deleted = 0
        for n in names:
            safe = self._safe_filename(n)
            fp = self.images_dir / safe
            if fp.exists() and fp.is_file():
                fp.unlink()
                deleted += 1
        self.image_files = self._scan_images()
        logger.info(f"批量删除 {deleted} 张图片")
        return {"status": "ok", "data": {"deleted": deleted, "count": len(self.image_files)}}

    async def _save_image_from_url(self, url: str) -> Path | None:
        try:
            ext = os.path.splitext(url.split('?')[0].split('#')[0])[1]
            if ext.lower() not in SUPPORTED_EXTS:
                ext = '.jpg'

            ts = int(asyncio.get_event_loop().time())
            rand = random.randint(1000, 9999)
            filename = f"kita_{ts}_{rand}{ext}"
            save_path = self.images_dir / filename

            def _dl():
                urllib.request.urlretrieve(url, save_path)

            await asyncio.get_event_loop().run_in_executor(None, _dl)
            return save_path

        except Exception as e:
            logger.error(f"保存图片失败 {url}: {e}")
            return None

    def _collect_image_urls(self, event: AstrMessageEvent) -> list[str]:
        urls = []
        for comp in event.message_obj.message:
            if isinstance(comp, Comp.Image):
                url = getattr(comp, 'url', None) or getattr(comp, 'file', None)
                if url:
                    urls.append(url)

        reply = getattr(event.message_obj, 'reply', None)
        if reply and hasattr(reply, 'message'):
            for comp in reply.message:
                if isinstance(comp, Comp.Image):
                    url = getattr(comp, 'url', None) or getattr(comp, 'file', None)
                    if url:
                        urls.append(url)

        return urls

    @filter.command("随机喜多")
    async def random_kita(self, event: AstrMessageEvent):
        """随机发送一张喜多图片"""
        self.image_files = self._scan_images()
        if not self.image_files:
            yield event.plain_result("还没有喜多图片呢~ 试试用 /上传喜多 来添加叭！")
            return

        img = random.choice(self.image_files)
        yield event.image_result(str(img))

    @filter.command("上传喜多")
    async def upload_kita(self, event: AstrMessageEvent):
        """上传一张喜多图片（直接发送图片或回复带图的消息）"""
        image_urls = self._collect_image_urls(event)

        if not image_urls:
            yield event.plain_result("没有检测到图片~ 请直接发送图片，或回复一张带图片的消息~")
            return

        saved = 0
        for url in image_urls:
            result = await self._save_image_from_url(url)
            if result:
                saved += 1

        self.image_files = self._scan_images()
        yield event.plain_result(f"成功保存 {saved} 张喜多图片！当前共 {len(self.image_files)} 张~")

    @filter.command("喜多数量")
    async def count_kita(self, event: AstrMessageEvent):
        """查看当前喜多图片数量"""
        self.image_files = self._scan_images()
        yield event.plain_result(f"当前有 {len(self.image_files)} 张喜多图片哦~")

    async def terminate(self):
        logger.info("随机喜多插件已卸载，再见~")
