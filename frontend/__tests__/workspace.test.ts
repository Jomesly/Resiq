import { afterEach, expect, test, vi } from "vitest";
import { getToken } from "../lib/workspace";

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

