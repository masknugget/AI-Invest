"""
简化版推荐引擎
支持用户个性化的股票推荐
"""

import json
import logging
from typing import List, Optional
from datetime import datetime, timedelta

from tradingagents.llm_adapters.embeddings import create_dashscope_embeddings

from recommender.models import UserProfile, StockBrief, Recommendation, RiskLevel, InvestmentStyle
from recommender.stock_scanner import get_all_stocks, get_all_symbols

logger = logging.getLogger(__name__)


class SimpleRecommender:
    """
    简化版推荐引擎
    
    流程:
    1. 根据用户画像筛选候选 (本地)
    2. LLM根据用户偏好评分 (API调用)
    3. 返回Top-K推荐
    """
    
    def __init__(self):
        self.embeddings = create_dashscope_embeddings()
        logger.info("SimpleRecommender 初始化完成")
    
    def recommend(
        self,
        user: UserProfile,
        market: str = "cn",
        top_k: int = 5
    ) -> List[Recommendation]:
        """
        为用户推荐股票
        
        Args:
            user: 用户画像
            market: 市场
            top_k: 推荐数量
            
        Returns:
            推荐列表
        """
        logger.info(f"为用户 {user.user_id} 生成推荐: {user.style.value}")
        
        # 1. 获取并筛选候选
        candidates = self._get_candidates(user, market, max_candidates=50)
        if not candidates:
            logger.warning("没有符合条件的候选股票")
            return []
        
        logger.info(f"候选股票: {len(candidates)} 只")
        
        # 2. LLM个性化评分
        recommendations = self._llm_rank(user, candidates, top_k)
        
        logger.info(f"生成推荐: {len(recommendations)} 只")
        return recommendations
    
    def _get_candidates(
        self,
        user: UserProfile,
        market: str,
        max_candidates: int = 50
    ) -> List[StockBrief]:
        """获取符合条件的候选股票"""
        
        # 获取所有股票基础数据
        stocks = get_all_stocks(
            market=market,
            fields=["symbol", "name", "industry", "pe_ttm", "pb", 
                   "roe", "dv_ttm", "total_mv"]
        )
        
        candidates = []
        for s in stocks:
            # 跳过排除行业
            industry = s.get("industry", "")
            if industry in user.excluded_industries:
                continue
            
            # 基本面过滤
            pe = self._to_float(s.get("pe_ttm"))
            pb = self._to_float(s.get("pb"))
            roe = self._to_float(s.get("roe"))
            dividend = self._to_float(s.get("dv_ttm"))
            market_cap = self._to_float(s.get("total_mv"))
            
            # 根据用户偏好过滤
            if not self._pass_filter(user, pe, pb, roe, dividend, market_cap):
                continue
            
            # 偏好行业加分（排序用）
            score = 0
            if industry in user.preferred_industries:
                score += 10
            
            candidates.append((score, StockBrief(
                symbol=s.get("symbol", ""),
                name=s.get("name", ""),
                industry=industry,
                pe=pe,
                pb=pb,
                roe=roe,
                dividend_yield=dividend,
                market_cap=market_cap
            )))
        
        # 按偏好排序，取前N
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [c[1] for c in candidates[:max_candidates]]
    
    def _pass_filter(
        self,
        user: UserProfile,
        pe: Optional[float],
        pb: Optional[float],
        roe: Optional[float],
        dividend: Optional[float],
        market_cap: Optional[float]
    ) -> bool:
        """检查是否通过用户筛选条件"""
        
        # 用户自定义PE上限
        if user.max_pe is not None and pe is not None and pe > user.max_pe:
            return False
        
        # 用户自定义股息率下限
        if user.min_dividend_yield is not None and dividend is not None:
            if dividend < user.min_dividend_yield:
                return False
        
        # 根据投资风格默认条件
        if user.style == InvestmentStyle.VALUE:
            # 价值投资：PE<30, PB<5, ROE>5%
            if pe is not None and pe > 30:
                return False
            if pb is not None and pb > 5:
                return False
            if roe is not None and roe < 5:
                return False
                
        elif user.style == InvestmentStyle.GROWTH:
            # 成长投资：允许高PE，但ROE>8%
            if roe is not None and roe < 8:
                return False
                
        elif user.style == InvestmentStyle.DIVIDEND:
            # 股息投资：股息率>2%
            if dividend is not None and dividend < 0.02:
                return False
        
        # 保守型：过滤小市值
        if user.risk_level == RiskLevel.CONSERVATIVE:
            if market_cap is not None and market_cap < 100:  # 100亿
                return False
        
        return True
    
    def _llm_rank(
        self,
        user: UserProfile,
        candidates: List[StockBrief],
        top_k: int
    ) -> List[Recommendation]:
        """LLM评分排序"""
        
        # 构建提示词
        prompt = self._build_prompt(user, candidates, top_k)
        
        try:
            # 调用LLM
            response = self._call_llm(prompt)
            
            # 解析结果
            return self._parse_response(response)
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return []
    
    def _build_prompt(
        self,
        user: UserProfile,
        candidates: List[StockBrief],
        top_k: int
    ) -> str:
        """构建LLM提示词"""
        
        # 构建候选股票列表
        stocks_text = "\n".join([
            f"{i+1}. {s.name}({s.symbol}) - {s.industry} "
            f"PE:{s.pe:.1f if s.pe else 'N/A'} "
            f"PB:{s.pb:.1f if s.pb else 'N/A'} "
            f"ROE:{s.roe:.1f if s.roe else 'N/A'}% "
            f"股息:{s.dividend_yield:.1f if s.dividend_yield else 'N/A'}%"
            for i, s in enumerate(candidates)
        ])
        
        prompt = f"""作为专业投资顾问，请根据用户的个人画像，从以下候选股票中推荐最合适的{top_k}只。

{user.to_prompt_context()}

候选股票列表:
{stocks_text}

请严格按照以下JSON格式输出推荐结果（只输出JSON，不要有其他内容）:
{{
    "recommendations": [
        {{
            "symbol": "股票代码",
            "name": "股票名称",
            "score": 85,
            "reason": "推荐理由（50字以内）",
            "risk_level": "低/中/高",
            "suggested_holding_period": "建议持有期（如：3-6个月）",
            "tags": ["标签1", "标签2"]
        }}
    ]
}}

注意:
1. 必须充分考虑用户的风险承受能力和投资风格
2. 推荐理由要个性化，体现为什么适合这位用户
3. 保守型用户推荐低风险股票，激进型可接受更高波动
4. score范围0-100，分数越高越推荐
"""
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        from openai import OpenAI
        
        client = OpenAI(
            api_key=self.embeddings.client.api_key,
            base_url=self.embeddings.client.base_url
        )
        
        response = client.chat.completions.create(
            model="qwen-turbo",
            messages=[
                {"role": "system", "content": "你是专业的投资顾问，擅长根据客户需求提供个性化的股票推荐。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=1500
        )
        
        return response.choices[0].message.content
    
    def _parse_response(self, response: str) -> List[Recommendation]:
        """解析LLM响应"""
        try:
            # 提取JSON
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            
            data = json.loads(json_str.strip())
            
            recommendations = []
            for item in data.get("recommendations", []):
                rec = Recommendation(
                    symbol=item["symbol"],
                    name=item["name"],
                    score=float(item["score"]),
                    reason=item["reason"],
                    risk_level=item["risk_level"],
                    suggested_holding_period=item["suggested_holding_period"],
                    tags=item.get("tags", [])
                )
                recommendations.append(rec)
            
            # 按分数排序
            recommendations.sort(key=lambda x: x.score, reverse=True)
            return recommendations
            
        except Exception as e:
            logger.error(f"解析响应失败: {e}\n响应: {response}")
            return []
    
    @staticmethod
    def _to_float(value) -> Optional[float]:
        """安全转float"""
        if value is None:
            return None
        try:
            return float(value)
        except:
            return None


# 便捷函数
def recommend_for_user(
    user_id: str,
    risk_level: str = "稳健型",
    style: str = "价值投资",
    top_k: int = 5
) -> List[Recommendation]:
    """
    为用户推荐股票的便捷函数
    
    Args:
        user_id: 用户ID
        risk_level: 风险等级 (保守型/稳健型/激进型)
        style: 投资风格 (价值投资/成长投资/股息投资/趋势投资)
        top_k: 推荐数量
    """
    # 解析参数
    risk_map = {
        "保守型": RiskLevel.CONSERVATIVE,
        "稳健型": RiskLevel.MODERATE,
        "激进型": RiskLevel.AGGRESSIVE,
    }
    style_map = {
        "价值投资": InvestmentStyle.VALUE,
        "成长投资": InvestmentStyle.GROWTH,
        "股息投资": InvestmentStyle.DIVIDEND,
        "趋势投资": InvestmentStyle.MOMENTUM,
    }
    
    user = UserProfile(
        user_id=user_id,
        risk_level=risk_map.get(risk_level, RiskLevel.MODERATE),
        style=style_map.get(style, InvestmentStyle.VALUE)
    )
    
    engine = SimpleRecommender()
    return engine.recommend(user, top_k=top_k)
