# 信贷分析工具开发文档（无数据库架构版，适合 Codex）

## 0. 概要

### 0.1 项目目标

构建一套内部使用的**信贷分析 Web 工具**，基于：

* 公开网络信息（工商、新闻、舆情、行业信息等）；
* 企业最近 **3 年年度财务报表**（利润表、资产负债表、现金流量表）；

按照“两本书”总结出的**企业 / 小微信贷通用分析逻辑**（5C + 现金流为核心），自动完成：

1. **自动分析与评分**

   * 计算关键财务指标和趋势；
   * 使用规则 + 评分卡给出风险得分与风险等级；
   * 用大模型对指标做解释，对风险做总结与提出缓释建议。

2. **生成结构化信贷分析报告**

   * 固定结构：行业 → 企业 → 财务 → 综合结论；
   * 提供 Markdown / HTML 在线预览与 PDF / Word 导出。

3. **保证可解释性与可追溯性**

   * 所有得分来自明确的规则与指标，支持“为什么打这个分”的解释；
   * 网络信息标记为“公开来源，仅供参考”。

### 0.2 使用角色

* **客户经理**：录入企业信息和财报，发起分析，查看报告；
* **风控人员**：审核分析结果，关注评分及关键风险点；
* **管理层**：通过 Dashboard 查看整体分析数量与风险分布；
* **管理员**：配置大模型供应商、评分卡参数、报告模板等。

---

## 1. 业务逻辑与方法论

工具内部采用 5C 框架 + 现金流导向，与《信贷分析与公司贷款》《小微企业信贷工作笔记》的共通逻辑一致：

### 1.1 分析逻辑步骤

1. **宏观与行业（Conditions）**

   * 行业生命周期：成长/成熟/衰退；
   * 行业规模、竞争格局、政策与监管环境；
   * 行业主要风险与机会，由网络信息 + 大模型总结。

2. **企业与主体信用（Character & Business）**

   * 工商信息：成立时间、实收资本、法定代表人、经营范围；
   * 实际控制人/主要经营者的背景：经验年限、有无严重负面；
   * 商业模式：产品/服务、客户/供应商结构、账期与回款模式。

3. **财务与现金流（Capacity）**

   * 基于 3 年财报计算：

     * 盈利能力：收入增长、毛利率、净利率、ROE/ROA（如数据足够）；
     * 杠杆与偿债：资产负债率、有息负债比例、利息保障倍数；
     * 营运效率：应收账款周转天数、存货周转天数、应付周转天数、现金转换周期；
     * 现金流质量：经营性现金流 vs 净利润，三年走势。

4. **担保与抵押（Collateral）**

   * 有则分析：抵押物类型、覆盖率、变现难度；
   * 无则按“无抵押”逻辑，提醒风控关注。

5. **综合结论与建议**

   * 多维度评分：行业 / 主体 / 业务 / 财务 / 担保；
   * 计算总分并映射风险等级 A/B/C/D；
   * 列出关键风险点 + 风险缓释建议（例如缩短期限、要求增信）。

### 1.2 评分维度与等级规则（业务层）

* 维度：

  * 行业风险（Industry）
  * 主体信用（Character）
  * 业务与经营风险（Business）
  * 财务与现金流（Financial / Capacity）
  * 抵押与担保（Collateral）

* 每维 0–20 分，总分 100，等级：

  * A：≥85
  * B：70–84
  * C：55–69
  * D：<55

> 评分的**计算逻辑由规则引擎实现**（基于指标阈值、区间、红线项等），大模型不直接参与“打分”，只解释“为什么”。

---

## 2. 系统总体架构（前端 / 后端 / 中间层）

### 2.1 分层结构

1. **前端 Web 应用**

   * 技术：React / Vue + TypeScript + UI 组件库（建议 Ant Design）。
   * 职责：

     * 表单录入企业信息和 3 年财报；
     * 展示分析进度、风险评分、详细报告；
     * 提供仪表盘与历史分析列表。

2. **后端 API 服务**

   * 技术：Python + FastAPI / Django REST Framework。
   * 职责：

     * 提供 REST API；

     * 组织分析流程（Orchestrator）；

     * 财务指标计算；

     * 调用规则引擎进行评分；

     * 调用中间层 LLM + 搜索服务；

     * 生成 Markdown/HTML 报告，并提供导出接口。

   > 数据持久化采用何种数据库/ORM、表结构如何设计，由后续数据库设计文档决定，此处不展开。

3. **中间层智能服务**

   * `LLMService`：封装大模型调用、多供应商路由、Prompt 模板管理；
   * `WebSearchService`：封装工商/搜索接口，统一对接外部世界。

