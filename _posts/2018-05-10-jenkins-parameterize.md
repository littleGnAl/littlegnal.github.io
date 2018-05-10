---
title: Android Jenkins参数化配置
date: 2018-05-10 12:12:33 +0800
---
在我们的项目组里，构建Jenkins打包平台的初衷是让测试人员用这个打包平台，开发人员写完提测邮件之后，测试人员自行去打包，然后进行测试，开发就可以继续去开车了。

### Jenkins安装
本文不打算写手把手安装Jenkins教程，如果你还不了解怎么安装Jenkins，请自行百度，或者查看这里的官网教程: [https://pkg.jenkins.io/redhat/](https://pkg.jenkins.io/redhat/)。

### Jenkins参数化配置
Jenkins参数化配置主要有2个步骤：

* 在`gradle.properties`中配置需要动态修改的参数，并在`build.gradle`中使用。
* 在Jenkins中添加这些参数，进行参数化构建。

一般我们需要动态修改的参数有versionName、versionCode，是否测试环境等，同时我们可以提供一些额外配置，如选择需要构建的分支，打包的渠道号等，以提高打包灵活性。我们把需要Jenkins修改的参数放到`gradle.properties`文件下，如：
```gradle
# Jenkins配置
IS_JENKINS=false
VERSION_NAME=3.4
VERSION_CODE=30400002
IS_TEST_ENV=true
```

接下来就是重点了。我们在新建任务的时候选择“**构建一个自由风格的软件项目**”
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/choose-job.png" height="80%" width="80%">

接下来选择“参数化构建过程”添加参数配置：

<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/parameter-is-jenkins.png" height="80%" width="80%">
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/parameter-version-name.png" height="80%" width="80%">
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/parameter-version-code.png" height="80%" width="80%">
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/parameter-is-test-env.png" height="80%" width="80%">
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/parameter-banch.png" height="80%" width="80%">
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/parameter-build-types.png" height="80%" width="80%">
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/parameter-product-flavor.png" height="80%" width="80%">
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/parameter-pgyer-api-key.png" height="80%" width="80%">
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/parameter-pgyer-apk-pwd.png" height="80%" width="80%">

#### Git服务器
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/git-configuration.png" height="80%" width="80%">

可以看到在构建分支里我们使用了上面的`BRANCH`参数，这样我们就可以动态的选择需要构建的分支了。

#### Gradle构建
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/gradle-configuration.png" height="80%" width="80%">

** 这里最重要的地方就是标记部分，只有勾选该选项，`gradle.properties`的参数才能被Jenkins修改。**

如果你在github上下载过Android代码，你会发现一般项目中都会保留`gradle wrapper`文件夹，这样做的好处是升级gradle版本的时候不需要更新ci，这里我们也一样，勾选“**Use Gradle Wrapper**”，然后添加你需要的tasks，这里需要说明一下的是`assemble'${PRODUCT_FLAVORS}''${BUILD_TYPES}'`，如果你平时打包的时候有留意过gradle执行的task的时候你会发现gradle为每个`productFlavors`创建2个task，一个是debug版本的，一个是release版本的。利用这个规则我们就可以使用参数动态改变task了。这里有一个取巧的地方，细心的你会发现`PRODUCT_FLAVORS`第一个选项是空的，当选择该选项时，task的名称就变成`assemblerelease`或者`assembledebug`了，这种情况下就会打全渠道包，注意这里不能把空放在最后一个选项，放在最后的话会变成一个空格，导致task名称错误。

到这里Jenkins参数化构建的配置就已经完成了，但是我知道你肯定不会只满足于此。

#### 上传蒲公英
在**构建**框的底部我们选择**增加构建步骤**->**Execute shell**，使用[蒲公英的Api](https://www.pgyer.com/doc/view/api#uploadApp)来上传apk。
```shell
curl -F "file=@${WORKSPACE}/app/build/outputs/apk/${PRODUCT_FLAVORS}/${BUILD_TYPES}/gg-${BUILD_TYPES}-${PRODUCT_FLAVORS}-${VERSION_NAME}-${VERSION_CODE}.apk" -F "_api_key=${PGYER_API_KEY}" https://www.pgyer.com/apiv2/app/upload -F 'buildInstallType=2' -F "buildPassword=${PGYER_APK_PASSWORD}"
```
注意这里apk的名称的规则需要与项目生成的apk的名称规则一致，否则会找不到apk。另外，当我们打全渠道包的时候不上传到蒲公英，我们可以编写简单的shell脚本，判断是否`PRODUCT_FLAVORS`是否为空，如果空就是打多渠道包，不上传蒲公英。
```shell
if [-n "${PRODUCT_FLAVORS}"]
then
curl -F "file=@${WORKSPACE}/app/build/outputs/apk/${PRODUCT_FLAVORS}/${BUILD_TYPES}/gg-${BUILD_TYPES}-${PRODUCT_FLAVORS}-${VERSION_NAME}-${VERSION_CODE}.apk" -F "_api_key=${PGYER_API_KEY}" https://www.pgyer.com/apiv2/app/upload -F 'buildInstallType=2' -F "buildPassword=${PGYER_APK_PASSWORD}"
fi
```
> `WORKSPACE`是Jenkins内置的环境变量，想查看更多内置环境变量可查看：[https://wiki.jenkins.io/display/JENKINS/Building+a+software+project](https://wiki.jenkins.io/display/JENKINS/Building+a+software+project)

#### 更新Build Name
在构建项目的左下角，Jenkins会为我们列出构建历史，默认以`#${BUILD_NUMBER}`的形式展示的，所以我们会看到#1，#2，#3这样的名称，为了疯狂暗示，我们可以修改这个构建名称，我们需要先下载`build-name-setter`插件，然后选择**增加构建步骤**->**Update build name**进行配置。

<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/update-build-name.png" height="80%" width="80%">

构建完成后的效果如下：

<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/build-history.png" height="60%" width="60%">

> `BUILD_NUMBER`是Jenkins内置的环境变量，想查看更多内置环境变量可查看：[https://wiki.jenkins.io/display/JENKINS/Building+a+software+project](https://wiki.jenkins.io/display/JENKINS/Building+a+software+project)

#### 收集成果
在构建项目的首页会列出我们构建后的成果（apk），但是这需要我们配置一下成果的路径。
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/archive-artifacts-result.png" height="80%" width="80%">

选择**增加构建后操作步骤**->**Archive the artifacts**来进行配置：
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/archive-artifacts.png" height="80%" width="80%">

如果你没有多渠道包的需要，建议你使用完整的路径：
```shell
app/build/outputs/apk/${PRODUCT_FLAVORS}/${BUILD_TYPES}/*.apk
```
为了收集全渠道包所以这里直接使用`**/*.apk`来匹配`/apk`文件夹下的所有`.apk`文件。

#### 删除旧的构建
Jenkins默认会保留所有构建，可以在**构建历史**里查看，当我们构建次数多了之后，硬盘就会慢慢被塞满，这时候我们可以删除一些比较旧的构建，构建的目录在`/var/lib/jenkins/jobs/构建项目名称/builds/构建序号`，你可以手动进行删除，也可以使用插件。接下来我们就说下如何使用插件来自动删除旧的构建。这里我们需要借助`Discard Old Build`插件。安装插件后选择**增加构建后操作步骤**->**Discard Old Builds**来进行配置:

<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/discard-old-build.png" height="80%" width="80%">

这里我选择了保留7天内的构建。详细可查看插件说明：[Discard Old Build](https://wiki.jenkins.io/display/JENKINS/Discard+Old+Build+plugin)

#### Jenkins权限控制
如前所述，我们希望让测试人员自行打包，但是我们并不希望测试人员或者其他对Jenkins不了解的人员有过大的权限，避免误操作，所以我们限制一下权限，让他们只能进行构建等简单操作。

实现权限管理功能我们使用`Role-based Authorization Strategy`插件，安装完插件后进入**系统管理**->**全局安全配置**->**授权策略**中选择**Role-Based Strategy**。接下来就可以配置用户权限了。

1. **系统管理**->**Manage and Assign Roles**->**Manage Roles**

首先我们创建2个角色:`dev`，`test`。dev是分配给开发人员，可以对项目进行配置，test分配给测试人员，只能进行打包等简单操作。我们可以把鼠标光标移到权限名称上面，会显示权限描述。这里就不说明每个权限的作用了。
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/manage-roles.png" height="80%" width="80%">

2. **系统管理**->**Manage and Assign Roles**->**Assign Roles**

为不同用户分配不同的权限。确保该用户存在，如果用户还没创建，可以在**系统管理**->**管理用户**进行创建。

<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/assign-roles.png" height="80%" width="80%">

切换不同的用户，你会发现他们可以操作的功能不同，如测试人员只能进行构建和查看基本的构建信息：
<img src="https://raw.githubusercontent.com/littleGnAl/screenshot/master/blog-jenkins-parameterize/test-role.png" height="60%" width="60%">

### 结语
本文截图比较多，感谢你抽空阅读，本文主要记录自己配置Jenkins参数化的过程和一些遇到的问题，希望对你有所帮助。Jenkins能做的事很多，不仅仅是用来打包，如为git服务器添加hook，进行一些规范检查，代码检查等，提升项目质量。希望大家都能用做工程的想法来做项目。

### 参考
* [https://wiki.jenkins.io/display/JENKINS/Building+a+software+project](https://wiki.jenkins.io/display/JENKINS/Building+a+software+project)
* [https://pkg.jenkins.io/redhat/](https://pkg.jenkins.io/redhat/)
* [https://github.com/mabeijianxi/android-automation](https://github.com/mabeijianxi/android-automation)
* [https://juejin.im/entry/5a7329aef265da4e6e2b9644](https://juejin.im/entry/5a7329aef265da4e6e2b9644)
* [https://www.jianshu.com/p/c420bca3a855](https://www.jianshu.com/p/c420bca3a855)