const ph = "en-PH";
const short = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const timestampDay = new Intl.DateTimeFormat("en-GB", { dateStyle: "long", timeZone: "Asia/Manila" });
const timestampTime = new Intl.DateTimeFormat("en-GB", { timeStyle: "short", hour12: true, timeZone: "Asia/Manila" });
const monthName = new Intl.DateTimeFormat(ph, { month: "long", timeZone: "UTC" });
const monthYear = new Intl.DateTimeFormat(ph, { month: "long", year: "numeric", timeZone: "UTC" });

export const SAMPLE_MONTH = "2026-11";
export const isMonth = (value: string) => /^\d{4}-(0[1-9]|1[0-2])$/.test(value);
export const formatDate = (date: string | null) => date ? short.format(new Date(`${date.slice(0, 10)}T00:00:00Z`)) : "—";
export const formatDateTime = (date: string) => {
  const time = new Date(date);
  return timestampDay.format(time) + ", " + timestampTime.format(time);
};
export const formatMonth = (month: string, withYear = false) => (withYear ? monthYear : monthName).format(new Date(`${month}-01T00:00:00Z`));
export const currentMonth = () => new Intl.DateTimeFormat("sv-SE", { year: "numeric", month: "2-digit", timeZone: "Asia/Manila" }).format(new Date());

export function monthOptions(extra: string[] = []) {
  const [year, month] = currentMonth().split("-").map(Number);
  const recent = Array.from({ length: 12 }, (_, i) => new Date(Date.UTC(year, month - 1 - i, 1)).toISOString().slice(0, 7));
  return [...new Set([...recent, ...extra.filter(isMonth)])].sort().reverse();
}
