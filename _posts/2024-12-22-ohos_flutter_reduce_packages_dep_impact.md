---
title: "鸿蒙Flutter适配: 如何减少鸿蒙Flutter packages依赖对项目的影响"
date: 2024-12-22 00:00:00 +0800
---

## Motivation

这是一篇很简短的文章，主要记录我在适配[鸿蒙Flutter](https://gitee.com/openharmony-sig/flutter_flutter)时遇到的问题和解决办法。如果你也遇到类似的问题，希望这些内容能帮到你。

## 鸿蒙Flutter packages依赖
在适配一个新的平台的时候，我们希望尽可能减少对现有项目的修改，特别是各种依赖，减少和避免影响到其他平台（如 Android、iOS、macOS、Windows、Web 等）。适配鸿蒙Flutter也如此，但由于[鸿蒙Flutter packages](https://gitee.com/openharmony-sig/flutter_packages)基于[一年前的commit](https://github.com/flutter/packages/commit/b8b84b2304f00a3f93ce585cc7a30e1235bde7a0)，按照[官方的依赖方式](https://gitee.com/openharmony-sig/flutter_packages#%E4%BA%8C-%E6%8F%92%E4%BB%B6%E5%BA%93%E4%BD%BF%E7%94%A8)，相当于我们必须回滚某些依赖版本。这可能导致我们需要对现有支持的平台进行重新适配，这自然不是我们想要做的。

庆幸[Flutter官方packages](https://github.com/flutter/packages)都改造成了[Federated plugin结构](https://docs.flutter.dev/packages-and-plugins/developing-packages#federated-plugins)，这让我们在适配鸿蒙Flutter时，可以仅引入鸿蒙Flutter packages原生层（ets代码）的实现，而不需要影响其他平台。以`path_provider`为例，其原生层的实现在[path_provider_ohos
](https://gitee.com/openharmony-sig/flutter_packages/tree/master/packages/path_provider/path_provider_ohos) package中，我们仅需额外引入`path_provider_ohos`即可：

pubspec.yaml

```yaml
path_provider: ^2.1.5
# Import the native implementation of `path_provider` for ohos
path_provider_ohos:
  git:
    url: https://gitee.com/openharmony-sig/flutter_packages.git
    ref: master
    path: packages/path_provider/path_provider_ohos 
```

这样做的好处是只引入了鸿蒙Flutter packages原生层的代码，不影响其他平台。如果有问题，我们可以fork对应插件进行修改，修改的成本要低得多。

以上方式只支持[Federated plugin结构](https://docs.flutter.dev/packages-and-plugins/developing-packages#federated-plugins)，如果非Federated plugin结构的Plugin还是需要依赖鸿蒙Flutter packages的版本。

## TL;DR

理论上能保证鸿蒙Flutter ets层导出的接口不变，那么鸿蒙Flutter packages或其他三方packages的适配工作可以fork最新的代码来进行，而不需要基于一个比较旧的commit。但由于鸿蒙系统和鸿蒙Flutter仍处于初期阶段，我相信未来的开发体验会越来越好。

