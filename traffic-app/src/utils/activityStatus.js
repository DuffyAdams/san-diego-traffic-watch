// These are volume heuristics, not incident severity or statistical significance.
// Require both a relative change and an absolute margin so a single incident
// cannot trigger an alert against a small (or zero) baseline.
export function classifyActivity({ current, average, sampleCount, hasData }) {
  if (!hasData || !Number.isFinite(current) || current < 0) return "noData";
  if (!Number.isFinite(average) || average < 0 ||
      !Number.isInteger(sampleCount) || sampleCount < 3) return "insufficientHistory";

  const difference = current - average;
  if (current >= average * 2 && difference >= 5) return "highActivity";
  if (current >= average * 1.5 && difference >= 3) return "elevatedIncidents";
  if (current <= average * 0.75 && difference <= -3) return "lightIncidents";
  return "nominal";
}
