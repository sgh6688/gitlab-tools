# GitLab Repository 源码导出工具：简明用户手册

本手册面向第一次使用本工具的 Windows 用户。按顺序操作即可，不需要编写代码。

## 一、开始前准备

请准备以下信息：

1. 公司 GitLab 地址，例如 `https://gitlab.example.com`。
2. 要导出的项目或群组地址。
3. GitLab Access Token。公开项目可以不填；公司内部项目通常需要 Token。
4. 一台可以访问公司 GitLab 的 Windows 10 或更高版本电脑。

### 如何找到项目路径

打开项目网页。假设浏览器地址是：

```text
https://gitlab.example.com/dept/platform/project-a
```

项目路径就是：

```text
dept/platform/project-a
```

群组路径的找法相同。例如：

```text
https://gitlab.example.com/dept/platform
```

群组路径就是：

```text
dept/platform
```

## 二、检查电脑环境

按 `Win + R`，输入 `cmd`，按回车。依次执行：

```bat
py --version
```

```bat
git --version
```

正常情况下会看到类似内容：

```text
Python 3.11.9
git version 2.49.0.windows.1
```

要求：

- Python 必须是 3.11 或更高版本。
- Git 能正常显示版本号。

如果提示“不是内部或外部命令”，请根据电脑能否访问互联网选择下面的安装方式。

### 联网电脑安装 Python 和 Git

- Python：从 <https://www.python.org/downloads/windows/> 下载 Python 3.11 或更高版本。安装时勾选 `Add Python to PATH`。
- Git：从 <https://git-scm.com/download/win> 下载并安装，安装选项保持默认即可。

### 断网电脑安装 Python 和 Git

这里的“断网”是指不能访问互联网，但电脑仍须能访问公司内网 GitLab，否则无法导出项目。

先在一台联网电脑上准备：

1. Python 3.11 或更高版本的 Windows 64 位完整安装程序，例如 `python-3.11.x-amd64.exe`。
2. Git for Windows 64 位完整安装程序，例如 `Git-x.x.x-64-bit.exe`。
3. `gitlab-tools` 的 Wheel 安装包，例如 `gitlab_tools-0.3.0-py3-none-any.whl`。

把这三个文件通过公司允许的文件交换方式复制到断网电脑。先安装 Python，再安装 Git。安装 Python 时勾选 `Add Python to PATH`；Git 保持默认安装选项。

安装完成后，关闭命令提示符，再重新打开并检查版本：

```bat
py --version
git --version
```

## 三、安装 gitlab-tools

### Wheel 文件是什么

工具提供方通常会给你一个这样的文件：

```text
gitlab_tools-0.3.0-py3-none-any.whl
```

这是 Python 的 Wheel 安装包，可以理解为 `gitlab-tools` 的离线安装包：

- `gitlab_tools`：软件包名称。
- `0.3.0`：版本号。
- `py3`：适用于 Python 3。
- `none-any`：不依赖特定操作系统和 CPU。
- `.whl`：Python 可直接安装的软件包格式。

本工具没有第三方 Python 运行时依赖，因此离线电脑只需要这一个 Wheel，不需要再下载其他 Python 包。

### 联网安装

电脑能访问 GitHub 时，可以直接执行：

```bat
py -m pip install "git+https://github.com/sgh6688/gitlab-tools.git@main"
```

如果工具提供方已经给了 `.whl`，即使电脑联网，也建议安装指定版本的 Wheel，结果更稳定：

```bat
cd /d D:\GitLabTools
py -m pip install gitlab_tools-0.3.0-py3-none-any.whl
```

### 完全离线安装

把 Wheel 放到断网电脑的固定目录，例如：

```text
D:\GitLabTools
```

在命令提示符中执行：

```bat
cd /d D:\GitLabTools
py -m pip install --no-index .\gitlab_tools-0.3.0-py3-none-any.whl
```

`--no-index` 表示禁止 pip 访问互联网，只从当前 Wheel 安装。

如果要重新安装同一版本：

```bat
py -m pip install --no-index --force-reinstall .\gitlab_tools-0.3.0-py3-none-any.whl
```

