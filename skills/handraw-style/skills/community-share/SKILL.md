---
name: community-share
description: 通用手绘风社区发帖与管理 Skill。打通 handraw-style.com (Discourse) 官方论坛账号系统，具备高度泛用性，支持全板块（创作交流、好用的工具、综合大厅、运营与变现、实战作品与爆款、手绘skill）发布通用图文与纯文本帖子、自动配图直传与短链转换、双语生图提示词出版级智能排版、跟帖回复、帖子列表查询统计及管理删除。触发词：手绘风发帖, 社区发帖, 论坛发帖, 发到论坛, 发到社区, 发布帖子, 分享作品, 手绘提示词分享, 查看我的帖子, 删除帖子.
---

# HandRaw Community Publisher & Manager (手绘风社区通用发帖与内容管理)

本 Skill 是手绘风生态 ([handraw-style.com](https://handraw-style.com)) 的全功能社区发帖与互动管理引擎。
具备**全板块通用性**，支持向论坛的任意板块发布纯文本、图文混合长帖、出版级手绘提示词分享以及跟帖回复，并打通创作者个人帖子资产的全生命周期管理。

---

## 🏛️ 论坛全板块体系与智能路由矩阵

社区内置 6 大核心板块，本 Skill 提供**智能板块解析引擎**，支持直接传板块 ID、板块全称或语义关键词模糊匹配：

| 板块 ID | 板块名称 | Slug 标识 | 核心定位与适用内容 | 推荐匹配关键词 |
| :---: | :--- | :--- | :--- | :--- |
| **4** | **综合大厅** | `creation-monetization` | 社区官方公告、新人报到、生态思辨、行业前瞻资讯 | 公告, 新人, 大厅, 综合, 资讯 |
| **5** | **好用的工具** | `tools` | 开源项目推荐、AI生图/改图工具、工作流分享、排错求助 | 工具, 开源, workflow, 工作流, 软件, 排错 |
| **6** | **创作交流** | `creative-exchange` | 绘画/写作/视频创作经验交流、出版级双语提示词分享 | 创作, 提示词, prompt, 经验, 交流, 画风 |
| **7** | **运营与变现** | `operations` | 自媒体起号与运营实操、推流算法、商业广告与变现案例 | 运营, 变现, 起号, 推流, 带货, 商业, 赚钱 |
| **8** | **实战作品与爆款** | `showcase` | 晒成片、晒图文、爆款拆解、社群互相点评点赞 | 爆款, 作品, 实战, 晒图, 成片, 案例, 拆解 |
| **9** | **手绘skill** | `handraw-skill` | HandRaw Skill（画风库、版式库、提示词工程）专项交流与建议 | skill, 手绘, 技能, 插件, 画风库 |

> [!TIP]
> **板块智能解析规则**：
> - 传数字（如 `5`）或名称（如 `"好用的工具"`）均可识别。
> - 传模糊词（如 `"工具"`、`"变现"`、`"提示词"`）会自动匹配至最契合的板块。
> - 未指定时：作品分享默认进入 `创作交流 (ID: 6)`；通用发帖默认进入 `综合大厅 (ID: 4)`。

---

## 🔄 发帖全流程工作流 (Workflow Architecture)

```mermaid
flowchart TD
    A["用户发帖请求\n(标题/正文/图片/板块)"] --> B["身份鉴权检查\n(whoami: API Key 或 Session)"]
    B --> C["板块智能路由\n(resolve_category: 匹配 ID 4-9)"]
    C --> D{"是否包含配图?"}
    D -- 是 --> E["调用 /uploads.json 直传图片\n获取 Discourse CDN 短链"]
    D -- 否 --> F["跳过图片上传"]
    E --> G["排版渲染引擎\n(通用图文 Markdown 或 出版级提示词卡片)"]
    F --> G
    G --> H["调用 POST /posts.json\n提交标题、正文、板块ID与标签"]
    H --> I["解析返回结果\n提取 Topic ID, Slug & 生成直达链接"]
    I --> J["向用户反馈直达链接与发布成果"]
```

---

## 🛠️ 操作指南与三大发帖模式

所有底层调用均由 `scripts/discourse_client.py` 驱动。

### 1. 账号绑定与凭据管理 (Authentication)

- **检查当前登录账号**：
  ```bash
  python scripts/discourse_client.py whoami
  ```
- **使用 API Key 绑定登录 (推荐模式)**：
  ```bash
  python scripts/discourse_client.py login --api-key <your_api_key>
  ```
- **使用 用户名/邮箱 + 密码 登录**：
  ```bash
  python scripts/discourse_client.py login --username <user> --password <pass>
  ```
- **退出登录并清除本地缓存**：
  ```bash
  python scripts/discourse_client.py logout
  ```

---

### 2. 模式一：通用全板块发帖 (Generic Post)

适用于发布任意讨论、长文教程、工具测评、行业分析或问题求助，支持纯文本或图文混合。

```bash
python scripts/discourse_client.py post \
  --title "【工具推荐】这个手绘风批量导出插件大幅提升出图效率" \
  --category "好用的工具" \
  --content "今天给大家分享一个非常实用的批量切图与转 WebP 格式的脚本..." \
  --image "path/to/screenshot.png" \
  --tags "工具,工作流,分享"
```

- **从本地 Markdown 文件读取正文**：
  正文内容可传入 `@文件路径`：
  ```bash
  python scripts/discourse_client.py post \
    --title "【运营干货】小红书手绘风起号 7 天破万粉复盘" \
    --category "运营与变现" \
    --content "@path/to/post_review.md" \
    --tags "运营,小红书,复盘"
  ```

---

### 3. 模式二：手绘风出版级作品与提示词分享 (Artwork & Prompts Share)

专为手绘风画廊打造，自动将本地画作直传对象存储，并格式化输出包含【画风编号】、【主题色彩】、【创作者名片】、【双语提示词代码块】的出版级社区卡片。

```bash
python scripts/discourse_client.py share \
  --image "path/to/images/poster-demo-autumn-equinox.webp" \
  --prompt "秋分节气手绘海报，暖秋落叶与静谧庭院，水彩手绘质感，极简构图与柔和光影，中英双语设计排版。A minimalist autumn watercolor illustration featuring golden falling leaves, a serene traditional courtyard, warm sunlight, clean layout, hand-drawn aesthetic, high resolution." \
  --title "【秋分节气手绘海报】暖秋意象与落叶 · 完整出版级提示词分享" \
  --category "创作交流" \
  --style "048" \
  --style-name "极简儿童绘本水彩" \
  --color "C-05" \
  --notes "通过 HandRaw Style Studio API Key 一键测试发布，包含完整高清配图与双语生图提示词。"
```

---

### 4. 模式三：跟帖与讨论互动 (Topic Reply)

支持向指定话题发表评论、追问或补充说明：

```bash
python scripts/discourse_client.py reply \
  --topic-id 38 \
  --content "亲测这个提示词在 DALL-E 3 上效果非常稳定，建议采样时把光影参数调柔和一些！" \
  --image "path/to/test_result.png"
```

---

### 5. 帖子资产管理 (Post Management)

- **查看论坛全部板块清单**：
  ```bash
  python scripts/discourse_client.py categories
  ```
- **查看我发布的帖子列表 (实时统计浏览量、点赞、回复)**：
  ```bash
  python scripts/discourse_client.py my-posts [--limit 15]
  ```
- **删除我的帖子**：
  ```bash
  python scripts/discourse_client.py delete --topic-id <topic_id>
  ```

---

## ⚠️ 关键技术细节与协议避坑指南

1. **中文用户名 Header 编码陷阱 (Latin-1 崩溃)**：
   - Python 的标准库 `http.client` 在处理 HTTP Header 时仅允许 `latin-1` 范围字符。
   - 当用户名为非 ASCII 中文（如 `@小旺旺`）时，**切勿向请求头追加 `Api-Username`**。
   - Discourse 支持直接使用 User API Key 鉴权，只需传递 `Api-Key: <key>`，服务器会自动绑定对应的创作者身份。
2. **图片上传协议规范**：
   - 接口：`POST /uploads.json`
   - Content-Type：`multipart/form-data`
   - 必须字段：`type="composer"`, `synchronous="true"`, `file=<二进制流>`。
   - 成功后返回 `short_url`（如 `upload://xxx.webp`），Discourse 前端会自动解析为带 Lightbox 灯箱缩放的高清视图。
3. **Discourse 权限控制规则**：
   - 标题长度：必须 $\ge 5$ 个字符。
   - 帖子删除权限：普通用户（TL1）可以自由删除自己发表的跟帖回复 (`DELETE /posts/{id}.json`)；但删除话题主贴（首楼）受论坛系统管理权限控制，若未配置允许用户删主题，论坛将返回 `422/403` 提示联系管理员。
