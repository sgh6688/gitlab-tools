# 设计说明

## 1. 产品定位

`gitlab-tools` 是可持续增加功能的 GitLab 工具集合，不是单一导出脚本。顶层命令负责发现和分发功能；每个功能域拥有独立的参数、API 语义、配置和业务流程。

当前已实现 `milestones export`。下一阶段计划增加 `repositories export`，用于导出单个 project 或 group 下多个 project 的代码。

设计约束：

- Windows 10 + Python 3.11+
- 运行时零第三方依赖
- 支持办公内网离线部署
- Personal Access Token 访问 GitLab API
- 功能模块彼此隔离，共享基础设施

## 2. 命令模型

```text
gitlab-tools <功能域> <动作> [参数]
```

当前命令：

```text
python -m gitlab_tools milestones export --config milestones.config.txt
```

计划命令：

```text
python -m gitlab_tools repositories export --project group/project
python -m gitlab_tools repositories export --group group/subgroup
```

两级子命令可以避免顶层参数不断膨胀，也能让每个功能独立提供帮助信息和配置。

## 3. 分层架构

```text
gitlab_tools/
  cli.py
  common/
    gitlab_api.py
    runtime_logging.py
    utils.py
  commands/
    milestones/
      command.py
      api.py
      config.py
      exporter.py
      markdown.py
```

### 顶层 CLI

`gitlab_tools/cli.py` 只负责：

- 创建根命令 `gitlab-tools`
- 注册功能域子命令
- 解析参数并调用对应 handler

顶层不得包含具体导出业务。

### 通用基础设施

`common/gitlab_api.py` 只负责 GitLab REST API 的通用能力：

- Token 请求头
- HTTP/JSON
- SSL 配置
- 分页
- 统一异常

它不应包含 Milestone、Repository 等具体业务接口。业务 API 由各功能模块封装。

### Milestone 功能

- `command.py`：注册 `milestones export`，处理退出码和日志
- `api.py`：封装 group/project Milestone 与 Issue API
- `config.py`：读取该功能的 `key=value` 配置
- `exporter.py`：编排查询、排序和文件输出
- `markdown.py`：渲染 Markdown

## 4. Milestone 数据流

### Group

1. 分别查询 active、closed Milestone 并按 ID 去重；
2. 对每个 Milestone 调用 group issues API；
3. 按标题查询后，再用 `issue.milestone.id` 精确过滤；
4. 生成 scope 索引、Milestone 文档和 Issue 文档。

不直接依赖 `/groups/:id/milestones/:milestone_id/issues`，因为该接口对 subgroup Issue 的覆盖存在限制。

### Project

1. 分别查询 active、closed Milestone 并按 ID 去重；
2. 调用 project milestone issues API；
3. 生成 Markdown 目录。

## 5. 输出与文件名

每个 scope 目录包含：

```text
<scope>/index.md
<scope>/<DatePrefix>_<MilestoneName>/milestone.md
<scope>/<DatePrefix>_<MilestoneName>/issues/*.md
```

日期前缀：

1. 已关闭：优先 `closed_at`，缺失时回退 `updated_at`；
2. 未关闭且已到期：使用 `due_date`；
3. 其他：`20269999`。

文件名会清洗 Windows 非法字符和保留名。

## 6. 扩展新功能的规则

新增功能应遵循以下步骤：

1. 新建 `gitlab_tools/commands/<feature>/`；
2. 在模块内提供命令注册函数和 handler；
3. 业务 API 放在该模块，不进入 `common/gitlab_api.py`；
4. 通用 HTTP、日志和无业务含义的工具函数才可进入 `common/`；
5. 在 `gitlab_tools/cli.py` 注册功能；
6. 先增加命令、API 和关键流程测试；
7. README 明确区分“已实现”和“规划中”。

## 7. Repository 源码导出建议设计

建议模块名为 `commands/repositories/`，避免把“项目元数据查询”和“源码导出”混入 Milestone 功能。

建议能力边界：

- `--project`：导出单个项目；
- `--group`：递归或按参数控制是否包含 subgroup；
- GitLab API：枚举项目、读取默认分支和仓库元数据；
- Git/Archive 层：执行 clone、mirror 或 archive；
- Manifest：记录项目 ID、路径、分支、提交版本、导出状态；
- 失败隔离：单个项目失败不阻断整个 group，其结果进入失败清单。

建议先明确“工作副本、裸镜像、还是压缩归档”三种交付模式，再实现具体命令，因为它们在分支、历史、LFS、submodule 和磁盘占用上差异较大。

## 8. 错误处理与日志

命令区分：

- 配置文件不存在：退出码 1
- GitLab HTTP 错误：退出码 2
- 其他异常：退出码 3

Milestone 日志写入配置文件同级的 `milestones-export.log`。后续功能使用自己的日志名，避免多个功能互相覆盖。

## 9. 当前边界

Milestone 功能暂不包含：

- Issue 评论
- 二进制附件
- 浏览器/LDAP 自动登录
- exe 打包
- 第三方 Python 依赖

Repository 源码导出仍处于规划阶段，当前版本不声明该功能可用。
