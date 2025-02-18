### 前言

- 这里给出一份最简单的前后端交互代码，同学们可以照着这份代码自行调整

- 如果想要使用其他前端当然也可以，但请自行学习（如 Qt 等）

### 所需环境一览

- git，略

- python>=3.6，装 Emscripten 时需要

- Emscripten，安装配置方式见下

- jsoncpp，不需要配环境直接按照代码里写的就能跑所以就不写了

### Emscripten 安装方法

- 网上教程挺多的（官网教程也可以），这里总结一下

- 首先克隆仓库并进入文件夹（这个路径要写入环境变量的所以最好不要放在项目文件夹）

```cmd
git clone https://github.com/emscripten-core/emsdk.git
cd emsdk
```

- 安装 SDK 工具（windows 版本，linux 去掉.bat）

- 按照命令输出写入环境变量

- 最后看一下`emcc -v`报不报错，没报错就装成功了，报错了就重启电脑

```cmd
./emsdk.bat install latest
./emsdk.bat activate latest
./emsdk_env.bat
emcc -v
```

### 代码说明

- 后端代码（test.cpp）

  - 使用 json 数据格式存储数据

  - EMSCRIPTEN_BINDINGS 是 Emscripten 的神奇功能，主要是因为 c++编译完之后函数名会发生一些改变所以前端用不了，用这个 bind 就可以把这些函数名保持下来

- 前端代码（frontend/index.html）

  - 约等于啥都没写的前端，只是为了展示一下数据确实获取到了

  - 通过 canvas 画多边形，比较简陋，同学们可以思考如何优化

### 最终运行方法

- 命令行输入，因为加了很多东西所以变得特别长

```cmd
emcc tinyxml/tinyxml.cpp tinyxml/tinystr.cpp tinyxml/tinyxmlerror.cpp tinyxml/tinyxmlparser.cpp jsoncpp/json_reader.cpp jsoncpp/json_value.cpp jsoncpp/json_writer.cpp test.cpp -o frontend/test.js -lembind --preload-file map
cd frontend
python -m http.server
```

- 先编译，进入编译完之后的前端文件夹，然后用 python 或者 emrun 启动前端来展示

- 编译出的内容为前端文件夹下除了 index.html 的其他三个文件，其中 test.data 其实就是 map，但如果要加载多个文件的话需要打包

- 如果用 python 启动的话，浏览器输入 127.0.0.1:8000 即可
