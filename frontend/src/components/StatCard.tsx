interface StatCardProps { label: string; value: string; detail: string; positive?: boolean }

export function StatCard({ label, value, detail, positive }: StatCardProps) {
  return <article className="stat-card"><span>{label}</span><strong className={positive ? "positive" : undefined}>{value}</strong><small>{detail}</small></article>;
}
