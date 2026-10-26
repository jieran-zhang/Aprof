# grid_sampler_3d R2第二次静态复核

20case逻辑H=4/8/16分组边界共240次断言仅证明逻辑索引覆盖，不能证明物理写独占。进一步审读发现奇数S使同一个T空间切点在不同channel具有不同64B余数，H=C也不能使跨空间task安全。R2保留原64B线性owner，只复用其内部完整channel平面，头尾残片fallback；因此削弱R1全覆盖ceil(C/H)坐标计数预测，改为逐owner实际计数。保留独立轴权重和原累加顺序。

条件后继：先取得实际AIV/owner边界和输出DataCopyPad物理规则，计算每owner完整channel数量。若多数owner不足2个完整channel，可仅在S*b对齐域重规划H组，或保留原路径；禁止牺牲所有并行度强制整batch一个owner。完整20case原oracle后再比较。

修订方案：新P按(n,channel-group,spatial-tile)拥有互斥输出，H∈{4,8,16}, T∈{64,128,256,512}。同一个空间tile先算一次坐标几何，再按channel顺序采样，保留原GridRead边界和三线性八项相加/乘法顺序；只缓存x0/x1,y0/y1,z0/z1与6个独立FP32轴权重，禁止预乘权重改变舍入。nearest缓存3个int64坐标。U≤Align32(3*b*T)+Align32(geometry*T)+Align32((b+4)*T)+reserve，geometry=72或24B；输出每次只保留一个channel的T元素；不新增GM workspace。R2收紧输出所有权：S*b可64B整除时按H组与64B空间边界分区。否则复用原64B对齐线性owner区间[B,E)，只在同一batch、完整落在此owner内的channel平面之间共享几何；头尾不完整平面保留原GridSampler3DOne。各完整平面内部切T不会跨owner；禁止为了共享几何把别的owner输出移进来。若owner包含不足2个完整channel，则直接fallback。实际坐标求值数按每owner完整平面数量与头尾残片求和，不能沿用理想ceil(C/H)全覆盖节省量。

未执行候选、构建、native、oracle或性能计时；保留原始父本。
