# GitLab Tools 发布与离线交付说明

本文面向工具维护者。普通用户请阅读 [USER_GUIDE.md](USER_GUIDE.md)。

## Wheel 一般发布到哪里

| 位置 | 适用场景 | 建议 |
|---|---|---|
| GitHub Releases | 开源项目、固定版本下载 | 本项目的公开主发布位置 |
| GitLab Package Registry、Nexus、Artifactory | 企业内网统一制品管理 | 公司环境优先使用 |
| 内部文件服务器或离线介质 | 完全断网、没有制品库 | 同时提供 SHA-256 校验文件 |
| PyPI | 面向所有 Python 用户公开安装 | 当前不是必需，可后续启用 |

本项目建议：

1. 在 GitHub Releases 发布版本、Wheel 和 SHA-256。
2. 将完全相同的 Wheel 和 SHA-256 同步到公司内部制品库。
3. 完全断网环境使用公司允许的文件交换方式分发离线包。

不要在不同渠道重新构建同一版本。应发布同一个 Wheel，保证哈希一致。

## 1. 发布前检查

确认版本号已经更新，例如：

```text
pyproject.toml: 0.3.4
gitlab_tools/__init__.py: 0.3.4
```

执行：

```bash
python3.11 -m compileall -q gitlab_tools tests
python3.11 -m unittest discover -s tests -q
git diff --check
git status --short
```

工作区应干净，所有测试必须通过。

## 2. 构建 Wheel

联网环境可执行：

```bash
python3.11 -m pip wheel --no-deps --wheel-dir dist .
```

生成：

```text
dist/gitlab_tools-0.3.4-py3-none-any.whl
```

## 3. 隔离安装验证

macOS/Linux：

```bash
python3.11 -m venv /tmp/gitlab-tools-release-check
/tmp/gitlab-tools-release-check/bin/python -m pip install --no-index dist/gitlab_tools-0.3.4-py3-none-any.whl
/tmp/gitlab-tools-release-check/bin/gitlab-tools --help
/tmp/gitlab-tools-release-check/bin/gitlab-tools milestones --help
/tmp/gitlab-tools-release-check/bin/gitlab-tools repositories --help
```

Windows：

```bat
py -m venv release-check
release-check\Scripts\python -m pip install --no-index dist\gitlab_tools-0.3.4-py3-none-any.whl
release-check\Scripts\gitlab-tools --help
release-check\Scripts\gitlab-tools milestones --help
release-check\Scripts\gitlab-tools repositories --help
```

还应验证两个初始化命令：

```bat
gitlab-tools milestones init-config --directory milestone-check
gitlab-tools repositories init-config --directory repository-check
```

## 4. 生成 SHA-256 校验文件

macOS：

```bash
(cd dist && shasum -a 256 gitlab_tools-0.3.4-py3-none-any.whl > SHA256SUMS.txt)
```

Linux：

```bash
(cd dist && sha256sum gitlab_tools-0.3.4-py3-none-any.whl > SHA256SUMS.txt)
```

Windows PowerShell：

```powershell
$wheel = "dist\gitlab_tools-0.3.4-py3-none-any.whl"
$hash = (Get-FileHash $wheel -Algorithm SHA256).Hash.ToLower()
"$hash  $([IO.Path]::GetFileName($wheel))" | Set-Content dist\SHA256SUMS.txt
```

收件人下载或复制文件后应再次校验。

macOS：

```bash
shasum -a 256 -c dist/SHA256SUMS.txt
```

Linux：

```bash
sha256sum -c dist/SHA256SUMS.txt
```

Windows PowerShell：

```powershell
$wheel = "dist\gitlab_tools-0.3.4-py3-none-any.whl"
$expected = (Get-Content dist\SHA256SUMS.txt).Split()[0].ToLower()
$actual = (Get-FileHash $wheel -Algorithm SHA256).Hash.ToLower()
if ($actual -ne $expected) { throw "SHA-256 校验失败，请勿安装该文件。" }
"SHA-256 校验通过"
```

## 5. 发布到 GitHub Releases

公开发布前，先确认仓库为 Public。仓库为 Private 时，Release 也只能由有权限的账号下载。

使用 GitHub CLI 修改并核对可见性：

```bash
gh repo edit sgh6688/gitlab-tools --visibility public --accept-visibility-change-consequences
gh repo view sgh6688/gitlab-tools --json visibility
```

输出必须包含：

```json
{"visibility":"PUBLIC"}
```

确认 Public 后，提交并推送版本，然后创建版本标签：

```bash
git tag -a v0.3.4 -m "gitlab-tools v0.3.4"
git push origin v0.3.4
```

已安装并登录 GitHub CLI 时：

```bash
gh release create v0.3.4 \
  dist/gitlab_tools-0.3.4-py3-none-any.whl \
  dist/SHA256SUMS.txt \
  --title "gitlab-tools v0.3.4" \
  --generate-notes
```

也可以在 GitHub 网页进入 `Releases`，选择 `Draft a new release`，上传 Wheel 和 `SHA256SUMS.txt`。

发布完成后，普通用户从 Release 页面下载 Wheel，不需要克隆源码仓库。

## 6. 同步到企业内网

建议保持下面的目录结构：

```text
gitlab-tools\
  0.3.4\
    gitlab_tools-0.3.4-py3-none-any.whl
    SHA256SUMS.txt
```

可以存放在：

- GitLab Generic Package Registry 或 PyPI Package Registry。
- Nexus、Artifactory 等内部制品库。
- 只读内部文件服务器。
- 经批准的离线介质。

上传后重新计算 SHA-256，并与 GitHub Release 中的值比较。两边必须一致。

## 7. 准备完全离线交付目录

如果目标电脑连 Python 和 Git 都没有，准备：

```text
GitLabTools-Offline-0.3.4\
  python-3.11.x-amd64.exe
  Git-x.x.x-64-bit.exe
  gitlab_tools-0.3.4-py3-none-any.whl
  SHA256SUMS.txt
  USER_GUIDE.md
```

注意：

- Python 和 Git 安装程序应从各自官方网站下载。
- 不要把 Token 或用户配置文件放进离线交付包。
- 本工具没有第三方 Python 运行时依赖，不需要额外下载依赖 Wheel。

## 8. 是否发布到 PyPI

如果希望用户直接运行：

```bash
pip install gitlab-tools
```

才需要发布到 PyPI。发布前应确认：

1. PyPI 上的包名可用。
2. 已配置可信发布（Trusted Publishing）或安全的 API Token。
3. 版本发布流程和 GitHub Release 保持一致。

企业内部工具通常不需要公开发布到 PyPI。GitHub Releases加内部制品库已经足够。
