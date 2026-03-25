export function newId() {
  const c = globalThis.crypto as Crypto | undefined;
  if (c && "randomUUID" in c && typeof c.randomUUID === "function") return c.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

