import type { MetricValue } from "../types";

export function formatDate(value: string | null) {
  if (!value) {
    return "";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "short"
  }).format(new Date(value));
}

export function labelize(value: string) {
  return value.replaceAll("_", " ");
}

export function metricValue(value: MetricValue): number | string | null {
  if (typeof value === "object" && value !== null) {
    return value.value ?? value.status;
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? value : value.toFixed(2);
  }
  return value;
}
