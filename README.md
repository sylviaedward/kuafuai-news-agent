# AI Daily：每日 AI 新闻助手 Agent（选项 A）

一个可运行的 Python Agent 作业：用户设置身份、话题与关键词；系统每天按北京时间检查订阅；模型通过 **function calling 循环自主选择工具、调用次数和停止时机**，生成有来源链接的 AI 新闻简报，并投递到站内收件箱。配置 SMTP 后也会发送邮件。

## 5 分钟启动

需要 Python 3.11+ 和网络连接。新闻从公开 RSS 获取，模型需支持 OpenAI 兼容的 Chat Completions + function calling。

```bash
cp .env.example .env
# 编辑 .env，填写 OPENAI_COMPAT_API_KEY 和 OPENAI_COMPAT_MODEL。
# 若使用其他兼容服务，也修改 OPENAI_COMPAT_BASE_URL。
chmod +x start.sh
./start.sh
```

打开 <http://127.0.0.1:8000>，填姓名、邮箱、话题和关键词，保存后点“立即生成一份简报”。首次启动会自动建 SQLite 数据库，建表脚本在 `sql/001_init.sql`。API 文档在 <http://127.0.0.1:8000/docs>。

**没有模型密钥时**：页面、订阅设置和历史简报仍可访问；生成接口会明确返回 503。仓库不包含任何模型密钥，也不使用预制新闻冒充实时结果。若要真实邮件推送，在 `.env` 里填写 `SMTP_HOST`、`SMTP_FROM` 等字段；未配置时投递到站内收件箱。

## 如何满足 A 题

| 要求 | 实现 |
| --- | --- |
| 用户身份与偏好 | 姓名、邮箱、话题、关键词和每日投递小时；SQLite 持久化 |
| 真实新闻来源 | Google AI Blog、arXiv cs.AI/cs.LG、MarkTechPost 的 RSS；只取近 14 天，展示原文链接和发布时间 |
| Agent Loop | `app/agent.py` 最多 12 轮模型决策、24 次工具调用；模型决定工具顺序及何时返回最终 JSON |
| 指定 5 个工具 | `list_dir`、`read_file`、`search_content`、`write_file`、`bash`，另有 `search_news`；定义与执行见 `app/tools.py` |
| 每日自动推送 | 后台线程每分钟检查一次，按 `Asia/Shanghai` 的用户设定小时执行；同一用户同一天只有一条定时任务 |
| 历史简报 | SQLite 保留简报、状态、来源、投递状态与工具轨迹；页面可查看 |
| 配置和依赖 | `.env.example`、`requirements.txt`、`start.sh`；密钥不进 Git |

### 工具循环的边界

系统先获取一批新闻候选，这是数据源适配层，不决定简报内容。模型可调用 `search_news(query)` 搜索这批新闻，也可按自己的需要调用五个文件/命令工具。模型若停止调用工具，必须返回指定 JSON。服务器核对每条 `source_id` 是否来自**该轮实际搜索结果**，再把真实来源链接、标题和时间附回简报。校验失败会让模型继续修正。这样能阻止伪造来源，但不能完全保证摘要准确，因此页面要求点击原文核实。

`bash` 只允许工作区内的 `pwd`、`date`、`ls [path]` 和 `rg keyword`。文件工具仅能访问当前运行的独立工作区。限制是为避免模型误删文件、读取密钥或执行任意命令；工具名称与签名仍满足题目要求。

### 定时与投递语义

每天达到用户设定小时后，调度器创建定时任务。数据库的部分唯一索引 `(user_id, local_day) WHERE is_manual=0` 防止同一天重复投递。若服务在设定时间之后启动，会在当天补跑一次。手动生成允许重复，用于演示和调试。服务需要持续运行；生产场景可把同一个 `tick` 逻辑放进独立 worker/cron，并把任务状态与重试机制做得更完整。

站内收件箱是默认的真实投递目标。邮件为可选外部渠道；邮件故障不会丢失站内简报，投递状态会标记邮件失败。此项目是本地演示版，用户身份通过邮箱区分，**没有登录鉴权**，不应直接作为公网多用户服务部署。

## 代码结构

```text
app/agent.py       LLM 工具循环、预算与引用校验
app/tools.py       6 个工具及工作区限制
app/news.py        RSS 抓取、解析、去重和搜索
app/scheduler.py   每日任务与后台执行
app/delivery.py    站内及可选 SMTP 投递
app/db.py          SQLite 读写
app/main.py        FastAPI 与静态页面
app/static/        原生 HTML/CSS/JS 页面
sql/001_init.sql   建表与幂等索引
tests/            核心行为测试
```

## 验证

```bash
.venv/bin/python -m pytest -q
```

测试覆盖多轮且非固定顺序的工具调用、引用校验、路径/命令限制、RSS 解析与定时幂等。实际模型效果取决于所配置模型和新闻源可用性。

## 可扩展点与已知限制

- RSS 站点可能中断或延迟更新；当前会继续使用其他可用源，并把源错误记录在工具轨迹中。全部来源不可用则明确失败，不生成假新闻。
- 中文关键词和英文 RSS 的字面搜索可能不匹配；`search_news` 可使用英文查询，最终由模型结合订阅意图筛选。可扩展为向量召回或搜索 API。
- 目前每次运行重新拉取 RSS；用户多时可增加共享缓存和请求限流。
- 只提供站内身份识别，未实现账号认证、邮件验证、细粒度权限和分布式任务队列。

