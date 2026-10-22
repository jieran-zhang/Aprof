"""将 Agent 自主分析的字段装配为 v2；不选择机制、Action 或方案。"""
from copy import deepcopy


def assemble_v2(base, *, path_overview, analyses, comparison_basis, reassessment=None):
    """base 使用原核心身份/机会结构；全部新分析需调用者明确提供。

    analyses: opportunity_id -> analysis 对象。不得从 Action 名称自动生成。
    需调用 aprof_runtime.action_decision.validate_decision 做实际身份及语义结构校验。
    """
    value = deepcopy(base)
    value['schema_version'] = 'aprof.action-decision/v2'
    if set(analyses) != {o['id'] for o in value['opportunities']}:
        raise ValueError('analyses 必须唯一覆盖 Agent 已比较的所有机会')
    value['path_overview'] = deepcopy(path_overview)
    for opportunity in value['opportunities']:
        opportunity['analysis'] = deepcopy(analyses[opportunity['id']])
    value['selection']['comparison_basis'] = deepcopy(comparison_basis)
    if value['previous_feedback'] is not None:
        if reassessment is None:
            raise ValueError('后继必须提供分层反馈，不把 v1 反馈自动改写成已复盘')
        value['previous_feedback']['reassessment'] = deepcopy(reassessment)
    elif reassessment is not None:
        raise ValueError('首轮不应伪造前轮反馈')
    return value
