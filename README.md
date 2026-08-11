# GitLab Tools

`gitlab-tools` 是一个可扩展的 GitLab 自动化与导出工具集，通过“功能域 + 动作”组织命令。

第一次使用 Repository 导出，请直接阅读：[简明用户手册](USER_GUIDE.md)。手册包含环境检查、安装、配置、运行和常见问题处理。

## 当前功能

| 命令 | 说明 |
|---|---|
| `milestones export` | 导出 group/project 的 Milestone 和 Issue Markdown |
| `repositories export` | 导出单个 project 或 group 下所有 project 的代码 |

运行环境：Windows 10、Python 3.11+、Git 命令行。Python 运行时无第三方依赖。联网和断网安装步骤均见简明用户手册。

```bat
py -m gitlab_tools --help
```

# Repository 源码导出

## 导出行为

- `--project` 支持 project ID、完整 `group/project` 路径或唯一的精确项目名；推荐使用完整路径。
- `--group` 支持 group ID 或完整 group 路径。
- group 默认包含所有 subgroup 中的 project，可用 `--no-include-subgroups` 关闭。
- 每个项目使用 GitLab API 返回的 `http_url_to_repo`（或 `ssh_url_to_repo`）执行 Git clone。协议由 `clone_protocol` 控制。
- 不压缩，保留完整 Git 工作区和 `.git` 目录。
- 输出路径保持完整 `path_with_namespace`。
- 同一 project 同时被直接指定和被 group 枚举到时，只导出一次。
- 单个 project 不存在、名称歧义、路径冲突或 clone 失败都不会中断其他目标；最终退出码为 `4` 并记录失败数。
- Windows 文件名清理或截断后若两个项目映射到同一路径，将拒绝导出这两个项目，避免串库。
- 输出路径按真实解析结果检测链接/目录联接别名碰撞；clone 先在隔离暂存区完成，再以不可覆盖、拒绝链接的原子操作安装，update 在支持的平台通过已打开的目录句柄操作，避免路径替换竞态。

例如 GitLab 项目为：

```text
dept/platform/backend/service-a
dept/platform/frontend/web-a
```

输出为：

```text
D:\Downloads\ExportedByGitLabTools\Repositories\
  dept\
    platform\
      backend\
        service-a\
          .git\
          ...
      frontend\
        web-a\
          .git\
          ...
```

## 推荐配置方式

采用三层优先级：

1. 内置默认值；
2. 配置文件；
3. 命令行参数（最高优先级）。

连接信息与功能参数分离，避免每个功能重复保存 GitLab 地址和 Token。

安装后可直接生成完整的可编辑配置和 Windows 启动脚本：

```bat
py -m gitlab_tools repositories init-config
```

命令不会覆盖任何已有文件。也可用 `--directory D:\configs\gitlab-export` 指定生成目录。

### 1. GitLab 通用连接配置

```bat
copy configs\gitlab.example.txt gitlab.config.txt
```

上面的 `copy` 方式适用于源码仓库；通过 wheel 安装时推荐使用 `repositories init-config`。

编辑 `gitlab.config.txt`：

```text
gitlab_url=https://gitlab.example.com
token=
token_env_var=GITLAB_TOKEN
request_timeout_seconds=30
page_size=100
verify_ssl=true
```

推荐不把 Token 写入文件，而是在运行前设置：

```bat
set GITLAB_TOKEN=你的Token
```

`gitlab.config.txt` 已加入 `.gitignore`。Token 用于 API 请求和 HTTP Git 获取；Git 子进程环境会剥离所有含有当前 Token 值的父环境变量。认证网络操作只在工具创建、禁用全局/系统 Git 配置的隔离 bare 仓库中进行，普通工作树的 checkout、hook、filter、fetch 和 merge 均处于无 Token 环境。认证头仅限定到配置的 GitLab 同源地址，不写进 clone URL，也不会保存在仓库的 `origin` 地址中。API 跨 origin 重定向会被拒绝，Git 跨 origin 重定向不会携带该认证头；API/Git 错误文本会清洗明文及编码后的认证值。

### 2. Repository 功能配置

```bat
copy configs\repositories.example.txt repositories.config.txt
```

```text
output_dir=D:\Downloads\ExportedByGitLabTools\Repositories
projects=dept/platform/project-a,dept/platform/project-b
groups=dept/shared-components
include_subgroups=true
clone_protocol=http
existing=skip
```

