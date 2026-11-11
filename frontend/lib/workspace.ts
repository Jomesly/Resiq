const keyFor = (base: string) => "resiq.token:" + base;
const pending = new Map<string, Promise<string>>();

export function clearToken(base: string): void {
  pending.delete(base);
  if (typeof localStorage !== "undefined") localStorage.removeItem(keyFor(base));
}

/** The anonymous workspace token: read from storage, or created once (concurrent callers share one request). */
export function getToken(base: string): Promise<string> {
  const stored = localStorage.getItem(keyFor(base));
  if (stored) return Promise.resolve(stored);
  if (!pending.has(base)) {
    pending.set(base, fetch(`${base}/api/workspaces`, { method: "POST" })
      .then(async (res) => {
        if (!res.ok) throw new Error(`Could not start a workspace (${res.status})`);
        const { token } = (await res.json()) as { token: string };
        if (typeof token !== "string" || !token) throw new Error("The workspace response was invalid.");
        localStorage.setItem(keyFor(base), token);
        return token;
      })
      .finally(() => {
        pending.delete(base);
      }));
  }
  return pending.get(base)!;
}
