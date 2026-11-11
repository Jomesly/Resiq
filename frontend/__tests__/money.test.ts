import { describe, expect, it } from "vitest";
import { formatPeso, sumMoney, toCents, centsToString } from "@/lib/money";

describe("money", () => {
  it("formats pesos with grouping and two decimals", () => {
    expect(formatPeso("1250.5")).toBe("₱1,250.50");
    expect(formatPeso("135")).toBe("₱135.00");
  });
  it("formats null as a dash", () => {
    expect(formatPeso(null)).toBe("—");
  });
  it("sums in centavos, never floats", () => {
    expect(sumMoney(["0.10", "0.20"])).toBe("0.30");
    expect(sumMoney(["120.54", "14.46", null])).toBe("135.00");
  });
  it("converts to and from centavos", () => {
    expect(toCents("1,250.50")).toBe(125050);
    expect(toCents("")).toBeNull();
    expect(centsToString(-1000)).toBe("-10.00");
  });
});
