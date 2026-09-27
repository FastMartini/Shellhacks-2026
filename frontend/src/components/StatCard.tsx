interface StatCardProps { label: string; value: string; detail: string; tone?: "positive" | "negative" }

export function StatCard({ label, value, detail, tone }: StatCardProps) {
  return <article className="stat-card"><span>{label}</span><strong className={tone}>{value}</strong><small className={tone}>{detail}</small></article>;
}