离线环境不建议直接从源码安装，因为源码构建工具可能不齐全。请优先使用管理员提供的 Wheel。

### 工具提供方如何准备离线包

在一台联网且已经获取源码的电脑上执行：

```bat
cd /d D:\workspace\gitlab-tools
py -m pip wheel --no-deps --wheel-dir offline-package .
```

生成结果类似：

```text
offline-package\gitlab_tools-0.3.0-py3-none-any.whl
```

建议把下面三个文件放在同一个离线交付目录中：

```text
GitLabTools-Offline\
  python-3.11.x-amd64.exe
  Git-x.x.x-64-bit.exe
  gitlab_tools-0.3.0-py3-none-any.whl
```

然后通过公司允许的介质或内部文件传输系统交给断网环境用户。由于本工具没有第三方 Python 运行时依赖，不需要额外执行 `pip download`。

### 检查安装结果

```bat
py -m gitlab_tools --help
```

只要帮助信息中出现 `repositories`，安装就成功了。

## 四、创建配置文件

建议单独创建一个日常使用目录：

```bat
mkdir D:\GitLabRepositoryExport
cd /d D:\GitLabRepositoryExport
```

生成配置文件：

```bat
py -m gitlab_tools repositories init-config
```

执行后会生成三个文件：

```text
gitlab.config.txt
repositories.config.txt
run_repositories_export.bat
```

如果提示文件已经存在，工具不会覆盖原文件。这是正常的保护措施。

## 五、填写 GitLab 连接信息

用记事本打开 `gitlab.config.txt`。

### 最简单的填写方法

把内容改成下面的形式：

```text
gitlab_url=https://gitlab.example.com
token=在这里填写你的Token
token_env_var=GITLAB_TOKEN
request_timeout_seconds=30
page_size=100
verify_ssl=true
```

注意：

- `gitlab_url` 改成公司的真实 GitLab 地址。
- 地址末尾不要写 `/api/v4`。
- 地址末尾也不需要 `/`。
- `token` 后面直接填写 Token，中间不要加引号或空格。
- 该文件含有敏感信息，不要发给别人，也不要提交到 Git 仓库。

### 更安全的 Token 使用方法

如果不希望把 Token 写入文件，请保持：

```text
token=
```

每次运行前，在同一个命令提示符窗口中执行：

```bat
set "GITLAB_TOKEN=你的Token"
```

然后继续在该窗口中运行导出命令。关闭窗口后，这个临时环境变量会自动失效。

### Token 权限建议

私有项目通常需要以下只读权限：

- `read_api`
- `read_repository`

不要给 Token 增加写入仓库、删除项目等无关权限。

## 六、填写要导出的项目或群组

用记事本打开 `repositories.config.txt`。

### 情况一：导出一个项目

```text
output_dir=D:\GitLabExport\Repositories
projects=dept/platform/project-a
groups=
include_subgroups=true
clone_protocol=http
existing=skip
```

### 情况二：一次导出多个项目

项目之间用英文逗号分隔：

```text
projects=dept/platform/project-a,dept/platform/project-b
```

### 情况三：导出整个群组

```text
output_dir=D:\GitLabExport\Repositories
projects=
groups=dept/platform
include_subgroups=true
clone_protocol=http
existing=skip
```

`include_subgroups=true` 表示连同子群组中的项目一起导出。

如果只想导出该群组直属项目，改为：

```text
include_subgroups=false
```

### 其他配置先保持默认

首次使用建议保持：

```text
clone_protocol=http
existing=skip
```

含义：

- `clone_protocol=http`：使用 GitLab Token 下载，最适合新用户。
- `existing=skip`：目标目录已经存在时跳过，不覆盖、不删除。

## 七、开始导出

确认三个文件位于同一目录：

```text
D:\GitLabRepositoryExport\
  gitlab.config.txt
  repositories.config.txt
  run_repositories_export.bat
```

### 日常使用

双击：

```text
run_repositories_export.bat
```

### 第一次运行或需要排查错误