4. **外部资源**

   * 大模型 API（多供应商 / 聚合商）；
   * 搜索引擎/工商信息 API；
   * PDF/Word 生成工具（如 wkhtmltopdf 或 Docx 模板引擎）。

### 2.2 单次分析调用链（概览）

1. 前端：客户经理提交“企业基础信息 + 3 年结构化财报”；
2. 后端：

   * 调用 `WebSearchService` → 获取工商 + 新闻 + 行业简要；
   * 财务模块解析报表 → 计算各项指标；
   * 规则引擎 → 计算 5 维得分 + 总分 + 风险等级；
   * 调 `LLMService` → 分别生成行业分析、财务解读、综合风险总结与建议；
   * 组合生成报告，返回前端。
3. 前端：展示分析详情页 + 报告预览页，支持导出 PDF/Word。

---

## 3. 后端服务设计（API 与模块）

### 3.1 关键 REST API（不含持久化细节）

#### `POST /api/v1/analysis`

**功能**：创建并执行一次完整信贷分析（同步返回结果为主，必要时可设计异步模式）。

请求体示例（结构化财报）：

```json
{
  "customer": {
    "name": "珠海某某科技有限公司",
    "uscc": "9144xxxxxxxxxxxxx",
    "region": "广东省珠海市",
    "industry_code": "C39"
  },
  "financial_statements": [
    {
      "year": 2022,
      "income_statement": { /* 营业收入、成本、费用等 */ },
      "balance_sheet": { /* 资产负债项目 */ },
      "cashflow_statement": { /* 经营/投资/筹资现金流 */ }
    },
    {
      "year": 2023,
      "income_statement": { /* ... */ },
      "balance_sheet": { /* ... */ },
      "cashflow_statement": { /* ... */ }
    },
    {
      "year": 2024,
      "income_statement": { /* ... */ },
      "balance_sheet": { /* ... */ },
      "cashflow_statement": { /* ... */ }
    }
  ],
  "collateral_info": {
    "has_collateral": false
    // 可选：若有抵押，可附类型、评估值等
  }
}
```

响应示例：

```json
{
  "analysis_id": "uuid-or-integer",
  "status": "SUCCESS",
  "total_score": 78,
  "risk_level": "B",
  "summary": {
    "headline": "客户整体风险中等，盈利能力尚可但现金流走弱",
    "key_risks": [
      "客户集中度偏高",
      "毛利率下滑导致盈利空间收窄",
      "经营性现金流连续下降"
    ],
    "suggestions": [
      "控制单一客户授信敞口比例",
      "要求增加保证金或引入保证人",
      "缩短授信期限并设置触发预警条款"
    ]
  }
}
```

#### `GET /api/v1/analysis/{id}`

**功能**：获取某次分析的完整详情（用于“分析详情页”）。

返回内容示例（简要结构）：

```json
{
  "analysis_id": "123",
  "customer": { "name": "珠海某某科技有限公司", "industry_code": "C39", "region": "广东珠海" },
  "status": "SUCCESS",
  "total_score": 78,
  "risk_level": "B",
  "scores": {
    "industry": 14,
    "character": 18,
    "business": 15,
    "financial": 16,
    "collateral": 15
  },
  "metrics": { /* 财务指标 JSON */ },
  "web_profile": { /* 工商+网络画像抽象 */ },
  "llm_sections": {
    "industry_analysis": "……",
    "financial_analysis": "……",
    "risk_summary": "……"
  },
  "report_html": "<html>...</html>",
  "created_at": "2025-11-14T10:00:00Z"
}
```

#### `GET /api/v1/analysis`

**功能**：分页查询分析列表（用于“分析列表页”）。

支持查询参数：时间范围、行业、风险等级、操作人等。

#### `GET /api/v1/analysis/{id}/report`

**功能**：获取报告内容（Markdown / HTML），用于前端预览及导出。

---

### 3.2 后端模块划分

1. **AnalysisOrchestrator**

   * 负责串起完整流程：

     * 保存输入 → 调 WebSearchService → 计算指标 → 评分 → 调 LLMService → 生成报告。

2. **FinancialMetricsService**

   * 从 3 年财报中计算：

     * 盈利指标、杠杆指标、周转指标、现金流指标等。

3. **ScorecardEngine**

   * 将指标与规则配置结合，输出：

     * 各维度得分、总分、风险等级；
     * 触发的关键规则，用于“评分与规则”页面展示。

