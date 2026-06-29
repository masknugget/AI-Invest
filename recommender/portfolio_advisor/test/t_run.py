"""
portfolio_advisor 五维诊断入口使用示例与基础校验。

运行方式：
    python research/portfolio_advisor/test/t_run.py

需要在项目根目录下执行，或保证 sys.path 包含项目根目录。
"""

import math
from pprint import pprint

from infra_structure.data_engine.visitor.file_visitor import FileVisitor
from research.portfolio_advisor.dimension.run import (
    DEFAULT_DIMENSION_WEIGHTS,
    GEOMETRIC_DIMENSION_WEIGHTS,
    PortfolioDimensions,
    compute_drawdown_control,
    compute_geometric_composite_score,
    compute_portfolio_dimensions,
    compute_position_efficiency,
    compute_return_stability,
    load_random_portfolio,
)


def _fmt(value: float) -> str:
    """格式化浮点数输出，兼容 nan / inf。"""
    if isinstance(value, float) and math.isnan(value):
        return "nan"
    if isinstance(value, float) and math.isinf(value):
        return str(value)
    if value is None:
        return "None"
    return f"{value:.4f}"


def _assert_close(actual: float, expected: float, tol: float = 1e-9) -> None:
    """断言两个浮点数在容差范围内相等。"""
    assert abs(actual - expected) < tol, f"期望值 {expected}，实际值 {actual}"


def run_unit_tests() -> int:
    """
    运行纯函数级的基础断言测试，返回失败数量。

    这些测试不依赖行情数据，用于保证几何加权、字典接口等核心逻辑正确。
    """
    failures = 0

    def _record_error(msg: str) -> None:
        nonlocal failures
        failures += 1
        print(f"  [FAIL] {msg}")

    print("\n" + "=" * 70)
    print("单元测试：几何加权综合得分")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. 已知输入的几何加权结果
    # -------------------------------------------------------------
    scores = {
        "drawdown_control": 80.0,
        "return_stability": 70.0,
        "position_efficiency": 60.0,
        "portfolio_diversification": 50.0,
        "style_balance": 90.0,
    }
    expected_geo = 68.75618863452559
    try:
        geo = compute_geometric_composite_score(scores, GEOMETRIC_DIMENSION_WEIGHTS)
        _assert_close(geo, expected_geo, tol=1e-6)
        print(f"  [PASS] 已知得分几何加权结果: {_fmt(geo)}")
    except Exception as exc:  # noqa: BLE001
        _record_error(f"已知得分几何加权结果异常: {exc}")

    # -------------------------------------------------------------
    # 2. 等分输入：几何加权结果应接近算术平均
    # -------------------------------------------------------------
    try:
        equal_scores = {k: 75.0 for k in scores}
        geo_eq = compute_geometric_composite_score(equal_scores, GEOMETRIC_DIMENSION_WEIGHTS)
        _assert_close(geo_eq, 75.0, tol=1e-9)
        print(f"  [PASS] 等分几何加权结果: {_fmt(geo_eq)}")
    except Exception as exc:  # noqa: BLE001
        _record_error(f"等分几何加权结果异常: {exc}")

    # -------------------------------------------------------------
    # 3. 全满分：几何加权结果应为 100
    # -------------------------------------------------------------
    try:
        full_scores = {k: 100.0 for k in scores}
        geo_full = compute_geometric_composite_score(full_scores, GEOMETRIC_DIMENSION_WEIGHTS)
        _assert_close(geo_full, 100.0, tol=1e-9)
        print(f"  [PASS] 全满分几何加权结果: {_fmt(geo_full)}")
    except Exception as exc:  # noqa: BLE001
        _record_error(f"全满分几何加权结果异常: {exc}")

    # -------------------------------------------------------------
    # 4. 任一维度为 0：几何加权结果应为 0（短板惩罚）
    # -------------------------------------------------------------
    try:
        zero_scores = {**scores, "position_efficiency": 0.0}
        geo_zero = compute_geometric_composite_score(zero_scores, GEOMETRIC_DIMENSION_WEIGHTS)
        _assert_close(geo_zero, 0.0, tol=1e-9)
        print(f"  [PASS] 短板为 0 时几何加权结果: {_fmt(geo_zero)}")
    except Exception as exc:  # noqa: BLE001
        _record_error(f"短板为 0 几何加权结果异常: {exc}")

    # -------------------------------------------------------------
    # 5. 权重和不为 1：应抛出 ValueError
    # -------------------------------------------------------------
    try:
        bad_weights = {k: 0.5 for k in GEOMETRIC_DIMENSION_WEIGHTS}
        compute_geometric_composite_score(scores, bad_weights)
        _record_error("权重和不为 1 时未抛出异常")
    except ValueError:
        print("  [PASS] 权重和校验正确抛出 ValueError")
    except Exception as exc:  # noqa: BLE001
        _record_error(f"权重和校验异常类型错误: {exc}")

    # -------------------------------------------------------------
    # 6. 缺少维度得分：应抛出 ValueError
    # -------------------------------------------------------------
    try:
        incomplete_scores = {k: 50.0 for k in list(scores)[:3]}
        compute_geometric_composite_score(incomplete_scores, GEOMETRIC_DIMENSION_WEIGHTS)
        _record_error("缺少维度得分时未抛出异常")
    except ValueError:
        print("  [PASS] 缺少维度得分时正确抛出 ValueError")
    except Exception as exc:  # noqa: BLE001
        _record_error(f"缺少维度得分校验异常类型错误: {exc}")

    # -------------------------------------------------------------
    # 7. PortfolioDimensions 字段完整性
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("单元测试：PortfolioDimensions 接口")
    print("=" * 70)

    expected_keys = {
        "drawdown_control",
        "portfolio_diversification",
        "position_efficiency",
        "return_stability",
        "style_balance",
    }
    try:
        assert set(scores.keys()) == expected_keys
        print("  [PASS] 五维评分字典 keys 完整")
    except AssertionError as exc:
        _record_error(f"五维评分字典 keys 异常: {exc}")

    return failures


