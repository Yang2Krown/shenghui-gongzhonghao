"""实操创作流的数据结构。

ProductResearch 是产品研究产出，对应前端「研究确认」的三块：产品定位 / 功能点 / 产品优势。
功能点（FeaturePoint）同时是「卖点选择」步骤里可勾选成实操段的候选项。
references 是筛选后的参考资料（含知乎/CSDN 等教程站 + Exa 搜来的公众号爆文），
每条带 source 标签，既在前端展示、也喂给正文生成。
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class FeaturePoint:
    """一个功能点，可被选成一个实操段。"""
    name: str                     # 功能点名称（= 实操段标题）
    desc: str = ""                # 一句话说明
    steps: List[str] = field(default_factory=list)  # 操作步骤（从教程全文提炼，写实操段的依据）
    recommend: bool = False       # AI 是否推荐入选
    reason: str = ""              # 推荐 / 略过理由

    def to_dict(self) -> dict:
        return {"name": self.name, "desc": self.desc, "steps": self.steps,
                "recommend": self.recommend, "reason": self.reason}

    @staticmethod
    def from_dict(d: dict) -> "FeaturePoint":
        return FeaturePoint(
            name=str(d.get("name", "")).strip(),
            desc=str(d.get("desc", "")).strip(),
            steps=[str(s).strip() for s in (d.get("steps") or []) if str(s).strip()],
            recommend=bool(d.get("recommend", False)),
            reason=str(d.get("reason", "")).strip(),
        )


@dataclass
class ProductResearch:
    """产品研究结果。"""
    product: str
    positioning: str = ""                    # 产品定位
    features: List[FeaturePoint] = field(default_factory=list)  # 功能点（可选成实操段）
    advantages: List[str] = field(default_factory=list)        # 产品优势
    insufficient: bool = False               # 信息不足标记
    sources: List[str] = field(default_factory=list)           # 来源链接
    references: List[dict] = field(default_factory=list)       # 参考资料 [{title,url,summary,source}]

    def to_dict(self) -> dict:
        return {
            "product": self.product,
            "positioning": self.positioning,
            "features": [f.to_dict() for f in self.features],
            "advantages": self.advantages,
            "insufficient": self.insufficient,
            "sources": self.sources,
            "references": self.references,
        }

    @staticmethod
    def from_dict(d: dict) -> "ProductResearch":
        return ProductResearch(
            product=str(d.get("product", "")).strip(),
            positioning=str(d.get("positioning", "")).strip(),
            features=[FeaturePoint.from_dict(f) for f in (d.get("features") or []) if f.get("name")],
            advantages=[str(a).strip() for a in (d.get("advantages") or []) if str(a).strip()],
            insufficient=bool(d.get("insufficient", False)),
            sources=[str(s).strip() for s in (d.get("sources") or []) if str(s).strip()],
            references=[r for r in (d.get("references") or []) if isinstance(r, dict) and r.get("url")],
        )

    def to_material_text(self) -> str:
        """格式化为正文流水线的防幻觉素材文本。"""
        lines = [f"【产品研究素材】产品：{self.product}", ""]
        if self.positioning:
            lines += ["--- 产品定位 ---", self.positioning, ""]
        if self.features:
            lines.append("--- 功能点与操作步骤 ---")
            for f in self.features:
                lines.append(f"  · {f.name}：{f.desc}" if f.desc else f"  · {f.name}")
                for j, s in enumerate(f.steps, 1):
                    lines.append(f"      步骤{j}：{s}")
            lines.append("")
        if self.advantages:
            lines.append("--- 产品优势 ---")
            for a in self.advantages:
                lines.append(f"  · {a}")
            lines.append("")
        # 参考资料原文：已经筛选过，全部带上；实操步骤据此写，别凭空编操作流程
        refs = [r for r in self.references if r.get("summary")]
        if refs:
            lines.append("--- 参考资料原文（写实操步骤时据此，尤其教程 / 公众号爆文）---")
            for r in refs:
                tag = f"[{r['source']}]" if r.get("source") else ""
                lines.append(f"  · {tag}{r.get('title', '')}：{r['summary'][:300]}")
            lines.append("")
        lines += [
            "【使用规则】",
            "- 涉及具体事实（数字、价格、版本、功能名）只能来自以上素材",
            "- 实操步骤要基于「参考资料原文」里的真实用法来写；资料没覆盖到的操作细节，",
            "  写成让读者照着做的引导（如「进入X→点击Y」）并预留截图位，不要编造不存在的按钮/路径",
            "- 素材没有的，用泛化表述，不要编造具体数据",
        ]
        if self.insufficient:
            lines.append("- 本次联网信息不足，缺失处需在正文显式标注「（信息有限）」或改用分析性表述")
        return "\n".join(lines)