4. **ReportGenerator**

   * 接收：客户信息、网络画像、指标、评分结果、大模型各段文字；
   * 渲染 Markdown/HTML 模板，并提供导出为 PDF / Word 功能。

5. **LLMProxyClient**

   * 与中间层的 `LLMService` 通信，发起大模型任务。

6. **SearchProxyClient**

   * 与 `WebSearchService` 通信，获取工商+搜索结果。

---

### 3.3 Orchestrator 伪代码（Codex 可直接展开）

```python
async def run_full_analysis(request: AnalysisRequest) -> AnalysisResult:
    # 1. 记录/更新企业基础信息（持久化细节在别处设计）
    customer = upsert_customer(request.customer)

    # 2. 创建分析任务记录（状态 PENDING → RUNNING）
    analysis = create_analysis_record(customer, status="RUNNING")

    try:
        # 3. 调用 WebSearchService 获取网络画像
        web_profile = await web_search_service.enrich_company_profile(
            name=customer.name,
            uscc=customer.uscc,
            region=customer.region,
        )

        # 4. 财务指标计算
        metrics = financial_metrics_service.compute(request.financial_statements)

        # 5. 规则评分
        score_result = scorecard_engine.compute(metrics=metrics, web_profile=web_profile)

        # 6. 调 LLM 生成文字部分
        industry_text = await llm_service.generate_industry_analysis(
            web_profile=web_profile,
            metrics=metrics,
        )
        financial_text = await llm_service.explain_financials(metrics=metrics)
        risk_summary = await llm_service.summarize_risks(
            score_result=score_result,
            metrics=metrics,
            web_profile=web_profile,
        )

        # 7. 组合生成报告
        report_html = report_generator.render_html(
            customer=customer,
            web_profile=web_profile,
            metrics=metrics,
            score_result=score_result,
            industry_text=industry_text,
            financial_text=financial_text,
            risk_summary=risk_summary,
        )

        # 8. 更新分析记录为 SUCCESS，并存储核心结果
        mark_analysis_success(
            analysis,
            total_score=score_result.total_score,
            risk_level=score_result.risk_level,
            summary=risk_summary,
            report_html=report_html,
        )

        # 9. 返回响应 DTO
        return build_analysis_result_dto(analysis)

    except Exception as e:
        mark_analysis_failed(analysis, error=str(e))
        raise
```

---

## 4. 中间层智能服务：LLM & 搜索

### 4.1 LLMService 设计

#### 4.1.1 目标

* 屏蔽不同大模型供应商与聚合商差异；
* 按“任务类型”选择合适模型（行业分析 / 财务解释 / 综合风险总结 / 报告分段等）；
* 统一管理 Prompt 模板与调用日志、错误重试。

#### 4.1.2 关键任务类型

* `INDUSTRY_ANALYSIS`：行业与环境分析段落；
* `FINANCIAL_EXPLAIN`：财务指标解释与异常说明；
* `RISK_SUMMARY`：综合风险评估与缓释建议；
* `COMPANY_PROFILE_ENRICH`：根据工商 + 搜索结果补全企业画像；
* `REPORT_SECTION`：生成报告某一节的完整文本（如有需要）。

#### 4.1.3 伪代码示例

```python
class LLMService:
    def __init__(self, router, template_repository):
        self.router = router
        self.templates = template_repository

    async def _call(self, task_type: str, variables: dict) -> dict | str:
        template = self.templates.get(task_type)
        prompt = template.render(variables)  # 使用 Jinja2 或简易替换
        provider, model = self.router.route(task_type)
        adapter = get_adapter(provider)

        raw_output = await adapter.generate(
            model=model,
            prompt=prompt,
        )

        # 输出解析：可以根据 task_type 解析为 JSON/文本
        return parse_llm_output(task_type, raw_output)

    async def generate_industry_analysis(self, web_profile, metrics):
        return await self._call(
            "INDUSTRY_ANALYSIS",
            {"web_profile": web_profile, "metrics": metrics},
        )

    async def explain_financials(self, metrics):
        return await self._call(
            "FINANCIAL_EXPLAIN",
            {"metrics": metrics},
        )

    async def summarize_risks(self, score_result, metrics, web_profile):
        return await self._call(
            "RISK_SUMMARY",
            {
                "score_result": score_result,
                "metrics": metrics,
                "web_profile": web_profile,
            },
        )
```

#### 4.1.4 多供应商路由配置（YAML 示例）