建议在命令提示符中执行，这样窗口不会自动关闭：

```bat
cd /d D:\GitLabRepositoryExport
run_repositories_export.bat
```

也可以直接执行：

```bat
py -m gitlab_tools repositories export --gitlab-config gitlab.config.txt --config repositories.config.txt
```

## 八、检查导出结果

如果项目路径是：

```text
dept/platform/project-a
```

并且配置为：

```text
output_dir=D:\GitLabExport\Repositories
```

最终目录是：

```text
D:\GitLabExport\Repositories\dept\platform\project-a
```

这是正常 Git 工作区，里面会有：

```text
.git
README.md
项目源码文件
```

运行日志位于配置文件同一目录：

```text
repositories-export.log
```

出现问题时，先打开这个日志查看最后几行。

## 九、再次运行时如何处理已有目录

编辑 `repositories.config.txt` 中的 `existing`。

### 跳过已有项目，最安全

```text
existing=skip
```

适合第一次使用和只想下载新增项目的情况。

### 更新已有项目

```text
existing=update
```

工具只执行安全的 fast-forward 更新，不会强制覆盖本地历史。如果本地仓库有特殊修改、分支不匹配或远程地址不一致，该项目会报错并保留原目录。

### 已存在就报错

```text
existing=fail
```

适合要求输出目录必须为空的场景。

工具不会自动删除已有目录。

## 十、使用 SSH（可选）

只有已经配置好公司 GitLab SSH Key 的用户才使用 SSH。

把配置改为：

```text
clone_protocol=ssh
```

先测试 SSH 是否正常：

```bat
ssh -T git@gitlab.example.com
```

如果不知道 SSH Key 是什么，继续使用 `clone_protocol=http` 即可。

## 十一、常见问题

### 1. 提示 `py` 不是内部或外部命令

Python 没安装，或者没有加入 PATH。重新安装 Python，并勾选 `Add Python to PATH`。

### 2. 提示 `git` 不是内部或外部命令

安装 Git for Windows，安装后重新打开命令提示符。

### 3. 提示 `No module named gitlab_tools`

工具没有安装成功。进入 `.whl` 文件所在目录，重新执行：

```bat
py -m pip install --force-reinstall gitlab_tools-0.3.0-py3-none-any.whl
```

### 4. HTTP 401 或 403

通常是 Token 错误、过期或权限不足。检查：

- Token 是否复制完整。
- Token 是否已过期。
- 是否有 `read_api` 和 `read_repository` 权限。
- 当前账号是否有权访问目标项目。

### 5. 提示 project 名称不唯一

不要只写项目名称，改用完整路径。

错误示例：

```text
projects=project-a
```

正确示例：

```text
projects=dept/platform/project-a
```

### 6. 提示配置文件不存在

先进入配置文件所在目录：

```bat
cd /d D:\GitLabRepositoryExport
```

再执行启动脚本。

### 7. 提示 SSL 证书错误

优先联系公司网络或 GitLab 管理员处理证书。只有确认是可信的公司内网 GitLab、且管理员明确允许时，才临时改为：

```text
verify_ssl=false
```

这会降低连接安全性，不建议长期使用。

### 8. 部分项目失败，但其他项目成功

这是工具的正常批量处理方式。打开：

```text
repositories-export.log
```

搜索“失败”或查看最后几行。退出码 `4` 表示批量任务已执行完，但至少有一个项目失败。

### 9. 运行后已有项目没有变化

检查是否配置了：

```text
existing=skip
```

如果需要更新已有项目，改为：

```text
existing=update
```

## 十二、最短操作清单

已经安装 Python、Git 和工具后，只需要：

```bat
mkdir D:\GitLabRepositoryExport
cd /d D:\GitLabRepositoryExport
py -m gitlab_tools repositories init-config
notepad gitlab.config.txt
notepad repositories.config.txt
run_repositories_export.bat
```

填写配置时记住三点：

1. GitLab 地址不要带 `/api/v4`。
2. 项目尽量填写完整 `group/project` 路径。
3. 第一次运行保持 `clone_protocol=http`、`existing=skip`。
