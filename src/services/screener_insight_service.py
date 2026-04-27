import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from src.storage import DatabaseManager, ScreenerInsight

logger = logging.getLogger(__name__)


class ScreenerInsightService:
    """LLM 增强分析服务 — 对选股 Top N 结果进行深度解读。"""

    INSIGHT_SYSTEM_PROMPT = (
        "你是一位专业的A股量化分析师。你的任务是对选股系统筛选出的优质标的进行深度解读，"
        "帮助投资者理解量化信号背后的逻辑和风险。"
        "请基于提供的数据给出客观、专业的分析，避免主观臆断。"
        "输出使用中文，各部分用明确的标题分隔。"
    )

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._analyzer = None
        self._search_service = None

    def _get_analyzer(self):
        if self._analyzer is not None:
            return self._analyzer
        try:
            from src.analyzer import GeminiAnalyzer
            from src.config import get_config
            config = get_config()
            if config.gemini_api_key or config.openai_api_key:
                self._analyzer = GeminiAnalyzer(api_key=config.gemini_api_key)
                if not self._analyzer.is_available():
                    logger.warning("[ScreenerInsight] LLM 分析器不可用")
                    self._analyzer = None
        except Exception as exc:
            logger.warning("[ScreenerInsight] 初始化 LLM 分析器失败: %s", exc)
        return self._analyzer

    def _get_search_service(self):
        if self._search_service is not None:
            return self._search_service
        try:
            from src.search_service import get_search_service
            self._search_service = get_search_service()
        except Exception as exc:
            logger.warning("[ScreenerInsight] 初始化搜索服务失败: %s", exc)
        return self._search_service

    def generate_insights(
        self,
        candidates: List[Dict[str, Any]],
        screen_date: date,
        market_regime: Optional[str] = None,
        market_regime_label: Optional[str] = None,
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        """为 Top N 候选股批量生成 AI 洞察。

        Returns:
            {"generated": int, "skipped": int, "errors": int}
        """
        analyzer = self._get_analyzer()
        if not analyzer:
            logger.warning("[ScreenerInsight] LLM 不可用，跳过洞察生成")
            return {"generated": 0, "skipped": len(candidates), "errors": 0, "reason": "llm_unavailable"}

        search = self._get_search_service()

        generated = 0
        errors = 0

        for candidate in candidates:
            code = candidate.get("code", "")
            name = candidate.get("name", "")
            try:
                if self._has_insight(screen_date, code) and not force_regenerate:
                    logger.debug("[ScreenerInsight] %s(%s) 洞察已存在，跳过", name, code)
                    continue

                news_text = self._fetch_news(search, code, name)
                prompt = self._build_prompt(candidate, news_text, market_regime, market_regime_label)

                logger.info("[ScreenerInsight] 生成 %s(%s) 洞察...", name, code)
                result_text = analyzer.generate_text(prompt, max_tokens=2048, temperature=0.5)

                if result_text:
                    sections = self._parse_sections(result_text)
                    self._save_insight(screen_date, code, name, sections, model_used="llm")
                    generated += 1
                else:
                    errors += 1
                    logger.warning("[ScreenerInsight] %s(%s) LLM 返回空结果", name, code)
            except Exception as exc:
                errors += 1
                logger.warning("[ScreenerInsight] 生成 %s(%s) 洞察失败: %s", name, code, exc)

        return {"generated": generated, "skipped": len(candidates) - generated - errors, "errors": errors}

    def get_insight(self, screen_date: date, code: str) -> Optional[Dict[str, Any]]:
        return self._get_insight(screen_date, code)

    def get_insights_by_date(self, screen_date: date) -> List[Dict[str, Any]]:
        with self.db.get_session() as session:
            rows = session.query(ScreenerInsight).filter(
                ScreenerInsight.screen_date == screen_date
            ).order_by(ScreenerInsight.id).all()
            return [self._insight_to_dict(r) for r in rows]

    def _get_insight(self, screen_date: date, code: str) -> Optional[Dict[str, Any]]:
        with self.db.get_session() as session:
            row = session.query(ScreenerInsight).filter(
                ScreenerInsight.screen_date == screen_date,
                ScreenerInsight.code == code,
            ).first()
            if row is None:
                return None
            return self._insight_to_dict(row)

    def _has_insight(self, screen_date: date, code: str) -> bool:
        with self.db.get_session() as session:
            return session.query(ScreenerInsight).filter(
                ScreenerInsight.screen_date == screen_date,
                ScreenerInsight.code == code,
            ).first() is not None

    def _fetch_news(self, search, code: str, name: str) -> str:
        if not search:
            logger.warning("[ScreenerInsight] 搜索服务未初始化，%s(%s) 无法获取新闻", name, code)
            return ""
        try:
            resp = search.search_stock_news(code, name, max_results=5)
            if resp and resp.results:
                items = []
                for r in resp.results[:5]:
                    items.append(f"- {r.title}: {getattr(r, 'snippet', '')}")
                logger.info("[ScreenerInsight] %s(%s) 获取到 %d 条新闻", name, code, len(resp.results))
                return "\n".join(items)
            else:
                logger.info("[ScreenerInsight] %s(%s) 搜索返回空结果", name, code)
        except Exception as exc:
            logger.warning("[ScreenerInsight] 获取 %s(%s) 新闻失败: %s", name, code, exc)
        return ""

    def _build_prompt(
        self,
        candidate: Dict[str, Any],
        news_text: str,
        market_regime: Optional[str],
        market_regime_label: Optional[str],
    ) -> str:
        code = candidate.get("code", "")
        name = candidate.get("name", "")
        score = candidate.get("score", 0)
        quality_tier = candidate.get("quality_tier", "")
        quality_tier_label = candidate.get("quality_tier_label", "")
        price = candidate.get("price", 0)
        market_cap = candidate.get("market_cap", 0)
        pe_ratio = candidate.get("pe_ratio")
        turnover_rate = candidate.get("turnover_rate")
        signals = candidate.get("signals", {})
        strategy_scores = candidate.get("strategy_scores", {})

        market_cap_yi = f"{market_cap / 1e8:.1f}亿" if market_cap else "N/A"
        pe_str = f"{pe_ratio:.1f}" if pe_ratio else "N/A"
        turnover_str = f"{turnover_rate:.2f}%" if turnover_rate else "N/A"

        triggered_strategies = strategy_scores.get("triggered_strategies", [])
        strategy_lines = []
        for s in triggered_strategies[:5]:
            strategy_lines.append(
                f"  - {s.get('display_name', s.get('name', ''))}: "
                f"得分{s.get('score', 0):.1f}, 权重{s.get('weight', 0):.3f}"
            )
        strategy_text = "\n".join(strategy_lines) if strategy_lines else "  无显著触发策略"

        category_breakdown = strategy_scores.get("category_breakdown", {})
        category_lines = []
        for cat, info in category_breakdown.items():
            category_lines.append(f"  - {cat}: 均分{info.get('avg_score', 0):.1f}, 权重{info.get('weight', 0):.2f}")
        category_text = "\n".join(category_lines) if category_lines else "  无"

        regime_text = market_regime_label or market_regime or "N/A"

        news_section = ""
        if news_text:
            news_section = f"""
## 近期新闻
{news_text}
"""

        return f"""请对以下选股系统筛选出的股票进行深度解读分析：

## 股票基本信息
- 代码: {code}
- 名称: {name}
- 综合评分: {score:.2f}/100
- 质量等级: {quality_tier_label or quality_tier}
- 当前价格: ¥{price:.2f}
- 市值: {market_cap_yi}
- PE: {pe_str}
- 换手率: {turnover_str}

## 市场环境
- 当前市场状态: {regime_text}

## 触发的策略信号
{strategy_text}

## 策略类别得分
{category_text}
{news_section}
---

请按以下格式输出分析结果（每个标题必须严格一致）：

### 新闻解读
基于近期新闻，分析该股票面临的主要利好和利空因素。如无新闻数据，说明"暂无近期新闻数据"并基于已知信息推断。

### 信号解读
解读量化策略信号的含义：为什么这些策略被触发？信号之间是否存在矛盾？综合来看技术面是否支持？

### 板块联动
分析该股票所属板块的整体表现和联动效应，是否有板块轮动或资金集中流入的迹象。

### 风险提示
指出该股票当前面临的主要风险，包括但不限于：估值风险、技术面风险、行业风险、流动性风险等。

### 综合评估
给出对该股票的总体评价（1-2段），明确表达看多/中性/谨慎的态度及理由。"""

    def _parse_sections(self, text: str) -> Dict[str, str]:
        sections = {
            "news_summary": "",
            "signal_interpretation": "",
            "sector_correlation": "",
            "risk_warnings": "",
            "overall_assessment": "",
        }
        mapping = {
            "新闻解读": "news_summary",
            "信号解读": "signal_interpretation",
            "板块联动": "sector_correlation",
            "风险提示": "risk_warnings",
            "综合评估": "overall_assessment",
        }
        current_key = None
        current_lines: List[str] = []

        for line in text.split("\n"):
            stripped = line.strip()
            header_found = False
            for cn_key, en_key in mapping.items():
                if stripped.startswith("###") and cn_key in stripped:
                    if current_key and current_lines:
                        sections[current_key] = "\n".join(current_lines).strip()
                    current_key = en_key
                    current_lines = []
                    header_found = True
                    break
            if not header_found:
                if current_key:
                    current_lines.append(line)

        if current_key and current_lines:
            sections[current_key] = "\n".join(current_lines).strip()

        return sections

    def _save_insight(
        self,
        screen_date: date,
        code: str,
        name: str,
        sections: Dict[str, str],
        model_used: str = "llm",
    ) -> None:
        with self.db.get_session() as session:
            existing = session.query(ScreenerInsight).filter(
                ScreenerInsight.screen_date == screen_date,
                ScreenerInsight.code == code,
            ).first()
            if existing:
                existing.news_summary = sections.get("news_summary", "")
                existing.signal_interpretation = sections.get("signal_interpretation", "")
                existing.sector_correlation = sections.get("sector_correlation", "")
                existing.risk_warnings = sections.get("risk_warnings", "")
                existing.overall_assessment = sections.get("overall_assessment", "")
                existing.model_used = model_used
                existing.generated_at = datetime.now()
            else:
                row = ScreenerInsight(
                    screen_date=screen_date,
                    code=code,
                    name=name,
                    news_summary=sections.get("news_summary", ""),
                    signal_interpretation=sections.get("signal_interpretation", ""),
                    sector_correlation=sections.get("sector_correlation", ""),
                    risk_warnings=sections.get("risk_warnings", ""),
                    overall_assessment=sections.get("overall_assessment", ""),
                    model_used=model_used,
                    generated_at=datetime.now(),
                )
                session.add(row)
            session.commit()

    @staticmethod
    def _insight_to_dict(row: ScreenerInsight) -> Dict[str, Any]:
        return {
            "id": row.id,
            "screenDate": row.screen_date.isoformat() if row.screen_date else None,
            "code": row.code,
            "name": row.name,
            "newsSummary": row.news_summary,
            "signalInterpretation": row.signal_interpretation,
            "sectorCorrelation": row.sector_correlation,
            "riskWarnings": row.risk_warnings,
            "overallAssessment": row.overall_assessment,
            "modelUsed": row.model_used,
            "generatedAt": row.generated_at.isoformat() if row.generated_at else None,
        }