```yaml
llm_routing:
  INDUSTRY_ANALYSIS:
    provider: aggregator
    model: "general-32k"
  FINANCIAL_EXPLAIN:
    provider: providerA
    model: "finance-pro"
  RISK_SUMMARY:
    provider: aggregator
    model: "risk-analyst"
  COMPANY_PROFILE_ENRICH:
    provider: providerA
    model: "general-16k"
```

### 4.2 WebSearchService 设计

职责：

* 统一对接工商信息 API 与通用搜索；
* 将搜索结果（网页摘要、新闻等）转化为简化结构，再交给 LLM 做摘要和结构化。

伪代码：

```python
class WebSearchService:
    async def enrich_company_profile(self, name: str, uscc: str | None, region: str | None):
        # 1. 查询工商信息（内部/官方 API）
        ic_data = query_ic_api(name=name, uscc=uscc)

        # 2. 通用搜索（企业名 + 地区）
        search_results = await search_web(f"{name} {region or ''}")

        # 3. 用 LLM 做结构化摘要
        profile = await llm_service._call(
            "COMPANY_PROFILE_ENRICH",
            {
                "ic_data": ic_data,
                "search_results": search_results,
            },
        )
        return profile
```

---

## 5. 前端 Web 设计（UI / UX）

技术建议：React + TypeScript + Ant Design

### 5.1 全局布局

* 顶部 Header：系统名称、当前环境（TEST/PROD）、用户信息、帮助按钮；
* 左侧 Sidebar：主导航；
* 内容区域 Content：显示各页面。

**主菜单：**

*  仪表盘（Dashboard）
*  新建分析
*  分析列表
*  报告管理（可选）
* ⚙️ 系统设置（仅管理员可见）

### 5.2 页面设计

#### 5.2.1 登录页

* 右侧：账号密码登录框；
* 左侧：产品简介 & Logo。

#### 5.2.2 仪表盘页

内容模块：

1. 概况卡片

   * 本周分析企业数
   * 高风险企业数（C + D）
   * 平均评分

2. 行业分布图

   * 按行业统计分析数量 + 平均风险等级（柱状图 / 饼图）

3. 风险等级分布

   * A/B/C/D 数量/比例条形图

4. 最近分析列表

   * 表格列：企业名、行业、分析日期、风险等级、操作人、操作按钮（查看）

#### 5.2.3 新建分析向导页（三步）

**Step 1：基础信息 & 网络补全**

* 表单字段：

  * 企业名称（必填）
  * 统一社会信用代码（可选但推荐）
  * 地区（省市区）
  * 行业（下拉 + 搜索）

* 按钮：`从网络补全工商信息`

  * 点击后右侧显示补全结果：成立日期、注册资本、经营范围摘要、是否检索到负面信息等；
  * 用户可编辑/覆盖。

* 底部按钮：`下一步：上传财报`

**Step 2：上传 3 年财报**

* 说明文字：

  * “请上传最近 3 年年度财务报表（支持 Excel/CSV，建议使用模板）”

* 控件：

  * `下载财报模板` 按钮
  * 拖拽上传区域（支持多文件）

* 上传后显示：

  * 简要字段预览
  * 校验结果（缺字段、资产负债不平等）

* 底部按钮：`上一步` / `开始分析`

**Step 3：分析进度与初步结果**

* 使用 Steps 组件展示进度：

  1. 获取工商与网络信息
  2. 计算财务指标
  3. 调用大模型生成分析
  4. 生成报告

* 分析成功后：

  * 显示企业名称
  * 初步风险等级：如 **B（78 分）**
  * 三条主要风险点概览
  * 按钮：`查看详细分析`

#### 5.2.4 分析详情页（核心）

布局：顶部 Summary 区 + 下方 Tab 分页。

**顶部 Summary：**

* 企业信息卡片（名称、行业、地区、成立时间等）；
* 总评分卡（分数 + 风险等级 Badge + 1–2 句简评）；
* 雷达图：五个维度得分（Industry / Character / Business / Financial / Collateral）；
* 操作按钮：

  * `导出 PDF 报告`
  * `复制摘要`
  * `重新分析`（若财报更新）

**下方 Tabs：**

1. **综述**

   * LLM 生成的综合分析段落；
   * 关键风险点（列表 + 严重程度）
   * 风险缓释建议（列表）

2. **行业与环境**

   * 行业分析文字；
   * 行业生命周期标签；
   * 行业风险与机会的 bullet list。

3. **企业与治理**

   * 股权/控制人信息摘要；
   * 公开负面舆情总结；
   * 主体信用与治理结构分析文字。

