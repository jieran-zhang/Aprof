# ScatterAddWithSorted

## 产品支持情况

| 产品                                                         | 是否支持 |
| :----------------------------------------------------------- | :------: |
| <term>Ascend 950PR&950DT系列产品</term>                          |    √  |
| <term>Atlas A3系列产品</term>    |    √    |
| <term>Atlas A2系列产品</term>     |    √     |
| <term>Atlas 200I/500 A2推理产品</term>                      |    ×     |
| <term>Atlas推理系列产品</term>                             |    ×     |
| <term>Atlas训练系列产品</term>                              |    ×   |
|  <term>Kirin X90处理器系列产品</term> | √ |
|  <term>Kirin 9030处理器系列产品</term> | √ |

## 功能说明

- 算子功能: 将tensor src中的值按指定的轴和方向和对应的位置关系逐个替换/累加/累乘至tensor self中。

- 示例：
  对于一个3D tensor,self会按照如下的规则进行更新：

  ```cpp
  self[index[i][j][k]][j][k] += src[i][j][k] # 如果dim == 0 && reduction == 1
  self[i][index[i][j][k]][k] *= src[i][j][k] # 如果dim == 1 && reduction == 2
  self[i][j][index[i][j][k]] = src[i][j][k]  # 如果dim == 2 && reduction == 0
  ```

  在计算时需要满足以下要求：
  - self、index和src的维度数量必须相同。
  - 对于每一个维度d，有index.size(d) <= src.size(d)的限制。
  - 对于每一个维度d，如果d != dim,有index.size(d) <= self.size(d)的限制。
  - dim的值的大小必须在 [-self的维度数量, self的维度数量-1] 之间。
  - self的维度数应该小于等于8。
  - index中对应维度dim的值大小必须在[0, self.size(dim)-1]之间。

## 参数说明

<table style="undefined;table-layout: fixed; width: 1576px"><colgroup>
  <col style="width: 170px">
  <col style="width: 170px">
  <col style="width: 310px">
  <col style="width: 212px">
  <col style="width: 100px">
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
      <td>var</td>
      <td>输入</td>
      <td>公式中的`self`，Device侧的aclTensor。</td>
      <td>FLOAT16、FLOAT32、BFLOAT16</td>
      <td>ND</td>
    </tr>
    <tr>
      <td>value</td>
      <td>输入</td>
      <td>公式中的`index`，Device侧的aclTensor。</td>
      <td>FLOAT16、FLOAT32、BFLOAT16</td>
      <td>ND</td>
    </tr>
    <tr>
      <td>sorted_index</td>
      <td>输入</td>
      <td>公式中的`src`，Device侧的aclTensor。</td>
      <td>INT32、INT64</td>
      <td>ND</td>
    </tr>
    <tr>
      <td>pos</td>
      <td>输入</td>
      <td>公式中的`src`，Device侧的aclTensor。</td>
      <td>INT32、INT64</td>
      <td>ND</td>
    </tr>
    <tr>
      <td>var</td>
      <td>输出</td>
      <td>公式中的`self`，公式中的输出。</td>
      <td>FLOAT16、FLOAT32、BFLOAT16</td>
      <td>ND</td>
    </tr>
  </tbody></table>

- Kirin X90/Kirin 9030处理器系列产品：不支持BFLOAT16。

## 约束说明

无
