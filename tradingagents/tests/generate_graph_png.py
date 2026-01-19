#!/usr/bin/env python3
"""
StateGraph Mermaid PNG可视化工具
使用graph.draw_mermaid_png()生成图形结构图片
"""

import sys
from pathlib import Path
import os

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG


def generate_mermaid_png(selected_analysts=None, output_dir=None):
    """生成StateGraph的Mermaid PNG图片"""
    if selected_analysts is None:
        selected_analysts = ["market", "social", "news", "fundamentals"]
    
    if output_dir is None:
        output_dir = Path(__file__).parent / "graph_outputs"
    
    # 确保输出目录存在
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # 生成文件名
    analysts_str = "_".join(selected_analysts)
    output_file = output_dir / f"stategraph_{analysts_str}.png"
    
    print("=" * 80)
    print(f"🎨 正在生成Mermaid PNG - 分析师: {selected_analysts}")
    print(f"📁 输出文件: {output_file}")
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
        
        # 生成Mermaid PNG
        print(f"\n🖼️  正在生成Mermaid PNG图片...")
        try:
            # 获取可打印的图对象
            printable_graph = state_graph.get_graph()
            
            # 生成PNG图片
            png_data = printable_graph.draw_mermaid_png()
            
            # 保存到文件
            with open(output_file, 'wb') as f:
                f.write(png_data)
            
            print(f"✅ PNG图片生成成功!")
            print(f"📄 文件路径: {output_file.absolute()}")
            
            # 显示文件大小
            file_size = output_file.stat().st_size
            print(f"📊 文件大小: {file_size:,} 字节 ({file_size/1024:.1f} KB)")
            
            return output_file
            
        except ImportError as e:
            print(f"⚠️  生成PNG需要额外依赖: {e}")
            print("💡 请安装: pip install pillow playwright")
            print("💡 然后运行: playwright install")
            
            # 备用方案：生成Mermaid文本
            print(f"\n📝 生成Mermaid文本格式...")
            try:
                mermaid_text = printable_graph.draw_mermaid()
                txt_file = output_file.with_suffix('.mmd')
                with open(txt_file, 'w', encoding='utf-8') as f:
                    f.write(mermaid_text)
                print(f"✅ Mermaid文本生成成功: {txt_file}")
                return txt_file
                
            except Exception as e2:
                print(f"❌ Mermaid文本也生成失败: {e2}")
                return None
                
        except Exception as e:
            print(f"❌ PNG生成失败: {e}")
            
            # 备用方案：显示基本信息
            print(f"\n📋 StateGraph基本信息:")
            if hasattr(state_graph, 'nodes'):
                print(f"  节点数量: {len(state_graph.nodes)}")
                print(f"  节点列表: {list(state_graph.nodes)}")
            
            if hasattr(state_graph, 'edges'):
                print(f"  边数量: {len(state_graph.edges)}")
                print(f"  连接关系: {list(state_graph.edges)}")
            
            return None
        
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    print("🎨 StateGraph Mermaid PNG生成工具")
    print("=" * 80)
    print("💡 这个工具使用graph.draw_mermaid_png()生成StateGraph的图片")
    print("💡 可以直观地看到图的结构和节点间的连接关系")
    print("=" * 80)
    
    # 设置输出目录
    output_dir = Path(__file__).parent / "graph_outputs"
    
    # 测试不同的分析师组合
    combinations = [
        ["market"],
        ["market", "news"],
        ["market", "social", "news"],
        ["market", "social", "news", "fundamentals"]
    ]
    
    generated_files = []
    
    for i, analysts in enumerate(combinations, 1):
        print(f"\n{'='*80}")
        print(f"🧪 生成组合 {i}/{len(combinations)}: {analysts}")
        print(f"{'='*80}")
        
        output_file = generate_mermaid_png(analysts, output_dir)
        
        if output_file:
            generated_files.append(output_file)
            print(f"\n✅ 组合 {i} 生成成功")
        else:
            print(f"\n❌ 组合 {i} 生成失败")
        
        if i < len(combinations):
            input(f"\n⏸️  按回车键继续下一个组合...")
    
    print(f"\n{'='*80}")
    print("🎉 所有Mermaid图片生成完成!")
    print(f"📁 输出目录: {output_dir.absolute()}")
    print(f"📄 生成文件数量: {len(generated_files)}")
    
    if generated_files:
        print("\n📋 生成的文件:")
        for i, file in enumerate(generated_files, 1):
            print(f"  {i:2d}. {file.name}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()