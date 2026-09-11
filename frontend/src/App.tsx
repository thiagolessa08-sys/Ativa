import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Bot,
  Box,
  Building2,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  CircleDollarSign,
  Clock3,
  Cloud,
  Database,
  FileSpreadsheet,
  Filter,
  Gauge,
  LayoutDashboard,
  Menu,
  MessageSquareText,
  PackageCheck,
  RefreshCw,
  Route,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Truck,
  Users,
  Weight,
  X,
  Zap,
} from "lucide-react";

type Tab =
  | "overview"
  | "operations"
  | "deliveries"
  | "finance"
  | "fleet"
  | "sources"
  | "chat";
type Filters = {
  start: string;
  end: string;
  branch: string;
  uf: string;
  segment: string;
};
type Row = Record<string, string | number | null>;

const tabs: {
  id: Tab;
  label: string;
  icon: typeof Activity;
  eyebrow: string;
  description: string;
}[] = [
  {
    id: "overview",
    label: "Visão geral",
    icon: LayoutDashboard,
    eyebrow: "INTELIGÊNCIA OPERACIONAL",
    description: "Performance da operação em uma única leitura.",
  },
  {
    id: "operations",
    label: "Operações",
    icon: Route,
    eyebrow: "FLUXO E CAPACIDADE",
    description: "Movimento por filial, rota e horário de emissão.",
  },
  {
    id: "deliveries",
    label: "Entregas",
    icon: PackageCheck,
    eyebrow: "NÍVEL DE SERVIÇO",
    description: "Pontualidade, atrasos e ocorrências que exigem ação.",
  },
  {
    id: "finance",
    label: "Receita & clientes",
    icon: CircleDollarSign,
    eyebrow: "RESULTADO COMERCIAL",
    description: "Receita, ticket médio e concentração da carteira.",
  },
  {
    id: "fleet",
    label: "Frota",
    icon: Truck,
    eyebrow: "TRANSFERÊNCIAS",
    description: "Viagens, veículos, motoristas e custos operacionais.",
  },
  {
    id: "sources",
    label: "Fontes de dados",
    icon: Database,
    eyebrow: "CONFIABILIDADE DOS DADOS",
    description: "Saúde do PostgreSQL e dos arquivos do BI2.",
  },
  {
    id: "chat",
    label: "Pergunte aos dados",
    icon: MessageSquareText,
    eyebrow: "ANÁLISE CONVERSACIONAL",
    description: "Pergunte em português e receba a resposta com os dados.",
  },
];

const colors = {
  navy: "#071e42",
  blue: "#1474e4",
  cyan: "#4fb4ee",
  orange: "#f28b20",
  green: "#18a97c",
  red: "#e45f52",
  purple: "#7457d9",
  grid: "#e9eef5",
  muted: "#77859a",
};
const chartText = {
  color: colors.muted,
  fontFamily: "Inter, Segoe UI, sans-serif",
};
const tooltip = {
  trigger: "axis",
  backgroundColor: colors.navy,
  borderWidth: 0,
  textStyle: { color: "#fff", fontSize: 12 },
  padding: [10, 12],
};

function formatNumber(value: unknown, compact = true) {
  return new Intl.NumberFormat(
    "pt-BR",
    compact
      ? { notation: "compact", maximumFractionDigits: 1 }
      : { maximumFractionDigits: 0 },
  ).format(Number(value || 0));
}
function formatCurrency(value: unknown, compact = true) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: compact ? 1 : 2,
  }).format(Number(value || 0));
}
function formatDate(value: unknown) {
  if (!value) return "—";
  const [y, m, d] = String(value).slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}
function routeLabel(value: unknown) {
  return String(value || "").replace(" - ", " → ");
}
function pct(value: unknown) {
  return `${Number(value || 0)
    .toFixed(1)
    .replace(".", ",")}%`;
}
function queryString(filters: Filters) {
  const p = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => v && p.set(k, v));
  return p.toString();
}

function LoadingPanel() {
  return (
    <div className="loading-grid">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <div className={`skeleton s${i}`} key={i} />
      ))}
    </div>
  );
}
function EmptyState({
  message = "Não há dados para este recorte.",
}: {
  message?: string;
}) {
  return (
    <div className="empty-state">
      <Search size={24} />
      <strong>Nenhum resultado</strong>
      <span>{message}</span>
    </div>
  );
}
function Panel({
  eyebrow,
  title,
  action,
  className = "",
  children,
}: {
  eyebrow?: string;
  title: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <article className={`panel ${className}`}>
      <div className="panel-title">
        <div>
          {eyebrow && <span>{eyebrow}</span>}
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </article>
  );
}

function Delta({
  value,
  points = false,
}: {
  value: number | null | undefined;
  points?: boolean;
}) {
  if (value == null)
    return <small className="delta neutral">Sem comparação</small>;
  const up = value >= 0,
    Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <small className={`delta ${up ? "up" : "down"}`}>
      <Icon size={14} />
      {Math.abs(value).toFixed(1).replace(".", ",")}
      {points ? " p.p." : "%"}
      <em> vs. período anterior</em>
    </small>
  );
}
function KpiCard({
  icon: Icon,
  tone,
  label,
  value,
  delta,
  points,
  note,
}: {
  icon: typeof Activity;
  tone: string;
  label: string;
  value: string;
  delta?: number | null;
  points?: boolean;
  note?: string;
}) {
  return (
    <article className="kpi-card">
      <div className={`kpi-icon ${tone}`}>
        <Icon size={21} />
      </div>
      <span>{label}</span>
      <strong>{value}</strong>
      {note ? (
        <small className="kpi-note">{note}</small>
      ) : (
        <Delta value={delta} points={points} />
      )}
    </article>
  );
}