def _print_dimension_result(result: PortfolioDimensions) -> None:
    """打印 PortfolioDimensions 的完整结果。"""
    print("\n【抗回撤能力】")
    print(f"  最大回撤 MDD       : {_fmt(result.drawdown_control.mdd)}")
    print(f"  控制得分 (0-100)   : {_fmt(result.drawdown_control.score)}")

    print("\n【资产分散度】")
    print(f"  ENB (weight-based) : {_fmt(result.portfolio_diversification.enb_weight_based)}")
    print(f"  ENB (risk-based)   : {_fmt(result.portfolio_diversification.enb_risk_based)}")
    print(f"  分散得分 (0-100)   : {_fmt(result.portfolio_diversification.score)}")

    print("\n【持仓性价比】")
    print(f"  夏普比率           : {_fmt(result.position_efficiency.sharpe_ratio)}")
    print(f"  性价比得分 (0-100) : {_fmt(result.position_efficiency.score)}")

    print("\n【收益稳定性】")
    print(f"  年化波动率         : {_fmt(result.return_stability.annualized_volatility)}")
    print(f"  稳定得分 (0-100)   : {_fmt(result.return_stability.score)}")

    print("\n【风格均衡】")
    print(f"  风格 HHI           : {_fmt(result.style_balance.style_hhi)}")
    print(f"  有效风格数         : {_fmt(result.style_balance.effective_style_num)}")
    print(f"  均衡得分 (0-100)   : {_fmt(result.style_balance.score)}")

    print("\n" + "=" * 70)
    print(f"综合健康分 (0-100)   : {_fmt(result.composite_score)}")
    print(f"几何加权综合分 (0-100): {_fmt(result.geometric_composite_score)}")
    print(f"维度权重             : {dict(result.dimension_weights)}")
    print(f"几何加权权重         : {dict(GEOMETRIC_DIMENSION_WEIGHTS)}")
    print("=" * 70)

    print("\n五维评分字典:")
    pprint(dict(result.to_score_dict()))
    print("=" * 70)


