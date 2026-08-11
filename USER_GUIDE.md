# GitLab Tools 简明用户手册

本工具目前有两项功能：

| 功能 | 命令 | 输出 |
|---|---|---|
| 导出 Milestone | `milestones export` | Milestone 和 Issue 的 Markdown 文件 |
| 导出项目源码 | `repositories export` | 可直接浏览和使用的普通 Git 工作区 |

下面按“检查环境、安装工具、选择功能、填写配置、执行导出”的顺序说明。示例以 Windows 为主。

## 1. 使用前准备

需要准备：

1. Windows 10 或更高版本电脑。
2. Python 3.11 或更高版本。
3. Git 命令行。
4. 公司 GitLab 地址，例如 `https://gitlab.example.com`。
5. GitLab Access Token。
6. 电脑能够访问目标 GitLab。

“断网环境”可以不能访问互联网，但必须能够访问公司内网 GitLab，否则无法导出数据和代码。

## 2. 检查 Python 和 Git

按 `Win + R`，输入 `cmd`，按回车。执行：

```bat
py --version
git --version
```

正常结果类似：

```text
Python 3.11.9
git version 2.49.0.windows.1
```

Python 版本必须是 3.11 或更高。

### 联网电脑安装依赖

- Python：<https://www.python.org/downloads/windows/>
- Git：<https://git-scm.com/download/win>

安装 Python 时勾选 `Add Python to PATH`。Git 保持默认安装选项即可。

### 断网电脑安装依赖

在联网电脑上下载并带入断网环境：

```text
python-3.11.x-amd64.exe
Git-x.x.x-64-bit.exe
```

先安装 Python，再安装 Git。安装后关闭命令提示符，重新打开并再次检查版本。

## 3. 安装 gitlab-tools

### Wheel 文件是什么

工具通常以这个文件交付：

```text
gitlab_tools-0.3.1-py3-none-any.whl
```

它是 Python Wheel 安装包，可以理解为 `gitlab-tools` 的离线安装包：

- `gitlab_tools`：软件包名称。
- `0.3.1`：版本号。
- `py3`：适用于 Python 3。
- `none-any`：不依赖特定操作系统和 CPU。
- `.whl`：Python 可直接安装的软件包格式。

本工具没有第三方 Python 运行时依赖，离线安装只需要这一个 Wheel。

### 联网安装

GitHub 仓库为 Public，或当前账号已有访问权限时，可以直接从 GitHub 源码安装：

```bat
py -m pip install "git+https://github.com/sgh6688/gitlab-tools.git@main"
```

如果已经拿到 Wheel，推荐安装固定版本：

```bat
cd /d D:\GitLabTools
py -m pip install .\gitlab_tools-0.3.1-py3-none-any.whl
```

### 完全离线安装

把 Wheel 复制到断网电脑，例如放在：

```text
D:\GitLabTools
```

执行：

```bat
cd /d D:\GitLabTools
py -m pip install --no-index .\gitlab_tools-0.3.1-py3-none-any.whl
```

`--no-index` 表示禁止 pip 访问互联网。

重新安装同一版本：

```bat
py -m pip install --no-index --force-reinstall .\gitlab_tools-0.3.1-py3-none-any.whl
```

### 检查安装结果

```bat
py -m pip show gitlab-tools
py -m gitlab_tools --help
```

`pip show` 应显示当前安装版本；工具帮助中应同时出现：

```text
milestones
repositories
```

## 4. GitLab 地址、项目路径和 Token

### GitLab 地址

假设项目网页是：

```text
https://gitlab.example.com/dept/platform/project-a
```

那么：

```text
GitLab 地址：https://gitlab.example.com
项目路径：dept/platform/project-a
群组路径：dept/platform
```

GitLab 地址不要带 `/api/v4`。

### Token 权限

Milestone 导出通常需要：

```text
read_api
```

Repository HTTP 导出通常还需要：

```text
read_repository
```

只授予读取权限，不要增加写入、删除等无关权限。

### Token 的两种填写方法

最简单的方法是在配置文件中填写：

```text
token=你的Token
```

