---
layout: post
title:  "从状态管理(State Manage)到MVI（Model-View-Intent）"
date: 2018-01-22 17:45:33 +0800
---

什么是状态？界面上展示给用户的都是一种状态，如loading显示，error信息显示，列表展示等。这是日常开发中必然会遇到的，本文将讲解如何用更有效的方式来进行状态管理，提高代码的可读性，可维护性，健壮性。。。。。。文章中代码示例比较多，但是别慌，逻辑都比较简单，稳住就行。文章代码使用kotlin实现，关于状态管理部分示例代码使用`MVP` + `RxJava`模式来编写。

## 关于状态管理
假设我们有这样一个需求：在输入框输入用户名，点击保存按钮把用户保存到数据库。在保存数据库之前，显示loading状态，然后把保存按钮设置为不可点击，保存数据库需要异步操作，最后在成功的时候隐藏loading状态并且把保存按钮设置为可点击，若发生错误，需要隐藏loading状态，把保存按钮设置为可点击状态，然后显示错误信息。Show you the code：
```kotlin
class MainPresenter constructor(
    private val service: UserService,
    private val view: MainView,
    private val disposables: CompositeDisposable
) : Presenter {

  val setUserSubject = PublishSubject.create<String>()
  
  init {
    disposables.add(
        setUserSubject
            .doOnNext {
              view.showLoading()
              view.setButtonUnable()
            }
            .flatMap { service.setUser(it) }
            .subscribeOn(Schedulers.io())
            .observeOn(AndroidSchedulers.mainThread())
            .subscribe(
                {
                  view.hideLoading()
                  view.setButtonEnable()
                },
                {
                  view.hideLoading()
                  view.setButtonEnable()
                  view.showError(it.message.toString())
                }
            ))
  }

  override fun setUser(userName: String) {
    setUserSubject.onNext(userName)
  }
}
```
这段代码看上去不怎么优雅，但已经实现了我们的需求了。简单画下流程图：
![setUser流程](https://raw.githubusercontent.com/littleGnAl/Accounting/master/art/setuser.png)

可以看到当保存数据库操作前调用`view.showLoading()`和`view.setButtonUnable()`，当操作成功或者错误的时候调用`view.hideLoading()`和`view.setButtonEnable()`，像这种“配套”方法越来越多的时候就很容易会疏忽，出现忘记隐藏loading状态，忘记把按钮设置为可点击等问题。在这简单例子你可能会觉得没什么，实际开发的时候一定会记得调用相应的方法，这不同于注册接口监听，一般我们会在`Activity#onCreate()`的时候注册监听，在`Activity#onDestroy()`取消监听，但我们在**View**里可以有很多地方调用**Presenter**的方法，如`setUser() `，我们认为调用**Presenter**方法是一种输入，同时**Presenter**也有很多地方输出状态给**View**，如`view.showLoading()`，`view.showError()`等。我们不能确定`setUser()`方法在哪里被调用，`view.showLoading()`方法在哪里被调用，假设我们还有其他方法在同时执行：
![多个方法调用流程](https://github.com/littleGnAl/Accounting/blob/master/art/multi-methods.png?raw=true)

这很容易会造成状态混乱，例如loading状态和错误信息同时出现，当错误信息显示的时候保存按钮没有恢复可点击状态等，在实际的业务中，这种问题尤其明显。

### 响应式状态（Reative State）
我们能不能限制**Presenter**只有一个输入，状态只从一个地方输出呢？我们借助`PublishSubject`作为桥接（如上面代码片段`setUserSubject`），然后通过`Observable.merge()`把它们合并成一个流，来实现只有一个地方输入。下面我们主要看看我们如何实现状态只从一个地方输出。

引用面向对象编程一句经典的话：*万物皆对象*。用户输入用户名，点击保存按钮，这是一个事件，我们把它看成一个事件对象`SetUserEvent`，把UI状态作为一个状态对象（`SetUserState`），同时状态是对界面的描述。于是我们在把事件作为输入（`SetUserEvent`），输出状态（`SetUserState`），**View**只需要根据状态`SetUserState`的信息（如loading，显示错误信息）来展示界面就可以了：
![用户输入-状态](https://github.com/littleGnAl/Accounting/blob/master/art/event-state.png?raw=true)

可以看到这是一条单向的“流”，而且是循环的，**View**把用户事件输出到**Presenter**，接收状态展示界面；**Presenter**对**View**的事件输入进行处理，输出状态。接下来看看如何用代码实现。

首先定义界面状态`SetUserState`:

```kotlin
data class SetUserState(
    val isLoading: Boolean, // 是否在加载
    val isSuccess: Boolean, // 是否成功
    val error: String? // 错误信息
) {
  companion object {

    fun inProgress() = SetUserState(isLoading = true, isSuccess = false, error = null)
    
    fun success() = SetUserState(isLoading = false, isSuccess = true, error = null)
    
    fun failure(error: String) = SetUserState(isLoading = false, isSuccess = false, error = error)
  }
} 
```
这里定义了3个方法，用于表示正在加载状态，成功状态和失败状态。接下来对保存数据库操作进行重写：
```kotlin
  ...

  val setUserSubject = PublishSubject.create<SetUserEvent>()

  init {
    disposables.add(
        setUserSubject.flatMap {
          service.setUser(it.userName)
              .map { SetUserState.success() }
              .onErrorReturn { SetUserState.failure(it.message.toString()) }
              .subscribeOn(Schedulers.io())
              .observeOn(AndroidSchedulers.mainThread())
              .startWith(SetUserState.inProgress())
        }
        .subscribe { setUserState ->
          if (setUserState.isLoading) {
            view.showLoading()
            view.setButtonUnable()
            return@subscribe
          }

          view.hideLoading()
          view.setButtonEnable()
          if (setUserState.isSuccess) {
            // do something...
          } else {
            setUserState.error?.apply { view.showError(this) }
          }
        })
  }

  override fun setUser(setUserEvent: SetUserEvent) {
    setUserSubject.onNext(setUserEvent)
  }
```
修改的核心部分是`flatMap`里的内部`Observable`:
```kotlin
service.setUser(it.userName)
    .map { SetUserState.success() }
    .onErrorReturn { SetUserState.failure(it.message.toString()) }
    .subscribeOn(Schedulers.io())
    .observeOn(AndroidSchedulers.mainThread())
    .startWith(SetUserState.inProgress())
```
在这个内部`Observable`里，把事件转换为`SetUserState`状态并输出。这个`Observable`在执行时，会先输出loading状态（`startWith(SetUserState.inProgress())`）；当`service.setUser(it.userName)`成功后输出成功状态（`map { SetUserState.success() }`）；当错误时输出错误状态，错误状态中包括错误信息（`onErrorReturn { SetUserState.failure(it.message.toString()) }`）。可以看到，我们不需要关心UI，不需要关心什么时候调用`view.showLoading()`显示loading状态，不需要关心什么时候调用`view.hideLoading()`隐藏loading状态，在`subscribe()`中根据`SetUserState`状态展示界面就可以了。为了方便单元测试和重用，把这部分拆分出来：
```kotlin
  ...

  private val setUserTransformer = ObservableTransformer<SetUserEvent, SetUserState> {
    event -> event.flatMap {
      service.setUser(it.userName)
          .map { SetUserState.success() }
          .onErrorReturn { SetUserState.failure(it.message.toString()) }
          .subscribeOn(Schedulers.io())
          .observeOn(AndroidSchedulers.mainThread())
          .startWith(SetUserState.inProgress())
    }
  }

  init {
    disposables.add(
        setUserSubject.compose(setUserTransformer)
            .subscribe { setUserState ->
              if (setUserState.isLoading) {
                view.showLoading()
                view.setButtonUnable()
                return@subscribe
              }

              view.hideLoading()
              view.setButtonEnable()
              if (setUserState.isSuccess) {
                // do something...
              } else {
                setUserState.error?.apply { view.showError(this) }
              }
            })
  }

  ...
```
一般情况下都会有很多输入，如上拉加载下一页，下拉刷新等。现假设需要添加一个`checkUser()`方法，用于查询用户是否存在，要把不同输入合并，我们需要定义一个公共的父类`UIEvent`，让每个输入都继承该父类：
```kotlin
sealed class UIEvent {

  data class SetUserEvent(val userName: String) : UIEvent()

  data class CheckUserEvent(val userName: String) : UIEvent()
}
```
下面是**Presenter**的实现：

```kotlin
class MainPresenter(
    private val service: UserService,
    private val view: MainView,
    private val disposables: CompositeDisposable
) : Presenter {

  val setUserSubject = PublishSubject.create<UIEvent.SetUserEvent>()

  val checkUserSubject = PublishSubject.create<UIEvent.CheckUserEvent>()

  private val setUserTransformer = ObservableTransformer<UIEvent.SetUserEvent, UIState> {
    event -> event.flatMap {
      service.setUser(it.userName)
          .map { UIState.success() }
          .onErrorReturn { UIState.failure(it.message.toString()) }
          .subscribeOn(Schedulers.io())
          .observeOn(AndroidSchedulers.mainThread())
          .startWith(UIState.inProgress())
    }
  }

  private val checkUserTransformer = ObservableTransformer<UIEvent.CheckUserEvent, UIState> {
    event -> event.flatMap {
      service.checkUser(it.userName)
          .map { UIState.success() }
          .onErrorReturn { UIState.failure(it.message.toString()) }
          .subscribeOn(Schedulers.io())
          .observeOn(AndroidSchedulers.mainThread())
          .startWith(UIState.inProgress())
    }
  }

  private val transformers = ObservableTransformer<UIEvent, UIState> {
    events -> events.publish { shared ->
      Observable.merge(
          shared.ofType(UIEvent.SetUserEvent::class.java).compose(setUserTransformer),
          shared.ofType(UIEvent.CheckUserEvent::class.java).compose(checkUserTransformer))
    }
  }

  init {
    val allEvents: Observable<UIEvent> = Observable.merge(setUserSubject, checkUserSubject)

    disposables.add(
        allEvents.compose(transformers)
            .subscribe { setUserState ->
              if (setUserState.isLoading) {
                view.showLoading()
                view.setButtonUnable()
                return@subscribe
              }

              view.hideLoading()
              view.setButtonEnable()
              if (setUserState.isSuccess) {
                // do something...
              } else {
                setUserState.error?.apply { view.showError(this) }
              }
            })
  }

  override fun setUser(setUserEvent: UIEvent.SetUserEvent) {
    setUserSubject.onNext(setUserEvent)
  }

  override fun checkUser(checkUserEvent: UIEvent.CheckUserEvent) {
    checkUserSubject.onNext(checkUserEvent)
  }
}
```
如前面提到的，我们使用`Observable.merge()`对输入事件进行合并：
```kotlin
val allEvents: Observable<UIEvent> = Observable.merge(setUserSubject, checkUserSubject)
```
然后按照前面的套路，定义`checkUserTransformer`。这部分代码需要注意的是`transformers`属性的实现：
```kotlin
  private val transformers = ObservableTransformer<UIEvent, UIState> {
    events -> events.publish { shared ->
      Observable.merge(
          shared.ofType(UIEvent.SetUserEvent::class.java).compose(setUserTransformer),
          shared.ofType(UIEvent.CheckUserEvent::class.java).compose(checkUserTransformer))
    }
  }
```
为了让不同的事件输入组合不同的业务逻辑，这里把合并的输入拆分，然后对不同的输入组合不同的业务逻辑，最后再重新合并成一个流：
![publish拆分-merge合并](https://github.com/littleGnAl/Accounting/blob/master/art/events-publish.png?raw=true)

这样做的好处是每个事件输入做自己的事而不影响到其他。现在回过头来整个流程，我们已经实现了一个循环单向的流：

![用户输入-状态](https://github.com/littleGnAl/Accounting/blob/master/art/event-state2.png?raw=true)

但细心的你会发现，左侧逻辑部分跟**View**耦合了，事实上逻辑部分不应该关心用户的输入事件（`UIEvent`）是什么，也不应该关心界面（`UIState`）该怎么展示，这还会导致该部分无法重用。为了把这部分解耦出来，我们多加一层转换：

![增加Action-Result转换](https://github.com/littleGnAl/Accounting/blob/master/art/action-result.png?raw=true)

逻辑部分只关心`Action`和`Result`，不与**View**耦合。`Result`并不关心界面状态，只是某个`Action`的结果，前面说过状态是对界面的描述，**View**根据状态来展示相应的界面，如果我们每次创建一个新的状态就相当于把界面重置了，所以我们需要知道上一次的状态，来做相应的调整，如开始状态`UIState.isLoading = true`，成功后我们只需要`UIState.isLoading = false`就可以了，借助RxJava的`scan()`来实现这一点：
```kotlin
sealed class Action {

  data class SetUserAction(val userName: String) : Action()

  data class CheckUserAction(val userName: String) : Action()
}
```
```kotlin
sealed class Result {

  data class SetUserResult(
      val isLoading: Boolean,
      val isSuccess: Boolean,
      val error: String?
  ) : Result() {
    companion object {
      fun inProgress() = SetUserResult(isLoading = true, isSuccess = false, error = null)

      fun success() = SetUserResult(isLoading = false, isSuccess = true, error = null)

      fun failure(error: String) = SetUserResult(
          isLoading = false,
          isSuccess = false,
          error = error)
    }
  }

  data class CheckNameResult(
      val isLoading: Boolean,
      val isSuccess: Boolean,
      val error: String?
  ) : Result() {
    companion object {
      fun inProgress() = CheckNameResult(isLoading = true, isSuccess = false, error = null)

      fun success() = CheckNameResult(isLoading = false, isSuccess = true, error = null)

      fun failure(error: String) = CheckNameResult(
          isLoading = false,
          isSuccess = false,
          error = error)
    }
  }
}
```
```kotlin
data class UIState(val isLoading: Boolean, val isSuccess: Boolean, val error: String?) {
  companion object {
    fun idle() = UIState(isLoading = false, isSuccess = false, error = null)
  }
}
```
```kotlin
  ...

  private val setUserTransformer = ObservableTransformer<Action.SetUserAction, Result.SetUserResult> {
    event -> event.flatMap {
      service.setUser(it.userName)
          .map { Result.SetUserResult.success() }
          .onErrorReturn { Result.SetUserResult.failure(it.message.toString()) }
          .subscribeOn(Schedulers.io())
          .observeOn(AndroidSchedulers.mainThread())
          .startWith(Result.SetUserResult.inProgress())
    }
  }

  private val checkUserTransformer = ObservableTransformer<Action.CheckUserAction, Result.CheckNameResult> {
    event -> event.flatMap {
      service.checkUser(it.userName)
          .map { Result.CheckNameResult.success() }
          .onErrorReturn { Result.CheckNameResult.failure(it.message.toString()) }
          .subscribeOn(Schedulers.io())
          .observeOn(AndroidSchedulers.mainThread())
          .startWith(Result.CheckNameResult.inProgress())
    }
  }

  private val transformers = ObservableTransformer<Action, Result> {
    events -> events.publish { shared ->
      Observable.merge(
          shared.ofType(Action.SetUserAction::class.java).compose(setUserTransformer),
          shared.ofType(Action.CheckUserAction::class.java).compose(checkUserTransformer))
    }
  }

  init {
    val setUserAction = setUserSubject.map { Action.SetUserAction(it.userName) }
    val checkUserAction = checkUserSubject.map { Action.CheckUserAction(it.userName) }
    val allActions: Observable<Action> = Observable.merge(setUserAction, checkUserAction)

    disposables.add(
        allActions.compose(transformers)
            .scan(UIState.idle(),
                { previousState, result ->
                  when(result) {
                    is Result.SetUserResult -> {
                      previousState.copy(
                          isLoading = result.isLoading,
                          isSuccess =  result.isSuccess,
                          error =  result.error)
                    }
                    is Result.CheckNameResult -> {
                      previousState.copy(
                          isLoading = result.isLoading,
                          isSuccess =  result.isSuccess,
                          error =  result.error)
                    }
                  }
                })
            .subscribe { ... })
  }

  ...
```
代码比较多，但逻辑应该算比较清晰，把`setUserTransformer`及`checkUserTransformer`属性的输入和输出对象调整为`Action`和`Result`，在`scan()`方法里根据上一次的状态和当前的结果`Result`来组合新的状态。

至此，我们简单的了解了状态管理是如何实现的，接下来我们基于状态管理的知识来讲解**MVI**模式。

## MVI（Model-View-Intent）
### 什么是MVI
简单概括为：单向流(unidirectional flow)，数据流不可变（immutability）(关于不可变Model的优缺点网上已经很多，可自行百度或者查看[该文章](https://www.quora.com/What-are-the-advantages-and-disadvantages-of-immutable-data-structures))，响应式的，接收用户输入，通过函数转换为特定Model（状态），将其结果反馈给用户（渲染界面）。把**MVI**抽象为**model()**, **view()**, **intent()**三个方法，描述如下：

![MVI示意图](https://upload-images.jianshu.io/upload_images/8666477-804fa3042a4d31d8.png)

* **intent()**:中文意思为**意图**，将用户操作（如触摸，点击，滑动等）作为数据流的输入，传递给**model()**方法。
* **model()**: **model()**方法把**intent()**方法的输出作为输入来创建Model（状态），传递给**view()**。
* **view()**: **view()**方法把**model()**方法的输出的Model（状态）作为输入，根据Model（状态）的结果来展示界面。

你会发现，这跟前面所说的状态管理描述的如出一辙，下面稍微详细的描述一下**MVI**模式：

![mvi-detail](https://raw.githubusercontent.com/oldergod/android-architecture/todo-mvi-rxjava-kotlin/art/MVI_detail.png)

我们使用**ViewModel**来解耦业务逻辑，接收**Intent**（用户意图）并返回**State**（状态），其中**Processor**用于处理业务逻辑，如前面的拆分出来`setUserTransformer`和`checkUserTransformer`属性。
**View**只暴露2个方法：
```kotlin
interface MviView<I : MviIntent, in S : MviViewState> {
  
  fun intents(): Observable<I>

  fun render(state: S)
}
```
* 将用户意图传递给**ViewModel**
* 订阅**ViewModel**输出的状态用于展示界面

同时**ViewModel**也只暴露2个方法：
```kotlin
interface MviViewModel<I : MviIntent, S : MviViewState> {
  fun processIntents(intents: Observable<I>)

  fun states(): Observable<S>
}
```
* 处理**View**传递过来的用户意图
* 输出状态给**View**，用于渲染界面

需要说明的是，**ViewModel**会缓存最新的状态，当`Activity/Fragment`配置发生改变时（如屏幕旋转），我们不应该重新创建
**ViewModel**，而是使用缓存的状态来直接渲染界面，这里使用google的[Architecture Components library](https://developer.android.com/topic/libraries/architecture/viewmodel.html)的来实现**ViewModel**，方便生命周期的管理。

关于**MVI**的代码实现可以参考状态管理部分，下面是我写的demo中汇总页的效果，这个页面只有2个意图，1)初始化意图`InitialIntent`，2)点击曲线点切换月份意图`SwitchMonthIntent`。

![SummaryActivity](https://github.com/littleGnAl/Accounting/blob/master/art/SummaryActivity.gif?raw=true)

这里给出部分代码实现：

```kotlin
data class SummaryViewState(
    val isLoading: Boolean, // 是否正在加载
    val error: Throwable?, // 错误信息
    val points: List<Pair<Int, Float>>, // 曲线图点
    val months: List<Pair<String, Date>>, // 曲线图月份
    val values: List<String>, // 曲线图数值文本
    val selectedIndex: Int, // 曲线图选中月份索引
    val summaryItemList: List<SummaryListItem>, // 当月标签汇总列表
    val isSwitchMonth: Boolean // 是否切换月份
) : MviViewState {
  companion object {

    /**
     * 初始[SummaryViewState]用于Reducer
     */
    fun idle() = SummaryViewState(false, null, listOf(), listOf(), listOf(), 0, listOf(), false)
  }
}
```

```kotlin
class SummaryActivity : BaseActivity(), MviView<SummaryIntent, SummaryViewState> {

  @Inject lateinit var viewModelFactory: ViewModelProvider.Factory
  private lateinit var summaryViewModel: SummaryViewModel

  private val disposables = CompositeDisposable()

  ...

  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    
    ...

    bind()
  }

  private fun bind() {
    summaryViewModel = ViewModelProviders.of(this, viewModelFactory)
        .get(SummaryViewModel::class.java)

    // 订阅render方法根据发送过来的state渲染界面
    disposables += summaryViewModel.states().subscribe(this::render)
    // 传递UI的intents给ViewModel
    summaryViewModel.processIntents(intents())
  }

  private fun initialIntent(): Observable<SummaryIntent> { ... }

  private fun switchMonthIntent(): Observable<SummaryIntent> { ... }

  override fun render(state: SummaryViewState) { ... }

  override fun intents(): Observable<SummaryIntent> {
    return Observable.merge(initialIntent(), switchMonthIntent())
  }

  ...
}
```

```kotlin
class SummaryViewModel @Inject constructor(
    private val summaryActionProcessorHolder: SummaryActionProcessorHolder
) : BaseViewModel<SummaryIntent, SummaryViewState>() {

  override fun compose(intentsSubject: PublishSubject<SummaryIntent>):
      Observable<SummaryViewState> =
      intentsSubject
          .compose(intentFilter)
          .map(this::actionFromIntent)
          .compose(summaryActionProcessorHolder.actionProcessor)
          .scan(SummaryViewState.idle(), reducer)
          .replay(1)
          .autoConnect(0)

  /**
   * 只取一次初始化[MviIntent]和其他[MviIntent]，过滤掉配置改变（如屏幕旋转）后重新传递过来的初始化
   * [MviIntent]，导致重新加载数据
   */
  private val intentFilter: ObservableTransformer<SummaryIntent, SummaryIntent> =
      ObservableTransformer { intents -> intents.publish { shared ->
          Observable.merge(
              shared.ofType(SummaryIntent.InitialIntent::class.java).take(1),
              shared.filter { it !is SummaryIntent.InitialIntent }
          )
        }
      }

  /**
   * 把[MviIntent]转换为[MviAction]
   */
  private fun actionFromIntent(summaryIntent: SummaryIntent): SummaryAction =
      when(summaryIntent) {
        is SummaryIntent.InitialIntent -> {
          SummaryAction.InitialAction()
        }
        is SummaryIntent.SwitchMonthIntent -> {
          SummaryAction.SwitchMonthAction(summaryIntent.date)
        }
      }

  private val reducer = BiFunction<SummaryViewState, SummaryResult, SummaryViewState> {
        previousState, result ->
          when(result) {
            is SummaryResult.InitialResult -> {
              when(result.status) {
                LceStatus.SUCCESS -> {
                  previousState.copy(
                      isLoading = false,
                      error = null,
                      points = result.points,
                      months = result.months,
                      values = result.values,
                      selectedIndex = result.selectedIndex,
                      summaryItemList = result.summaryItemList,
                      isSwitchMonth = false)
                }
                LceStatus.FAILURE -> {
                  previousState.copy(isLoading = false, error = result.error)
                }
                LceStatus.IN_FLIGHT -> {
                  previousState.copy(isLoading = true, error = null)
                }
              }
            }
            is SummaryResult.SwitchMonthResult -> {
              when(result.status) {
                LceStatus.SUCCESS -> {
                  previousState.copy(
                      isLoading = false,
                      error = null,
                      summaryItemList = result.summaryItemList,
                      isSwitchMonth = true)
                }
                LceStatus.FAILURE -> {
                  previousState.copy(
                      isLoading = false,
                      error = result.error,
                      isSwitchMonth = true)
                }
                LceStatus.IN_FLIGHT -> {
                  previousState.copy(
                      isLoading = true,
                      error = null,
                      isSwitchMonth = true)
                }
              }
            }
          }
      }

}
```

```kotlin
class SummaryActionProcessorHolder(
    private val schedulerProvider: BaseSchedulerProvider,
    private val applicationContext: Context,
    private val accountingDao: AccountingDao) {

  ...

  private val initialProcessor =
      ObservableTransformer<SummaryAction.InitialAction, SummaryResult.InitialResult> {
        actions -> actions.flatMap { ... }
      }


  private val switchMonthProcessor =
      ObservableTransformer<SummaryAction.SwitchMonthAction, SummaryResult.SwitchMonthResult> {
        actions -> actions.flatMap { ... }
      }

  /**
   * 拆分[Observable<MviAction>]并且为不同的[MviAction]提供相应的processor，processor用于处理业务逻辑，
   * 同时把[MviAction]转换为[MviResult]，最终通过[Observable.merge]合并回一个流
   *
   * 为了防止遗漏[MviAction]未处理，在流的最后合并一个错误检测，方便维护
   */
  val actionProcessor: ObservableTransformer<SummaryAction, SummaryResult> =
      ObservableTransformer { actions -> actions.publish {
          shared -> Observable.merge(
            shared.ofType(SummaryAction.InitialAction::class.java)
                .compose(initialProcessor),
            shared.ofType(SummaryAction.SwitchMonthAction::class.java)
                .compose(switchMonthProcessor))
          .mergeWith(shared.filter {
                it !is SummaryAction.InitialAction &&
                    it !is SummaryAction.SwitchMonthAction
              }
              .flatMap {
                Observable.error<SummaryResult>(
                    IllegalArgumentException("Unknown Action type: $it"))
              })
        }
      }
}
```

这里不帖过多的代码了，感兴趣的兄弟可以查看我写的[demo（一个简单的增删改记帐app）](https://github.com/littleGnAl/Accounting)，演示了如何用状态管理的方式实现**MVI**，逻辑比较简单。

### 测试
编写单元测试的时候，我们只需要提供用户意图，借助RxJava的`TestObserver`，测试输出的状态是否符合我们预期的状态就可以了，如下面代码片段：
```kotlin
summaryViewModel.processIntents(SummaryIntent.InitialIntent())
testObserver.assertValueAt(2, SummaryViewState(...))
```
这消除了很多我们用**MVP**时对**View**的验证测试，如`Mockito.verify(view，times(1)).showFoo()`，因为我们不必处理实际代码的实现细节，使得单元测试的代码更具可读性，可理解性和可维护性。总所周知，在Android中UI测试是一件很头大的事，但状态是界面的描述，按照状态来展示界面，对界面显示正确性也有所帮助，但是要保证界面显示正确性，还是需要编写UI测试代码。

## 总结
文章花了很大的篇幅介绍状态管理（其实就是代码比较多），因为状态管理理解了，**MVI**也理解了。强烈建议大家看下[Jake Wharton关于状态管理的演讲](https://www.youtube.com/watch?v=0IKHxjkgop4)（youtube），和[Hannes Dorfmann’s 关于MVI的系列博客](http://hannesdorfmann.com/android/mosby3-mvi-1)。感谢您阅读本文，希望对您有帮助。本文的[demo](https://github.com/littleGnAl/Accounting) 已上传到github，如果对本文有疑问，或者哪里说得不对的地方，欢迎在[github上实锤](https://github.com/littleGnAl/Accounting/issues)。

## 参考
[Managing State with RxJava by Jake Wharton](https://www.youtube.com/watch?v=0IKHxjkgop4)  
[github TODO-MVI-RxJava](https://github.com/oldergod/android-architecture)   
[REACTIVE APPS WITH MODEL-VIEW-INTENT PART 1 - 7](http://hannesdorfmann.com/android/mosby3-mvi-1)
