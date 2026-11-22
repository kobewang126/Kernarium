# Ubuntu Touch / Toucharium 项目

目标是在独立的 iOS 应用内运行官方 Ubuntu Touch 用户空间、Lomiri 界面和应用，复用 Andarium / Kernarium 的进程内 Linux 执行、虚拟设备与 GuestHost 显示输入机制。运行验证统一使用当前 Mac 上的 iPhone 17 模拟器。

工程位于 [`Toucharium/`](Toucharium/README.md)，镜像生产入口位于 [`tools/rootfs/ubuntu-touch/`](tools/rootfs/ubuntu-touch/README.md)。独立应用共享本仓库运行时和宿主组件，继续遵守其许可证与依赖边界。

## 架构

```mermaid
flowchart TB
    APP[Toucharium SwiftUI 应用] --> HOST[GuestHost 显示、触控与生命周期]
    APP --> RT[Kernarium 通用 Linux 运行时]
    RT --> CPU[arm64 用户态执行引擎与软件 MMU]
    RT --> KERNEL[项目移植的 arm64 UML Linux 内核]
    KERNEL --> ROOT[官方 UBports PDK 用户空间]
    ROOT --> INIT[systemd 与 LightDM]
    INIT --> UI[Mir / Lomiri 与 Ubuntu Touch 应用]
    KERNEL --> DEV[Virtio 图形、输入、网络与块设备]
    DEV --> HOST
```

采用官方 mainline PDK 用户空间适配虚拟设备，不依赖某款 Android 实体设备的 Halium 厂商层。iOS 模拟器使用独立的软件渲染产物。

## 构建与部署

```mermaid
flowchart TB
    SRC[锁定的内核源码与项目补丁] --> BUILD[Linux 服务器编译及产物校验]
    BUILD --> KERNEL[取回兼容的内核 bundle]
    PDK[锁定的官方 UBports PDK 镜像] --> DERIVE[Linux 上校验输入并应用设备策略]
    DERIVE --> EROFS[检查 EROFS 与来源收据]
    DEPS[验证的私有依赖与启动基础镜像] --> RT[CMake / Ninja 构建 Linux 运行时]
    KERNEL --> RT --> FW[打包对应平台 XCFramework]
    FW --> XCODE[Xcode 构建 Toucharium]
    XCODE --> APP[iPhone 17 模拟器]
    EROFS --> DOC[暂存到应用 Documents]
    DOC --> APP --> VERIFY[验证系统、Lomiri、应用与触控]
```

内核、系统镜像和应用各有独立的构建校验。安装成功、内核启动、图形会话可用和应用可操作必须分别取得运行证据。

## 验收范围

- 输入来源锁定，内核与宿主 ABI、4 KiB 客体页配置一致。
- 官方 Ubuntu Touch 系统启动；进程、文件系统、虚拟网络和 D-Bus 服务正常。
- Mir / Lomiri 持续显示，触控与键盘可操作，至少一个 Ubuntu Touch 应用可运行。
- 用户数据能在停止与重新启动后保留，应用更新不覆盖用户数据。
- 在 iPhone 17 模拟器完成冷启动、交互、暂停恢复、停止与重启验证。

目前已建立独立 Xcode 工程与官方 PDK 镜像派生工具；系统启动、图形交互与持久化尚未完成验收。不能以普通 Ubuntu 桌面或应用外壳替代 Ubuntu Touch 客体验收。