function DataTable({
  rows,
  columns,
}: {
  rows: Row[];
  columns: {
    key: string;
    label: string;
    format?: (v: unknown) => string;
    align?: "right";
  }[];
}) {
  if (!rows?.length) return <EmptyState />;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th className={c.align || ""} key={c.key}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td className={c.align || ""} key={c.key}>
                  {c.format ? c.format(row[c.key]) : String(row[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function horizontalBar(
  rows: Row[],
  category: string,
  metric: string,
  color = colors.blue,
  formatter?: (v: unknown) => string,
) {
  const data = [...rows].slice(0, 10).reverse();
  return {
    animationDuration: 600,
    grid: { left: 88, right: 38, top: 12, bottom: 28 },
    tooltip: { ...tooltip, valueFormatter: formatter },
    xAxis: {
      type: "value",
      axisLabel: { ...chartText, formatter: (v: number) => formatNumber(v) },
      splitLine: { lineStyle: { color: colors.grid } },
    },
    yAxis: {
      type: "category",
      data: data.map((r) =>
        category === "route" ? routeLabel(r[category]) : r[category],
      ),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { ...chartText, width: 78, overflow: "truncate" },
    },
    series: [
      {
        type: "bar",
        data: data.map((r) => r[metric]),
        barWidth: 12,
        itemStyle: { color, borderRadius: [0, 6, 6, 0] },
        label: {
          show: true,
          position: "right",
          ...chartText,
          formatter: (p: any) =>
            formatter ? formatter(p.value) : formatNumber(p.value),
        },
      },
    ],
  };
}

function Overview({ data, filters }: { data: any; filters: Filters }) {
  const [selected, setSelected] = useState("sla");
  const k = data?.kpis || {};
  const previous = data?.previous || {};
  const trend: Row[] = data?.trend || [];
  const number = (value: unknown) => Number(value || 0);
  const change = (current: number, before: number) =>
    before ? ((current - before) / Math.abs(before)) * 100 : null;
  const freightKg = number(k.weight) ? number(k.revenue) / number(k.weight) : 0;
  const prevFreightKg = number(previous.weight)
    ? number(previous.revenue) / number(previous.weight)
    : 0;
  const pending = Math.max(0, number(k.shipments) - number(k.delivered));
  const prevPending = Math.max(
    0,
    number(previous.shipments) - number(previous.delivered),
  );
  const metrics = [
    {
      key: "sla",
      label: "No prazo",
      value: pct(k.sla),
      delta: number(k.sla) - number(previous.sla),
      points: true,
      note: "entrega x previsão",
      daily: (r: Row) =>
        number(r.delivered) ? (number(r.on_time) / number(r.delivered)) * 100 : 0,
      axis: (v: number) => `${Math.round(v)}%`,
    },
    {
      key: "delivered",
      label: "Entregas",
      value: formatNumber(k.delivered, false),
      delta: change(number(k.delivered), number(previous.delivered)),
      note: "com baixa no período",
      daily: (r: Row) => number(r.delivered),
      axis: (v: number) => formatNumber(v),
    },
    {
      key: "freightKg",
      label: "Frete / kg",
      value: formatCurrency(freightKg, false),
      delta: change(freightKg, prevFreightKg),
      note: "frete ÷ peso cálculo",
      daily: (r: Row) =>
        number(r.weight) ? number(r.revenue) / number(r.weight) : 0,
      axis: (v: number) => formatCurrency(v, false),
    },
    {
      key: "volumes",
      label: "Volumes",
      value: formatNumber(k.volumes),
      delta: change(number(k.volumes), number(previous.volumes)),
      note: "volumes transportados",
      daily: (r: Row) => number(r.volumes),
      axis: (v: number) => formatNumber(v),
    },
    {
      key: "transit",
      label: "Prazo médio",
      value: `${number(k.avg_transit).toFixed(1).replace(".", ",")} dias`,
      delta: change(number(k.avg_transit), number(previous.avg_transit)),
      note: "emissão → entrega",
      daily: (r: Row) => number(r.avg_transit),
      axis: (v: number) => `${v.toFixed(1)}d`,
    },
    {
      key: "pending",
      label: "Em aberto",
      value: formatNumber(pending, false),
      delta: change(pending, prevPending),
      note: "sem baixa de entrega",
      daily: (r: Row) => Math.max(0, number(r.shipments) - number(r.delivered)),
      axis: (v: number) => formatNumber(v),
    },
    {
      key: "ticket",
      label: "Ticket médio",
      value: formatCurrency(k.avg_ticket),
      delta: change(number(k.avg_ticket), number(previous.avg_ticket)),
      note: "frete por conhecimento",
      daily: (r: Row) => number(r.avg_ticket),
      axis: (v: number) => formatCurrency(v),
    },
    {
      key: "delayed",
      label: "Pendentes",
      value: formatNumber(k.delayed, false),
      delta: change(number(k.delayed), number(previous.delayed)),
      note: "acima da previsão",
      daily: (r: Row) => number(r.delayed),
      axis: (v: number) => formatNumber(v),
    },
  ];
  const active = metrics.find((metric) => metric.key === selected) || metrics[0];
  const periodLabel = `${formatDate(filters.start)} a ${formatDate(filters.end)}`;
  const selectedTrend = {
    animationDuration: 700,
    grid: { left: 12, right: 12, top: 18, bottom: 23, containLabel: true },
    tooltip: {
      ...tooltip,
      formatter: (items: any[]) =>
        `${items[0]?.axisValue}<br/><b>${active.label}: ${active.axis(items[0]?.value || 0)}</b>`,
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: trend.map((r) => formatDate(r.date).slice(0, 5)),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { ...chartText, fontSize: 10, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: { lineStyle: { color: "#e1e3e7" } },
    },
    series: [
      {
        type: "line",
        smooth: 0.35,
        showSymbol: false,
        lineStyle: { width: 2.5, color: "#17468f" },
        areaStyle: { color: "rgba(23,70,143,.10)" },
        data: trend.map(active.daily),
      },
    ],
  };
  const dailyOption = {
    animationDuration: 650,
    grid: { left: 12, right: 10, top: 36, bottom: 26, containLabel: true },
    tooltip,
    legend: {
      top: 0,
      right: 0,
      textStyle: { ...chartText, fontSize: 10 },
      itemWidth: 10,
      itemHeight: 8,
    },
    xAxis: {
      type: "category",
      data: trend.map((r) => formatDate(r.date).slice(0, 5)),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { ...chartText, fontSize: 10, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { ...chartText, fontSize: 10, formatter: (v: number) => formatNumber(v) },
      splitLine: { lineStyle: { color: "#eef0f4" } },
    },
    series: [
      {
        name: "No prazo",
        type: "bar",
        stack: "deliveries",
        data: trend.map((r) => r.on_time),
        barMaxWidth: 16,
        itemStyle: { color: "#17468f", borderRadius: [0, 0, 3, 3] },
      },
      {
        name: "Fora do prazo",
        type: "bar",
        stack: "deliveries",
        data: trend.map((r) => Math.max(0, number(r.delivered) - number(r.on_time))),
        barMaxWidth: 16,
        itemStyle: { color: "#fec52e", borderRadius: [3, 3, 0, 0] },
      },
    ],
  };
  const stateOption = {
    animationDuration: 650,
    tooltip: { trigger: "item", valueFormatter: (v: number) => formatNumber(v, false) },
    legend: { bottom: 0, left: "center", textStyle: { ...chartText, fontSize: 10 } },
    series: [
      {
        type: "pie",
        radius: ["47%", "72%"],
        center: ["50%", "43%"],
        label: { show: false },
        itemStyle: { borderColor: "#fff", borderWidth: 3 },
        color: ["#17468f", "#fec52e", "#6f8fbe", "#aebcd0", "#dce2ea"],
        data: (data?.states || []).slice(0, 5).map((r: Row) => ({
          name: String(r.uf || "N/I"),
          value: r.shipments,
        })),
      },
    ],
  };
  const totalAttention = (data?.occurrences || []).reduce(
    (sum: number, row: Row) => sum + number(row.occurrence_count),
    0,
  );
  return (
    <div className="reference-overview">
      <section className="truck-stage">
        <div className="trend-side">
          <span className="section-kicker">Tendência</span>
          <div className="trend-heading">
            <strong>{active.label}</strong>
            <small>{periodLabel}</small>
          </div>
          <div className="trend-value">
            <b>{active.value}</b>
            <Delta value={active.delta} points={active.points} />
          </div>
          <ReactECharts option={selectedTrend} className="truck-trend-chart" />
          <small className="truck-help">Clique em um KPI no baú para trocar a série</small>
        </div>
        <div className="truck-visual">
          <img src="/truck-clean.png" alt="Caminhão da operação logística" />
          <div className="trailer-kpis">
            {metrics.map((metric) => (
              <button
                className={selected === metric.key ? "active" : ""}
                onClick={() => setSelected(metric.key)}
                key={metric.key}
                title={`${metric.label}: ${metric.value} — ${metric.note}`}
              >
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                <small>{metric.delta == null ? "—" : `${metric.delta >= 0 ? "▲" : "▼"} ${Math.abs(metric.delta).toFixed(1).replace(".", ",")}${metric.points ? " p.p." : "%"}`}</small>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="reference-grid">
        <Panel eyebrow="NÍVEL DE SERVIÇO" title="Entregas por dia" className="daily-panel">
          <ReactECharts option={dailyOption} style={{ height: 235 }} />
        </Panel>
        <Panel eyebrow="REDE ATIVA" title="SLA por filial">
          <ReactECharts
            option={horizontalBar(data?.branches || [], "branch", "sla", "#17468f", pct)}
            style={{ height: 235 }}
          />
        </Panel>
        <Panel eyebrow="DESTINOS" title="Mix por estado" className="map-mix-panel">
          <img src="/map.png" alt="Mapa de referência da malha" />
          <ReactECharts option={stateOption} style={{ height: 235 }} />
        </Panel>
      </section>

      <section className="reference-bottom">
        <Panel
          eyebrow="PULSO DA OPERAÇÃO"
          title="Principais pendências"
          action={<b className="alert-count">{formatNumber(totalAttention, false)}</b>}
        >
          <div className="attention-list compact">
            {(data?.occurrences || []).slice(0, 5).map((r: Row, i: number) => (
              <div className="attention-row" key={i}>
                <i className={["red", "orange", "blue", "purple", "gray"][i]} />
                <div>
                  <strong>{String(r.occurrence_label || "Sem ocorrência")}</strong>
                  <small>Conhecimentos ainda em aberto</small>
                </div>
                <b>{formatNumber(r.occurrence_count, false)}</b>
              </div>
            ))}
          </div>
        </Panel>
        <Panel eyebrow="COBERTURA" title="Destinos com maior movimento">
          <div className="state-ranking">
            {(data?.states || []).slice(0, 8).map((r: Row, i: number) => (
              <div key={String(r.uf)}>
                <span className="rank">{String(i + 1).padStart(2, "0")}</span>
                <strong>{r.uf}</strong>
                <div className="mini-track">
                  <i style={{ width: `${(number(r.shipments) / number(data.states[0]?.shipments || 1)) * 100}%` }} />
                </div>
                <span>{formatNumber(r.shipments, false)}</span>
                <small>{formatCurrency(r.revenue)}</small>
              </div>
            ))}
          </div>
        </Panel>
      </section>
    </div>
  );
}

function Operations({ data }: { data: any }) {
  const branches: Row[] = data?.branches || [],
    t = branches.reduce<{
      shipments: number;
      tons: number;
      volumes: number;
      delayed: number;
    }>(
      (a, r) => ({
        shipments: a.shipments + Number(r.shipments || 0),
        tons: a.tons + Number(r.tons || 0),
        volumes: a.volumes + Number(r.volumes || 0),
        delayed: a.delayed + Number(r.delayed || 0),
      }),
      { shipments: 0, tons: 0, volumes: 0, delayed: 0 },
    ),
    hourly = data?.hourly || [];
  const hourlyOption = {
    animationDuration: 600,
    grid: { left: 44, right: 15, top: 18, bottom: 30 },
    tooltip,
    xAxis: {
      type: "category",
      data: hourly.map(
        (r: Row) => `${String(r.hour_of_day).padStart(2, "0")}h`,
      ),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: chartText,
    },
    yAxis: {
      type: "value",
      axisLabel: { ...chartText, formatter: (v: number) => formatNumber(v) },
      splitLine: { lineStyle: { color: colors.grid } },
    },
    series: [
      {
        type: "bar",
        data: hourly.map((r: Row) => r.shipments),
        barWidth: "58%",
        itemStyle: { color: colors.cyan, borderRadius: [5, 5, 0, 0] },
      },
    ],
  };
  return (
    <>
      <section className="kpis">
        <KpiCard
          icon={Box}
          tone="blue"
          label="Embarques"
          value={formatNumber(t.shipments, false)}
          note="No período selecionado"
        />
        <KpiCard
          icon={Weight}
          tone="purple"
          label="Peso transportado"
          value={`${formatNumber(t.tons)} t`}
          note={`${formatNumber(t.volumes)} volumes`}
        />
        <KpiCard
          icon={Building2}
          tone="green"
          label="Filiais com movimento"
          value={String(branches.length)}
          note="Origem de emissão"
        />
        <KpiCard
          icon={Clock3}
          tone="red"
          label="Em atraso"
          value={formatNumber(t.delayed, false)}
          note="Pendências acima da previsão"
        />
      </section>
      <section className="two-grid">
        <Panel eyebrow="MALHA LOGÍSTICA" title="Rotas com maior volume">
          <ReactECharts
            option={horizontalBar(data?.routes || [], "route", "shipments")}
            style={{ height: 340 }}
          />
        </Panel>
        <Panel eyebrow="RITMO DIÁRIO" title="Emissões por horário">
          <ReactECharts option={hourlyOption} style={{ height: 340 }} />
        </Panel>
      </section>
      <Panel
        eyebrow="PERFORMANCE DA REDE"
        title="Filiais"
        className="table-panel"
      >
        <DataTable
          rows={branches}
          columns={[
            { key: "branch", label: "Filial" },
            {
              key: "shipments",
              label: "Conhecimentos",
              format: (v) => formatNumber(v, false),
              align: "right",
            },
            {
              key: "volumes",
              label: "Volumes",
              format: formatNumber,
              align: "right",
            },
            {
              key: "tons",
              label: "Toneladas",
              format: (v) => Number(v || 0).toLocaleString("pt-BR"),
              align: "right",
            },
            { key: "sla", label: "SLA", format: pct, align: "right" },
            {
              key: "delayed",
              label: "Atrasados",
              format: (v) => formatNumber(v, false),
              align: "right",
            },
            {
              key: "revenue",
              label: "Receita",
              format: formatCurrency,
              align: "right",
            },
          ]}
        />
      </Panel>
    </>
  );
}

function Deliveries({ data }: { data: any }) {
  const sla = data?.sla_trend || [],
    late = data?.lateness || [];
  const slaOption = {
    animationDuration: 600,
    grid: { left: 42, right: 16, top: 28, bottom: 34 },
    tooltip,
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: sla.map((r: Row) => formatDate(r.date).slice(0, 5)),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: chartText,
    },
    yAxis: {
      type: "value",
      min: 70,
      max: 100,
      axisLabel: { ...chartText, formatter: (v: number) => `${v}%` },
      splitLine: { lineStyle: { color: colors.grid } },
    },
    series: [
      {
        type: "line",
        smooth: true,
        symbol: "none",
        data: sla.map((r: Row) => r.sla),
        lineStyle: { width: 3, color: colors.green },
        areaStyle: { color: "rgba(24,169,124,.10)" },
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: colors.orange, type: "dashed" },
          data: [
            {
              yAxis: 95,
              label: { formatter: "Meta 95%", color: colors.orange },
            },
          ],
        },
      },
    ],
  };
  const latenessOption = {
    tooltip: {
      trigger: "item",
      backgroundColor: colors.navy,
      borderWidth: 0,
      textStyle: { color: "#fff" },
    },
    legend: { bottom: 0, textStyle: chartText },
    series: [
      {
        type: "pie",
        radius: ["48%", "70%"],
        center: ["50%", "43%"],
        itemStyle: { borderColor: "#fff", borderWidth: 3, borderRadius: 5 },
        label: { formatter: "{b}\n{d}%", fontSize: 11, color: colors.muted },
        data: late.map((r: Row, i: number) => ({
          name: r.bucket,
          value: r.bucket_count,
          itemStyle: {
            color: [
              colors.red,
              colors.orange,
              "#f5b94d",
              colors.cyan,
              colors.green,
            ][i],
          },
        })),
      },
    ],
  };
  return (
    <>
      <section className="two-grid">
        <Panel eyebrow="EVOLUÇÃO" title="SLA de entrega">
          <ReactECharts option={slaOption} style={{ height: 330 }} />
        </Panel>
        <Panel eyebrow="AGING" title="Faixas de atraso">
          <ReactECharts option={latenessOption} style={{ height: 330 }} />
        </Panel>
      </section>
      <section className="two-grid tables">
        <Panel eyebrow="CAUSAS" title="Ocorrências em aberto">
          <DataTable
            rows={data?.occurrences || []}
            columns={[
              { key: "occurrence", label: "Ocorrência" },
              {
                key: "shipments",
                label: "Conhecimentos",
                format: (v) => formatNumber(v, false),
                align: "right",
              },
              { key: "branches", label: "Filiais", align: "right" },
              {
                key: "oldest_due",
                label: "Mais antiga",
                format: formatDate,
                align: "right",
              },
            ]}
          />
        </Panel>
        <Panel eyebrow="DESTINOS" title="Cidades com maior volume">
          <DataTable
            rows={data?.destination_cities || []}
            columns={[
              { key: "city", label: "Cidade" },
              {
                key: "shipments",
                label: "Volume",
                format: (v) => formatNumber(v, false),
                align: "right",
              },
              { key: "sla", label: "SLA", format: pct, align: "right" },
              {
                key: "delayed",
                label: "Atrasados",
                format: (v) => formatNumber(v, false),
                align: "right",
              },
            ]}
          />
        </Panel>
      </section>
    </>
  );
}

function Finance({ data }: { data: any }) {
  const monthly: Row[] = data?.monthly || [],
    revenue = monthly.reduce((s, r) => s + Number(r.revenue || 0), 0),
    shipments = monthly.reduce((s, r) => s + Number(r.shipments || 0), 0),
    merchandise = monthly.reduce((s, r) => s + Number(r.merchandise || 0), 0);
  const option = {
    animationDuration: 600,
    grid: { left: 56, right: 48, top: 40, bottom: 36 },
    tooltip,
    legend: { top: 0, right: 0, textStyle: chartText },
    xAxis: {
      type: "category",
      data: monthly.map((r) => String(r.period).split("-").reverse().join("/")),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: chartText,
    },
    yAxis: [
      {
        type: "value",
        axisLabel: {
          ...chartText,
          formatter: (v: number) => formatCurrency(v),
        },
        splitLine: { lineStyle: { color: colors.grid } },
      },
      {
        type: "value",
        axisLabel: { ...chartText, formatter: (v: number) => formatNumber(v) },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "Receita",
        type: "bar",
        data: monthly.map((r) => r.revenue),
        barWidth: 24,
        itemStyle: { color: colors.blue, borderRadius: [5, 5, 0, 0] },
      },
      {
        name: "Conhecimentos",
        type: "line",
        yAxisIndex: 1,
        data: monthly.map((r) => r.shipments),
        smooth: true,
        symbolSize: 7,
        lineStyle: { width: 3, color: colors.orange },
        itemStyle: { color: colors.orange },
      },
    ],
  };
  return (
    <>
      <section className="kpis">
        <KpiCard
          icon={CircleDollarSign}
          tone="blue"
          label="Receita de frete"
          value={formatCurrency(revenue)}
          note="No período selecionado"
        />
        <KpiCard
          icon={Gauge}
          tone="green"
          label="Ticket médio"
          value={formatCurrency(revenue / (shipments || 1), false)}
          note="Por conhecimento"
        />
        <KpiCard
          icon={Box}
          tone="orange"
          label="Conhecimentos"
          value={formatNumber(shipments, false)}
          note="Base faturada"
        />
        <KpiCard
          icon={Activity}
          tone="purple"
          label="Valor das mercadorias"
          value={formatCurrency(merchandise)}
          note="Carga transportada"
        />
      </section>
      <section className="two-grid">
        <Panel eyebrow="EVOLUÇÃO" title="Receita e volume">
          <ReactECharts option={option} style={{ height: 330 }} />
        </Panel>
        <Panel eyebrow="MIX COMERCIAL" title="Receita por segmento">
          <ReactECharts
            option={horizontalBar(
              data?.segments || [],
              "segment",
              "revenue",
              colors.orange,
              formatCurrency,
            )}
            style={{ height: 330 }}
          />
        </Panel>
      </section>
      <Panel
        eyebrow="CARTEIRA"
        title="Maiores clientes pagadores"
        className="table-panel"
      >
        <DataTable
          rows={data?.customers || []}
          columns={[
            { key: "customer", label: "Cliente" },
            {
              key: "shipments",
              label: "Conhecimentos",
              format: (v) => formatNumber(v, false),
              align: "right",
            },
            {
              key: "avg_ticket",
              label: "Ticket médio",
              format: (v) => formatCurrency(v, false),
              align: "right",
            },
            {
              key: "merchandise",
              label: "Mercadorias",
              format: formatCurrency,
              align: "right",
            },
            {
              key: "revenue",
              label: "Receita",
              format: formatCurrency,
              align: "right",
            },
          ]}
        />
      </Panel>
    </>
  );
}

function Fleet({ data }: { data: any }) {
  const k = data?.kpis || {},
    transfer = data?.transfer_costs || {},
    summary = transfer.summary || {};
  return (
    <>
      <section className="kpis">
        <KpiCard
          icon={Route}
          tone="blue"
          label="Manifestos"
          value={formatNumber(k.manifests, false)}
          note="Viagens no período"
        />
        <KpiCard
          icon={Truck}
          tone="orange"
          label="Veículos ativos"
          value={formatNumber(k.vehicles, false)}
          note="Placas distintas"
        />
        <KpiCard
          icon={Users}
          tone="purple"
          label="Motoristas"
          value={formatNumber(k.drivers, false)}
          note="Condutores na operação"
        />
        <KpiCard
          icon={ShieldCheck}
          tone="green"
          label="Chegadas no prazo"
          value={pct(k.sla)}
          note={`${Number(k.avg_transit || 0)
            .toFixed(1)
            .replace(".", ",")} dias em média`}
        />
      </section>
      <section className="two-grid">
        <Panel
          eyebrow="MALHA DE TRANSFERÊNCIA"
          title="Rotas por número de viagens"
        >
          <ReactECharts
            option={horizontalBar(data?.routes || [], "route", "manifests")}
            style={{ height: 345 }}
          />
        </Panel>
        <Panel
          eyebrow="BI2 · RELATÓRIO 220"
          title="Custo das transferências"
          action={
            <span className="source-chip">
              <FileSpreadsheet size={14} /> {transfer.file || "Indisponível"}
            </span>
          }
        >
          <div className="transfer-summary">
            <div>
              <small>Viagens concluídas</small>
              <strong>{formatNumber(summary.trips, false)}</strong>
            </div>
            <div>
              <small>Custo CTRB/OS</small>
              <strong>{formatCurrency(summary.cost)}</strong>
            </div>
            <div>
              <small>Frete proporcional</small>
              <strong>{formatCurrency(summary.freight)}</strong>
            </div>
            <div>
              <small>Peso calculado</small>
              <strong>{formatNumber(summary.tons)} t</strong>
            </div>
          </div>
          <div className="compact-routes">
            {(transfer.routes || []).slice(0, 5).map((r: Row) => (
              <div key={String(r.route)}>
                <span>{r.route}</span>
                <i>
                  <b
                    style={{
                      width: `${(Number(r.cost) / Number(transfer.routes[0]?.cost || 1)) * 100}%`,
                    }}
                  />
                </i>
                <strong>{formatCurrency(r.cost)}</strong>
              </div>
            ))}
          </div>
        </Panel>
      </section>
      <section className="two-grid tables">
        <Panel eyebrow="UTILIZAÇÃO" title="Veículos com mais viagens">
          <DataTable
            rows={data?.vehicles || []}
            columns={[
              { key: "vehicle", label: "Placa" },
              { key: "model", label: "Modelo" },
              { key: "trips", label: "Viagens", align: "right" },
              { key: "destinations", label: "Destinos", align: "right" },
              {
                key: "avg_transit",
                label: "Trânsito médio",
                format: (v) => `${Number(v || 0).toFixed(1)} d`,
                align: "right",
              },
            ]}
          />
        </Panel>
        <Panel eyebrow="EQUIPE" title="Motoristas com mais viagens">
          <DataTable
            rows={data?.drivers || []}
            columns={[
              { key: "driver", label: "Motorista" },
              { key: "trips", label: "Viagens", align: "right" },
              { key: "vehicles", label: "Veículos", align: "right" },
              { key: "sla", label: "SLA", format: pct, align: "right" },
            ]}
          />
        </Panel>
      </section>
    </>
  );
}

function Sources({ data }: { data: any }) {
  const db = data?.database || {},
    transfer = data?.transfer || {};
  return (
    <section className="sources-layout">
      <article className="source-card">
        <div className="source-head">
          <div className="source-icon">
            <Database />
          </div>
          <div>
            <span>POSTGRESQL</span>
            <h2>Servidor BI</h2>
          </div>
          <b>
            <CheckCircle2 size={16} /> Operacional
          </b>
        </div>
        <div className="source-metrics">
          <div>
            <small>Registros de conhecimentos</small>
            <strong>{formatNumber(db.rows, false)}</strong>
          </div>
          <div>
            <small>Primeiro registro</small>
            <strong>{formatDate(db.min_date)}</strong>
          </div>
          <div>
            <small>Última atualização</small>
            <strong>{formatDate(db.max_date)}</strong>
          </div>
        </div>
        <p>
          Fonte principal dos indicadores de emissão, entrega, receita,
          ocorrências e manifestos.
        </p>
      </article>
      <article className="source-card">
        <div className="source-head">
          <div className="source-icon orange">
            <Cloud />
          </div>
          <div>
            <span>SFTP</span>
            <h2>Servidor BI2</h2>
          </div>
          <b className={transfer.ok ? "" : "off"}>
            <CheckCircle2 size={16} />{" "}
            {transfer.ok ? "Sincronizado" : "Indisponível"}
          </b>
        </div>
        <div className="folder-list">
          {(transfer.folders || []).map((f: Row) => (
            <div key={String(f.folder)}>
              <FileSpreadsheet size={18} />
              <div>
                <strong>/{f.folder}</strong>
                <small>{f.latest_file}</small>
              </div>
              <span>{formatNumber(f.files, false)} arquivos</span>
              <time>
                {f.latest_at
                  ? new Date(String(f.latest_at)).toLocaleString("pt-BR", {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "—"}
              </time>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}

function chatChart(rows: Row[], type: string) {
  const keys = Object.keys(rows[0] || {}),
    category = keys.find((k) => typeof rows[0][k] === "string") || keys[0],
    metric =
      keys.find((k) => k !== category && typeof rows[0][k] === "number") ||
      keys[1];
  return type === "line"
    ? {
        grid: { left: 50, right: 20, top: 25, bottom: 35 },
        tooltip,
        xAxis: {
          type: "category",
          data: rows.map((r) => r[category]),
          axisLabel: chartText,
        },
        yAxis: { type: "value", axisLabel: chartText },
        series: [
          {
            type: "line",
            smooth: true,
            data: rows.map((r) => r[metric]),
            lineStyle: { color: colors.blue, width: 3 },
          },
        ],
      }
    : horizontalBar(rows, category, metric);
}

function Chat({ filters }: { filters: Filters }) {
  const [messages, setMessages] = useState<any[]>([
      {
        role: "assistant",
        answer:
          "Olá! Posso consultar a operação da Ativa para você. Pergunte sobre entregas, receita, filiais, clientes, rotas, ocorrências ou frota.",
        title: "Assistente de dados",
      },
    ]),
    [input, setInput] = useState(""),
    [busy, setBusy] = useState(false);
  const suggestions = [
    "Qual foi o SLA nos últimos 30 dias?",
    "Quais filiais têm mais entregas atrasadas?",
    "Mostre os 10 maiores clientes por receita",
    "Quais rotas tiveram maior movimento?",
  ];
  async function submit(text: string) {
    if (!text.trim() || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", answer: text }]);
    setBusy(true);
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, filters }),
      });
      const json = await response.json();
      if (!response.ok)
        throw new Error(json.detail || "Não foi possível consultar os dados.");
      setMessages((m) => [...m, { role: "assistant", ...json }]);
    } catch (error: any) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          error: true,
          title: "Não consegui concluir",
          answer: error.message,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="chat-layout">
      <section className="chat-window">
        <div className="chat-scroll">
          {messages.map((m, i) => (
            <div className={`message ${m.role}`} key={i}>
              {m.role === "assistant" && (
                <div className="bot-avatar">
                  <Bot size={19} />
                </div>
              )}
              <div className="bubble">
                {m.title && <strong>{m.title}</strong>}
                <p>{m.answer}</p>
                {m.data?.length > 1 && m.chart_type !== "table" && (
                  <ReactECharts
                    option={chatChart(m.data, m.chart_type)}
                    style={{ height: 270 }}
                  />
                )}
                {m.data?.length > 0 && (
                  <DataTable
                    rows={m.data.slice(0, 15)}
                    columns={Object.keys(m.data[0]).map((key) => ({
                      key,
                      label: key.replaceAll("_", " "),
                    }))}
                  />
                )}{" "}
                {m.sql && (
                  <details>
                    <summary>Ver consulta SQL</summary>
                    <pre>{m.sql}</pre>
                  </details>
                )}
                {m.provider && (
                  <small className="provider">
                    <ShieldCheck size={13} /> Consulta somente leitura ·{" "}
                    {m.provider}
                  </small>
                )}
              </div>
            </div>
          ))}
          {busy && (
            <div className="message assistant">
              <div className="bot-avatar">
                <Bot size={19} />
              </div>
              <div className="bubble thinking">
                <i />
                <i />
                <i />
                <span>Analisando a pergunta e preparando a consulta…</span>
              </div>
            </div>
          )}
        </div>
        <form
          className="chat-input"
          onSubmit={(e) => {
            e.preventDefault();
            submit(input);
          }}
        >
          <Sparkles size={18} />
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Pergunte algo sobre a operação…"
          />
          <button disabled={busy || !input.trim()}>
            <Send size={18} />
          </button>
        </form>
        <small className="chat-hint">
          O assistente gera e executa apenas consultas de leitura nas fontes
          autorizadas.
        </small>
      </section>
      <aside className="chat-side">
        <span>PERGUNTAS SUGERIDAS</span>
        {suggestions.map((q) => (
          <button onClick={() => submit(q)} key={q}>
            {q}
            <ArrowUpRight size={15} />
          </button>
        ))}
        <div className="active-filter-card">
          <Filter size={17} />
          <strong>Contexto ativo</strong>
          <p>
            {formatDate(filters.start)} a {formatDate(filters.end)}
          </p>
          <small>
            {filters.branch || "Todas as filiais"} ·{" "}
            {filters.uf || "Todo o Brasil"}
          </small>
        </div>
      </aside>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("overview"),
    [menuOpen, setMenuOpen] = useState(false),
    [options, setOptions] = useState<any>(null),
    [filters, setFilters] = useState<Filters>({
      start: "",
      end: "",
      branch: "",
      uf: "",
      segment: "",
    }),
    [data, setData] = useState<any>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [refresh, setRefresh] = useState(0);
  const current = tabs.find((item) => item.id === tab)!,
    activeFilters = useMemo(
      () =>
        [filters.branch, filters.uf, filters.segment].filter(Boolean).length,
      [filters],
    );
  useEffect(() => {
    fetch("/api/filters")
      .then((r) => r.json())
      .then((j) => {
        setOptions(j);
        setFilters((f) => ({
          ...f,
          start: f.start || j.default_start,
          end: f.end || j.max_date,
        }));
      })
      .catch(() => setError("A API ainda não está disponível."));
  }, []);
  useEffect(() => {
    if (tab === "chat" || !filters.start) return;
    setLoading(true);
    setError("");
    const suffix = tab === "sources" ? "" : `?${queryString(filters)}`;
    fetch(`/api/${tab}${suffix}`)
      .then(async (r) => {
        const j = await r.json();
        if (!r.ok) throw new Error(j.detail || "Falha ao carregar dados");
        return j;
      })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tab, filters, refresh]);
  function change(key: keyof Filters, value: string) {
    setFilters((f) => ({ ...f, [key]: value }));
  }
  return (
    <div className="shell">
      <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
        <div className="brand">
          <span className="brand-mark">A</span>
          <span>
            ATIVA<small>COMMAND CENTER</small>
          </span>
          <button className="close-menu" onClick={() => setMenuOpen(false)}>
            <X />
          </button>
        </div>
        <nav>
          {tabs.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={tab === item.id ? "active" : ""}
                onClick={() => {
                  setTab(item.id);
                  setMenuOpen(false);
                }}
                key={item.id}
              >
                <Icon size={19} />
                <span>{item.label}</span>
                {tab === item.id && <i />}
              </button>
            );
          })}
        </nav>
        <div className="side-status">
          <span className="pulse" />
          <div>
            <strong>Dados conectados</strong>
            <small>PostgreSQL + BI2</small>
          </div>
        </div>
      </aside>
      {menuOpen && (
        <button className="scrim" onClick={() => setMenuOpen(false)} />
      )}
      <main>
        <header>
          <button className="mobile-menu" onClick={() => setMenuOpen(true)}>
            <Menu />
          </button>
          <div className="page-heading">
            <div className="top-brand" aria-label="Ativa Logística">
              <span>A</span>
              <b>ATIVA<small>LOGÍSTICA</small></b>
            </div>
            <div>
            <span className="eyebrow">{current.eyebrow}</span>
            <h1>{current.label}</h1>
            <p>{current.description}</p>
            </div>
          </div>
          {tab !== "chat" && tab !== "sources" && (
            <section className="filters header-filters">
              <div className="date-range">
                <label>
                  <CalendarDays size={13} /> Período
                </label>
                <div>
                  <input
                    type="date"
                    value={filters.start}
                    min={options?.min_date}
                    max={filters.end || options?.max_date}
                    onChange={(e) => change("start", e.target.value)}
                  />
                  <span>até</span>
                  <input
                    type="date"
                    value={filters.end}
                    min={filters.start || options?.min_date}
                    max={options?.max_date}
                    onChange={(e) => change("end", e.target.value)}
                  />
                </div>
              </div>
              <SelectFilter
                label="Filial"
                value={filters.branch}
                options={options?.branches || []}
                placeholder="Todas as filiais"
                onChange={(v) => change("branch", v)}
              />
              <SelectFilter
                label="Destino"
                value={filters.uf}
                options={options?.states || []}
                placeholder="Todos os estados"
                onChange={(v) => change("uf", v)}
              />
              <SelectFilter
                label="Segmento"
                value={filters.segment}
                options={options?.segments || []}
                placeholder="Todos os segmentos"
                onChange={(v) => change("segment", v)}
              />
              <button
                className="refresh"
                onClick={() => setRefresh((r) => r + 1)}
                title="Atualizar dados"
              >
                <RefreshCw size={17} />
                {activeFilters > 0 && <b>{activeFilters}</b>}
              </button>
            </section>
          )}
          <div className="header-actions">
            {tab !== "chat" && (
              <button className="assistant" onClick={() => setTab("chat")}>
                <Sparkles size={17} />
                <span>Pergunte aos dados</span>
              </button>
            )}
            <button className="avatar">AL</button>
          </div>
        </header>
        <div className="page-content">
          {tab === "chat" ? (
            <Chat filters={filters} />
          ) : loading ? (
            <LoadingPanel />
          ) : error ? (
            <div className="error-state">
              <Zap />
              <strong>Não foi possível carregar esta visão</strong>
              <p>{error}</p>
              <button onClick={() => setRefresh((r) => r + 1)}>
                <RefreshCw size={16} /> Tentar novamente
              </button>
            </div>
          ) : tab === "overview" ? (
            <Overview data={data} filters={filters} />
          ) : tab === "operations" ? (
            <Operations data={data} />
          ) : tab === "deliveries" ? (
            <Deliveries data={data} />
          ) : tab === "finance" ? (
            <Finance data={data} />
          ) : tab === "fleet" ? (
            <Fleet data={data} />
          ) : (
            <Sources data={data} />
          )}
        </div>
      </main>
    </div>
  );
}

function SelectFilter({
  label,
  value,
  options,
  placeholder,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  placeholder: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="select-filter">
      <label>{label}</label>
      <div>
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">{placeholder}</option>
          {options.map((o) => (
            <option value={o} key={o}>
              {o}
            </option>
          ))}
        </select>
        <ChevronDown size={14} />
      </div>
    </div>
  );
}
