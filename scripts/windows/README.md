# Windows 启动脚本

本目录存放源码仓库使用的 Windows BAT 脚本，避免不同功能的启动脚本散落在仓库根目录。

```text
run_milestones_export.bat
run_repositories_export.bat
```

这些脚本会先切换到仓库根目录，再读取根目录中的配置文件。

普通用户通过下面的命令初始化各功能配置：

```bat
py -m gitlab_tools milestones init-config
py -m gitlab_tools repositories init-config
```

命令会从 Python 包内的 `gitlab_tools/templates/` 复制当前功能所需的配置和 BAT 到用户目录。用户不需要进入本目录，也不需要从源码仓库手工复制脚本。
