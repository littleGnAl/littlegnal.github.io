---
title: How to Use GPT to Generate Boilerplate Code
date: 2023-04-24 20:52:35 +0800
---
## Motivation
> The GPT referred to in this article is the OpenAI GPT-x model, for details see https://platform.openai.com/docs/models/overview

GPT is a powerful natural language processing tool that can help you complete code based on your comments or code snippets. Sometimes, we want it to assist us in completing repetitive tasks, such as generating template code in programming. However, the OpenAI API has a token limit. For example, gpt-3.5 only supports 4096 tokens, which is not suitable for generating an entire file of code at once. Although gpt-4 can support 8k or even 32k tokens, a large code file can easily exceed this limit.

So how can we use GPT to generate boilerplate code based on a large codebase? The core idea is to divide the code into small snippets, and then input these snippets to GPT. GPT will process the code snippets based on the prompt and output the result. Finally, we will concatenate the generated code snippets into the template and output the final code file. To avoid GPT outputting ambiguous results, we need to ensure that the code snippets have sufficient context information.

Based on the above ideas, I developed a tool called [gpt_code_gen](https://github.com/littleGnAl/gpt_code_gen), which currently only supports C++ code generation. Below, I will share some of the thinking and experience I had while implementing this tool.

## Dividing Code Snippets
In most cases, we can use regular expressions to divide code snippets. If we need to obtain code information more accurately, we can use the corresponding language's AST tool to divide the code snippets. The specific implementation details are not within the scope of this article.

### Granularity of Dividing Code Snippets
1. Dividing by code definition

    We can divide a code snippets based on `class`, `struct`, `enum` and other definitions.

2. Dividing sub-code snippets

    In a large, long-term maintained project, the definition of a `class` often exceeds several hundred methods, so we need to divide the `class` into sub-code snippets.

    - Divide each method into a code snippet.

    - Divide macro definitions as a code snippet. Here, macro definitions refer to code wrapped by a macro definition, as shown below:
      ```c++
      #if defined(__ANDROID__)
          virtual void func3() = 0;
      #endif
      ```

Here is an example code:

```c++
struct MyStruct {
    int field1;
    int field2;
};

enum MyEnum {
    ENUM1 = 1;
}

class MyClass {
    virtual void func1() = 0;

    virtual void func2(const MyStruct& my_struct) = 0;

#if defined(__ANDROID__)
    virtual void func3() = 0;
#endif
};
```
We can divide the above code into the following code snippets:

Code snippet 1:
```c++
struct MyStruct {
    int field1;
    int field2;
};
```
Code snippet 2:
```c++
enum MyEnum {
    ENUM1 = 1;
}
```
Code snippet 3:
```c++
class MyClass {
    virtual void func1() = 0;

    virtual void func2(const MyStruct& my_struct) = 0;

#if defined(__ANDROID__)
    virtual void func3() = 0;
#endif
};
```

We can divide a `class` into the following code snippets:

sub-code Snippet 1:
```c++
virtual void func1() = 0;
```
Sub-code Snippet 2:
```c++
virtual void func2(const MyStruct& my_struct) = 0;
```
Sub-code Snippet 3:
```c++
#if defined(__ANDROID__)
    virtual void func3() = 0;
#endif
```


### Ensure Code Snippets Have Sufficient Context
To ensure accuracy, we try to provide GPT with as much information as possible about user-defined `struct` and `enum` involved in the code snippets. For example, in *sub-code snippet 2*, we would include the information from *code snippet 1*: 
```c++
struct MyStruct {
    int field1;
    int field2;
};

virtual void func2(const MyStruct& my_struct) = 0;
```

### Natural Language Code Generation
In the previous section, we discussed how to split code snippets, and now we will see how to use the split code snippets to generate code. In the era of AI, natural language programming has become possible, and all you need to do is write a prompt to control code generation flexibly (you can refer to [awesome-chatgpt-prompts](https://github.com/f/awesome-chatgpt-prompts) or use ChatGPT to write more accurate prompts).

In this project, we mainly use the [Chat Completion API](https://platform.openai.com/docs/guides/chat) to complete code generation. Using YAML format can eliminate the trouble of symbol escape and make it more convenient to use code as input, better supporting Few-shot prompting. Therefore, YAML is selected as the prompt input file format in this project(maybe change in the furture), and it is converted to JSON format to be sent to the Chat Completion API. The specific format is as follows:

```yaml
- role: system
  content: The system content
  
- role: user
  content: This is the user content

- role: assistant
  content: This is the assistant content
```

The above *sub-code snippet 1* will be converted into the following JSON format and sent to the Chat Completion API:

```json
[
    {"role": "system", "content": "The system content"},
    {"role": "user", "content": "This is the user content"},
    {"role": "assistant", "content": "This is the assistant content"},
    {"role": "user", "content": "virtual void func1() = 0;"}
]
```

The following is an example of the Prompt used in the project to generate gMock's `MOCK_METHOD` code:
```yaml
- role: system
  content: |
    Write a gMock mock method definition in C++. The mock method should take C++ function code snippets as inputs and return the mock method definition. Use your knowledge of C++ and gMock to write the exact gMock mock function declaration. Your solution should be in the form of a C++ code snippet that defines the mock method.
    The mock method should should also handle any macro declarations in the input and include them in the output.
    I want you to only reply the mock method definition. Do not write explanations.

- role: user
  content: |
    virtual void release(bool sync = false) = 0;

- role: assistant
  content: |
    MOCK_METHOD(void, release, (bool sync), (override));

```

The above prompts generate `MOCK_METHOD` for each method code block. The final step is to concatenate the generated `MOCK_METHOD`s together. As mentioned at the beginning of the article, we need a template class to hold these generated methods, which can also be generated through prompts. Here is an example prompt from this project that generates the entire gMock mock class template:
```yaml
- role: system
  content: |
    Given the class name, replace the {{ CLASS_NAME }} in the following template:
    /// GENERATED BY gpt_code_gen, DO NOT MODIFY BY HAND.
    class Mock{{ CLASS_NAME }} : public {{ CLASS_NAME }} {
    public:
    {{ BODY }}
    };

    I want you to only reply the replaced template Do not write explanations.

- role: user
  content: IRtcEngine

- role: assistant
  content: |
    /// GENERATED BY gpt_code_gen, DO NOT MODIFY BY HAND.
    class MockIRtcEngine : public IRtcEngine {
    public:
    {{ BODY }}
    };
```

The generated method code will be replaced into `{{ BODY }}` of the template, and then output.

```c++
/// GENERATED BY gpt_code_gen, DO NOT MODIFY BY HAND.
class MockIRtcEngine : public IRtcEngine {
public:
MOCK_METHOD(void, release, (bool sync), (override));

MOCK_METHOD(int, queryInterface, (INTERFACE_ID_TYPE iid, void** inter), (override));
...
};
```

## TL;DR
This article is written with the help of ChatGPT. Please forgive any inadequacies.

Above are some experiences I shared about the `gpt_code_gen` project. I hope it can be helpful to you.

Project address: [https://github.com/littleGnAl/gpt_code_gen](https://github.com/littleGnAl/gpt_code_gen) <br />
Demo: [https://github.com/littleGnAl/gpt_code_gen/tree/main/examples](https://github.com/littleGnAl/gpt_code_gen/tree/main/examples)