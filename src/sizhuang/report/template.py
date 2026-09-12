"""HTML 报告模板（内联样式，兼容主流邮箱客户端）。"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ subject }}</title>
</head>
<body style="margin:0;padding:0;background:#eef1f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;color:#1f2937;">
<div style="max-width:760px;margin:0 auto;padding:16px 12px;">

  <!-- ===== 头部 ===== -->
  <div style="background:linear-gradient(135deg,#1e3a8a,#2563eb);border-radius:12px 12px 0 0;padding:22px 24px;color:#fff;">
    <div style="font-size:13px;opacity:.85;letter-spacing:1px;">每日个股观察报告</div>
    <div style="font-size:26px;font-weight:700;margin-top:6px;">
      {{ stock.name }} <span style="font-size:16px;font-weight:400;opacity:.9;">{{ stock.code }}</span>
    </div>
    <div style="font-size:13px;opacity:.85;margin-top:8px;">
      数据交易日 {{ trade_date }} &nbsp;·&nbsp; 生成于 {{ generated_at }}
    </div>
  </div>

  <!-- ===== 一句话速览 ===== -->
  <div style="background:#fff;padding:18px 24px;border-left:4px solid {{ score_color }};border-right:1px solid #e5e7eb;border-bottom:1px solid #e5e7eb;">
    <div style="font-size:12px;color:#6b7280;letter-spacing:1px;margin-bottom:8px;">速览</div>
    <div style="font-size:15px;line-height:1.7;">{{ headline }}</div>
    <div style="margin-top:12px;">
      <span style="display:inline-block;background:{{ score_bg }};color:{{ score_color }};font-size:13px;font-weight:600;padding:4px 12px;border-radius:999px;">
        多空比 {{ trend.score }} : {{ 100 - trend.score }} · {{ trend.label }}
      </span>
      {% if news_stats.total %}
      <span style="display:inline-block;margin-left:8px;background:#f3f4f6;color:#374151;font-size:13px;padding:4px 12px;border-radius:999px;">
        消息面情绪 {{ news_stats.index }}（{{ news_stats.label }}）
      </span>
      {% endif %}
    </div>
  </div>

  <!-- ===== 行情快照 ===== -->
  <div style="background:#fff;padding:20px 24px;border:1px solid #e5e7eb;border-top:none;">
    <div style="font-size:15px;font-weight:700;color:#111827;border-left:3px solid #2563eb;padding-left:10px;margin-bottom:14px;">行情快照</div>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr>
        <td style="padding:8px 6px;background:#f9fafb;border-radius:6px;width:25%;">
          <div style="color:#6b7280;font-size:11px;">最新价</div>
          <div style="font-size:19px;font-weight:700;color:{{ chg_color }};">{{ quote.price }}</div>
        </td>
        <td style="width:8px;"></td>
        <td style="padding:8px 6px;background:#f9fafb;border-radius:6px;width:25%;">
          <div style="color:#6b7280;font-size:11px;">涨跌幅</div>
          <div style="font-size:19px;font-weight:700;color:{{ chg_color }};">{{ quote.pct_chg_str }}</div>
        </td>
        <td style="width:8px;"></td>
        <td style="padding:8px 6px;background:#f9fafb;border-radius:6px;width:25%;">
          <div style="color:#6b7280;font-size:11px;">成交额</div>
          <div style="font-size:19px;font-weight:700;color:#111827;">{{ quote.amount_str }}</div>
        </td>
        <td style="width:8px;"></td>
        <td style="padding:8px 6px;background:#f9fafb;border-radius:6px;width:25%;">
          <div style="color:#6b7280;font-size:11px;">换手率</div>
          <div style="font-size:19px;font-weight:700;color:#111827;">{{ quote.turnover_str }}</div>
        </td>
      </tr>
    </table>

    <table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:14px;">
      <tr style="background:#f9fafb;">
        <th style="padding:8px;text-align:left;color:#6b7280;font-weight:500;border-bottom:1px solid #e5e7eb;">开盘</th>
        <th style="padding:8px;text-align:left;color:#6b7280;font-weight:500;border-bottom:1px solid #e5e7eb;">最高</th>
        <th style="padding:8px;text-align:left;color:#6b7280;font-weight:500;border-bottom:1px solid #e5e7eb;">最低</th>
        <th style="padding:8px;text-align:left;color:#6b7280;font-weight:500;border-bottom:1px solid #e5e7eb;">昨收</th>
        <th style="padding:8px;text-align:left;color:#6b7280;font-weight:500;border-bottom:1px solid #e5e7eb;">振幅</th>
        <th style="padding:8px;text-align:left;color:#6b7280;font-weight:500;border-bottom:1px solid #e5e7eb;">量比</th>
      </tr>
      <tr>
        <td style="padding:8px;border-bottom:1px solid #f3f4f6;">{{ quote.open }}</td>
        <td style="padding:8px;border-bottom:1px solid #f3f4f6;">{{ quote.high }}</td>
        <td style="padding:8px;border-bottom:1px solid #f3f4f6;">{{ quote.low }}</td>
        <td style="padding:8px;border-bottom:1px solid #f3f4f6;">{{ quote.pre_close }}</td>
        <td style="padding:8px;border-bottom:1px solid #f3f4f6;">{{ quote.amplitude_str }}</td>
        <td style="padding:8px;border-bottom:1px solid #f3f4f6;">{{ quote.volume_ratio_str }}</td>
      </tr>
      <tr>
        <td style="padding:8px;color:#6b7280;">总市值</td>
        <td style="padding:8px;color:#6b7280;">流通市值</td>
        <td style="padding:8px;color:#6b7280;">市盈率(TTM)</td>
        <td style="padding:8px;color:#6b7280;">市净率</td>
        <td style="padding:8px;color:#6b7280;">涨停价</td>
        <td style="padding:8px;color:#6b7280;">跌停价</td>
      </tr>
      <tr>
        <td style="padding:8px;">{{ quote.total_mv_str }}</td>
        <td style="padding:8px;">{{ quote.float_mv_str }}</td>
        <td style="padding:8px;">{{ quote.pe_str }}</td>
        <td style="padding:8px;">{{ quote.pb_str }}</td>
        <td style="padding:8px;color:#dc2626;">{{ quote.limit_up }}</td>
        <td style="padding:8px;color:#16a34a;">{{ quote.limit_down }}</td>
      </tr>
    </table>

    {% if indexes %}
    <div style="margin-top:16px;padding-top:12px;border-top:1px dashed #e5e7eb;">
      <div style="font-size:12px;color:#6b7280;margin-bottom:8px;">大盘环境</div>
      {% for ix in indexes %}
      <span style="display:inline-block;margin:0 14px 6px 0;font-size:13px;">
        {{ ix.name }}
        <b style="color:{{ ix.color }};">{{ ix.price }}</b>
        <span style="color:{{ ix.color }};">{{ ix.pct_str }}</span>
      </span>
      {% endfor %}
    </div>
    {% endif %}
  </div>

  <!-- ===== 技术研判 ===== -->
  <div style="background:#fff;padding:20px 24px;border:1px solid #e5e7eb;border-top:none;">
    <div style="font-size:15px;font-weight:700;color:#111827;border-left:3px solid #2563eb;padding-left:10px;margin-bottom:14px;">技术研判（{{ signals|length }} 项信号）</div>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      {% for s in signals %}
      <tr>
        <td style="padding:7px 8px;border-bottom:1px solid #f3f4f6;white-space:nowrap;vertical-align:top;">
          <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{{ s.color }};margin-right:6px;vertical-align:middle;"></span>
          <b style="color:#374151;">{{ s.name }}</b>
        </td>
        <td style="padding:7px 8px;border-bottom:1px solid #f3f4f6;color:#6b7280;white-space:nowrap;vertical-align:top;">{{ s.label }}</td>
        <td style="padding:7px 8px;border-bottom:1px solid #f3f4f6;color:#374151;">{{ s.detail }}</td>
      </tr>
      {% endfor %}
    </table>

    <table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:16px;background:#f9fafb;border-radius:8px;">
      <tr>
        <td style="padding:12px;vertical-align:top;width:50%;">
          <div style="color:#16a34a;font-weight:600;margin-bottom:6px;">支撑位</div>
          <div style="color:#374151;">{{ supports_str }}</div>
        </td>
        <td style="padding:12px;vertical-align:top;border-left:1px solid #e5e7eb;">
          <div style="color:#dc2626;font-weight:600;margin-bottom:6px;">压力位</div>
          <div style="color:#374151;">{{ resistances_str }}</div>
        </td>
      </tr>
    </table>
    {% if position_pct is not none %}
    <div style="margin-top:10px;font-size:12px;color:#6b7280;">当前价处于近 60 日波动区间的 {{ position_pct }}% 分位</div>
    {% endif %}
  </div>

  <!-- ===== 资金面 ===== -->
  {% if fundflow_rows %}
  <div style="background:#fff;padding:20px 24px;border:1px solid #e5e7eb;border-top:none;">
    <div style="font-size:15px;font-weight:700;color:#111827;border-left:3px solid #2563eb;padding-left:10px;margin-bottom:14px;">资金面</div>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr style="background:#f9fafb;">
        <th style="padding:8px;text-align:left;color:#6b7280;font-weight:500;">周期</th>
        <th style="padding:8px;text-align:right;color:#6b7280;font-weight:500;">主力净额</th>
        <th style="padding:8px;text-align:right;color:#6b7280;font-weight:500;">超大单</th>
        <th style="padding:8px;text-align:right;color:#6b7280;font-weight:500;">大单</th>
        <th style="padding:8px;text-align:right;color:#6b7280;font-weight:500;">中单</th>
        <th style="padding:8px;text-align:right;color:#6b7280;font-weight:500;">小单</th>
      </tr>
      {% for r in fundflow_rows %}
      <tr>
        <td style="padding:8px;border-bottom:1px solid #f3f4f6;">{{ r.label }}</td>
        <td style="padding:8px;text-align:right;border-bottom:1px solid #f3f4f6;font-weight:600;color:{{ r.color }};">{{ r.main }}</td>
        <td style="padding:8px;text-align:right;border-bottom:1px solid #f3f4f6;color:{{ r.super_color }};">{{ r.super_large }}</td>
        <td style="padding:8px;text-align:right;border-bottom:1px solid #f3f4f6;color:{{ r.large_color }};">{{ r.large }}</td>
        <td style="padding:8px;text-align:right;border-bottom:1px solid #f3f4f6;color:{{ r.medium_color }};">{{ r.medium }}</td>
        <td style="padding:8px;text-align:right;border-bottom:1px solid #f3f4f6;color:{{ r.small_color }};">{{ r.small }}</td>
      </tr>
      {% endfor %}
    </table>
    {% if margin_line %}
    <div style="margin-top:12px;padding:10px 12px;background:#f9fafb;border-radius:8px;font-size:13px;color:#374151;">
      融资融券：{{ margin_line }}
    </div>
    {% endif %}
  </div>
  {% endif %}

  <!-- ===== 新闻 ===== -->
  <div style="background:#fff;padding:20px 24px;border:1px solid #e5e7eb;border-top:none;">
    <div style="font-size:15px;font-weight:700;color:#111827;border-left:3px solid #2563eb;padding-left:10px;margin-bottom:14px;">
      全网相关资讯 <span style="font-size:12px;font-weight:400;color:#6b7280;">共 {{ news|length }} 条 · 按时间倒序</span>
    </div>
    {% if news %}
    {% for n in news %}
    <div style="padding:12px 0;border-bottom:1px solid #f3f4f6;">
      <div style="font-size:14px;line-height:1.55;">
        <span style="display:inline-block;font-size:11px;padding:2px 7px;border-radius:4px;background:{{ n.badge_bg }};color:{{ n.badge_fg }};margin-right:5px;vertical-align:1px;">{{ n.sentiment_label }}</span>
        <span style="display:inline-block;font-size:11px;padding:2px 7px;border-radius:4px;background:{{ n.scope_bg }};color:{{ n.scope_fg }};margin-right:7px;vertical-align:1px;">{{ n.scope_label }}</span>
        {% if n.url %}<a href="{{ n.url }}" style="color:#1d4ed8;text-decoration:none;font-weight:600;">{{ n.title }}</a>
        {% else %}<span style="font-weight:600;color:#111827;">{{ n.title }}</span>{% endif %}
      </div>
      {% if n.summary %}
      <div style="font-size:12px;color:#6b7280;line-height:1.6;margin-top:5px;">{{ n.summary }}</div>
      {% endif %}
      <div style="font-size:11px;color:#9ca3af;margin-top:5px;">
        {{ n.source }}{% if n.published %} · {{ n.published }}{% endif %}{% if n.url %} · <a href="{{ n.url }}" style="color:#9ca3af;">原文</a>{% endif %}
      </div>
    </div>
    {% endfor %}
    {% else %}
    <div style="font-size:13px;color:#9ca3af;padding:10px 0;">本期未获取到相关资讯。</div>
    {% endif %}
  </div>

  <!-- ===== 近期重要公司事件 ===== -->
  {% if news_context %}
  <div style="background:#fff;padding:20px 24px;border:1px solid #e5e7eb;border-top:none;">
    <div style="font-size:15px;font-weight:700;color:#111827;border-left:3px solid #64748b;padding-left:10px;margin-bottom:6px;">
      近期重要公司事件回顾
    </div>
    <div style="font-size:12px;color:#6b7280;margin-bottom:12px;">
      时间窗口之外、但对判断公司基本面有参考价值的稿件
    </div>
    {% for n in news_context %}
    <div style="padding:9px 0;border-bottom:1px solid #f3f4f6;font-size:13px;line-height:1.6;">
      <span style="display:inline-block;font-size:11px;padding:2px 7px;border-radius:4px;background:{{ n.badge_bg }};color:{{ n.badge_fg }};margin-right:7px;vertical-align:1px;">{{ n.sentiment_label }}</span>
      {% if n.url %}<a href="{{ n.url }}" style="color:#1d4ed8;text-decoration:none;">{{ n.title }}</a>
      {% else %}{{ n.title }}{% endif %}
      <div style="font-size:11px;color:#9ca3af;margin-top:3px;">{{ n.source }} · {{ n.published }}</div>
    </div>
    {% endfor %}
  </div>
  {% endif %}

  <!-- ===== 公告 ===== -->
  {% if announcements %}
  <div style="background:#fff;padding:20px 24px;border:1px solid #e5e7eb;border-top:none;">
    <div style="font-size:15px;font-weight:700;color:#111827;border-left:3px solid #f59e0b;padding-left:10px;margin-bottom:14px;">
      公司公告 <span style="font-size:12px;font-weight:400;color:#6b7280;">共 {{ announcements|length }} 条</span>
    </div>
    {% for a in announcements %}
    <div style="padding:9px 0;border-bottom:1px solid #f3f4f6;font-size:13px;line-height:1.6;">
      <span style="display:inline-block;font-size:11px;padding:2px 7px;border-radius:4px;background:{{ a.badge_bg }};color:{{ a.badge_fg }};margin-right:7px;vertical-align:1px;">{{ a.sentiment_label }}</span>
      {% if a.url %}<a href="{{ a.url }}" style="color:#1d4ed8;text-decoration:none;">{{ a.title }}</a>
      {% else %}{{ a.title }}{% endif %}
      <span style="color:#9ca3af;font-size:11px;margin-left:6px;">{{ a.published }}{% if a.column %} · {{ a.column }}{% endif %}</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}

  <!-- ===== 研报 ===== -->
  {% if research %}
  <div style="background:#fff;padding:20px 24px;border:1px solid #e5e7eb;border-top:none;">
    <div style="font-size:15px;font-weight:700;color:#111827;border-left:3px solid #7c3aed;padding-left:10px;margin-bottom:14px;">机构研报</div>
    {% for r in research %}
    <div style="padding:9px 0;border-bottom:1px solid #f3f4f6;font-size:13px;line-height:1.6;">
      {% if r.url %}<a href="{{ r.url }}" style="color:#1d4ed8;text-decoration:none;">{{ r.title }}</a>
      {% else %}{{ r.title }}{% endif %}
      <div style="font-size:11px;color:#9ca3af;margin-top:3px;">
        {{ r.org }}{% if r.rating %} · 评级 {{ r.rating }}{% endif %} · {{ r.published }}
        {% if r.pdf %} · <a href="{{ r.pdf }}" style="color:#9ca3af;">PDF</a>{% endif %}
      </div>
    </div>
    {% endfor %}
  </div>
  {% endif %}

  <!-- ===== 股吧 ===== -->
  {% if guba %}
  <div style="background:#fff;padding:20px 24px;border:1px solid #e5e7eb;border-top:none;">
    <div style="font-size:15px;font-weight:700;color:#111827;border-left:3px solid #0891b2;padding-left:10px;margin-bottom:6px;">
      股吧热议 <span style="font-size:12px;font-weight:400;color:#6b7280;">散户情绪为人气与反向参考指标</span>
    </div>
    <div style="font-size:12px;color:#6b7280;margin-bottom:12px;">
      多 {{ guba_stats.positive }} / 空 {{ guba_stats.negative }} / 中性 {{ guba_stats.neutral }} · 人气指数 {{ guba_stats.index }}（{{ guba_stats.label }}）
    </div>
    {% for g in guba %}
    <div style="padding:8px 0;border-bottom:1px solid #f3f4f6;font-size:13px;line-height:1.55;">
      <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{{ g.color }};margin-right:6px;vertical-align:middle;"></span>
      {% if g.url %}<a href="{{ g.url }}" style="color:#374151;text-decoration:none;">{{ g.title }}</a>
      {% else %}{{ g.title }}{% endif %}
      <span style="font-size:11px;color:#9ca3af;margin-left:6px;">阅读 {{ g.click_count }} · 评论 {{ g.comment_count }} · {{ g.published }}</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}

  <!-- ===== 基本面 ===== -->
  {% if fundamental.report_name %}
  <div style="background:#fff;padding:20px 24px;border:1px solid #e5e7eb;border-top:none;">
    <div style="font-size:15px;font-weight:700;color:#111827;border-left:3px solid #059669;padding-left:10px;margin-bottom:14px;">基本面（{{ fundamental.report_name }}）</div>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr>
        <td style="padding:8px;background:#f9fafb;border-radius:6px;"><div style="color:#6b7280;font-size:11px;">营业总收入</div><div style="font-weight:700;">{{ fundamental.revenue_str }}</div></td>
        <td style="width:8px;"></td>
        <td style="padding:8px;background:#f9fafb;border-radius:6px;"><div style="color:#6b7280;font-size:11px;">归母净利润</div><div style="font-weight:700;color:{{ fundamental.profit_color }};">{{ fundamental.profit_str }}</div></td>
        <td style="width:8px;"></td>
        <td style="padding:8px;background:#f9fafb;border-radius:6px;"><div style="color:#6b7280;font-size:11px;">ROE</div><div style="font-weight:700;">{{ fundamental.roe_str }}</div></td>
        <td style="width:8px;"></td>
        <td style="padding:8px;background:#f9fafb;border-radius:6px;"><div style="color:#6b7280;font-size:11px;">资产负债率</div><div style="font-weight:700;">{{ fundamental.debt_str }}</div></td>
      </tr>
    </table>
    {% if fundamental.holder_line %}
    <div style="margin-top:10px;font-size:12px;color:#6b7280;">{{ fundamental.holder_line }}</div>
    {% endif %}
  </div>
  {% endif %}

  <!-- ===== 观察要点 ===== -->
  <div style="background:#fff;padding:20px 24px;border:1px solid #e5e7eb;border-top:none;">
    <div style="font-size:15px;font-weight:700;color:#111827;border-left:3px solid #dc2626;padding-left:10px;margin-bottom:14px;">今日观察要点</div>
    <ol style="margin:0;padding-left:20px;font-size:13px;line-height:1.9;color:#374151;">
      {% for w in watch_points %}<li style="margin-bottom:4px;">{{ w }}</li>{% endfor %}
    </ol>
  </div>

  <!-- ===== 数据缺口 ===== -->
  {% if errors %}
  <div style="background:#fffbeb;padding:14px 24px;border:1px solid #fde68a;border-top:none;border-radius:0 0 12px 12px;">
    <div style="font-size:12px;color:#92400e;font-weight:600;margin-bottom:6px;">本期数据缺口</div>
    <div style="font-size:12px;color:#92400e;line-height:1.7;">{{ errors_str }}</div>
  </div>
  {% else %}
  <div style="background:#f0fdf4;padding:12px 24px;border:1px solid #bbf7d0;border-top:none;border-radius:0 0 12px 12px;font-size:12px;color:#166534;">
    全部数据源采集正常。
  </div>
  {% endif %}

  <!-- ===== 页脚 ===== -->
  <div style="padding:18px 12px;text-align:center;font-size:11px;color:#9ca3af;line-height:1.8;">
    本邮件由「合众思壮个股观察工程」自动生成，数据来源于东方财富公开接口。<br>
    所有内容仅为公开信息程序化统计结果，<b>不构成任何投资建议</b>，投资决策及风险请自行承担。<br>
    生成时间 {{ generated_at }}
  </div>

</div>
</body>
</html>
"""
