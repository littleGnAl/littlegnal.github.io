---
title: Add Flutter to APP, Manage the FlutterEngine
date: 2020-03-01 20:48:42 +0800
---
## Motivation
随着Flutter v1.12.13发布，Flutter正式支持[Add-to-app](https://flutter.dev/docs/development/add-to-app)，相信有不少人使用该模式将Flutter集成到自己的项目里。打开一个Flutter页面很简单，如，Android中使用`startActivity(FlutterActivity.createDefaultIntent(this))`就可以打开Flutter页面，为了减少`FlutterEngine`初始化时间，一般会选择[pre-warm FlutterEngine](https://flutter.dev/docs/development/add-to-app/android/add-flutter-screen?tab=default-activity-launch-kotlin-tab#step-3-optional-use-a-cached-flutterengine)的方式。但是，当用户进入APP，至始至终都没有打开Flutter页面，`FlutterEngine`会一直存在内存中（如果对pre-warming `FlutterEngine`需要多少内存可以查看[官方的测试数据](https://flutter.dev/docs/development/add-to-app/performance#memory-and-latency)），造成内存浪费。更糟糕的情况，`FlutternEngine`一直存在内存中得不到回收，内存不足的时候甚至会发生OOM。

## 延迟创建`FlutterEngine`
为了解决pre-warm `FlutterEngine`可能会造成内存浪费的问题，可以在用户第一次打开Flutter页面时才创建`FlutterEngine`，将其缓存起来，减少用户再次打开Flutter页面时`FlutterEngine`的初始化时间。但是，延迟创建`FlutterEngine`会出现在第一个Flutter帧渲染出来前出现白屏的情况，为了优化用户体验可以为页面加上[Splash Screen](https://flutter.dev/docs/development/ui/splash-screen/android-splash-screen)。原理听上去很简单，接下来我们就来探讨如何在Android和iOS中实现（Android代码使用Kotlin实现，iOS代码使用Swift实现）。

### Android
在`FlutterActivity`/`FlutterFragment`中，都有`provideFlutterEngine`方法，用于让子类更容易的提供自定义的`FlutterEngine`，可以重写这个方法，来延迟创建并缓存`FlutterEngine`。下面以继承`FlutterFragment`为例(因为`FlutterFragment`还没有迁移到AndroidX，导致使用Kotlin实现会报错，所以这里使用Java来实现)。

```java
public class AddonFlutterFragment extends FlutterFragment {
  @Override
  public FlutterEngine provideFlutterEngine(@NotNull Context context) {
    FlutterEngine flutterEngine = super.provideFlutterEngine(context);
    if (flutterEngine != null) return flutterEngine;

    flutterEngine = FlutterEngineCache.getInstance().get("cache_engine");
    if (flutterEngine == null) {
      flutterEngine = new FlutterEngine(context.getApplicationContext());
      FlutterEngineCache.getInstance().put("cache_engine", flutterEngine);
    }

    return flutterEngine;
  }
}
```

接着实现自己的[Splash Screen](https://flutter.dev/docs/development/ui/splash-screen/android-splash-screen)即可，这里不再展开。

### iOS
由于`FlutterViewController`没有提供类似Android中`provideFlutterEngine`的方法（因为对OC语法不熟悉，所以这个结论可能存在错误，还请大家不吝指正），所以需要实现自己Container View Controller，先显示Splash Screen，然后创建并缓存`FlutterEngine`，再创建`FlutterViewController`。
```swift
@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {
  
  var flutterEngine: FlutterEngine
  
  func getFlutterEngine() -> FlutterEngine {
    if (flutterEngine == nil) {
      flutterEngine = FlutterEngine(name: "cache_engine")
    }
    
    return flutterEngine
  }
  
  ...
}

class AddonFlutterViewController: UIViewController {
    override func viewDidLoad() {
    super.viewDidLoad()
    let splashViewController = SplashViewControler()
    splashViewController!.willMove(toParent: self)
    addChild(splashViewController!)
    splashViewController!.view.frame = self.view.bounds
    view.addSubview(splashViewController!.view)
    splashViewController!.didMove(toParent: self)
    
    let engine = (UIApplication.shared.delegate as! AppDelegate)
        .getFlutterEngine()
    
    let flutterViewController = FlutterViewController(
      engine: engine,
      nibName: nil,
      bundle: nil)
    flutterViewController.setFlutterViewDidRenderCallback {
      [unowned self, splashViewController] in
      self.flutterViewDidRenderCallback?()
      
      if (splashViewController != nil) {
        UIView.animate(withDuration: 0.5, animations: {
          splashViewController!.view.alpha = 0
        }, completion: { (_) -> Void in
          splashViewController!.willMove(toParent: nil)
          splashViewController!.view.removeFromSuperview()
          splashViewController!.removeFromParent()
        })
      }
    }
    flutterViewController.willMove(toParent: self)
    addChild(flutterViewController)
    flutterViewController.view.frame = self.view.bounds
    view.addSubview(flutterViewController.view)
    flutterViewController.didMove(toParent: self)
  }
}
```

## 管理`FlutterEngine`
上面展示了如何在Android和iOS中实现延迟创建`FlutterEngine`。但在实际开发中需要处理从Flutter页面跳转Native页面，再从Native页面跳转Flutter页面的场景（Flutter -> Native -> Flutter），这是目前使用单个`FlutterEngine`（不使用第三方库）无法解决的。这种情况不能每个Flutter页面都创建并缓存`FlutterEngine`，因为如果用户打开多个Flutter页面，然后将Flutter页面都关闭后，之后用户只重新打开一个Flutter页面（例如，用户打开了3个Flutter页面，然后将3个页面都关闭，之后只打开1个Flutter页面），其他被缓存的`FlutterEngine`就造成浪费，而且内存也得不到释。但为了更好的用户体验，不能每次都创建“一次性”`FlutterEngine`（随着Flutter页面创建，随着Flutter页面销毁）。这便需要我们管理好`FlutterEngine`，允许设置可缓存`FlutterEngine`的数量，超过这个数量的Flutter页面都使用“一次性”`FlutterEngine`，以解决缓存太多`FlutterEngine`的问题。同时要允许内存紧张的时候将`FlutterEngine`回收掉。下面我们来实现自己的`FlutterEngine`管理类。

### 实现Flutter Engine Cache
在实现`FlutterEngine`管理类之前，我们需要先解决允许内存紧张的时候将`FlutterEngine`回收掉的问题。这里需要实现自己的Flutter Engine Cache。

#### Android
你可能已经熟悉`FlutterEngineCache`，但是它内部缓存`FlutterEngine`使用的是强引用，不能满足我们的要求，所以我们需要稍微做一些修改。~~打开`FlutterEngineCahce`文件，按下Ctrl + C，然后Ctrl + V~~借鉴`FlutterEngineCache`的实现，将`cachedEngines`类型改为`MutableMap<String, SoftReference<FlutterEngine>>`。

```kotlin
class AddonFlutterEngineCache {
  ...

  private val cachedEngines: MutableMap<String, SoftReference<FlutterEngine>> = mutableMapOf()

  fun contains(engineId: String): Boolean = cachedEngines.containsKey(engineId)

  fun get(engineId: String): FlutterEngine? = cachedEngines[engineId]?.get()

  ...
}
```

#### iOS
在iOS中，主要使用`NSCache`，逻辑与Android实现一致。
```swift
class AddonFlutterEngineCache {
  ... 

  private let cachedEngines = NSCache<NSString, FlutterEngine>()

  func contains(engineId: String) -> Bool {
    return cachedEngines.object(forKey: NSString(string: engineId)) != nil
  }

  func get(engineId: String) -> FlutterEngine? {
    return cachedEngines.object(forKey: NSString(string: engineId))
  }
}
```

### 实现`FlutterEngine`管理类
如前面所说，需要允许设置可缓存`FlutterEngine`的数量，如果超过这个数量就创建“一次性”的`FlutterEngine`。因此需要以栈（这里使用列表来模拟栈）的方式记录`FlutterEngine`的使用情况，创建新`FlutterEngine`的时候为其分配一个Id，并将该Id进栈，页面销毁的时将Id移出栈顶。

#### Android
```kotlin
class AddonFlutterEngineManager private constructor() {
  ...

  // 可缓存FlutterEngine数量
  var cacheFlutterEngineThreshold = 2

  private val activeEngines = mutableListOf<String>()

  fun getFlutterEngine(context: Context): FlutterEngine {
    val cachedEngineIds = AddonFlutterEngineCache.instance.getCachedEngineIds()
    val cachedEngineIdsSize = cachedEngineIds.size
    val activeEngineSize = activeEngines.size
    if (cachedEngineIds.isNotEmpty() && activeEngineSize < cachedEngineIdsSize) {
      val existEngineId = cachedEngineIds.first { key ->
        activeEngines.none { key == it }
      }

      var engine = AddonFlutterEngineCache.instance.get(existEngineId)
      if (engine == null) {
        engine = createFlutterEngine(context)
      }
      activeEngines.add(existEngineId)
      return engine
    }

    val flutterEngine: FlutterEngine
    val cacheEngineKey: String
    if (cachedEngineIdsSize < cacheFlutterEngineThreshold) {
      flutterEngine = createFlutterEngine(context)

      cacheEngineKey = "cache_engine_${cachedEngineIdsSize + 1}"
      AddonFlutterEngineCache.instance.put(cacheEngineKey, flutterEngine)
    } else {
      flutterEngine = createFlutterEngine(context)
      cacheEngineKey = "new_engine_${activeEngineSize - cachedEngineIdsSize + 1}"
    }

    activeEngines.add(cacheEngineKey)

    return flutterEngine
  }

  private fun createFlutterEngine(context: Context): FlutterEngine {
    return FlutterEngine(context.applicationContext).apply {
      navigationChannel.setInitialRoute("/")
    }
  }

  // 页面关闭时将栈顶FlutterEngine Id移除
  fun inactiveEngine() {
    if (activeEngines.isNotEmpty()) {
      activeEngines.removeAt(activeEngines.size - 1)
    }
  }
}
```

#### iOS
```swift
class AddonFlutterEngineManager {
  
  // 可缓存FlutterEngine数量
  var cacheFlutterEngineThreshold = 2
  
  private var activeEngines = [String]()
  
  func getFlutterEngine() -> FlutterEngine {
    let cachedEngineIds = AddonFlutterEngineCache.shared.getCachedEngineIds()
    let cachedEngineIdsSize = cachedEngineIds.count
    let activeEngineSize = activeEngines.count
    if (!cachedEngineIds.isEmpty && activeEngineSize < cachedEngineIdsSize) {
      let existEngineId = cachedEngineIds.first(where: { (key) -> Bool in
        return !activeEngines.contains {
          return $0 == key as String
        }
      })!
      
      var engine = AddonFlutterEngineCache.shared.get(engineId: existEngineId)
      if engine == nil {
        engine = createFlutterEngine(name: existEngineId)
      }
      activeEngines.append(existEngineId)
      
      return engine!
    }
    
    let flutterEngine: FlutterEngine
    let cacheEngineId: String
    if cachedEngineIdsSize < cacheFlutterEngineThreshold {
      cacheEngineId = "cache_engine_\(cachedEngineIdsSize + 1)"
      flutterEngine = createFlutterEngine(name: cacheEngineId)
      AddonFlutterEngineCache.shared.put(engineId: cacheEngineId, engine: flutterEngine)
    } else {
      cacheEngineId = "new_engine_\(activeEngineSize - cachedEngineIdsSize + 1)"
      flutterEngine = createFlutterEngine(name: cacheEngineId)
    }
    
    activeEngines.append(cacheEngineId)
    
    return flutterEngine
  }
  
  private func createFlutterEngine(name: String) -> FlutterEngine {
    let engine = FlutterEngine(name: name)
    engine.navigationChannel.invokeMethod("setInitialRoute", arguments:"/")
    engine.run()
    return engine
  }
  
  // 页面关闭时将栈顶FlutterEngine Id移除
  func inactiveEngine() {
    if !activeEngines.isEmpty {
      activeEngines.remove(at: activeEngines.count - 1)
    }
  }
}
```

### `FlutterEngine`间通信
由于`FlutterEngine`之间是隔离的，我们可以实现一个事件`MethodChannel`来跟不同的`FlutterEngine`之间通信。为每个`FlutterEngine`创建事件`MethodChannel`对象，发送事件时直接将事件名作为`MethodChannel#invokeMethod`的`method`参数值。

#### Android
```kotlin
class AddonEngineEventChannel(
  messenger: BinaryMessenger,
  eventCallback: (eventName: String, arguments: Any?) -> Boolean
) {

  private val eventChannel = MethodChannel(messenger, "custom_channels/native_event").apply {
    setMethodCallHandler { call, result ->
      result.success(eventCallback(call.method, call.arguments))
    }
  }

  fun sendEvent(eventName: String, arguments: Any?) {
    eventChannel.invokeMethod(eventName, arguments)
  }
}
```

#### iOS
```swift
class AddonEngineEventChannel {
  private let eventChannel: FlutterMethodChannel
  
  init(
    messenger: FlutterBinaryMessenger,
    eventCallback: @escaping (_ eventName: String, _ arguments: Any?) -> Bool
  ) {
    eventChannel = FlutterMethodChannel(
      name: "custom_channels/native_event",
      binaryMessenger: messenger)
    eventChannel.setMethodCallHandler { call, result in
      result(eventCallback(call.method, call.arguments))
    }
  }
  
  func sendEvent(eventName: String, arguments: Any?) {
    eventChannel.invokeMethod(eventName, arguments: arguments)
  }
}
```

在前面`AddonFlutterEngineManager`代码的基础上，我们多加一个`eventChannels`列表，用于存储事件`AddonEngineEventChannel`。同样，页面被关闭时，将栈顶`AddonEngineEventChannel`移除，但不移除已缓存的`FlutterEngine`对应的`AddonEngineEventChannel`。

#### Android
```kotlin
class AddonFlutterEngineManager private constructor() {
  ...

  private val activeEngines = mutableListOf<String>()
  private val eventChannels = mutableListOf<Pair<String, AddonEngineEventChannel>>()

  fun getFlutterEngine(context: Context): FlutterEngine {
    ...

    val flutterEngine: FlutterEngine
    val cacheEngineKey: String
    if (cachedEngineIdsSize < cacheFlutterEngineThreshold) {
      flutterEngine = createFlutterEngine(context)

      cacheEngineKey = "cache_engine_${cachedEngineIdsSize + 1}"
      AddonFlutterEngineCache.instance.put(cacheEngineKey, flutterEngine)
    } else {
      flutterEngine = createFlutterEngine(context)
      cacheEngineKey = "new_engine_${activeEngineSize - cachedEngineIdsSize + 1}"
    }

    val eventChannel =
      AddonEngineEventChannel(
        flutterEngine.dartExecutor
      ) { eventName, arguments ->
        eventChannels.asSequence()
          .filter { (key, _) -> key != cacheEngineKey }
          .forEach { (_, eventChannel) ->
            eventChannel.sendEvent(eventName, arguments)
          }

        true
      }
    eventChannels.add(cacheEngineKey to eventChannel)

    activeEngines.add(cacheEngineKey)

    return flutterEngine
  }

  // 页面关闭时将栈顶FlutterEngine Id移除
  fun inactiveEngine() {
    if (activeEngines.isNotEmpty()) {
      val cachedEngineIds = AddonFlutterEngineCache.instance.getCachedEngineIds()
      val key = activeEngines.last()
      val removeEventChannelIndex = eventChannels.indexOfLast { (k, _) ->
        !cachedEngineIds.contains(key) && k == key
      }
      if (removeEventChannelIndex != -1) {
        eventChannels.removeAt(removeEventChannelIndex)
      }
      activeEngines.removeAt(activeEngines.size - 1)
    }
  }
}
```

#### iOS
```swift
class AddonFlutterEngineManager {
  ...
  
  private var activeEngines = [String]()
  private var eventChannels = [(String, AddonEngineEventChannel)]()
  
  func getFlutterEngine() -> FlutterEngine {
    ...
    
    let flutterEngine: FlutterEngine
    let cacheEngineId: String
    if cachedEngineIdsSize < cacheFlutterEngineThreshold {
      cacheEngineId = "cache_engine_\(cachedEngineIdsSize + 1)"
      flutterEngine = createFlutterEngine(name: cacheEngineId)
      AddonFlutterEngineCache.shared.put(engineId: cacheEngineId, engine: flutterEngine)
    } else {
      cacheEngineId = "new_engine_\(activeEngineSize - cachedEngineIdsSize + 1)"
      flutterEngine = createFlutterEngine(name: cacheEngineId)
    }
    
    let eventChannel = AddonEngineEventChannel(
      messenger: flutterEngine.binaryMessenger,
      eventCallback: { [unowned self] (eventName, arguments) -> Bool in
        self.eventChannels
          .filter { (key, _) in key != cacheEngineId }
          .forEach { (_, eventChannel: AddonEngineEventChannel) in
            eventChannel.sendEvent(eventName: eventName, arguments: arguments)
        }

        return true
    })
    eventChannels.append((cacheEngineId, eventChannel))

    activeEngines.append(cacheEngineId)
    
    return flutterEngine
  }
  
  ...
  
  // 页面关闭时将栈顶FlutterEngine Id移除
  func inactiveEngine() {
    if !activeEngines.isEmpty {
      let cachedEngineIds = AddonFlutterEngineCache.shared.getCachedEngineIds()
      let key = activeEngines.last!
      let removeEventChannelIndex = eventChannels.lastIndex { (k, _) -> Bool in
        !cachedEngineIds.contains(key) && k == key
      } ?? -1
      if removeEventChannelIndex != -1 {
        eventChannels.remove(at: removeEventChannelIndex)
      }
      
      activeEngines.remove(at: activeEngines.count - 1)
    }
  }
}
```

## TL;DR
以上，是个人对于将Flutter集成到现有APP，不使用hack的方式来管理`FlutterEngine`的一些想法和解决方案，希望对你有帮助。如有不正确的地方麻烦大佬们指正。本文[demo](https://github.com/littleGnAl/flutter-embedding-addon/tree/blog-manage-flutterengine)已经上传GitHub，欢迎clone，欢迎star。