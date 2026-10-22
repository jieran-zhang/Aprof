# case-01..05 自主回归汇总

仅原始源码与matrix20，未读取旧回归答案/硬件结果；目标910C/A3(dav-2201)来自任务配置，未探测实际资源。

- case-01 exp：action.software_pipeline_stages；见 case-01/REPORT.md
- case-02 mish：action.coalesce_contiguous_transfers；见 case-02/REPORT.md
- case-03 masked_scale：action.software_pipeline_stages；见 case-03/REPORT.md
- case-04 swi_glu：action.coalesce_contiguous_transfers；见 case-04/REPORT.md
- case-05 apply_adam_w：action.reuse_disjoint_onchip_buffers；见 case-05/REPORT.md

所有R1/R2均conditional_plan；实际P/O内部router记录、Problem展开、文档hash/locator及知识影响在各task内。反事实代价反转见counterfactual-probe.json。
