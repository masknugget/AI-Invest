"""
财经新闻Mock数据生成器
生成500条符合Article模型的财经新闻数据
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

# ==================== 数据池 ====================

# 股票代码池（约60只）
STOCK_POOL = [
    {"code": "600519.SH", "name": "贵州茅台", "exchange": "上交所"},
    {"code": "000858.SZ", "name": "五粮液", "exchange": "深交所"},
    {"code": "300750.SZ", "name": "宁德时代", "exchange": "深交所"},
    {"code": "002594.SZ", "name": "比亚迪", "exchange": "深交所"},
    {"code": "TSLA", "name": "特斯拉", "exchange": "纳斯达克"},
    {"code": "NVDA", "name": "英伟达", "exchange": "纳斯达克"},
    {"code": "MSFT", "name": "微软", "exchange": "纳斯达克"},
    {"code": "AAPL", "name": "苹果", "exchange": "纳斯达克"},
    {"code": "BABA", "name": "阿里巴巴", "exchange": "纽交所"},
    {"code": "0700.HK", "name": "腾讯控股", "exchange": "港交所"},
    {"code": "3690.HK", "name": "美团", "exchange": "港交所"},
    {"code": "2318.HK", "name": "中国平安", "exchange": "港交所"},
    {"code": "000333.SZ", "name": "美的集团", "exchange": "深交所"},
    {"code": "000001.SZ", "name": "平安银行", "exchange": "深交所"},
    {"code": "601318.SH", "name": "中国平安", "exchange": "上交所"},
    {"code": "601398.SH", "name": "工商银行", "exchange": "上交所"},
    {"code": "601288.SH", "name": "农业银行", "exchange": "上交所"},
    {"code": "601939.SH", "name": "建设银行", "exchange": "上交所"},
    {"code": "601988.SH", "name": "中国银行", "exchange": "上交所"},
    {"code": "601088.SH", "name": "中国神华", "exchange": "上交所"},
    {"code": "601628.SH", "name": "中国人寿", "exchange": "上交所"},
    {"code": "603288.SH", "name": "海天味业", "exchange": "上交所"},
    {"code": "002415.SZ", "name": "海康威视", "exchange": "深交所"},
    {"code": "002142.SZ", "name": "宁波银行", "exchange": "深交所"},
    {"code": "300760.SZ", "name": "迈瑞医疗", "exchange": "深交所"},
    {"code": "300274.SZ", "name": "阳光电源", "exchange": "深交所"},
    {"code": "002812.SZ", "name": "恩捷股份", "exchange": "深交所"},
    {"code": "300014.SZ", "name": "亿纬锂能", "exchange": "深交所"},
    {"code": "002460.SZ", "name": "赣锋锂业", "exchange": "深交所"},
    {"code": "603259.SH", "name": "药明康德", "exchange": "上交所"},
    {"code": "000568.SZ", "name": "泸州老窖", "exchange": "深交所"},
    {"code": "603501.SH", "name": "韦尔股份", "exchange": "上交所"},
    {"code": "300124.SZ", "name": "汇川技术", "exchange": "深交所"},
    {"code": "000063.SZ", "name": "中兴通讯", "exchange": "深交所"},
    {"code": "601012.SH", "name": "隆基绿能", "exchange": "上交所"},
    {"code": "600036.SH", "name": "招商银行", "exchange": "上交所"},
    {"code": "601888.SH", "name": "中国中免", "exchange": "上交所"},
    {"code": "600900.SH", "name": "长江电力", "exchange": "上交所"},
    {"code": "600309.SH", "name": "万华化学", "exchange": "上交所"},
    {"code": "600276.SH", "name": "恒瑞医药", "exchange": "上交所"},
    {"code": "GOOGL", "name": "谷歌", "exchange": "纳斯达克"},
    {"code": "AMZN", "name": "亚马逊", "exchange": "纳斯达克"},
    {"code": "META", "name": "Meta", "exchange": "纳斯达克"},
    {"code": "NFLX", "name": "奈飞", "exchange": "纳斯达克"},
    {"code": "AMD", "name": "AMD", "exchange": "纳斯达克"},
    {"code": "INTC", "name": "英特尔", "exchange": "纳斯达克"},
    {"code": "9988.HK", "name": "阿里巴巴-SW", "exchange": "港交所"},
    {"code": "9888.HK", "name": "百度集团", "exchange": "港交所"},
    {"code": "9999.HK", "name": "网易-S", "exchange": "港交所"},
    {"code": "1810.HK", "name": "小米集团", "exchange": "港交所"},
    {"code": "1024.HK", "name": "快手-W", "exchange": "港交所"},
    {"code": "9618.HK", "name": "京东集团", "exchange": "港交所"},
    {"code": "2015.HK", "name": "理想汽车", "exchange": "港交所"},
    {"code": "9868.HK", "name": "小鹏汽车", "exchange": "港交所"},
    {"code": "2382.HK", "name": "舜宇光学", "exchange": "港交所"},
    {"code": "1299.HK", "name": "友邦保险", "exchange": "港交所"},
    {"code": "0005.HK", "name": "汇丰控股", "exchange": "港交所"},
    {"code": "0388.HK", "name": "香港交易所", "exchange": "港交所"},
]

# 新闻来源
NEWS_SOURCES = [
    {"name": "财经早报", "url": "https://finance.morning.com"},
    {"name": "华尔街见闻", "url": "https://wallstreetcn.com"},
    {"name": "财联社", "url": "https://cls.cn"},
    {"name": "证券时报", "url": "https://stcn.com"},
    {"name": "深度投研", "url": "https://research.com"},
    {"name": "每日经济新闻", "url": "https://nbd.com.cn"},
    {"name": "第一财经", "url": "https://yicai.com"},
    {"name": "新浪财经", "url": "https://finance.sina.com.cn"},
    {"name": "东方财富网", "url": "https://eastmoney.com"},
    {"name": "同花顺财经", "url": "https://10jqka.com.cn"},
    {"name": "搜狐财经", "url": "https://business.sohu.com"},
    {"name": "网易财经", "url": "https://money.163.com"},
    {"name": "腾讯财经", "url": "https://finance.qq.com"},
    {"name": "凤凰财经", "url": "https://finance.ifeng.com"},
    {"name": "21世纪经济报道", "url": "https://21jingji.com"},
    {"name": "经济观察报", "url": "https://eeo.com.cn"},
    {"name": "中国证券报", "url": "https://cs.com.cn"},
    {"name": "上海证券报", "url": "https://cnstock.com"},
    {"name": "中金公司", "url": "https://cicc.com"},
    {"name": "中信证券", "url": "https://citics.com"},
]

# 作者池
AUTHORS = [
    "张明", "李华", "王磊", "陈思远", "刘洋",
    "赵静", "孙伟", "周芳", "吴强", "郑丽",
    "黄涛", "杨帆", "徐鹏", "朱婷", "马骏",
    "胡军", "郭明", "林红", "何平", "高峰",
    "宋江", "唐丽", "许文", "邓强", "韩梅",
    "冯刚", "曹阳", "彭飞", "曾华", "肖勇",
    "田甜", "董亮", "袁浩", "蒋婷", "魏东",
    "薛峰", "余波", "潘虹", "杜娟", "戴军",
    "夏冰", "钟诚", "汪涛", "丁敏", "任翔",
    "沈悦", "姜波", "范伟", "方芳", "石磊",
]

# 分类
CATEGORIES = [
    {"id": "market", "name": "市场动态"},
    {"id": "stock", "name": "个股分析"},
    {"id": "industry", "name": "行业研究"},
    {"id": "macro", "name": "宏观经济"},
    {"id": "company", "name": "公司新闻"},
    {"id": "policy", "name": "政策解读"},
    {"id": "global", "name": "全球市场"},
    {"id": "strategy", "name": "投资策略"},
]

# 行业词汇
INDUSTRIES = [
    "新能源汽车", "白酒", "锂电池", "半导体", "人工智能",
    "云计算", "生物医药", "消费电子", "光伏", "银行",
    "保险", "证券", "房地产", "煤炭", "钢铁",
    "化工", "机械", "食品饮料", "医药", "传媒",
]

# 标题模板
TITLE_TEMPLATES = {
    "flash": [
        "【快讯】{company}{event}",
        "{company}：{news}",
        "快讯：{company}{action}",
        "突发：{company}{event}",
        "盘中异动：{company}{change}",
    ],
    "news": [
        "{company}{year}年{quarter}净利润{profit}亿元，同比{change}%",
        "{company}与{partner}达成战略合作",
        "{company}{event}，股价{reaction}",
        "{company}董事长{action}",
        "{company}发布{year}年度业绩报告",
        "{company}宣布{action}计划",
    ],
    "analysis": [
        "深度分析：{industry}板块投资逻辑",
        "{company}基本面研究：{keyword}",
        "行业观察：{industry}迎来新机遇",
        "拆解{company}：{keyword}背后的增长密码",
        "透视{industry}：龙头企业竞争力分析",
    ],
    "research": [
        "{institution}：{company}深度研究报告",
        "{institution}上调{company}评级至{rating}",
        "研报精选：{industry}景气度持续向上",
        "{institution}：{company}目标价上调至{price}元",
        "机构观点：{company}中长期投资价值凸显",
    ],
    "opinion": [
        "观点：{topic}的市场思考",
        "评论：{company}面临的挑战与机遇",
        "从{event}看{industry}的发展趋势",
        "{author}：{keyword}背后的投资机会",
        "热评：{topic}值得关注的三个信号",
    ],
}

# ==================== 辅助函数 ====================

def random_date(start: datetime, end: datetime) -> datetime:
    """生成随机日期"""
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)

def weighted_choice(choices: List[tuple]) -> Any:
    """根据权重随机选择"""
    total = sum(weight for _, weight in choices)
    r = random.uniform(0, total)
    upto = 0
    for choice, weight in choices:
        if upto + weight >= r:
            return choice
        upto += weight
    return choices[-1][0]

def generate_title(news_type: str, stock: Dict) -> str:
    """生成标题"""
    templates = TITLE_TEMPLATES.get(news_type, TITLE_TEMPLATES["news"])
    template = random.choice(templates)
    
    year = random.randint(2023, 2025)
    quarter = random.choice(["一季报", "半年报", "三季报", "年报"])
    profit = round(random.uniform(10, 500), 2)
    change = round(random.uniform(-50, 100), 1)
    revenue = round(random.uniform(100, 2000), 2)
    
    company = stock["name"]
    code = stock["code"]
    industry = random.choice(INDUSTRIES)
    partner = random.choice([s["name"] for s in STOCK_POOL if s["name"] != company])
    institution = random.choice(["中金公司", "中信证券", "华泰证券", "国泰君安", "招商证券", "广发证券", "申万宏源"])
    rating = random.choice(["买入", "增持", "持有", "推荐"])
    price = round(random.uniform(50, 800), 2)
    keyword = random.choice(["技术突破", "市场扩张", "产品创新", "成本控制", "渠道优化", "品牌升级"])
    topic = random.choice(["市场波动", "政策变化", "行业整合", "技术革新", "消费升级", "出海战略"])
    event = random.choice(["发布新品", "完成收购", "获得订单", "签署协议", "产能扩张", "技术突破"])
    action = random.choice(["回购股份", "增持股票", "分红派息", "减持套现", "股权激励"])
    news = random.choice(["业绩预增", "重大合同", "战略合作", "高管变动", "股东增减持"])
    reaction = random.choice(["大涨5%", "下跌3%", "异动拉升", "震荡调整", "涨停"])
    author = random.choice(AUTHORS)
    
    try:
        title = template.format(
            company=company,
            code=code,
            year=year,
            quarter=quarter,
            profit=profit,
            change=change,
            revenue=revenue,
            partner=partner,
            industry=industry,
            institution=institution,
            rating=rating,
            price=price,
            keyword=keyword,
            topic=topic,
            event=event,
            action=action,
            news=news,
            reaction=reaction,
            author=author,
        )
    except KeyError:
        title = f"{company}最新动态：{event}"
    
    return title

def generate_content(news_type: str, title: str, stock: Dict, source: Dict, author: str) -> str:
    """生成正文内容"""
    company = stock["name"]
    code = stock["code"]
    industry = random.choice(INDUSTRIES)
    year = random.randint(2023, 2025)
    quarter = random.choice(["一季度", "上半年", "前三季度", "全年"])
    
    # 随机价格数据
    price = round(random.uniform(50, 2000), 2)
    change_pct = round(random.uniform(-10, 15), 2)
    change_desc = f"涨{change_pct}%" if change_pct > 0 else f"跌{abs(change_pct)}%"
    
    pdate = (datetime.now() - timedelta(days=random.randint(0, 30))).strftime("%m月%d日")
    
    # 根据类型生成不同内容
    if news_type == "flash":
        news = random.choice(["业绩预增", "重大合同", "战略合作", "高管变动"])
        detail = f"公司表示将{random.choice(['持续推进', '加快布局', '深化合作', '扩大投资'])}相关业务"
        return f"【{source['name']}】{company}于{pdate}发布公告，{news}。{detail}。截至发稿，{company}股价报{price}元，{change_desc}。"
    
    elif news_type == "news":
        revenue = round(random.uniform(100, 2000), 2)
        profit = round(random.uniform(10, 500), 2)
        change = round(random.uniform(-30, 80), 1)
        market_cap = round(random.uniform(500, 30000), 0)
        business = random.choice(["白酒生产与销售", "动力电池研发制造", "互联网服务", "新能源汽车", "金融保险", "芯片设计"])
        analysis = random.choice(["看好公司长期发展", "短期或面临压力", "估值已反映预期", "建议关注后续进展"])
        
        return f"""{company}（{code}）{pdate}晚间发布公告，{title.split('：')[1] if '：' in title else title}。

