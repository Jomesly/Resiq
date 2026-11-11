import { afterEach, expect, test, vi } from "vitest";
import { getToken, setToken } from "../lib/workspace";

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals(); });

test("workspace tokens are scoped to the API and concurrent requests share creation", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ token: "one" })))
    .mockResolvedValueOnce(new Response(JSON.stringify({ token: "two" })));
  vi.stubGlobal("fetch", fetcher);
  expect(await Promise.all([getToken("https://first.test"), getToken("https://first.test")])).toEqual(["one", "one"]);
  expect(await getToken("https://second.test")).toBe("two");
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(await getToken("https://first.test")).toBe("one");
});

test("an in-flight anonymous creation cannot overwrite a recovered workspace", async () => {
  let resolve!: (response: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((done) => { resolve = done; })));
  const pending = getToken("https://receipt.test");
  setToken("https://receipt.test", "recovered");
  resolve(new Response(JSON.stringify({ token: "anonymous" })));
  expect(await pending).toBe("recovered");
  expect(await getToken("https://receipt.test")).toBe("recovered");
});