`existing` 可选值：

| 值 | 行为 |
|---|---|
| `skip` | 默认；目标目录存在时保持不动并跳过 |
| `update` | 目标必须是 Git 工作区且 `origin` 与目标项目一致；先在隔离 bare 仓库认证获取当前分支，再在无 Token 环境中校验提交并执行 fast-forward merge，不跟随被修改的 upstream remote |
| `fail` | 目标存在时将该项目记为失败，继续处理其他项目 |

## 常用命令

### 使用默认配置文件批量导出

当前目录存在 `gitlab.config.txt` 和 `repositories.config.txt` 时：

```bat
py -m gitlab_tools repositories export
```

或运行：

```bat
run_repositories_export.bat
```

### 导出单个 project

```bat
py -m gitlab_tools repositories export --project dept/platform/project-a
```

也支持唯一的精确项目名：

```bat
py -m gitlab_tools repositories export --project project-a
```

如果同名项目不止一个，工具会列出完整路径并要求改用 `group/project`。

### 一次导出多个 project

```bat
py -m gitlab_tools repositories export ^
  --project dept/platform/project-a ^
  --project dept/platform/project-b
```

### 导出 group 及所有 subgroup 项目

```bat
py -m gitlab_tools repositories export --group dept/platform
```

仅导出 group 直属项目：

```bat
py -m gitlab_tools repositories export --group dept/platform --no-include-subgroups
```

### 指定自定义配置文件

```bat
py -m gitlab_tools repositories export ^
  --gitlab-config D:\configs\company-gitlab.txt ^
  --config D:\configs\backend-repositories.txt
```

### 命令行覆盖功能配置

```bat
py -m gitlab_tools repositories export ^
  --project dept/platform/project-a ^
  --output-dir D:\GitLabExport ^
  --existing update
```

只要命令行出现任一 `--project` 或 `--group`，命令行目标就会整体替换 `repositories.config.txt` 中的 `projects/groups`；输出目录等单值参数也以命令行为准。这样临时导出一个项目时不会误执行配置文件里的批量任务。

如果不指定 `--config`，工具会自动加载当前目录中的 `repositories.config.txt`；文件不存在时仍可完全依靠命令行参数运行。`gitlab.config.txt` 默认必须存在，也可以用 `--gitlab-config` 指定其他路径。

## 日志和退出码

日志文件：`repositories-export.log`。使用功能配置文件时写在该文件同级目录，否则写在当前目录。

| 退出码 | 含义 |
|---|---|
| `0` | 全部成功或按 `skip` 正常跳过 |
| `1` | 配置错误 |
| `2` | GitLab API HTTP、JSON、响应结构或分页协议错误 |
| `3` | Git 不可用或其他执行错误 |
| `4` | 批量任务完成，但一个或多个项目失败 |

## 当前边界

- 普通 clone 默认检出项目默认分支；远程分支和 Git 历史按标准 `git clone` 保留。
- 当前不自动初始化 submodule。
- Git LFS 行为由目标机器上的 Git LFS 安装和配置决定。
- 不导出 Wiki、Release 附件、CI Artifact 或 Container Registry。
- 支持 HTTP 和 SSH clone 协议（`clone_protocol=http|ssh`）；SSH 模式使用 `ssh_url_to_repo`、校验主机与配置的 GitLab 地址一致，不涉及 Token。

# Milestone 导出

复制并修改：

```bat
copy configs\milestones.example.txt milestones.config.txt
py -m gitlab_tools milestones export --config milestones.config.txt
```

源码仓库中的 Windows 脚本位于 `scripts\windows\`。也可运行 `scripts\windows\run_milestones_export.bat`；日志为配置文件同级的 `milestones-export.log`。

# 项目结构

```text
gitlab_tools/
  cli.py
  common/
    config.py
    gitlab_api.py
    runtime_logging.py
    utils.py
  commands/
    milestones/
    repositories/
      command.py
      config.py
      api.py
      exporter.py
configs/
  gitlab.example.txt
  milestones.example.txt
  repositories.example.txt
scripts/
  windows/
    run_milestones_export.bat
    run_repositories_export.bat
tests/
```

# 开发与测试

```bat
py -m unittest discover -s tests -v
```

完整设计见 [DESIGN.md](DESIGN.md)，需求基线见 [REQUIREMENTS.md](REQUIREMENTS.md)。