{company}表示，公司{random.choice(['将继续深耕主业', '致力于提升核心竞争力', '积极应对市场变化', '坚持高质量发展'])}。

根据公告，{company}{year}年{quarter}实现营业收入{revenue}亿元，同比增长{round(random.uniform(-10, 50), 1)}%；净利润{profit}亿元，同比{change}%。

{company}是{industry}行业的龙头企业，主营业务包括{business}。

对于此次业绩表现，市场分析人士认为{analysis}。

截至目前，{company}市值约为{market_cap:.0f}亿元。"""
    
    elif news_type == "analysis":
        advantage1 = random.choice(["品牌优势明显", "技术积累深厚", "渠道覆盖广泛", "成本控制能力强"])
        advantage2 = random.choice(["研发投入持续增加", "产品结构不断优化", "市场份额稳步提升", "国际化进程加速"])
        advantage3 = random.choice(["现金流充裕", "负债率较低", "盈利能力较强", "成长空间广阔"])
        
        return f"""{company}作为{industry}行业的代表性企业，近年来{random.choice(['发展迅速', '表现稳健', '增长亮眼', '持续突破'])}。

**一、行业背景**

{industry}行业正处于{random.choice(['快速成长期', '成熟期', '转型期', '整合期'])}阶段。随着{random.choice(['政策支持力度加大', '技术不断进步', '市场需求增长', '竞争格局优化'])}，行业整体呈现向好趋势。

