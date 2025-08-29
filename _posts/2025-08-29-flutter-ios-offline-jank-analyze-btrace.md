---
title: "分享一个使用btrace线下分析Flutter iOS卡顿的思路"
date: 2025-08-29 00:00:00 +0800
---

## Motivation

你可能不知道Flutter iOS profile模式下是可以看到dart代码的堆栈的

但是使用instrument不方便，对测试同学不友好，有没有不需要instrument的方法

## 使用btrace

按照btrace的官方文档把btrace依赖到项目中，这里我使用flutter官方add2app的demo。

我在代码中加一个耗时方法

![](../assets/images/2025-08-29-flutter-ios-offline-jank-analyze-btrace/jank-fun.png)

perfetto的效果

![](../assets/images/2025-08-29-flutter-ios-offline-jank-analyze-btrace/jank-fun-perfetto.png)

可以看到使用btrace我们可以使用perfetto很好的分析慢方法，方便我们定位Flutter的卡顿问题。
> 这个做法需要Flutter主线程UI线程合并的情况下才能用（Flutter SDK >= 3.32.x）

android需要等到btrace支持native 方法才可以。

## 这就完了？

你可能不知道perftto文件是可以通过API去分析的，https://perfetto.dev/docs/analysis/trace-processor-python

有了perfetto文件，我们可以通过perftto官方的sdk去分析了，详细怎么使用这里不展开。

下面例子查询耗时超过1s的方法

```py
# Open the trace file (replace the path with your actual trace file)
tp = TraceProcessor(trace="my/path/output.pb")

# SQL query to select slices with execution time exceeding 1 second
sql = """
SELECT
  name,
  dur
FROM slice
WHERE dur > 1000000000
ORDER BY dur DESC
LIMIT 200
"""
qr = tp.query(sql)

# Convert the result to a list for post-processing
rows = list(qr)
if not rows:
    print("No methods exceeded 1 second in duration.")
else:
    # Determine the maximum method name length for aligned output
    max_name_len = max(len(r.name) for r in rows)

    for r in rows:
        name = r.name
        dur_ms = r.dur / 1e6
        # Pretty print: "<method_name> (<duration ms>)"
        print(f"{name:<{max_name_len}} ({dur_ms:8.3f} ms)")
```

```
...
RendererBinding.dispatchEvent                            (2001.540 ms)
GestureBinding.dispatchEvent                             (2001.540 ms)
GestureBinding.handleEvent                               (2001.540 ms)
PointerRouter.route                                      (2001.540 ms)
PointerRouter._dispatchEventToRoutes                     (2001.540 ms)
LinkedHashMapMixin.forEach (#2)                          (2001.540 ms)
PointerRouter._dispatchEventToRoutes.<anonymous closure> (2001.540 ms)
PointerRouter._dispatch                                  (2001.540 ms)
PrimaryPointerGestureRecognizer.handleEvent (#2)         (2001.540 ms)
PrimaryPointerGestureRecognizer.handleEvent (#3)         (2001.540 ms)
BaseTapGestureRecognizer.handlePrimaryPointer            (2001.540 ms)
BaseTapGestureRecognizer._checkUp                        (2001.540 ms)
TapGestureRecognizer.handleTapUp                         (2001.540 ms)
GestureRecognizer.invokeCallback                         (2001.540 ms)
InkResponseState.handleTap (#2)                          (2001.540 ms)
InkResponseState.handleTap                               (2001.540 ms)
MyHomePageState._incrementCounter                        (2001.540 ms)
MyHomePageState._incrementCounter (#2)                   (2001.540 ms)
sleep                                                    (1977.250 ms)
ProcessUtils._sleep                                      (1977.250 ms)
stub CallAutoScopeNative                                 (1977.250 ms)
sleep                                                    (1969.110 ms)
ProcessUtils._sleep                                      (1969.110 ms)
stub CallBootstrapNative                                 (1969.110 ms)
```

## 这又完了？
现在什么最火？AI，无容置疑了。我们可以写一个AI Agent自动去做这件事，生成各种格式的报表，图，上报内部平台，自动创建工单。。。。。。

于是我们可以有这样一个流程

测试前开启btrace，测试完之后将perfetto文件交给AI Agent分析，让Agent去处理报表，创建工单。

## TL;DR
感谢btrace团队的无私奉献，让广大开发者受益。真心希望这个工具能一直维护下去。


### 参考
- https://perfetto.dev/docs/analysis/trace-processor-python
- https://github.com/bytedance/btrace

