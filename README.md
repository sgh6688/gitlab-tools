# GitLab Milestone Exporter

这个工具用于从 GitLab 导出你指定的 `group` 或 `project` 下的 Milestone，以及每个 Milestone 对应的 Issue 内容，输出为 Markdown 文件夹结构，适合离线归档、二次整理和后续分析。

这一版是**纯 Python 标准库**实现，不依赖任何第三方包，适合办公内网不能临时安装依赖的环境。

正式需求沉淀见 [REQUIREMENTS.md](REQUIREMENTS.md)，设计说明见 [DESIGN.md](DESIGN.md)。

## 适用环境

- Windows 10
- Python 3.11
- GitLab Community Edition `v17.7.4` 已验证设计接口
- 认证方式：`Personal Access Token`
- 第三方依赖：`无`

## 功能范围

- 支持配置多个 `group` 路径
- 支持配置多个 `project` 路径
- 导出全部 Milestone
- 导出 Milestone 下的全部 Issue
- 导出 Issue 正文内容
- 不导出评论
- 不下载图片和其他二进制附件
- 输出 Markdown 文件
- 按 Milestone 建独立文件夹

## 目录结构

导出结果默认会写到：

```text
D:\Downloads\ExportedByGitLabTools
```

单个 scope 的结构示例：

```text
ExportedByGitLabTools\
  group__dept__platform-group\
    index.md
    20260526_Sprint-2026-05\
      milestone.md
      issues\
        001_iid-12_登录页修复.md
        002_iid-18_接口超时处理.md
```

## 使用步骤

1. 把整个文件夹拷到你的 Windows 电脑。
2. 打开终端，进入这个工具目录。
3. 复制配置文件：

```bat
copy config.example.txt config.txt
```

4. 编辑 `config.txt`，填入你的 GitLab 地址、Token、group/project 路径。
5. 运行：

```bat
py -m gitlab_milestone_exporter --config config.txt
```

也可以直接双击：

```text
run_export.bat
```

## 配置说明

`config.txt` 示例：

```ini
gitlab_url=https://gitlab.example.com
token=
token_env_var=GITLAB_TOKEN
output_dir=D:\Downloads\ExportedByGitLabTools
request_timeout_seconds=30
page_size=100
verify_ssl=true
groups=dept/platform-group
projects=dept/platform-group/project-a
```

说明：

- `gitlab_url`：GitLab 根地址，不带 `/api/v4`
- `token`：可以直接填 Token
- `token_env_var`：也可以不把 Token 写进文件，改为先设置环境变量
- `output_dir`：导出目录，默认就是你要求的 `D:\Downloads\ExportedByGitLabTools`
- `groups`：要导出的 group 路径，多个值用英文逗号分隔
- `projects`：要导出的 project 路径，多个值用英文逗号分隔

## Token 建议

推荐使用 `read_api` 权限的 Personal Access Token。  
如果你们实例权限模型比较特殊，`api` 权限也可以，但不建议给超过需要的权限。

如果你不想把 Token 明文写进 `config.txt`，可以先设置环境变量：

```bat
set GITLAB_TOKEN=你的Token
py -m gitlab_milestone_exporter --config config.txt
```

## group 和 project 路径示例

示例 group：

```text
dept/platform-group
dept/shared-components/backend
```

示例 project：

```text
dept/platform-group/project-a
dept/platform-group/project-b
```

## 运行结果说明

- 每个 `group` 或 `project` 会生成一个单独目录
- 目录里有一个 `index.md`，列出当前 scope 下导出的 Milestone
- 每个 Milestone 目录内有：
  - `milestone.md`
  - `issues/`
- 工具运行时会在当前工具目录生成 `export.log`
- 终端会实时打印当前正在处理的 scope、milestone、issue 数量，以及错误信息

## 已知设计选择

- `project` scope 仅导出项目自己的 project milestones
- `group` scope 导出 group milestones，并从 group issues 接口按 milestone 过滤 issues
- milestone 目录名前缀规则：
  - 已关闭：取 close 日期；若接口没直接返回，则回退到 `updated_at`
  - 未关闭但已过期：取 `due_date`
  - 其他情况：固定 `20269999`
- 文件名会自动做 Windows 兼容清洗
- 遇到空标题或非法名称时，会自动回退成安全名称

## 常见问题

### 1. 为什么不用 SSH Key

SSH Key 主要用于 Git 仓库拉取和推送。  
这个工具读取的是 GitLab 元数据，走的是 REST API，所以应使用 Personal Access Token。

### 2. 为什么没有导出评论

这是按你的要求裁掉的，目的是先保证结构清晰、速度可控、导出包不膨胀。

### 3. 如果 GitLab 地址变了怎么办

改 `config.txt` 里的 `gitlab_url` 就行。

### 4. 如果我要新增导出目标

直接在 `groups=` 或 `projects=` 后面继续加，多个值用英文逗号分隔。

## 维护入口

核心入口：

- `gitlab_milestone_exporter/cli.py`
- `gitlab_milestone_exporter/exporter.py`
- `gitlab_milestone_exporter/gitlab_api.py`

配套文档：

- 需求说明：[REQUIREMENTS.md](REQUIREMENTS.md)
- 设计说明：[DESIGN.md](DESIGN.md)
