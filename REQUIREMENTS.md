# 需求说明

## 背景

在办公内网存在一个 GitLab Community Edition `v17.7.4` 服务。  
需要一个可带入 Windows 10 内网环境、直接通过终端运行的工具，用于按指定范围导出 GitLab 的 Milestone 和 Issue 内容，方便离线归档、审阅和后续整理。

## 目标

提供一个**纯 Python、无第三方依赖**的导出工具，支持用 `Personal Access Token` 访问 GitLab API，按配置导出 group/project 下的 Milestone 与对应 Issue，并生成结构化 Markdown 结果。

## 运行环境要求

- 操作系统：Windows 10
- Python：3.11
- 网络环境：办公内网，可访问 GitLab 地址
- 依赖要求：无第三方依赖，仅使用 Python 标准库
- 交付形式：完整工程文件夹，可压缩为一个 zip 带入办公网

## 输入与配置要求

### GitLab 访问

- GitLab 地址必须可配置，默认示例地址为：
  - `https://gitlab.example.com`
- 认证方式使用 `Personal Access Token`
- Token 支持两种提供方式：
  - 直接写入配置文件
  - 通过环境变量提供

### 配置文件

- 配置形式必须尽量简单
- 使用纯文本 `key=value` 格式
- 不依赖 YAML、JSON 或额外解析库

### 导出范围

- 必须支持按 `group` 路径配置导出范围
- 必须支持按 `project` 路径配置导出范围
- 必须允许同时配置多个 group 和多个 project
- 范围配置不做“全量自动遍历所有可见项目”作为默认行为
- 用户自行指定需要导出的 group/project 路径

## 导出内容要求

### Milestone

- 导出全部 Milestone
- 不区分 active / closed，要求都能覆盖

### Issue

- 导出 Milestone 下的 Issue
- 导出 Issue 正文内容
- 不导出 Issue 评论
- 不导出图片和其他二进制附件
- 保留 Issue 基本元数据，便于后续查看和追溯

## 输出要求

### 输出目录

- 导出结果默认放到：
  - `D:\Downloads\ExportedByGitLabTools`

### 目录结构

- 每个 `group` 或 `project` 生成一个独立目录
- 每个 Milestone 生成一个独立目录
- 每个 Milestone 目录内至少包含：
  - `milestone.md`
  - `issues/`
- 每个 scope 目录下生成一个 `index.md`，便于总览

### Milestone 目录命名规则

Milestone 文件夹名必须以日期前缀开头，日期格式为：

```text
YYYYMMDD
```

取值逻辑：

1. 如果 milestone 已关闭，取关闭日期
2. 如果 milestone 未关闭但已过期，取过期日期
3. 如果两者都没有，取：
   - `20269999`

实现时的补充约定：

- 若 GitLab 接口未稳定提供单独的关闭日期字段，但 milestone 状态已为 closed，可回退使用 `updated_at`

示例：

```text
20260526_Sprint-2026-05
20269999_长期规划
```

### Windows 文件名兼容

- 目录名和文件名必须兼容 Windows
- 非法字符要自动清洗
- 若标题不适合直接作为文件名，要自动回退为安全名称

## 交互与可观测性要求

### 终端运行

- 工具必须可在终端直接运行
- Windows 环境下默认使用 `py` 启动，而不是假设存在 `python` 命令

### 运行反馈

- 在终端实时打印当前进度
- 至少包括：
  - 程序启动
  - 当前处理哪个 group/project
  - 当前处理哪个 milestone
  - 已获取 issue 数量
  - 导出完成统计
  - 错误信息

### 日志

- 需要把运行日志写到当前工具目录
- 日志文件名为：
  - `export.log`
- 错误日志必须能够落盘，方便排查

## 交付要求

交付工程内至少包含：

- 源码
- 示例配置文件
- Windows 启动脚本
- 用户说明文档
- 设计/维护文档
- 需求说明文档

## 文档要求

### 用户说明

需要提供面向使用者的说明文档，至少包含：

- 工具用途
- 使用步骤
- 配置说明
- 运行方式
- 常见问题

### 设计说明

需要提供面向维护者的说明文档，至少包含：

- 技术路线
- 模块划分
- 数据流
- 输出结构
- 已知边界
- 后续可扩展点

### 需求沉淀

需要把聊天中确认过的需求整理成独立文件，放入工程目录，供后续继续使用和维护时参考。

## 明确不做

当前版本明确不做以下内容：

- SSH Key 直接用于 API 认证
- LDAP 用户名密码自动登录
- 浏览器模拟登录
- Issue 评论导出
- 二进制附件下载
- exe 打包
- 任何第三方 Python 依赖

## 验收标准

满足以下条件可视为通过：

1. 工具可在 Windows 10 + Python 3.11 环境运行
2. 无需安装第三方 Python 包
3. 可通过配置指定多个 group/project 路径
4. 可成功导出 Milestone 和对应 Issue 正文
5. 输出目录结构符合约定
6. milestone 目录名符合日期前缀规则
7. 终端可看到实时进度
8. 工具目录中可看到 `export.log`
9. 工程内包含 README、设计文档、需求文档
