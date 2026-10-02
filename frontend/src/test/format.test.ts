import { plateParts, toNepaliDigits } from "../lib/format";

describe("format helpers", () => {
  it("renders Devanagari numerals", () => {
    expect(toNepaliDigits(2026)).toBe("२०२६");
  });
  it("splits corpus ids for number plates", () => {
    expect(plateParts("NVL-021")).toEqual({ prefix: "NVL", number: "०२१" });
  });
});
