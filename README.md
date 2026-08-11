# GitLab Tools

`gitlab-tools` 是一个可扩展的 GitLab 自动化与导出工具集。项目不再绑定单一的 Milestone 导出场景，而是通过“功能域 + 动作”的子命令组织不同能力。

## 当前功能

| 命令 | 状态 | 说明 |
|---|---|---|
| `milestones export` | 已实现 | 导出指定 group/project 的 Milestone 及其 Issue，生成 Markdown 归档 |
| `repositories export` | 规划中 | 按 project 或 group 批量导出项目代码 |

统一命令形式：

```text
python -m gitlab_tools <功能域> <动作> [参数]
```

查看全部命令：

```bat
py -m gitlab_tools --help
```

## Milestone 导出

### 环境

- Windows 10
- Python 3.11+
- 仅使用 Python 标准库，无第三方运行依赖
- 网络可访问目标 GitLab

### 配置

复制示例配置：

```bat
copy configs\milestones.example.txt milestones.config.txt
```

编辑 `milestones.config.txt`：

```text
gitlab_url=https://gitlab.example.com
token=
token_env_var=GITLAB_TOKEN
output_dir=D:\Downloads\ExportedByGitLabTools
request_timeout_seconds=30
page_size=100
verify_ssl=true
groups=dept/platform-group,dept/shared-components/backend
projects=dept/platform-group/project-a,dept/platform-group/project-b
```

Token 可直接写入 `token`，也可通过环境变量提供（推荐）：

```bat
set GITLAB_TOKEN=你的Token
```

### 运行

```bat
py -m gitlab_tools milestones export --config milestones.config.txt
```

也可双击或在终端运行：

```bat
run_milestones_export.bat
```

日志写入配置文件同级目录的 `milestones-export.log`。

### 输出

```text
D:\Downloads\ExportedByGitLabTools\
  group__dept__platform-group\
    index.md
    20260526_Sprint 2026-05\
      milestone.md
      issues\
        001_iid-12_登录页修复.md
```

- 每个 group/project 单独建目录
- 每个 Milestone 单独建目录
- 导出 Milestone 元数据、描述和 Issue 正文
- 不导出评论和二进制附件
- 文件名自动处理 Windows 非法字符

## 项目结构

```text
gitlab_tools/
  cli.py                         # 顶层命令注册与分发
  common/                        # 所有功能共用的基础设施
    gitlab_api.py                # 认证、HTTP 请求、分页、通用错误
    runtime_logging.py
    utils.py
  commands/
    milestones/                  # Milestone 功能独立模块
      command.py                 # milestones export 子命令
      api.py                     # Milestone API 语义
      config.py
      exporter.py
      markdown.py
configs/
  milestones.example.txt
tests/
```

新增功能时，应在 `gitlab_tools/commands/<功能域>/` 下独立实现，仅复用 `common/`，并在顶层 CLI 注册命令。不要把新功能塞入 Milestone 模块。

## 规划中的项目代码导出

建议命令：

```text
py -m gitlab_tools repositories export --project group/project
py -m gitlab_tools repositories export --group group/subgroup
```

建议职责：

1. 通过 GitLab API 解析单个 project 或递归枚举 group 下项目；
2. 按配置选择默认分支、全部分支或仓库归档格式；
3. 输出项目清单、成功/失败统计和可重试记录；
4. Git/API 认证、日志和分页继续复用 `common/`；
5. 源码导出逻辑放入独立的 `commands/repositories/`，不影响现有 Milestone 导出。

当前版本尚未实现该命令，避免把规划能力误写成已交付功能。

## 开发与测试

```bat
py -m unittest discover -s tests -v
```

项目要求 Python 3.11+。完整设计见 [DESIGN.md](DESIGN.md)，现有功能需求基线见 [REQUIREMENTS.md](REQUIREMENTS.md)。