4. **财务与现金流**

   * 上方图表：

     * 收入/净利润三年趋势折线图；
     * 毛利率/净利率趋势；
     * 资产负债率与有息负债比例趋势；
     * 经营现金流 vs 净利润柱状图。

   * 下方 LLM 的财务分析文字：

     * 盈利能力说明；
     * 杠杆与偿债能力说明；
     * 营运效率说明；
     * 现金流质量说明。

5. **评分与规则**

   * 表格展示各维度得分与简要说明；
   * 展示关键规则触发信息（方便向监管/审计解释评分逻辑）。

6. **报告预览**

   * 渲染完整 HTML/Markdown 报告；
   * 顶部按钮：`导出 PDF` / `导出 Word` / `复制全文`.

#### 5.2.5 分析列表页

* 表格列：

  * 企业名称
  * 行业
  * 分析日期
  * 风险等级
  * 状态（成功/失败/待处理）
  * 操作人
  * 操作按钮：查看 / 导出报告 / 重新分析

* 支持筛选：

  * 时间、行业、风险等级、操作人。

#### 5.2.6 系统设置页

仅管理员可见，Tab 包括：

* **模型设置**：

  * 当前使用供应商、模型 ID、超时时间；
  * “测试调用”按钮。

* **评分卡设置**：

  * 各维度权重与等级区间（只读或极少修改）。

* **报告模板设置**：

  * 报告标题、页眉页脚文本、是否插入 Logo。

### 5.3 前端布局骨架（React + AntD 简例）

```tsx
// AppLayout.tsx
import React from "react";
import { Layout, Menu } from "antd";
import {
  BarChartOutlined,
  FileAddOutlined,
  FolderOpenOutlined,
  FileTextOutlined,
  SettingOutlined,
} from "@ant-design/icons";

const { Header, Sider, Content } = Layout;

export const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider breakpoint="lg" collapsible>
        <div style={{ height: 64, margin: 16, color: "#fff", fontWeight: 600 }}>
          信贷分析助手
        </div>
        <Menu
          theme="dark"
          mode="inline"
          defaultSelectedKeys={["dashboard"]}
          items={[
            { key: "dashboard", icon: <BarChartOutlined />, label: "仪表盘" },
            { key: "new-analysis", icon: <FileAddOutlined />, label: "新建分析" },
            { key: "analysis-list", icon: <FolderOpenOutlined />, label: "分析列表" },
            { key: "reports", icon: <FileTextOutlined />, label: "报告管理" },
            { key: "settings", icon: <SettingOutlined />, label: "系统设置" },
          ]}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>当前环境：<span style={{ color: "#faad14" }}>TEST</span></div>
          <div>张三（风控经理）</div>
        </Header>
        <Content style={{ margin: 24 }}>
          <div
            style={{
              background: "#fff",
              padding: 24,
              borderRadius: 12,
              minHeight: 360,
            }}
          >
            {children}
          </div>
        </Content>
      </Layout>
    </Layout>
  );
};
```

---

## 6. 非功能需求

### 6.1 安全与合规

* 部署在内网，所有外部访问通过网关；
* 与外部大模型/搜索 API 通信使用 HTTPS；
* API Key 与敏感配置通过环境变量或配置中心管理；
* 对发送到外部模型的数据可以按策略做脱敏（如金额区间化）。

### 6.2 可解释性与审计

* 所有评分结果需可追溯到指标与规则；
* 对大模型生成的关键段落记录调用信息（模型 ID、时间、任务类型）；
* 报告中对“公开网络信息”标注：

  * “信息来自公开来源，仅供参考，不构成本机构实质审查结论。”

### 6.3 性能目标

* 单次分析（已有结构化 3 年财报）：

  * 指标计算 + 评分：< 1 秒；
  * 大模型生成段落：视模型而定，目标总耗时 5–15 秒；
* 支持同时处理一定数量并发分析（根据业务规模调整）。

---

## 7. 后续可扩展方向

* 支持 PDF/图片财报 OCR → 自动结构化为三大报表；
* 接入内部征信系统、账户流水系统，增强“现金流”和“行为”分析维度；
* 增加“同业对标”：基于内部客户库做行业平均与分位数；
* 引入简单的违约历史统计，进行评分卡校准与 PD 映射。

---

这样一版就**完全去掉了数据库架构细节**，但对前端、后端、中间层、大模型、搜索、业务逻辑和 UI 都讲清楚了，Codex 可以直接拿这个当蓝图去生成项目骨架。

如果你愿意，下一步我可以单独给一份：

* **“后端 FastAPI 项目分模块代码清单”**（文件结构 + 每个模块大概有哪些函数），
  帮你把这个文档进一步变成“马上开工”的工程 TODO。