**二、公司竞争力分析**

{company}的核心优势主要体现在：
1. {advantage1}
2. {advantage2}
3. {advantage3}

**三、财务表现**

从财务数据来看，{company}营收和利润{random.choice(['保持双位数增长', '增速有所放缓', '实现逆势增长', '符合市场预期'])}。

**四、投资建议**

综合考虑{random.choice(['行业景气度', '公司竞争优势', '估值水平', '业绩确定性'])}等因素，建议{random.choice(['逢低关注', '长期持有', '谨慎乐观', '积极配置'])}。

风险提示：{random.choice(['行业竞争加剧', '原材料价格波动', '政策变化风险', '宏观经济下行'])}。"""
    
    elif news_type == "research":
        institution = random.choice(["中金公司", "中信证券", "华泰证券", "国泰君安"])
        rating = random.choice(["买入", "增持", "推荐"])
        target_price = round(price * random.uniform(0.9, 1.3), 2)
        eps1, eps2, eps3 = round(random.uniform(1, 10), 2), round(random.uniform(1.2, 12), 2), round(random.uniform(1.5, 15), 2)
        pe1, pe2, pe3 = random.randint(10, 50), random.randint(10, 45), random.randint(10, 40)
        
        return f"""【{institution}研报】{company}（{code}）

