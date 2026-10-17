#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HandRaw Style Community Client - 社区账号与内容管理模块
用于打通手绘风网站 (handraw-style.com) Discourse 账号系统，
支持：账号登录/绑定、作品与提示词一键分享发布、查看和管理（编辑/删除）我的帖子。
"""

import os
import sys
import json
import uuid
import mimetypes
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
from pathlib import Path

# 默认手绘风社区基准配置
DEFAULT_COMMUNITY_URL = "https://handraw-style.com"
DEFAULT_CATEGORY_ID = 4  # 默认板块: 创作与变现

# 凭据存储路径 (优先用户主目录 ~/.handraw-style/，后备客户端缓存目录)
HOME_DIR = Path.home() / ".handraw-style"
AUTH_FILE = HOME_DIR / "community_auth.json"
COOKIE_FILE = HOME_DIR / "community_cookies.txt"

CLIENT_CACHE_DIR = Path("E:/handraw-style/client/cache")
CLIENT_AUTH_FILE = CLIENT_CACHE_DIR / "community_auth.json"


def ensure_auth_dirs():
    HOME_DIR.mkdir(parents=True, exist_ok=True)
    try:
        CLIENT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def load_auth_profile():
    """读取已保存的用户登录凭据"""
    for filepath in [AUTH_FILE, CLIENT_AUTH_FILE]:
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data and (data.get("api_key") or data.get("session_cookie") or data.get("username")):
                        return data
            except Exception:
                pass
    return None


def save_auth_profile(data):
    """保存用户登录凭据到本地文件"""
    ensure_auth_dirs()
    success = False
    for filepath in [AUTH_FILE, CLIENT_AUTH_FILE]:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            success = True
        except Exception:
            pass
    return success


def clear_auth_profile():
    """清除登录凭据 (退出登录)"""
    for filepath in [AUTH_FILE, CLIENT_AUTH_FILE, COOKIE_FILE]:
        if filepath.exists():
            try:
                os.remove(filepath)
            except Exception:
                pass


class DiscourseClient:
    def __init__(self, base_url=DEFAULT_COMMUNITY_URL):
        self.base_url = base_url.rstrip("/")
        self.cookie_jar = http.cookiejar.LWPCookieJar()
        ensure_auth_dirs()
        if COOKIE_FILE.exists():
            try:
                self.cookie_jar.load(str(COOKIE_FILE), ignore_discard=True, ignore_expires=True)
            except Exception:
                pass
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.auth = load_auth_profile() or {}

    def _save_cookies(self):
        try:
            self.cookie_jar.save(str(COOKIE_FILE), ignore_discard=True, ignore_expires=True)
        except Exception:
            pass

    def get_csrf_token(self):
        """获取 Discourse CSRF Token"""
        req = urllib.request.Request(
            f"{self.base_url}/session/csrf.json",
            headers={
                "User-Agent": "HandRawStudio/1.0",
                "Accept": "application/json"
            }
        )
        with self.opener.open(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("csrf", "")

    def login_with_password(self, username_or_email, password):
        """
        使用用户名/邮箱与密码登录 Discourse
        """
        csrf = self.get_csrf_token()
        payload = urllib.parse.urlencode({
            "login": username_or_email,
            "password": password
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/session",
            data=payload,
            headers={
                "User-Agent": "HandRawStudio/1.0",
                "X-CSRF-Token": csrf,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )

        with self.opener.open(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("error"):
                raise ValueError(data.get("error"))

            user_info = data.get("user") or {}
            self._save_cookies()

            profile = {
                "auth_type": "session",
                "username": user_info.get("username", username_or_email),
                "user_id": user_info.get("id"),
                "name": user_info.get("name"),
                "avatar_template": user_info.get("avatar_template"),
                "trust_level": user_info.get("trust_level"),
                "base_url": self.base_url
            }
            save_auth_profile(profile)
            self.auth = profile
            return profile

    def login_with_api_key(self, api_key, username=None):
        """
        使用 Discourse API Key 绑定登录
        """
        headers = {
            "Api-Key": api_key,
            "User-Agent": "HandRawStudio/1.0",
            "Accept": "application/json"
        }
        if username:
            try:
                # 仅 ASCII 用户名可安全放入 Api-Username 请求头
                username.encode('ascii')
                headers["Api-Username"] = username
            except UnicodeEncodeError:
                pass

        req = urllib.request.Request(f"{self.base_url}/session/current.json", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            user_info = data.get("current_user") or {}
            real_username = user_info.get("username") or username or "user"
            profile = {
                "auth_type": "api_key",
                "api_key": api_key,
                "username": real_username,
                "user_id": user_info.get("id"),
                "name": user_info.get("name"),
                "avatar_template": user_info.get("avatar_template"),
                "trust_level": user_info.get("trust_level"),
                "base_url": self.base_url
            }
            save_auth_profile(profile)
            self.auth = profile
            return profile

    def whoami(self):
        """获取当前登录用户信息"""
        if not self.auth:
            return {"logged_in": False}

        username = self.auth.get("username")
        # 尝试在线校验最新会话状态
        headers = {"User-Agent": "HandRawStudio/1.0", "Accept": "application/json"}
        if self.auth.get("api_key"):
            headers["Api-Key"] = self.auth.get("api_key")
            try:
                username.encode('ascii')
                headers["Api-Username"] = username
            except (UnicodeEncodeError, AttributeError):
                pass
            req = urllib.request.Request(f"{self.base_url}/session/current.json", headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    u = data.get("current_user")
                    if u:
                        self.auth.update({
                            "username": u.get("username"),
                            "name": u.get("name"),
                            "avatar_template": u.get("avatar_template"),
                            "trust_level": u.get("trust_level"),
                            "user_id": u.get("id")
                        })
                        save_auth_profile(self.auth)
            except Exception:
                pass

        return {
            "logged_in": True,
            "username": self.auth.get("username"),
            "name": self.auth.get("name"),
            "user_id": self.auth.get("user_id"),
            "trust_level": self.auth.get("trust_level"),
            "avatar_url": self.get_avatar_url(self.auth.get("avatar_template")),
            "auth_type": self.auth.get("auth_type"),
            "community_url": self.base_url
        }

    def get_avatar_url(self, template, size=120):
        if not template:
            return f"{self.base_url}/images/avatar.png"
        url = template.replace("{size}", str(size))
        if not url.startswith("http"):
            url = f"{self.base_url}{url}"
        return url

    def upload_image(self, file_path_or_bytes, filename=None):
        """上传图片到 Discourse，返回 upload 对象"""
        if isinstance(file_path_or_bytes, (str, Path)):
            path = Path(file_path_or_bytes)
            if not path.exists():
                raise FileNotFoundError(f"本地图片文件不存在: {path}")
            filename = filename or path.name
            with open(path, "rb") as f:
                img_data = f.read()
        else:
            img_data = file_path_or_bytes
            filename = filename or f"handraw_{uuid.uuid4().hex[:8]}.png"

        mime_type, _ = mimetypes.guess_type(filename)
        mime_type = mime_type or "image/png"

        boundary = f"----HandRawBoundary{uuid.uuid4().hex}"
        body = bytearray()
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\ncomposer\r\n'.encode('utf-8'))
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="synchronous"\r\n\r\ntrue\r\n'.encode('utf-8'))
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {mime_type}\r\n\r\n'.encode('utf-8'))
        body.extend(img_data)
        body.extend(f'\r\n--{boundary}--\r\n'.encode('utf-8'))

        headers = {
            "User-Agent": "HandRawStudio/1.0",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json"
        }

        # 认证头装配
        if self.auth.get("api_key"):
            headers["Api-Key"] = self.auth.get("api_key")
            username = self.auth.get("username")
            if username:
                try:
                    username.encode('ascii')
                    headers["Api-Username"] = username
                except UnicodeEncodeError:
                    pass
            req = urllib.request.Request(f"{self.base_url}/uploads.json", data=bytes(body), headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        else:
            csrf = self.get_csrf_token()
            headers["X-CSRF-Token"] = csrf
            req = urllib.request.Request(f"{self.base_url}/uploads.json", data=bytes(body), headers=headers)
            with self.opener.open(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))

    def share_creation(self, image_path, prompt, title=None, style_id=None, style_name=None,
                       color_id=None, color_name=None, category_id=DEFAULT_CATEGORY_ID, tags=None, notes=None):
        """
        一键分享作品与提示词到社区论坛
        """
        if not self.auth:
            raise PermissionError("尚未登录手绘风社区账号，请先执行登录或绑定！")

        print(f"[*] 正在上传作品图片至手绘风社区: {image_path} ...")
        upload_res = self.upload_image(image_path)
        img_url = upload_res.get("url") or upload_res.get("short_url")
        short_url = upload_res.get("short_url") or img_url
        orig_name = upload_res.get("original_filename", "作品")

        # 智能生成标题
        if not title:
            style_label = f"#{style_id}" if style_id else "原创手绘"
            theme_snippet = prompt.split("，")[0].split("。")[0].split(",")[0][:25]
            title = f"【手绘风 {style_label}】{theme_snippet}"

        if len(title) < 5:
            title = f"{title} · 手绘风创作分享"

        # 构造图文出版级 Markdown 帖子结构
        meta_items = []
        if style_id:
            s_name = f" · {style_name}" if style_name else ""
            meta_items.append(f"🎨 **画风编号**：`#{style_id}{s_name}`")
        if color_id:
            c_name = f" · {color_name}" if color_name else ""
            meta_items.append(f"🌈 **主题色彩**：`{color_id}{c_name}`")
        meta_items.append(f"👤 **创作者**：@{self.auth.get('username')}")

        meta_block = "\n".join(meta_items)

        notes_block = f"\n> 💡 **创作心得/说明**：\n> {notes}\n" if notes else ""

        raw_content = f"""![{orig_name}]({short_url})