配置文件含有敏感信息，不要发送给别人，也不要提交到 Git 仓库。

更安全的方法是保持：

```text
token=
token_env_var=GITLAB_TOKEN
```

每次运行前，在同一个命令提示符窗口中执行：

```bat
set "GITLAB_TOKEN=你的Token"
```

关闭窗口后，这个临时环境变量会失效。

# 功能一：导出 Milestone 和 Issue

该功能导出指定 group/project 下的 Milestone，以及每个 Milestone 关联的 Issue。结果为 Markdown 文件，不导出项目源码。

## 5.1 创建 Milestone 配置

建议创建独立目录：

```bat
mkdir D:\GitLabToolsConfig\Milestones
cd /d D:\GitLabToolsConfig\Milestones
```

初始化：

```bat
py -m gitlab_tools milestones init-config
```

会生成：

```text
milestones.config.txt
run_milestones_export.bat
```

工具不会覆盖已有文件。

## 5.2 填写 Milestone 配置

用记事本打开 `milestones.config.txt`：

```bat
notepad milestones.config.txt
```

示例：

```text
gitlab_url=https://gitlab.example.com
token=
token_env_var=GITLAB_TOKEN

output_dir=D:\GitLabExport\Milestones

request_timeout_seconds=30
page_size=100
verify_ssl=true

groups=dept/platform
projects=dept/platform/project-a
```

说明：

- `groups`：导出群组 Milestone。
- `projects`：导出项目 Milestone。
- 两者可同时填写，多个目标用英文逗号分隔。
- 不使用的一项保持空值，例如 `groups=`。

只导出一个项目：

```text
groups=
projects=dept/platform/project-a
```

只导出一个群组：

```text
groups=dept/platform
projects=
```

## 5.3 执行 Milestone 导出

日常使用可双击：

```text
run_milestones_export.bat
```

第一次运行或排错时，建议在命令提示符中执行：

```bat
cd /d D:\GitLabToolsConfig\Milestones
run_milestones_export.bat
```

也可以直接执行：

```bat
py -m gitlab_tools milestones export --config milestones.config.txt
```

## 5.4 查看 Milestone 结果

输出目录示例：

```text
D:\GitLabExport\Milestones\
  group__dept__platform\
    index.md
    20261231_版本名称\
      milestone.md
      issues\
        001_iid-123_Issue标题.md
```

日志位于配置文件同级目录：

```text
milestones-export.log
```

# 功能二：导出 Repository 项目源码

该功能通过 Git clone 导出项目，保留 `.git`、完整历史和 GitLab namespace 层级，不生成压缩包。

## 6.1 创建 Repository 配置

建议创建独立目录：

```bat
mkdir D:\GitLabToolsConfig\Repositories
cd /d D:\GitLabToolsConfig\Repositories
```

初始化：

```bat
py -m gitlab_tools repositories init-config
```

会生成：

```text
gitlab.config.txt
repositories.config.txt
run_repositories_export.bat
```

工具不会覆盖已有文件。

## 6.2 填写 GitLab 连接配置

打开 `gitlab.config.txt`：

```text
gitlab_url=https://gitlab.example.com
token=
token_env_var=GITLAB_TOKEN
request_timeout_seconds=30
page_size=100
verify_ssl=true
```

## 6.3 填写 Repository 导出配置

打开 `repositories.config.txt`。

导出一个项目：

```text
output_dir=D:\GitLabExport\Repositories
projects=dept/platform/project-a
groups=
include_subgroups=true
clone_protocol=http
existing=skip
```

导出多个项目时，用英文逗号分隔：

```text
projects=dept/platform/project-a,dept/platform/project-b
```

导出整个群组及其子群组项目：

```text
output_dir=D:\GitLabExport\Repositories
projects=
groups=dept/platform
include_subgroups=true
clone_protocol=http
existing=skip
```

只导出群组直属项目：

```text
include_subgroups=false
```

首次使用建议保持：

```text
clone_protocol=http
existing=skip
```

## 6.4 执行 Repository 导出

日常使用可双击：

```text
run_repositories_export.bat
```

第一次运行或排错时执行：

