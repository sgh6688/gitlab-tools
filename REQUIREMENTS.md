# 需求说明

## 1. 项目级目标

项目名称为 **GitLab Tools**，仓库名和 Python 包名分别为：

- GitHub 仓库：`gitlab-tools`
- Python 包：`gitlab_tools`
- 命令名称：`gitlab-tools`

项目应作为可扩展的 GitLab 工具集合，通过“功能域 + 动作”子命令运行不同功能，不得以某一个具体导出功能作为整个项目名称或顶层代码组织。

当前交付功能为 `milestones export`。后续计划增加 `repositories export`，用于导出单个 project 或 group 下多个 project 的源码。

## 2. 通用要求

- Windows 10
- Python 3.11+
- 办公内网可直接运行
- 运行时无第三方 Python 依赖
- 支持 Personal Access Token
- 顶层 CLI 可继续注册新功能
- 通用 HTTP、分页、日志与工具函数可复用
- 各功能的业务 API、配置和流程相互隔离

统一运行形式：

```text
py -m gitlab_tools <功能域> <动作> [参数]
```

## 3. 当前功能：Milestone 导出

### 输入

- GitLab 根地址（不含 `/api/v4`）
- Token 或 Token 环境变量名
- 一个或多个 group 路径
- 一个或多个 project 路径
- 输出目录、超时、分页大小、SSL 校验开关
- 配置使用纯文本 `key=value`，不依赖 YAML/JSON 库

### 导出内容

- active 和 closed Milestone
- Milestone 对应的 Issue
- Issue 正文与基本元数据
- 不导出评论、图片和其他二进制附件

### 输出

默认目录：

```text
D:\Downloads\ExportedByGitLabTools
```

每个 group/project 独立建目录，每个 Milestone 目录至少包含：

```text
index.md
<DatePrefix>_<MilestoneName>/milestone.md
<DatePrefix>_<MilestoneName>/issues/*.md
```

日期前缀规则：

1. 已关闭时取关闭日期；没有单独关闭时间时回退 `updated_at`；
2. 未关闭但已到期时取 `due_date`；
3. 其他情况取 `20269999`。

目录和文件名必须兼容 Windows。

### 运行与日志

```text
py -m gitlab_tools milestones export --config milestones.config.txt
```

终端实时显示 scope、Milestone、Issue 数量和最终统计。日志写入配置文件同级的 `milestones-export.log`。

### 当前验收标准

1. Windows 10 + Python 3.11 可运行；
2. 无需安装第三方包；
3. 可配置多个 group/project；
4. 可导出全部 Milestone 及对应 Issue 正文；
5. 输出目录和日期前缀符合约定；
6. 终端和日志均有进度及错误信息；
7. `py -m gitlab_tools --help` 可显示功能域；
8. `py -m gitlab_tools milestones --help` 可显示 `export`；
9. 自动化测试可通过。

## 4. 后续功能：Repository 源码导出

目标是支持：

- 导出指定 project 的代码；
- 枚举并导出指定 group（可扩展 subgroup 策略）下的多个 project；
- 输出项目清单、版本信息、成功/失败状态；
- 单项目失败时尽量不阻断批量任务；
- 复用通用 GitLab 客户端、Token、分页和日志能力；
- 业务代码独立放在 `commands/repositories/`。

实现前仍需确认导出模式：普通工作副本、完整裸镜像或压缩归档，以及分支、Tag、Git LFS、submodule 的处理范围。

该部分是后续需求，不属于当前已实现能力。
