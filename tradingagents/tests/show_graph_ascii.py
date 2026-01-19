#!/usr/bin/env python3
"""
简单的StateGraph ASCII可视化工具
使用graph.get_graph().print_ascii()显示图的结构
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG


def show_ascii_graph(selected_analysts=None):
    """显示StateGraph的ASCII图形结构"""
    if selected_analysts is None:
        selected_analysts = ["market", "social", "news", "fundamentals"]
    
    print("=" * 80)
    print(f"🔍 正在创建StateGraph - 分析师: {selected_analysts}")
    print("=" * 80)
    
    try:
        # 创建TradingAgentsGraph对象
        print("🚀 创建TradingAgentsGraph...")
        ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())
        print("✅ TradingAgentsGraph创建成功!")
        
        # 获取GraphSetup对象
        graph_setup = ta.graph_setup
        print("✅ 获取GraphSetup对象成功!")
        
        # 创建StateGraph
        print(f"\n📝 正在创建StateGraph...")
        state_graph = graph_setup.setup_graph(selected_analysts)
        print("✅ StateGraph创建成功!")
        
        # 获取可打印的图对象并显示ASCII结构
        print(f"\n🎨 StateGraph ASCII结构图:")
        print("-" * 80)
        try:
            # 获取可打印的图对象
            printable_graph = state_graph.get_graph()
            # 打印ASCII图形
            printable_graph.print_ascii()
        except Exception as e:
            print(f"⚠️  ASCII打印失败: {e}")
            print("尝试备用方法...")
            
            # 备用：直接显示基本信息
            if hasattr(state_graph, 'nodes'):
                print(f"\n📍 节点 ({len(state_graph.nodes)}个):")
                for i, node in enumerate(state_graph.nodes, 1):
                    print(f"  {i:2d}. {node}")
            
            if hasattr(state_graph, 'edges'):
                print(f"\n🔗 边 ({len(state_graph.edges)}条):")
                for i, (from_node, to_node) in enumerate(state_graph.edges, 1):
                    print(f"  {i:2d}. {from_node} → {to_node}")
        
        print("-" * 80)
        return state_graph
        
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    print("🎨 StateGraph ASCII可视化工具")
    print("=" * 80)
    print("💡 这个工具使用graph.get_graph().print_ascii()显示StateGraph的结构")
    print("=" * 80)
    
    # 测试不同的分析师组合
    combinations = [
        ["market"],
        ["market", "news"],
        ["market", "social", "news"],
        ["market", "social", "news", "fundamentals"]
    ]
    
    for i, analysts in enumerate(combinations, 1):
        print(f"\n{'='*80}")
        print(f"🧪 测试组合 {i}/{len(combinations)}: {analysts}")
        print(f"{'='*80}")



        state_graph = show_ascii_graph(analysts)
        
        if state_graph:
            print(f"\n✅ 组合 {i} 显示完成")
        else:
            print(f"\n❌ 组合 {i} 显示失败")
        
        if i < len(combinations):
            input(f"\n⏸️  按回车键继续下一个组合...")
    
    print(f"\n{'='*80}")
    print("🎉 所有ASCII图形显示完成!")
    print("=" * 80)


if __name__ == "__main__":
    main()