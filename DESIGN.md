# 设计说明

## 目标

这个工具面向 Windows 10 + Python 3.11 环境，目标是稳定导出指定 GitLab group/project 范围内的：

- Milestone
- Milestone 对应的 Issue
- Issue 正文

输出结果是面向人阅读和后续再加工的 Markdown 文件。

这一版额外目标是：**零第三方依赖**。  
也就是只要目标机器上有 Python 3.11，就能直接跑。

完整需求基线见 [REQUIREMENTS.md](REQUIREMENTS.md)。本设计文档是在该需求基础上的实现说明。

## 为什么用 GitLab API

这个需求需要的是 GitLab 的业务元数据，不是仓库代码本身。  
因此技术上应走 GitLab REST API，而不是 Git over SSH。

认证方式选择：

- 推荐：Personal Access Token
- 不采用：LDAP 用户名密码直登脚本

原因：

- Token 更稳定
- 权限范围可控
- 不依赖网页登录流程
- 不容易被登录页、验证码、LDAP 中间页、SSO 策略变化打断

## 架构

项目分为五层：

1. `config.py`
   - 负责读取 `key=value` 纯文本配置
   - 处理 Token 读取逻辑

2. `gitlab_api.py`
   - 负责 GitLab REST API 通信
   - 基于 Python 标准库 `urllib`
   - 处理分页
   - 屏蔽 group/project 差异

3. `exporter.py`
   - 负责导出流程编排
   - 负责目录结构生成
   - 负责 Markdown 文件落盘
   - 负责进度日志输出

4. `markdown.py`
   - 负责把 milestone / issue 数据转成 Markdown

5. `runtime_logging.py`
   - 负责把日志同时输出到终端和 `export.log`

## 数据流程

### group 导出流程

1. 调 `GET /groups/:id/milestones?state=all`
2. 遍历每个 milestone
3. 调 `GET /groups/:id/issues?scope=all&state=all&milestone=<title>`
4. 由于 group milestone issues API 对 subgroup 覆盖有限，代码会再按 `issue.milestone.id == milestone.id` 做一次精确过滤
5. 写入 Markdown

### project 导出流程

1. 调 `GET /projects/:id/milestones?state=all`
2. 遍历每个 milestone
3. 调 `GET /projects/:id/milestones/:milestone_id/issues?state=all`
4. 写入 Markdown

## 为什么 group 不直接用 `/groups/:id/milestones/:milestone_id/issues`

GitLab 官方文档说明，这个接口当前**不返回 subgroup 的 issues**。  
所以这里采取了更稳的办法：

- 先用 `groups/:id/issues` 按 milestone 标题过滤
- 再用 milestone id 二次过滤，避免同名误命中

这样更贴近“group 视角下完整导出”的预期。

## 输出结构

按 scope 分目录：

```text
group__dept__platform-group
project__dept__platform-group__project-a
```

每个 scope 下：

- `index.md`：Milestone 总索引
- `<DatePrefix>_<MilestoneName>/milestone.md`
- `<DatePrefix>_<MilestoneName>/issues/*.md`

日期前缀规则：

- milestone 已关闭：取 close 日期
- 若接口未返回 close 日期但状态已关闭：回退取 `updated_at`
- 未关闭但已过期：取 `due_date`
- 其余情况：固定 `20269999`

## 文件名策略

Windows 文件名不能包含：

```text
< > : " / \ | ? *
```

因此实现里做了三层处理：

1. 先清洗非法字符
2. 去掉末尾空格和点号
3. 若仍为空或触发系统保留名，则回退到安全名称

这样可以降低中文标题、特殊符号标题在 Windows 上落盘失败的概率。

## 为什么不用第三方依赖

办公内网常见问题不是代码不会跑，而是：

- `pip` 装不了
- 没法联网拉包
- 镜像源不通
- 安全策略不让装额外依赖

所以这里刻意只用标准库：

- HTTP：`urllib`
- JSON：`json`
- 配置读取：手写 `key=value` 解析
- SSL：`ssl`

## 错误处理

CLI 里区分了几类错误：

- 配置文件不存在
- GitLab API HTTP 错误
- 其他运行错误

这样用户能快速判断是：

- 配置没填好
- Token/URL/权限有问题
- 还是程序逻辑异常

所有运行日志都会落到工具目录下的 `export.log`，便于排查：

- 启动信息
- 当前处理的 group/project
- 当前处理的 milestone
- 已导出 issue 数量
- HTTP 失败
- 未捕获异常堆栈

## 后续可扩展点

如果你后续继续维护，这几个方向最自然：

1. 增加 issue 评论导出
2. 增加附件链接归档
3. 增加 CSV / JSON 双格式导出
4. 增加按 milestone 名称关键词过滤
5. 增加时间范围过滤
6. 增加导出统计汇总页
7. 增加断点续跑和失败重试

## 当前边界

当前版本刻意不做：

- LDAP 登录自动化
- 浏览器模拟登录
- 二进制附件下载
- 评论导出
- exe 打包
- 第三方包依赖

这些都不是做不到，而是第一版为了稳定性和可迁移性，故意先不做。

这些边界也与 [REQUIREMENTS.md](REQUIREMENTS.md) 中“明确不做”部分保持一致。

## 维护建议

如果你后续改代码，优先遵守两条：

1. 不要把认证方式改回账号密码登录
2. 不要把输出格式和接口调用逻辑耦合在一起

前者会明显降低稳定性，后者会让后续改成 HTML/CSV/JSON 时很痛苦。

## 官方接口依据

本工具设计依据 GitLab 官方文档中的这些接口：

- Project milestones API
- Group milestones API
- Issues API

其中 group milestone issue 覆盖 subgroup 的限制，已在实现中规避。
