# 需求说明

## 1. 项目级要求

项目名称为 GitLab Tools：

- 仓库：`gitlab-tools`
- Python 包：`gitlab_tools`
- 命令：`gitlab-tools`
- Python 3.11+
- Windows 10 可运行
- Python 运行时无第三方依赖

统一命令模型：

```text
py -m gitlab_tools <功能域> <动作> [参数]
```

当前功能包括 `milestones export` 和 `repositories export`。

## 2. Repository 源码导出需求

### 输入范围

必须支持：

- project ID；
- 完整 project 路径；
- 唯一的精确 project 名称；
- group ID 或完整 group 路径；
- 多个 project/group；
- group 下所有 project；
- 可配置是否包含 subgroup。

裸 project 名称不唯一时不得猜测，必须提示完整候选路径。

### 输出

- 使用普通 `git clone`；
- 不压缩；
- 保留 `.git` 和正常工作目录；
- 按完整 `path_with_namespace` 保存；
- group 导出必须保留 group/subgroup 层级；
- 直接 project 与 group 重复命中时只导出一次。

### 配置与命令行

通用连接配置：`gitlab.config.txt`，包含：

- GitLab URL；
- Token 或 Token 环境变量；
- SSL 校验；
- API 超时；
- 分页大小。

功能配置：`repositories.config.txt`，包含：

- 输出目录；
- projects；
- groups；
- include_subgroups；
- existing。

必须允许 `--gitlab-config` 和 `--config` 指定自定义文件。功能参数也必须可通过命令行指定。

优先级为：内置默认值 < 配置文件 < 命令行。命令行指定任一 project/group 后，应整体覆盖配置文件目标，避免误执行默认批量任务。

### 已存在目录

支持：

- `skip`：保持不变；
- `update`：校验认证源提交后执行无 Token 的 fast-forward merge；
- `fail`：记录失败。

不得默认删除现有目录。

### Token 安全

- Token 不得拼入 clone URL；
- Token 不得写入导出仓库的 remote；
- 推荐通过环境变量提供；
- 配置文件必须默认加入 `.gitignore`；
- Git 命令不得使用 shell 拼接。
- 私有 HTTP clone 必须通过真实 Git 子进程认证测试。
- Git 认证头必须限定到配置的 GitLab 同源地址，不能发送到其他 HTTP(S) 主机；错误文本必须脱敏；
- GitLab API 必须拒绝跨 origin 重定向，Git clone 的跨 origin 重定向不得携带认证头；
- 认证 Git 操作只能在工具创建且隔离系统/全局配置的 bare 仓库中执行；用户仓库的 hook、filter、checkout、fetch 和 merge 不得继承 Token；所有含有当前 Token 值的父环境变量也必须从环境中剥离；
- `update` 必须使用已验证的 `origin` 和当前分支，校验隔离源提交，不能跟随本地被修改的 upstream remote；
- clone 必须先在隔离暂存区完成，并以不可覆盖、拒绝链接的原子安装降低目标路径竞态风险；

### 批量执行与日志

- 单项目失败不得阻断其他项目；
- Windows 清理或截断后的输出路径碰撞必须拒绝，不能跳过或更新到其他项目；
- 根目录内外的符号链接或目录联接不得绕过物理路径碰撞和输出边界检查；
- 无效 JSON、响应结构和分页元数据必须作为全局 API 错误快速失败，不得降级为单目标失败；
- 分页下一页必须为正数且严格向前推进；
- `update` 前必须校验现有仓库的 `origin`；
- 输出 discovered、cloned、updated、skipped、failed 统计；
- 日志文件为 `repositories-export.log`；
- 有部分项目失败时返回非零退出码。

### 验收标准

1. 单 project 默认可导出为剔除 `.git` 等元数据的纯项目快照，并可选导出为完整 Git 工作区；
2. group 可分页枚举项目并保留 namespace 路径；
3. subgroup 开关有效；
4. project/group 结果可去重；
5. 配置文件和命令行优先级符合约定；
6. Token 不进入 URL 或仓库 remote；
7. 路径穿越值被拒绝；
8. 自动化测试使用真实本地 Git 仓库验证 clone；
9. CLI 帮助、示例配置和 Windows 启动脚本完整。
10. wheel 安装后可通过 `repositories init-config` 生成配置，且不得覆盖已有文件。

## 3. Milestone 导出需求

Milestone 功能继续支持：

- 指定多个 group/project；
- 导出 active/closed Milestone；
- 导出对应 Issue 正文和元数据；
- 输出 Markdown；
- Windows 文件名兼容；
- 不导出评论和二进制附件。

运行：

```text
py -m gitlab_tools milestones export --config milestones.config.txt
```

## 4. 当前边界

Repository 功能当前不包括：

- submodule 自动初始化；
- Git LFS 环境安装；
- Wiki、Release 附件、CI Artifact、Container Registry；
- SSH clone 模式；
- 压缩或裸镜像导出。
