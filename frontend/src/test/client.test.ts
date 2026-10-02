import { analyzeStream } from "../api/client";

function sse(blocks: string[]): Response {
  const enc = new TextEncoder();
  const body = new ReadableStream({
    start(c) {
      // Split mid-event to prove the parser buffers across chunks.
      const text = blocks.join("");
      c.enqueue(enc.encode(text.slice(0, 25)));
      c.enqueue(enc.encode(text.slice(25)));
      c.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

describe("analyzeStream", () => {
  it("parses stage, preliminary and result events", async () => {
    const stages: string[] = [];
    let prelim = false;
    globalThis.fetch = vi.fn().mockResolvedValue(
      sse([
        'event: stage\ndata: {"stage":"normalize","message":"Reading"}\n\n',
        'event: preliminary\ndata: {"id":"preliminary"}\n\n',
        'event: result\ndata: {"id":"abc","payload":{}}\n\n',
      ]),
    );
    const result = await analyzeStream({ text: "माया" }, { onStage: (s) => stages.push(s.stage), onPreliminary: () => (prelim = true) });
    expect(stages).toEqual(["normalize"]);
    expect(prelim).toBe(true);
    expect(result.id).toBe("abc");
  });

  it("surfaces server error events", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(sse(['event: error\ndata: {"detail":"Please enter a phrase to analyse."}\n\n']));
    await expect(analyzeStream({ text: " " }, {})).rejects.toThrow("Please enter a phrase");
  });
});
