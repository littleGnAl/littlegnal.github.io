---
title: Flutter线上卡顿检测库：glance
date: 2024-11-09 00:00:00 +0800
---

## Motivation

受到[thread_collect_stack_example](https://github.com/mraleph/thread_collect_stack_example)项目的启发，我开发了一个线上卡顿监控库：[glance](https://github.com/littleGnAl/glance)。这篇文章主要记录一下开发过程中的一些想法，并帮助对[glance](https://github.com/littleGnAl/glance)感兴趣的朋友了解它的基本原理。

## 为什么要线上卡顿检测

用 Flutter 构建流畅的应用程序并不难，但随着应用复杂度增加，并在不同用户环境和设备上运行，确保在生产环境中的性能表现就变得具有挑战性。即使应用在本地运行流畅，也不代表所有用户的体验都是一样的。如果我们能够在线监控 UI 卡顿，并收集堆栈追踪信息，就能帮助我们快速定位性能问题的具体原因，从而有效解决问题。

## 卡顿检测

我们简单回顾一下Flutter的渲染原理。Flutter的UI Task Runner负责执行Dart代码，渲染管线也在其中运行。当界面需要更新时，Framework会通过 `SchedulerBinding.scheduleFrame`通知Engine层，Engine层向系统注册Vsync信号的回调，在下一个VSync信号到来时，通过`SchedulerBinding.handleBeginFrame`和`SchedulerBinding.handleDrawFrame`驱动渲染管线，依次执行Build、Layout和Paint阶段，生成最新的Layer Tree，最终通过`ui.FlutterView.render`交给Raster Task Runner进行光栅化并显示。

```
┌─────────┐                                       ┌─────────┐
│         │                                       │         │
│         │                                       │         │
│         │   SchedulerBinding.scheduleFrame      │         │
│         │─────────────────────────────────────► │         │
│         │                                       │         │
│         │                                       │         │
│         │  SchdulerBinding.handleBeginFrame     │         │
│         │◄───────────────────────────────────── │         │
│Framework│                                       │  Engine │
│         │                                       │         │
│         │   SchdulerBinding.handleDrawFrame     │         │
│         │    +--------------------------+       │         │
│         │    |                          |       │         │
│         │◄───| Build -> Layout -> Paint |────── │         │
│         │    |                          |       │         │
│         │    +--------------------------+       │         │
│         │                                       │         │
│         │                                       │         │
└─────────┘                                       └─────────┘
```

我们可以定义一个卡顿阈值，在`SchdulerBinding.handleBeginFrame`开始计时，到`SchdulerBinding.handleDrawFrame`结束。如果渲染管线的执行时间超过阈值，则认为发生了卡顿。

但是这种方法无法检测到点击事件的卡顿。我们简单回顾一下 Flutter的触摸事件处理流程：Flutter在平台侧收集触摸事件数据，通过Engine层调用`ui.PlatformDispatcher.onPointerDataPacket`，最终到达`GestureBinding.handlePointerEvent`进行处理。

```
┌─────────┐                                                 ┌─────────┐                  ┌─────────┐
│         │                                                 │         │                  │         │
│         │                                                 │         │                  │         │
│         │                                                 │         │                  │         │
│         │   +----------------------------------------+    │         │                  │         │
│         │   |                                        |    │         │                  │         │
│         │   | PlatformDispatcher.onPointerDataPacket |    │         │                  │         │
│         │   |                                        |    │         │ Dispatch Pointer │         │
│         │   |                  |                     |    │         │ Data Packet      │ Android │
│Framework│◄──|                  |                     |────│  Engine │ ◄━━━━━━━━━━━━━━━━│ iOS     │
│         │   |                  ▼                     |    │         │                  │         │
│         │   |                                        |    │         │                  │         │
│         │   |    GestureBinding.handlePointerEvent   |    │         │                  │         │
│         │   |                                        |    │         │                  │         │
│         │   +----------------------------------------+    │         │                  │         │
│         │                                                 │         │                  │         │
│         │                                                 │         │                  │         │
│         │                                                 │         │                  │         │
│         │                                                 │         │                  │         │
└─────────┘                                                 └─────────┘                  └─────────┘

```

通过检测`GestureBinding.handlePointerEvent`的执行时间，我们可以判断是否存在点击事件卡顿。同理，其他来自平台的回调（如`WidgetBindingObserver`的回调、`MethodChannel`的方法调用）也可以通过检测执行时间来判断是否存在卡顿。

## 卡顿堆栈采集

我们借鉴了[Dart SDK Profiler模块](https://github.com/dart-lang/sdk/blob/3cc6105316be32e2d48b1b9b253247ad4fc89698/runtime/vm/profiler.cc)的逻辑来实现堆栈采集。整体实现思路是开启一个专门用于采集堆栈的[Isolate](https://api.flutter.dev/flutter/dart-isolate/Isolate-class.html)，这个`Isolate`会定期轮询UI Task Runner，捕获当前的堆栈信息并保存到一个环形链表中。环形链表用于存储最近一段时间的堆栈信息。当检测到卡顿时，我们可以获取卡顿开始和结束时的堆栈，对其进行聚合就可以获取完整的卡顿堆栈了。

```
+--------------+                        +----------------------------------------+
|              |                        |                                        |
|              |                        |  Sampler Isolate                       |
|              |                        |                                        |
|              |                        |               ┌───────────────────┐    |
|              |                        |               │                   │    |
|              |                        |               ▼                   │    |
|              |                        |    ┌──────────────────────┐       │    |
|              |                        |    │                      │       │    |
|              |                        |    │ Capture Native Frames│     Loop   |
|              |                        |    │                      │       │    |
|              |                        |    └──────────────────────┘       │    |
|              |                        |               │                   │    |
|              |                        |               │───────────────────┘    |
|              |                        |               ▼                        |
| Main Isolate |                        |        ┌─────────────┐                 |
|              | Jank Detected(start/end time)   │             │                 |
|              |────────────────────────────────►│             │                 |
|              |                        |        │             │                 |
|              |                        |        │             │                 |
|              |                        |        │ Ring Buffer │                 |
|              |                        |        │             │                 |
|              |                        |        │             │                 |
|              |                        |        │             │                 |
|              |     Report             |        │             │                 |
|              |◄────────────────────────────────│             │                 |
|              |                        |        └─────────────┘                 |
|              |                        |                                        |
+--------------+                        +----------------------------------------+
```

###  如何获取当前堆栈

参考[Dart SDK Profiler](https://github.com/dart-lang/sdk/blob/3cc6105316be32e2d48b1b9b253247ad4fc89698/runtime/vm/profiler.cc)的实现，在Android使用[Signal Handler机制](https://en.wikipedia.org/wiki/Signal_(IPC))来中断线程，iOS则使用暂停线程的方式，然后通过栈帧回溯获取当前堆栈。

> 为什么 iOS不使用信号机制？iOS 也可以使用信号机制，而且在 Dart SDK 最初的实现中也是使用的信号机制，但由于[这个问题](https://github.com/dart-lang/sdk/issues/47139)改成了暂停线程的方式来实现。

#### 栈帧回溯

以ARM64栈帧布局为例子（如下图）。每次函数调用都会在调用栈上维护一个独立的栈帧，每个栈帧中都有一个FP（Frame Pointer），指向上一个栈帧的FP，而与FP相邻的LR（Link Register）中保存的是函数的返回地址。也就是我们可以根据FP找到上一个FP，而与FP相邻的LR对应的函数就是该栈帧对应的函数。

![](https://raw.githubusercontent.com/ARM-software/abi-aa/refs/heads/main/aapcs64/aapcs64-variadic-stack.png)

以下是栈帧回溯的伪代码：
```c++
while (fp) {
    pc = *(fp + 1);
    fp = *fp;
}
```

## 符号化堆栈

在 Flutter 中，我们可以通过`--split-debug-info`参数导出符号文件（见[https://docs.flutter.dev/deployment/obfuscate](https://docs.flutter.dev/deployment/obfuscate)），然后使用`flutter symbolize`命令进行符号化。然而，由于我们获取堆栈的方式是自定义的，格式不符合Dark SDK堆栈格式，无法直接使用`flutter symbolize`命令。因此，我们需要一种方法将自定义格式的堆栈转换为Dart SDK标准堆栈格式，以便`flutter symbolize`可以解析。

首先，来看一下通过`StackTrace.current`获取的堆栈：
```
*** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
pid: 8353, tid: 8399, name 1.ui
os: android arch: arm64 comp: yes sim: no
build_id: '083986ecd5337898b3b58b5e06cb8b9e'
isolate_dso_base: 751c2b3000, vm_dso_base: 751c2b3000
isolate_instructions: 751c379940, vm_instructions: 751c363000
    #00 abs 000000751c519567 virt 0000000000266567 _kDartIsolateSnapshotInstructions+0x19fc27
    #01 abs 000000751c3db98b virt 000000000012898b _kDartIsolateSnapshotInstructions+0x6204b
    #02 abs 000000751c3bc9eb virt 00000000001099eb _kDartIsolateSnapshotInstructions+0x430ab
    #03 abs 000000751c3bfd6b virt 000000000010cd6b _kDartIsolateSnapshotInstructions+0x4642b
    #04 abs 000000751c525b97 virt 0000000000272b97 _kDartIsolateSnapshotInstructions+0x1ac257
    #05 abs 000000751c4eace7 virt 0000000000237ce7 _kDartIsolateSnapshotInstructions+0x1713a7
```

为理解这种堆栈格式及其地址含义，我们深入研究了[StackTrace.current 的实现](https://github.com/dart-lang/sdk/blob/fff7b0589c5b39598b864533ca5fdabb60a8237c/runtime/vm/object.cc#L26259)。

经过分析，总结出 Dart SDK 堆栈的格式模板如下：

```
*** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
pid: <pid>, tid: <tid>, name io.flutter.1.ui
os: <os> arch: <arch> comp: <comp> sim: <sim>
build_id: '<build_id>'
isolate_dso_base: <isolate_dso_base>, vm_dso_base: <vm_dso_base>
isolate_instructions: <isolate_instructions>, vm_instructions: <vm_instructions>
    #00 abs <pc> _kDartIsolateSnapshotInstructions+<pc_offset>
```
在该格式中，我们主要关注以下两个字段：
- `pc`: 堆栈中的程序计数器（Program Counter）值。
- `pc_offset`: 计算方式为`pc - <isolate_instructions>`。

我们只需要将上面采集到的堆栈的`pc`值，按照上面规则重建符合Dart SDK格式的堆栈，就可以使用`flutter symbolize`直接对其进行符号化了。

### 自动符号化堆栈

在进行线上监控时，获取卡顿堆栈后，如何存储和符号化也是一个的难题。一些公司可能有自建监控平台，能够将卡顿堆栈上传至服务器，并在服务器上运行`flutter symbolize`进行符号化。然而，大多数团队可能缺乏这种基础设施。

幸运的是，一些崩溃收集平台（如Firebase和Sentry）提供了自动符号化堆栈的功能。通过上传符号文件，就能自动对堆栈进行解析：

- Firebase: [https://firebase.google.com/docs/crashlytics/get-deobfuscated-reports?platform=flutter](https://firebase.google.com/docs/crashlytics/get-deobfuscated-reports?platform=flutter)
- Sentry: [https://docs.sentry.io/platforms/flutter/upload-debug/](https://docs.sentry.io/platforms/flutter/upload-debug/)

以Firebase为例，你可以通过`recordError`上传卡顿堆栈，示例代码如下：
```dart
class MyJankDetectedReporter extends JankDetectedReporter {
  @override
  void report(JankReport info) {
    FirebaseCrashlytics.instance.recordError(
      'ui-jank',
      info.stackTrace,
      reason: 'ui-jank',
      fatal: false,
    );
  }
}
```
这种方式同样适用于其他支持Flutter堆栈自动符号化的平台。

## TL;DR

以上，是我开发[glance](https://github.com/littleGnAl/glance)过程中的一些想法。希望这些内容对你有所帮助。若有描述不当之处，恳请指正。欢迎试用并提出宝贵的建议和意见。
