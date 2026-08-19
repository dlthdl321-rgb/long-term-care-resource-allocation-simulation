export function InsightCallout({ label = "한눈에 보는 결론", title, detail }: {
  label?: string; title: string; detail: string;
}) {
  return <div className="insight-callout"><span>{label}</span><div><strong>{title}</strong><p>{detail}</p></div></div>;
}
