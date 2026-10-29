# GatherElementsV2

## 产品支持情况

| 产品                                                         | 是否支持 |
| :----------------------------------------------------------- | :------: |
| <term>Ascend 950PR&950DT系列产品</term>                          |    ×     |
| <term>Atlas A3系列产品</term>    |    √     |
| <term>Atlas A2系列产品</term>     |    √     |
| <term>Atlas 200I/500 A2推理产品</term>                      |    ×     |
| <term>Atlas推理系列产品</term>                             |    ×     |
| <term>Atlas训练系列产品</term>                              |    ×     |
|  <term>Kirin X90处理器系列产品</term> | √ |
|  <term>Kirin 9030处理器系列产品</term> | √ |

## 功能说明

- 算子功能：对输入tensor中指定的维度dim进行数据聚集。

- 计算公式：
  给定张量$x$，维度$d$，和一个索引张量$index$，定义$n$是$x$的维度，$i_d$表示维度$d$的索引，$index_{i_d}$表示索引张量$index$在维度$d$上的第$i_d$个索引值。对指定维度d的gather功能可以用如下的数学公式表示：

  $$
  gather(X,index,d)_{i_0,i_1,\cdots,i_{d-1},i_{d+1},\cdots,i_{n-1}} = x_{i_0,i_1,\cdots,i_{d-1},index_{i_d},i_{d+1},\cdots,i_{n-1}}
  $$

- 示例：
  - 示例1：
    假设输入张量$x=\begin{bmatrix}1 & 2 & 3\\ 4 & 5 & 6\\ 7 & 8 & 9\end{bmatrix}$，索引张量$index=\begin{bmatrix}0 & 2\\ 1 & 0\end{bmatrix}$，$dim = 0$，那么输出张量$y=\begin{bmatrix}1 & 8\\ 4 & 2\end{bmatrix}$，具体计算过程如下：

    $$
    \begin{aligned} y_{0,0}&=x_{index_{0,0}, 0}=x_{0,0}=1 \\
    y_{0,1}&=x_{index_{0,1}, 1}=x_{2,1}=8 \\
    y_{1,0}&=x_{index_{1,0}, 0}=x_{1,0}=4 \\
    y_{1,1}&=x_{index_{1,1}, 1}=x_{0,1}=2 \end{aligned}
    $$

  - 示例2：
    假设输入张量$x=\begin{bmatrix}1 & 2 & 3\\ 4 & 5 & 6\\ 7 & 8 & 9\end{bmatrix}$，索引张量$index=\begin{bmatrix}0 & 2\\ 1 & 0\end{bmatrix}$，$dim = 1$，那么输出张量$y=\begin{bmatrix}1 & 3\\ 5 & 4\end{bmatrix}$，具体计算过程如下：

    $$
    \begin{aligned} y_{0,0}&=x_{0, index_{0,0}}=x_{0,0}=1 \\
    y_{0,1}&=x_{0, index_{0,1}}=x_{0,2}=3 \\
    y_{1,0}&=x_{1, index_{1,0}}=x_{1,1}=5 \\
    y_{1,1}&=x_{1, index_{1,1}}=x_{1,0}=4 \end{aligned}
    $$

## 参数说明

<table style="undefined;table-layout: fixed; width: 1250px"><colgroup>
  <col style="width: 60px">
  <col style="width: 60px">
  <col style="width: 150px">
  <col style="width: 150px">
  <col style="width: 60px">
  </colgroup>
  <thead>
    <tr>
      <th>参数名</th>
      <th>输入/输出/属性</th>
      <th>描述</th>
      <th>数据类型</th>
      <th>数据格式</th>
    </tr></thead>
  <tbody>
    <tr>
      <td>x</td>
      <td>输入</td>
      <td>公式中的x。</td>
      <td>FLOAT、FLOAT16、BFLOAT16、INT32</td>
      <td>ND</td>
    </tr>
    <tr>
      <td>index</td>
      <td>输入</td>
      <td>公式中的index。</td>
      <td>INT32</td>
      <td>ND</td>
    </tr>
    <tr>
      <td>y</td>
      <td>输出</td>
      <td>公式中的y。</td>
      <td>FLOAT、FLOAT16、BFLOAT16、INT32</td>
      <td>ND</td>
    </tr>
    <tr>
      <td>dim</td>
      <td>可选属性</td>
      <td><ul><li>公式中的d。</li><li>默认值为0。</li></ul></td>
      <td>Int</td>
      <td>-</td>
    </tr>
  </tbody></table>

- Kirin X90/Kirin 9030处理器系列产品：x和y的数据类型不支持BFLOAT16。

## 约束说明

无

## 调用说明

| 调用方式 | 调用样例                                                                   | 说明                                                           |
|--------------|------------------------------------------------------------------------|--------------------------------------------------------------|
| aclnn调用 | [test_aclnn_gather_elements_v2](./examples/test_aclnn_gather_elements_v2.cpp) | 通过[aclnnGather](./docs/aclnnGather.md)接口方式调用GatherElementsV2算子。 |
