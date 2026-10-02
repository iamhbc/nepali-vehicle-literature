import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { Graph } from "../api/types";
import { ConfidenceIndicator, NepaliPhrase } from "../components/analysis-ui";
import { MindMap } from "../components/MindMap";

const graph: Graph = {
  nodes: [
    { id: "root", label: "माया भनेको सम्झना रहेछ", type: "root", detail: { translation: "Love turns out to be memory" } },
    { id: "dim:emotion", label: "Emotion", label_ne: "भावना", type: "dimension", dimension: "emotion", detail: { summary: "Longing" } },
    {
      id: "dim:emotion:0", label: "Longing", type: "finding", dimension: "emotion", confidence: "medium", kind: "interpretation",
      detail: { explanation: "Memory as the residue of love.", evidence: ["सम्झना"] },
    },
  ],
  edges: [
    { source: "root", target: "dim:emotion", weight: 1 },
    { source: "dim:emotion", target: "dim:emotion:0", weight: 0.66 },
  ],
};

describe("NepaliPhrase", () => {
  it("marks evidence quotes inside the phrase", () => {
    const { container } = render(<NepaliPhrase text="माया भनेको सम्झना रहेछ" highlight={["सम्झना", "not in text"]} />);
    const marks = container.querySelectorAll("mark");
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe("सम्झना");
  });
});

describe("ConfidenceIndicator", () => {
  it("always states confidence in words, not only colour", () => {
    render(<ConfidenceIndicator value="low" />);
    expect(screen.getByText("Low")).toBeInTheDocument();
  });
});

describe("MindMap", () => {
  it("offers an accessible branches view and node details", () => {
    render(
      <MemoryRouter>
        <MindMap graph={graph} />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Branches" }));
    const leaf = screen.getByRole("button", { name: /Longing/ });
    fireEvent.click(leaf);
    expect(screen.getByText("Memory as the residue of love.")).toBeInTheDocument();
    expect(screen.getByText("Interpretation")).toBeInTheDocument();
  });
});
