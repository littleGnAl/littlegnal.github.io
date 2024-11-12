---
title: "glance: An APM library for detecting UI jank in Flutter for mobile (Android/iOS)"
date: 2024-11-12 00:00:00 +0800
---

## Motivation

Inspired by the [thread_collect_stack_example](https://github.com/mraleph/thread_collect_stack_example) project, I developed an UI jank detection library for Flutter mobile apps (Android/iOS) in production: [glance](https://github.com/littleGnAl/glance). This article primarily records some ideas during the development process and helps those interested in [glance](https://github.com/littleGnAl/glance) understand its basic principles.

## Why Detect UI Jank in Production?

Building a smooth application with Flutter isn’t difficult, but as the complexity of the APP increases and it runs across different user environments and devices, ensuring performance in production becomes challenging. Even if the app runs smoothly locally, it doesn’t mean all users experience the same. If we can monitor UI jank in production and collect stack trace information, it would help us quickly pinpoint the specific cause of performance issues and effectively resolve them.

## Jank Detection

Let’s briefly review the rendering process of Flutter. The Flutter UI Task Runner is responsible for executing Dart code, with the rendering pipeline also running on it. When the UI needs to be updated, the Flutter Framework notifies the Flutter Engine through `SchedulerBinding.scheduleFrame`. The Flutter Engine registers a Vsync signal callback with the system, and when the next Vsync signal arrives, it drives the rendering pipeline via `SchedulerBinding.handleBeginFrame` and `SchedulerBinding.handleDrawFrame`, executing the Build, Layout, and Paint stages in sequence to generate the latest Layer Tree, which is finally handed over to the Raster Task Runner for rasterization and display.

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

We can define a jank threshold, starting at `SchedulerBinding.handleBeginFrame` and stopping it at `SchedulerBinding.handleDrawFrame`. If the time taken by the rendering pipeline exceeds the threshold, we consider it a jank occurrence.

However, this approach cannot detect jank in touch events. Reviewing Flutter’s touch event processing: the Platform side collects touch event data, invokes `ui.PlatformDispatcher.onPointerDataPacket` through the Flutter Engine, and finally reaches `GestureBinding.handlePointerEvent` for processing.

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

By measuring the execution time of `GestureBinding.handlePointerEvent`, we can determine if there is jank in touch events. Similarly, other Platform specific callbacks (such as callbacks from `WidgetBindingObserver` or method calls from `MethodChannel`) can be checked for jank by measuring their execution time.

## Capturing Jank Stack Trace

We refer to the implementation of the [Dart SDK Profiler](https://github.com/dart-lang/sdk/blob/3cc6105316be32e2d48b1b9b253247ad4fc89698/runtime/vm/profiler.cc) to implement our stack capturing logic. The main idea is to create a dedicated [Isolate](https://api.flutter.dev/flutter/dart-isolate/Isolate-class.html) for capturing stacks. This isolate periodically polls the UI Task Runner, captures the current stack information, and stores it in a ring buffer to retain recent stack traces. When jank is detected, we can retrieve the stacks at the start and end of the jank period and aggregate them to get a complete jank stack trace.

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

### Obtaining the Current Stack

Referencing the implemetation of the [Dart SDK Profiler](https://github.com/dart-lang/sdk/blob/3cc6105316be32e2d48b1b9b253247ad4fc89698/runtime/vm/profiler.cc), we interrupt the thread on Android using a [Signal Handler mechanism](https://en.wikipedia.org/wiki/Signal_(IPC)), while on iOS we pause the thread to unwind the stack.

> Why not use signals on iOS? iOS could use the signal handler mechanism, and the Dart SDK initially implemented it that way, but due to [this issue](https://github.com/dart-lang/sdk/issues/47139), it switched to pausing threads mechanism.

#### Stack Frame Unwinding

Take ARM64 stack frame layout as an example (below). Each function call maintains a separate stack frame, where each frame contains an `FP` (Frame Pointer) pointing to the previous frame’s `FP`, and the adjacent `LR` (Link Register) holds the return address. We can unwind to previous frames by following the `FP`, and the function corresponding to each stack frame is indicated by the function pointed to by the adjacent `LR`.

![ARM64 Stack Frame](https://raw.githubusercontent.com/ARM-software/abi-aa/refs/heads/main/aapcs64/aapcs64-variadic-stack.png)

The unwinding pseudocode:
```c++
while (fp) {
    pc = *(fp + 1);
    fp = *fp;
}
```

## Symbolizing the Stack Trace

In Flutter, we can export symbol files using the `--split-debug-info` argument (see [https://docs.flutter.dev/deployment/obfuscate](https://docs.flutter.dev/deployment/obfuscate)) and use the `flutter symbolize` command to symbolize them. However, because we obtain stacks in a custom format that doesn’t match Dart SDK stack trace format, we cannot directly use `flutter symbolize` command to symbolize them. Therefore, we need to convert our custom stack trace format into the Dart SDK standard format for the `flutter symbolize` command to symbolize.

Here is a stack trace obtained through `StackTrace.current`:

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

To better understand this stack trace format and the meaning of its addresses, we took a closer look at the [implementation of StackTrace.current](https://github.com/dart-lang/sdk/blob/fff7b0589c5b39598b864533ca5fdabb60a8237c/runtime/vm/object.cc#L26259).

After diving deeper at the implemetation, we summarized the format template for Dart SDK stack trace as follows:

```
*** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
pid: <pid>, tid: <tid>, name io.flutter.1.ui
os: <os> arch: <arch> comp: <comp> sim: <sim>
build_id: '<build_id>'
isolate_dso_base: <isolate_dso_base>, vm_dso_base: <vm_dso_base>
isolate_instructions: <isolate_instructions>, vm_instructions: <vm_instructions>
    #00 abs <pc> _kDartIsolateSnapshotInstructions+<pc_offset>
```

In this format, we primarily focus on the following two fields:
- `pc`: the Program Counter value in the stack.
- `pc_offset`: calculated as `pc - <isolate_instructions>`.

We simply need to take the `pc` values from the captured stack trace and reconstruct them according to the above rules to match the Dart SDK stack trace format, allowing `flutter symbolize` to directly symbolize it.

### Symbolize Stack Trace Automatically

In online monitoring, after obtaining a jank stack trace, storage and symbolization become challenging. Some companies may have in-house monitoring platforms that upload jank stack traces to a server and use `flutter symbolize` command on the server for symbolization. However, most teams may lack such infrastructure.

Fortunately, some crash collection platforms (like Firebase and Sentry) provide automatic stack trace symbolization. By uploading symbol files, these platforms can automatically symbolize the stack traces:

- Firebase: [https://firebase.google.com/docs/crashlytics/get-deobfuscated-reports?platform=flutter](https://firebase.google.com/docs/crashlytics/get-deobfuscated-reports?platform=flutter)
- Sentry: [https://docs.sentry.io/platforms/flutter/upload-debug/](https://docs.sentry.io/platforms/flutter/upload-debug/)

For example, in Firebase, you can upload the jank stack trace using `recordError`, as shown in the following code sample:
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

This method also applies to other platforms that support automatically symbolize the Dart stack trace.

## TL;DR

These are some of my thoughts from developing [glance](https://github.com/littleGnAl/glance). I hope this content is helpful to you. If there are any inaccuracies, please feel free to correct me. I welcome you to try it out and share any feedback or suggestions.



















