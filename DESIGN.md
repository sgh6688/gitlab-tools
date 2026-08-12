# 设计说明

## 1. 产品与命令模型

`gitlab-tools` 是可扩展的 GitLab 工具集合：

```text
gitlab-tools <功能域> <动作> [参数]
```

当前功能：

```text
milestones export
repositories export
repositories init-config
```

Repository 功能导出普通 Git 工作树，不压缩；支持单个 project 和 group 批量导出。

## 2. 配置模型

配置分为两层：

- `gitlab.config.txt`：GitLab URL、Token、Git HTTP 用户名、SSL、超时、分页等连接参数；
- `repositories.config.txt`：目标、输出目录、subgroup 和已存在目录策略。

优先级：内置默认值 < 功能配置文件 < 命令行。

集合参数采用安全覆盖规则：命令行一旦出现 `--project` 或 `--group`，就不再执行功能配置文件中的任何默认目标。这样临时任务不会误触发批量配置。

Token 优先读配置中的 `token`，为空时读取 `token_env_var` 指向的环境变量。同一个 Token 在 API 请求中通过 `PRIVATE-TOKEN` 使用，在 Git HTTP 获取中作为 Basic 密码使用；Basic 用户名由 `git_http_username` 配置；保留兼容默认值 `oauth2` 时，会通过同一 Token 调用 `/api/v4/user` 自动解析真实用户名，以兼容要求真实账号名的旧版 GitLab、LDAP 或前置代理。纯 HTTP 内网站点保持 `http://`，不强制升级为不存在的 HTTPS 服务。

HTTP Git 获取在工具创建的隔离 bare 仓库中使用 URL-scoped `http.<origin>.extraHeader`，协议、主机和端口必须与 GitLab API 返回的 clone 地址同源；同时禁用系统/全局 Git 配置。工作树 checkout、hook、filter、fetch 和 merge 不继承 Token；所有含有当前 Token 值的父环境变量均被剥离。Token 不拼入 URL，也不写入 `.git/config`。

## 3. 分层架构

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
```

- `common/config.py`：通用 key=value 与 GitLab 连接配置。
- `common/gitlab_api.py`：Token API 请求、单对象 GET、分页和错误映射。
- `repositories/command.py`：参数注册、配置合并、退出码。
- `repositories/api.py`：project 解析和 group 项目枚举。
- `repositories/exporter.py`：去重、路径校验、Git clone/update、统计。
- `templates/`：随 wheel 分发的通用连接配置、Repository 功能配置和 Windows 启动脚本。

## 4. Project 解析

`--project` 接受：

1. 数字 ID：直接请求 `/projects/:id`；
2. 包含 `/` 的完整路径：URL 编码后请求 `/projects/:path`；
3. 不含 `/` 的名称：调用 projects search，仅接受 `name` 或 `path` 的精确匹配。

裸名称存在多个精确匹配时拒绝猜测，并返回候选 `path_with_namespace`，要求用户使用完整路径。

## 5. Group 枚举

调用：

```text
GET /groups/:id/projects
```

参数：

- `include_subgroups=true|false`
- `with_shared=false`

不使用 `simple=true`，确保不同 GitLab 版本均返回 `http_url_to_repo` 等完整 clone 字段。

分页由通用客户端处理。默认包含 subgroup；使用 `with_shared=false` 避免把仅共享给 group、但命名空间不属于该 group 的项目混入导出树。

直接 project 与 group 枚举结果按 project ID 去重，结果按 `path_with_namespace` 排序，保证可重复执行时顺序稳定。

单个 project 的 404、名称歧义等目标级错误会记录失败并继续；401/403 等全局认证错误保持快速失败，返回 API 错误退出码。

## 6. 输出路径与安全

目标路径为：

```text
<output_dir>/<path_with_namespace>
```

例如：

```text
team/platform/sub/project
```

输出：

```text
<output_dir>/team/platform/sub/project
```

在拼接路径前：

- 拒绝空路径、`.` 和 `..`；
- 每层分别进行 Windows 文件名兼容处理；
- 对清理、截断和大小写归一化后的目标路径做批量碰撞检测，碰撞项目全部拒绝；
- 解析已存在的符号链接并拒绝任何逃逸输出根目录的目标；
- 不允许 API 返回值或本地链接把 clone 写到输出根目录之外。

## 7. Git 执行

新项目：

```text
git clone -- <http_url_to_repo> <destination>
```

已存在目录策略：

- `skip`：不修改；
- `update`：必须含 `.git`；校验 `origin` 后，在隔离 bare 仓库获取目标分支，并在无 Token 环境中校验提交后执行 fast-forward merge；
- `fail`：记录失败。

Git 命令使用参数数组，不使用 shell。Token 不出现在命令行参数中。设置 `GIT_TERMINAL_PROMPT=0`，避免无人值守任务因凭据提示永久等待。

执行 `update` 前读取 `origin` 并与 GitLab API 返回的 `http_url_to_repo` 比较，拒绝更新到其他项目的本地仓库。HTTP clone URL 无条件校验 scheme/host/port 及无 userinfo；同源校验在有 Token 时额外执行。clone 先写入同一文件系统的隔离暂存区，再以不可覆盖且拒绝链接路径的原子操作安装；POSIX update 通过已打开的目录句柄运行，缩小并阻断路径替换窗口。

单项目异常在项目边界捕获，批量任务继续运行；最终统计 cloned、updated、skipped、failed。存在失败时命令返回退出码 4。

## 8. 当前边界

- 导出标准 clone 的默认检出分支和 Git 历史；
- 不递归初始化 submodule；
- Git LFS 依赖目标机器环境；
- 不导出 Wiki、Artifact、Registry；
- 支持 HTTP 和 SSH clone 协议（`clone_protocol`）；SSH 校验主机一致，不涉及 Token；
- 不自动物理删除失败或已存在目录。

## 9. 测试策略

- CLI 帮助和缺失配置错误路径；
- 通用 Token 环境变量回退；
- 真实 Git HTTP 子进程发送 Basic Authorization；
- 纯 HTTP GitLab、自定义 Basic 用户名、控制字符拒绝及凭据脱敏；
- API 分页响应头大小写不敏感；
- 配置优先级和目标覆盖；
- project 精确解析和同名歧义；
- group + subgroup 参数；
- project/group 去重；
- 路径穿越拒绝；
- 符号链接逃逸、Windows 路径碰撞和错误 origin 拒绝；
- wheel 内配置模板及 `init-config` 防覆盖；
- 使用真实临时 Git 仓库验证普通工作树 clone 和命名空间目录。