**投资评级**：{rating}
**目标价**：{target_price}元

**核心观点**

{company}是{industry}领域的领先企业，{random.choice(['竞争优势突出', '成长空间广阔', '业绩确定性高', '估值具有吸引力'])}。

**业绩预测**

预计{year}年-{year+2}年EPS分别为{eps1}元、{eps2}元、{eps3}元，对应PE分别为{pe1}、{pe2}、{pe3}倍。

**投资逻辑**

1. {random.choice(['行业景气度持续向上', '市场份额稳步提升', '产品结构持续优化'])}
2. {random.choice(['成本控制能力增强', '研发投入成效显著', '渠道下沉进展顺利'])}
3. {random.choice(['现金流持续向好', '分红比例有望提升', '估值处于历史低位'])}

**风险提示**

{random.choice(['宏观经济波动风险', '行业竞争加剧风险', '原材料价格上涨风险', '政策监管变化风险'])}

免责声明：本报告仅供参考，不构成投资建议。"""
    
    else:  # opinion
        return f"""{title}近期引发市场广泛关注。

从{random.choice(['基本面', '技术面', '资金面', '政策面'])}来看，{company}当前{random.choice(['估值合理', '有一定安全边际', '存在配置价值', '需要谨慎对待'])}。

从{random.choice(['行业竞争', '公司战略', '市场趋势'])}来看，{random.choice(['龙头地位稳固', '转型进展顺利', '创新投入加大', '市场份额提升'])}。