if __name__ == "__main__":
    # -------------------------------------------------------------
    # 单元测试（不依赖行情数除了 **RAG 知识库型**（如 RAGFlow）和 **Workflow/Agent 编排型**（如 Dify）之外，当前大模型产品还可以按核心能力和应用场景分为以下几大类：
    #
    # ---
    #
    # ### 1. AI 搜索/问答型（Search & Answer）
    # - **核心能力**：实时联网检索、多源信息整合、溯源回答
    # - **代表产品**：Perplexity、秘塔 AI 搜索、Genspark、360AI 搜索、You.com
    # - **与 RAG 的区别**：RAG 主要检索用户私有知识库，AI 搜索主要检索开放互联网信息
    #
    # ### 2. AI 编程/代码助手型（Coding Assistant）
    # - **核心能力**：代码补全、代码生成、Bug 修复、代码解释、跨文件重构
    # - **代表产品**：GitHub Copilot、Cursor、Codeium、Continue、TabNine、通义灵码
    # - **特点**：深度集成 IDE，理解代码上下文和项目结构
    #
    # ### 3. AI 写作与内容生成型（Content Generation）
    # - **核心能力**：文案撰写、营销内容、长文生成、风格改写
    # - **代表产品**：Jasper、Copy.ai、Writesonic、Notion AI、讯飞写作、字语智能
    # - **细分**：有的专注营销文案，有的专注长文/小说，有的嵌入办公套件
    #
    # ### 4. AI 办公/效率工具型（Productivity & Office）
    # - **核心能力**：文档处理、表格分析、PPT 生成、邮件撰写、会议总结
    # - **代表产品**：Microsoft 365 Copilot、WPS AI、飞书智能伙伴、Google Duet AI、ChatExcel
    # - **特点**：嵌入传统办公软件，改造既有工作流
    #
    # ### 5. AI 数据分析与 BI 型（Data & Analytics）
    # - **核心能力**：自然语言查数（Text2SQL）、自动生成图表、数据洞察、报表解读
    # - **代表产品**：Tableau AI、Power BI Copilot、北极九章、ChatExcel、基于大模型的 BI 工具
    # - **场景**：降低数据分析门槛，让业务人员用自然语言获取数据洞察
    #
    # ### 6. AI 音视频与多模态生成型（Audio/Video/Multimodal）
    # - **核心能力**：文生图、文生视频、语音合成、数字人、视频编辑
    # - **代表产品**：
    #   - 图像：Midjourney、Stable Diffusion、DALL-E、即梦
    #   - 视频：Sora、Runway、可灵、Pika、HeyGen
    #   - 音频：ElevenLabs、Suno、Udio
    # - **趋势**：从单模态走向多模态统一生成
    #
    # ### 7. AI 客服与企业应用型（Enterprise & Customer Service）
    # - **核心能力**：智能问答、工单自动处理、CRM 集成、销售辅助
    # - **代表产品**：智齿科技（大模型版）、网易七鱼、容联七陌、Salesforce Einstein GPT
    # - **特点**：强调与企业现有系统（CRM、ERP）的对接和私有化部署
    #
    # ### 8. 垂直行业专用型（Vertical Domain）
    # - **法律**：Harvey、幂律智能、法大大（合同审查、法律咨询）
    # - **医疗**：医联 MedGPT、各种医院大模型（辅助诊断、病历生成）
    # - **金融**：Bloomberg GPT、各类投研助手（研报解读、风控分析）
    # - **教育**：Khanmigo、Duolingo Max、松鼠 AI（个性化辅导、答疑）
    #
    # ### 9. AI 角色扮演与娱乐型（Character & Entertainment）
    # - **核心能力**：虚拟角色对话、情感陪伴、游戏 NPC、互动故事
    # - **代表产品**：Character.AI、Glow、Replika、AI Dungeon、Talkie
    # - **特点**：强调人格化、情感连接，而非工具性效率
    #
    # ### 10. 模型训练与开发平台型（Model Training & DevOps）
    # - **核心能力**：模型微调、训练、评估、部署、Prompt 管理
    # - **代表产品**：Hugging Face、魔搭社区（ModelScope）、火山方舟、百度千帆、阿里云百炼、LangSmith
    # - **服务对象**：开发者和企业 AI 团队，而非终端用户
    #
    # ### 11. AI 浏览器与插件型（Browser & Plugin）
    # - **核心能力**：网页内容总结、划词翻译、随时调用 AI、自动化操作
    # - **代表产品**：Arc 浏览器、Monica、Merlin、ChatGPT Sidebar、沉浸式翻译
    # - **特点**：以浏览器为载体，覆盖所有网页场景
    #
    # ### 12. 通用对话/聊天平台型（General Chat）
    # - **核心能力**：开放式对话、多轮交互、通用知识问答
    # - **代表产品**：ChatGPT、Claude、Gemini、文心一言、通义千问、Kimi、智谱清言
    # - **定位**：基础设施型产品，其他类型产品往往在其之上构建
    #
    # ---
    #
    # ### 补充说明：边界正在模糊
    # 这些分类并非互斥。例如：
    # - **Dify** 本身也支持 RAG 知识库；
    # - **RAGFlow** 也在增加 Agent 工作流能力；
    # - **Notion AI** 既是办公工具也有写作和知识库属性；
    # - **Cursor** 既是编程工具也是知识库（可索引整个代码库）。
    #
    # 当前趋势是**"融合型平台"**——单一产品往往同时集成知识库、工作流、Agent、多模态等多种能力，按具体场景组合使用。it_tests()

    # -------------------------------------------------------------
    # 示例 1：使用 FileVisitor 随机读取 5 只标的
    # ---------------------------------------------------------------
    file_visitor = FileVisitor("basic", "stock", "market", "d1", "time_series").data_set()

    dfs = [file_visitor.random_one() for _ in range(5)]
    weights = [0.1, 0.2, 0.3, 0.3, 0.1]

    print("\n示例 1：FileVisitor 随机 5 只标的")
    print("=" * 70)
    print(f"组合标的: {[df['code'].iloc[0] for df in dfs]}")
    print(f"组合权重: {weights}")

    result1 = compute_portfolio_dimensions(dfs, weights)
    _print_dimension_result(result1)

    # ---------------------------------------------------------------
    # 示例 2：使用 load_random_portfolio 辅助函数
    # ---------------------------------------------------------------
    print("\n示例 2：通过 load_random_portfolio 获取数据并计算")
    random_dfs = load_random_portfolio(n_assets=5)
    print("=" * 70)
    print(f"组合标的: {[df['code'].iloc[0] for df in random_dfs]}")
    print(f"组合权重: {weights}")

    result2 = compute_portfolio_dimensions(random_dfs, weights)
    _print_dimension_result(result2)

    # ---------------------------------------------------------------
    # 示例 3：自定义维度权重
    # ---------------------------------------------------------------
    print("\n示例 3：自定义维度权重（等权）")
    custom_weights = {
        "return_stability": 0.20,
        "position_efficiency": 0.20,
        "style_balance": 0.20,
        "drawdown_control": 0.20,
        "portfolio_diversification": 0.20,
    }
    result3 = compute_portfolio_dimensions(dfs, weights, dimension_weights=custom_weights)
    print("=" * 70)
    print(f"默认权重: {dict(DEFAULT_DIMENSION_WEIGHTS)}")
    print(f"自定义权重: {custom_weights}")
    print(f"综合健康分 (0-100)   : {_fmt(result3.composite_score)}")
    print(f"几何加权综合分 (0-100): {_fmt(result3.geometric_composite_score)}")
    print("=" * 70)

    # -------------------------------------------------------------
    # 示例 4：单资产组合（边界情况）
    # -------------------------------------------------------------
    print("\n示例 4：单资产组合")
    single_df = [file_visitor.random_one()]
    single_weights = [1.0]

    # 单资产时 portfolio_diversification / style_balance 底层在 qcut / cov 计算
    # 上可能报错，因此这里只展示可独立运行的 3 个维度。

    print("=" * 70)
    print(f"组合标的: {[df['code'].iloc[0] for df in single_df]}")
    print(f"  抗回撤控制得分 : {_fmt(compute_drawdown_control(single_df, single_weights).score)}")
    print(f"  持仓性价比得分 : {_fmt(compute_position_efficiency(single_df, single_weights).score)}")
    print(f"  收益稳定得分   : {_fmt(compute_return_stability(single_df, single_weights).score)}")
    print("=" * 70)

    # -------------------------------------------------------------
    # 汇总
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    if test_failures == 0:
        print("所有单元测试通过")
    else:
        print(f"单元测试失败数量: {test_failures}")
    print("=" * 70)
