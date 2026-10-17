---
name: community-share
description: Connect with handraw-style.com community account. Share generated images and bilingual prompts to the forum, view published posts with views/likes stats, and manage/edit/delete topics.
---

# HandRaw Style Community Integration (社区账号与作品分享)

This Skill integrates HandRaw Style with the official community platform ([handraw-style.com](https://handraw-style.com)).
It allows users to:
1. **Bind & Login Account**: Log in with username/email and password or Discourse API Key, saving authentication credentials securely.
2. **Share Artworks & Prompts**: One-click upload of generated images and bilingual prompts to Discourse, formatting a publication-grade community topic with style number, theme color, prompt code blocks, and tags.
3. **View My Posts**: Query and list all topics published by the user with real-time statistics (views, likes, replies, topic URL).
4. **Manage Posts**: Edit topic content/prompt or delete/archive published topics.

---

## Operational Guide

All community operations are powered by `scripts/discourse_client.py`.

### 1. Account Management (账号绑定与状态检查)

- **Check Current Login Status**:
  ```bash
  python scripts/discourse_client.py whoami
  ```
- **Login with Username & Password**:
  ```bash
  python scripts/discourse_client.py login --username <username_or_email> --password <password>
  ```
- **Login / Bind with API Key**:
  ```bash
  python scripts/discourse_client.py login --api-key <api_key> [--username <username>]
  ```
- **Logout (清除本地凭据)**:
  ```bash
  python scripts/discourse_client.py logout
  ```

---

### 2. Share Image & Prompt to Forum (作品与提示词一键分享)

When the user asks to "分享这幅画到社区", "把作品和提示词发到论坛", or "发布手绘风帖子":

```bash
python scripts/discourse_client.py share \
  --image "<path_to_image>" \
  --prompt "<full_bilingual_prompt>" \
  --title "【手绘风 #048】拉绳子的小人" \
  --style "048" \
  --style-name "极简儿童绘本" \
  --color "C-01" \
  --notes "创作心得与使用模型..."
```

**What this does automatically:**
1. Uploads the image binary to `https://handraw-style.com/uploads.json`.
2. Generates an aesthetic Discourse Markdown topic with the image banner, style pill, color badge, creator signature, copyable prompt code block, and auto-generated tags (`手绘风`, `style-048`, `提示词分享`).
3. Submits the topic to the forum and returns the clickable URL `https://handraw-style.com/t/<slug>/<topic_id>`.

---

### 3. View My Posts (查看我的帖子)

When the user asks "查看我发的帖子", "我的社区动态", or "查看帖子数据":

```bash
python scripts/discourse_client.py my-posts [--limit 20]
```

Returns the structured post list with topic IDs, titles, direct URLs, views, likes, and reply counts.

---

### 4. Manage / Delete Posts (管理与删除帖子)

When the user asks to delete a post:

```bash
python scripts/discourse_client.py delete --topic-id <topic_id>
```