值得注意的是，{random.choice(['需关注后续业绩验证', '行业政策变化值得关注', '竞争格局或将重塑', '估值修复需要时间'])}。

对于投资者而言，建议{random.choice(['长期配置优质资产', '关注回调机会', '控制仓位风险', '做好价值投资'])}。

总的来说，{company}作为行业代表，其{random.choice(['长期投资价值', '竞争优势', '成长潜力', '管理水平'])}值得持续关注。"""

def generate_tags(news_type: str, stock: Dict) -> List[str]:
    """生成标签"""
    base_tags = [stock["name"], stock["code"].split('.')[0]]
    type_tags = {
        "flash": ["快讯", "突发"],
        "news": ["财报", "业绩", "公司新闻"],
        "analysis": ["深度", "分析", "研究"],
        "research": ["研报", "评级", "目标价"],
        "opinion": ["观点", "评论", "策略"],
    }
    extra_tags = random.sample(
        ["热门", "推荐", "必读", "关注", "重磅", "独家", "精选"],
        k=random.randint(1, 3)
    )
    return base_tags + type_tags.get(news_type, []) + extra_tags

def generate_keywords(stock: Dict) -> List[str]:
    """生成关键词"""
    return [
        stock["name"],
        stock["code"],
        random.choice(INDUSTRIES),
        random.choice(["股市", "A股", "港股", "美股"]),
        random.choice(["投资", "理财", "股票", "基金"]),
        random.choice(["业绩", "财报", "分析", "评级"]),
    ]

def generate_stock_codes() -> List[Dict]:
    """生成关联股票"""
    num = random.choices([1, 2, 3, 4], weights=[50, 30, 15, 5])[0]
    stocks = random.sample(STOCK_POOL, k=min(num, len(STOCK_POOL)))
    return [
        {
            "code": s["code"],
            "name": s["name"],
            "exchange": s["exchange"],
            "price": round(random.uniform(10, 2000), 2),
            "change_pct": round(random.uniform(-10, 10), 2),
        }
        for s in stocks
    ]

def generate_article(article_num: int) -> Dict:
    """生成单条文章数据"""
    # 确定类型（按权重）
    news_type = weighted_choice([
        ("flash", 0.20),
        ("news", 0.30),
        ("analysis", 0.25),
        ("research", 0.15),
        ("opinion", 0.10),
    ])
    
    # 确定状态
    status = weighted_choice([
        ("published", 0.70),
        ("draft", 0.15),
        ("pending", 0.10),
        ("archived", 0.05),
    ])
    
    # 确定情感
    sentiment = weighted_choice([
        ("positive", 0.40),
        ("neutral", 0.35),
        ("negative", 0.15),
        ("mixed", 0.10),
    ])
    
    # 生成基本信息
    article_id = f"article_{article_num:05d}"
    stock = random.choice(STOCK_POOL)
    source_info = random.choice(NEWS_SOURCES)
    author = random.choice(AUTHORS)
    category = random.choice(CATEGORIES)
    
    # 生成标题
    title = generate_title(news_type, stock)
    
    # 生成时间
    base_date = datetime(2024, 1, 1)
    create_time = random_date(base_date, datetime.now())
    
    if status == "published":
        publish_time = create_time + timedelta(hours=random.randint(1, 48))
    elif status == "draft":
        publish_time = None
    else:
        publish_time = create_time + timedelta(hours=random.randint(1, 24))
    
    update_time = create_time + timedelta(hours=random.randint(1, 72)) if random.random() > 0.5 else None
    
    # 生成内容
    content = generate_content(news_type, title, stock, source_info, author)
    
    # 生成摘要
    summary = f"{stock['name']}{random.choice(['最新动态', '业绩分析', '投资要点', '市场解读'])}，{random.choice(['值得关注', '建议关注', '持续跟踪', '谨慎对待'])}。"
    
    # 生成统计数据
    view_count = random.randint(100, 100000)
    like_count = int(view_count * random.uniform(0.01, 0.1))
    share_count = int(view_count * random.uniform(0.005, 0.05))
    comment_count = int(view_count * random.uniform(0.001, 0.03))
    
    # 构建文章数据
    article = {
        "article_id": article_id,
        "title": title,
        "sub_title": f"{stock['name']}：{random.choice(['业绩表现亮眼', '战略布局清晰', '竞争优势突出', '成长空间广阔'])}",
        "summary": summary,
        "content": content,
        "source": {
            "name": source_info["name"],
            "url": source_info["url"],
            "author": author,
        },
        "category_id": category["id"],
        "category_name": category["name"],
        "stock_codes": generate_stock_codes(),
        "slug": f"{article_id}-{stock['name']}-{title[:20]}",
        "seo_url": f"https://ai-invest.com/article/{article_id}",
        "language": "zh-CN",
        "status": status,
        "news_type": news_type,
        "tags": generate_tags(news_type, stock),
        "keywords": generate_keywords(stock),
        "view_count": view_count,
        "like_count": like_count,
        "share_count": share_count,
        "comment_count": comment_count,
        "create_time": create_time.isoformat(),
        "publish_time": publish_time.isoformat() if publish_time else None,
        "update_time": update_time.isoformat() if update_time else None,
        "metadata": {
            "sentiment": sentiment,
            "sentiment_score": round(random.uniform(-1, 1), 2),
            "impact_level": random.choice(["high", "medium", "low"]),
            "trading_signals": None,
            "video_url": None,
            "audio_url": None,
            "attachments": None,
            "is_paywall": random.choice([True, False, False, False]),
            "access_level": random.choice(["free", "free", "free", "vip"]),
            "region_restriction": None,
            "push_status": random.choice([None, "sent", "pending"]),
        },
    }
    
    return article

def generate_batch(start_num: int, count: int) -> List[Dict]:
    """生成一批文章"""
    return [generate_article(start_num + i) for i in range(count)]

def main():
    """主函数"""
    import os
    
    output_dir = "G:\\git_data\\AI-Invest\\mock"
    os.makedirs(output_dir, exist_ok=True)
    
    print("开始生成500条财经新闻Mock数据...")
    print()
    
    # 统计数据
    stats = {
        "news_type": {},
        "status": {},
        "sentiment": {},
    }
    
    # 生成5个文件
    for batch_num in range(1, 6):
        start_num = (batch_num - 1) * 100 + 1
        articles = generate_batch(start_num, 100)
        
        # 统计
        for article in articles:
            nt = article["news_type"]
            st = article["status"]
            se = article["metadata"]["sentiment"]
            stats["news_type"][nt] = stats["news_type"].get(nt, 0) + 1
            stats["status"][st] = stats["status"].get(st, 0) + 1
            stats["sentiment"][se] = stats["sentiment"].get(se, 0) + 1
        
        # 保存文件
        filename = f"mock_articles_{batch_num:03d}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        
        # 打印信息
        first_id = articles[0]["article_id"]
        last_id = articles[-1]["article_id"]
        print(f"[OK] {filename}: {first_id} ~ {last_id} (100条)")
    
    print()
    print("=" * 50)
    print("生成完成！数据统计：")
    print("-" * 50)
    print(f"新闻类型分布: {stats['news_type']}")
    print(f"状态分布: {stats['status']}")
    print(f"情感分布: {stats['sentiment']}")
    print("-" * 50)
    print(f"输出目录: {output_dir}")

if __name__ == "__main__":
    main()