```bat
cd /d D:\GitLabToolsConfig\Repositories
run_repositories_export.bat
```

也可以直接执行：

```bat
py -m gitlab_tools repositories export --gitlab-config gitlab.config.txt --config repositories.config.txt
```

临时导出一个项目：

```bat
py -m gitlab_tools repositories export --project dept/platform/project-a
```

临时导出一个群组：

```bat
py -m gitlab_tools repositories export --group dept/platform
```

命令行出现 `--project` 或 `--group` 时，命令行目标会整体替换配置文件中的目标，避免误执行原来的批量任务。

## 6.5 查看 Repository 结果

项目路径：

```text
dept/platform/project-a
```

输出目录：

```text
D:\GitLabExport\Repositories\dept\platform\project-a
```

里面是普通 Git 工作区：

```text
.git
README.md
项目源码文件
```

日志位于配置文件同级目录：

```text
repositories-export.log
```

## 6.6 已有目录处理方式

`repositories.config.txt` 中的 `existing` 有三个值：

| 配置 | 行为 | 建议 |
|---|---|---|
| `skip` | 目录存在时跳过，不修改 | 首次使用推荐 |
| `update` | 只做安全 fast-forward 更新 | 需要同步已有仓库时使用 |
| `fail` | 目录存在时把该项目记为失败 | 要求输出目录必须为空时使用 |

工具不会自动删除已有目录。

## 6.7 使用 SSH（可选）

只有已配置 GitLab SSH Key 的用户才使用：

```text
clone_protocol=ssh
```

先测试：

```bat
ssh -T git@gitlab.example.com
```

不熟悉 SSH Key 时继续使用 `clone_protocol=http`。

# 7. 常见问题

## `py` 不是内部或外部命令

Python 未安装或没有加入 PATH。重新安装并勾选 `Add Python to PATH`。

## `git` 不是内部或外部命令

安装 Git for Windows，然后重新打开命令提示符。

## `No module named gitlab_tools`

重新安装 Wheel：

```bat
py -m pip install --no-index --force-reinstall .\gitlab_tools-0.3.1-py3-none-any.whl
```

## HTTP 401 或 403

检查：

- Token 是否完整、是否过期。
- 是否有 `read_api` 权限。
- Repository HTTP 导出是否还有 `read_repository` 权限。
- 当前账号是否有权访问目标 group/project。

## 项目名称不唯一

不要只写 `project-a`，改用完整路径：

```text
dept/platform/project-a
```

## 配置文件不存在

先进入该功能的配置目录，再运行 BAT；或在命令中明确指定配置路径。

## SSL 证书错误

优先联系 GitLab 或网络管理员。只有确认是可信内网 GitLab、且管理员明确允许时，才临时设置：

```text
verify_ssl=false
```

这会降低连接安全性，不建议长期使用。

## 部分 Repository 项目失败

打开 `repositories-export.log`。退出码 `4` 表示批量任务执行完成，但至少有一个项目失败。

## 已有 Repository 没有更新

如果配置是：

```text
existing=skip
```

工具会跳过已有目录。需要更新时改为：

```text
existing=update
```

# 8. 最短操作清单

## Milestone

```bat
mkdir D:\GitLabToolsConfig\Milestones
cd /d D:\GitLabToolsConfig\Milestones
py -m gitlab_tools milestones init-config
notepad milestones.config.txt
run_milestones_export.bat
```

## Repository

```bat
mkdir D:\GitLabToolsConfig\Repositories
cd /d D:\GitLabToolsConfig\Repositories
py -m gitlab_tools repositories init-config
notepad gitlab.config.txt
notepad repositories.config.txt
run_repositories_export.bat
```

# 9. Wheel 的发布和离线分发

普通用户通常从以下位置获取 Wheel：

1. GitHub Releases：适合公开版本下载。
2. 公司内部制品库，如 GitLab Package Registry、Nexus 或 Artifactory。
3. 公司允许的内部文件服务器或离线介质。

本项目建议把 GitHub Releases 作为公开版本源，再把同一 Wheel 和校验文件同步到公司内网。完整发布步骤见 [RELEASE.md](RELEASE.md)。
