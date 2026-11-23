import React, { useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const RISK_COLORS = {
  Low: '#10b981',
  Medium: '#f59e0b',
  High: '#f97316',
  Critical: '#ef4444',
  Unscored: '#94a3b8',
};

const EXEC_COLORS = {
  Pass: '#10b981',
  Fail: '#ef4444',
  Blocked: '#f59e0b',
  'Not Run': '#94a3b8',
};

const BUG_COLORS = {
  Critical: '#dc2626',
  High: '#ea580c',
  Medium: '#d97706',
  Low: '#0d9488',
};

function ChartCard({ title, subtitle, hasData, emptyText, children }) {
  return (
    <article className="flex flex-col rounded-xl border border-line bg-surface p-4 shadow-xs min-w-0">
      <div className="mb-3 space-y-0.5">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
      </div>
      {hasData ? (
        <div className="h-[220px] w-full min-w-0">{children}</div>
      ) : (
        <div className="flex h-[220px] items-center justify-center rounded-lg border border-dashed border-line bg-surface-alt/40 px-4 text-center text-xs text-muted">
          {emptyText}
        </div>
      )}
    </article>
  );
}

const TOOLTIP_STYLE = {
  backgroundColor: 'var(--surface)',
  borderColor: 'var(--line)',
  borderRadius: '0.5rem',
  color: 'var(--ink)',
  fontSize: '12px',
};

export default function DashboardCharts({ riskData = [], executionCounts = {}, bugSeverityCounts = {} }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const riskSeries = riskData.filter((item) => item && typeof item.count === 'number');
  const hasRisk = riskSeries.some((item) => item.count > 0);

  const executionSeries = ['Pass', 'Fail', 'Blocked', 'Not Run'].map((name) => ({
    name,
    value: Number(executionCounts?.[name] || 0),
  }));
  const hasExecutions = executionSeries.some((item) => item.value > 0);
  const totalPassFail = (executionCounts?.Pass || 0) + (executionCounts?.Fail || 0);
  const passRate = totalPassFail ? Math.round(((executionCounts?.Pass || 0) * 100) / totalPassFail) : 0;

  const bugSeries = ['Critical', 'High', 'Medium', 'Low'].map((name) => ({
    name,
    count: Number(bugSeverityCounts?.[name] || 0),
  }));
  const hasBugs = bugSeries.some((item) => item.count > 0);

  return (
    <section className="grid grid-cols-1 gap-4 lg:grid-cols-3" aria-label="Quality analytics charts">
      <ChartCard
        title="Requirement Risk Breakdown"
        subtitle="AI quality risk classification across requirements"
        hasData={hasRisk && mounted}
        emptyText={hasRisk ? 'Rendering chart…' : 'No analyzed requirements recorded yet.'}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={riskSeries} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={{ stroke: 'var(--line)' }} tickLine={false} />
            <YAxis allowDecimals={false} tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'var(--surface-alt)' }} />
            <Bar dataKey="count" name="Requirements" radius={[6, 6, 0, 0]} maxBarSize={38}>
              {riskSeries.map((entry) => (
                <Cell key={entry.name} fill={RISK_COLORS[entry.name] || '#6366f1'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard
        title="Test Pass / Fail Ratio"
        subtitle={totalPassFail ? `${passRate}% pass across executed pass/fail cases` : 'Latest execution per active case revision'}
        hasData={hasExecutions && mounted}
        emptyText={hasExecutions ? 'Rendering chart…' : 'No active test cases recorded yet.'}
      >
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={executionSeries.filter((item) => item.value > 0)}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="46%"
              innerRadius={48}
              outerRadius={74}
              paddingAngle={2}
            >
              {executionSeries
                .filter((item) => item.value > 0)
                .map((entry) => (
                  <Cell key={entry.name} fill={EXEC_COLORS[entry.name] || '#94a3b8'} />
                ))}
            </Pie>
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Legend iconType="circle" wrapperStyle={{ fontSize: '11px', color: 'var(--muted)' }} />
          </PieChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard
        title="Open Defects by Severity"
        subtitle="Non-closed bugs across project history"
        hasData={hasBugs && mounted}
        emptyText={hasBugs ? 'Rendering chart…' : 'No open defects reported.'}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={bugSeries} layout="vertical" margin={{ top: 6, right: 16, left: 4, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" horizontal={false} />
            <XAxis type="number" allowDecimals={false} tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={{ stroke: 'var(--line)' }} tickLine={false} />
            <YAxis type="category" dataKey="name" width={64} tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'var(--surface-alt)' }} />
            <Bar dataKey="count" name="Open Bugs" radius={[0, 6, 6, 0]} maxBarSize={24}>
              {bugSeries.map((entry) => (
                <Cell key={entry.name} fill={BUG_COLORS[entry.name] || '#6366f1'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </section>
  );
}