{meta_block}
{notes_block}
---

### 📝 完整出版级生图提示词 (Prompts)

```markdown
{prompt.strip()}
```

---
*本帖由 [HandRaw Style Studio](https://handraw-style.com) 一键分享生成。欢迎点赞、交流与临摹复现！*
"""

        topic_payload = {
            "title": title,
            "raw": raw_content,
            "category": category_id
        }
        if tags and isinstance(tags, list):
            topic_payload["tags"] = tags
        else:
            auto_tags = ["手绘风", "提示词分享"]
            if style_id:
                auto_tags.append(f"style-{style_id}")
            topic_payload["tags"] = auto_tags

        print(f"[*] 正在发布帖子: 《{title}》 ...")
        post_data = self._post_json(f"{self.base_url}/posts.json", topic_payload)

        topic_id = post_data.get("topic_id")
        topic_slug = post_data.get("topic_slug", "topic")
        post_id = post_data.get("id")
        full_url = f"{self.base_url}/t/{topic_slug}/{topic_id}"

        return {
            "success": True,
            "post_id": post_id,
            "topic_id": topic_id,
            "topic_slug": topic_slug,
            "title": title,
            "url": full_url,
            "image_url": img_url
        }

    def list_my_posts(self, username=None, limit=20):
        """
        获取当前登录用户发布的全部帖子列表
        """
        target_user = username or self.auth.get("username")
        if not target_user:
            raise PermissionError("请先登录或指定用户名查看帖子！")

        quoted_user = urllib.parse.quote(target_user)
        url = f"{self.base_url}/topics/created-by/{quoted_user}.json"

        headers = {"User-Agent": "HandRawStudio/1.0", "Accept": "application/json"}
        if self.auth.get("api_key"):
            headers["Api-Key"] = self.auth.get("api_key")
            u = self.auth.get("username")
            if u:
                try:
                    u.encode('ascii')
                    headers["Api-Username"] = u
                except UnicodeEncodeError:
                    pass
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        else:
            req = urllib.request.Request(url, headers=headers)
            with self.opener.open(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

        topics = data.get("topic_list", {}).get("topics", [])
        results = []
        for t in topics[:limit]:
            topic_id = t.get("id")
            slug = t.get("slug", "topic")
            image_url = t.get("image_url")
            if image_url and not image_url.startswith("http"):
                image_url = f"{self.base_url}{image_url}"

            results.append({
                "topic_id": topic_id,
                "title": t.get("title"),
                "slug": slug,
                "url": f"{self.base_url}/t/{slug}/{topic_id}",
                "created_at": t.get("created_at"),
                "views": t.get("views", 0),
                "like_count": t.get("like_count", 0),
                "posts_count": t.get("posts_count", 1),
                "image_url": image_url,
                "category_id": t.get("category_id")
            })
        return results

    def delete_post(self, topic_id=None, post_id=None):
        """
        删除帖子或主题 (需要当前用户具备删除权限)
        """
        if not self.auth:
            raise PermissionError("尚未登录手绘风社区账号！")

        if topic_id:
            url = f"{self.base_url}/t/{topic_id}.json"
        elif post_id:
            url = f"{self.base_url}/posts/{post_id}.json"
        else:
            raise ValueError("必须提供 topic_id 或 post_id")

        headers = {
            "User-Agent": "HandRawStudio/1.0",
            "Accept": "application/json"
        }

        if self.auth.get("api_key"):
            headers["Api-Key"] = self.auth.get("api_key")
            username = self.auth.get("username")
            if username:
                try:
                    username.encode('ascii')
                    headers["Api-Username"] = username
                except UnicodeEncodeError:
                    pass
            req = urllib.request.Request(url, headers=headers, method="DELETE")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 204)
        else:
            csrf = self.get_csrf_token()
            headers["X-CSRF-Token"] = csrf
            req = urllib.request.Request(url, headers=headers, method="DELETE")
            with self.opener.open(req, timeout=10) as resp:
                return resp.status in (200, 204)

    def edit_post(self, post_id, new_raw, new_title=None):
        """编辑帖子内容或标题"""
        payload = {"post": {"raw": new_raw}}
        if new_title:
            payload["title"] = new_title
        return self._put_json(f"{self.base_url}/posts/{post_id}.json", payload)

    def _post_json(self, url, payload):
        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "User-Agent": "HandRawStudio/1.0",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.auth.get("api_key"):
            headers["Api-Key"] = self.auth.get("api_key")
            username = self.auth.get("username")
            if username:
                try:
                    username.encode('ascii')
                    headers["Api-Username"] = username
                except UnicodeEncodeError:
                    pass
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        else:
            csrf = self.get_csrf_token()
            headers["X-CSRF-Token"] = csrf
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
            with self.opener.open(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))

    def _put_json(self, url, payload):
        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "User-Agent": "HandRawStudio/1.0",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.auth.get("api_key"):
            headers["Api-Key"] = self.auth.get("api_key")
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method="PUT")
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        else:
            csrf = self.get_csrf_token()
            headers["X-CSRF-Token"] = csrf
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method="PUT")
            with self.opener.open(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))


# ---------------- 命令行 CLI 支持 ----------------

def cli_main():
    import argparse
    parser = argparse.ArgumentParser(description="HandRaw Style 社区互动命令行工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # login
    p_login = subparsers.add_parser("login", help="登录手绘风社区账号")
    p_login.add_argument("--username", "-u", help="用户名或邮箱")
    p_login.add_argument("--password", "-p", help="登录密码")
    p_login.add_argument("--api-key", "-k", help="Discourse API Key (可选直接绑定)")

    # whoami
    subparsers.add_parser("whoami", help="查看当前登录账号状态")

    # logout
    subparsers.add_parser("logout", help="退出当前登录账号")

    # share
    p_share = subparsers.add_parser("share", help="分享图片与提示词到社区")
    p_share.add_argument("--image", "-i", required=True, help="要分享的图片本地路径")
    p_share.add_argument("--prompt", required=True, help="生成的完整提示词")
    p_share.add_argument("--title", "-t", help="帖子标题（留空自动生成）")
    p_share.add_argument("--style", "-s", help="画风编号 (如 048)")
    p_share.add_argument("--style-name", help="画风名称")
    p_share.add_argument("--color", "-c", help="主题色编号 (如 C-01)")
    p_share.add_argument("--notes", "-n", help="创作心得或说明")

    # my-posts
    p_posts = subparsers.add_parser("my-posts", help="查看我发布的帖子列表")
    p_posts.add_argument("--limit", type=int, default=15, help="显示数量")

    # delete
    p_del = subparsers.add_parser("delete", help="删除我的指定帖子")
    p_del.add_argument("--topic-id", type=int, required=True, help="要删除的主题 ID")

    args = parser.parse_args()
    client = DiscourseClient()

    if args.command == "login":
        if args.api_key:
            res = client.login_with_api_key(args.api_key, args.username)
            print(f"[OK] API Key 绑定成功！欢迎创作者: @{res.get('username')}")
        elif args.username and args.password:
            res = client.login_with_password(args.username, args.password)
            print(f"[OK] 登录成功！欢迎回来: @{res.get('username')} (信任等级: TL{res.get('trust_level')})")
        else:
            print("请输入 --username 和 --password，或提供 --api-key 进行登录。")

    elif args.command == "whoami":
        info = client.whoami()
        if info.get("logged_in"):
            print(f"✅ 当前已登录手绘风社区账号:")
            print(f"   用户名: @{info.get('username')}")
            print(f"   昵称: {info.get('name') or '无'}")
            print(f"   社区地址: {info.get('community_url')}")
            print(f"   认证方式: {info.get('auth_type')}")
        else:
            print("❌ 当前未登录任何手绘风社区账号。请使用 login 命令进行登录绑定。")

    elif args.command == "logout":
        clear_auth_profile()
        print("[OK] 已安全退出手绘风社区账号并清除本地凭据。")

    elif args.command == "share":
        res = client.share_creation(
            image_path=args.image,
            prompt=args.prompt,
            title=args.title,
            style_id=args.style,
            style_name=args.style_name,
            color_id=args.color,
            notes=args.notes
        )
        print(f"🎉 作品与提示词已成功分享到手绘风社区！")
        print(f"   标题: {res.get('title')}")
        print(f"   直达链接: {res.get('url')}")

    elif args.command == "my-posts":
        posts = client.list_my_posts(limit=args.limit)
        if not posts:
            print("暂未发布任何帖子。快去生成一幅手绘画作分享吧！")
        else:
            print(f"📚 你在手绘风社区发布的帖子列表 (共 {len(posts)} 条):")
            for idx, p in enumerate(posts, 1):
                print(f"[{idx}] (ID: {p['topic_id']}) {p['title']}")
                print(f"    链接: {p['url']} | 浏览: {p['views']} | 点赞: {p['like_count']} | 回复: {p['posts_count']}")

    elif args.command == "delete":
        ok = client.delete_post(topic_id=args.topic_id)
        if ok:
            print(f"🗑️ 帖子 (ID: {args.topic_id}) 已成功删除。")
        else:
            print(f"删除失败，请检查网络或是否拥有该帖子的删除权限。")

    else:
        parser.print_help()


if __name__ == "__main__":
    cli_main()
