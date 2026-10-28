import { runtime } from "./config.js";

export { runtime };
export async function readJSON(path) {
  const response = await fetch(path, { cache: "no-cache" });
  if (!response.ok) throw Error(`Data request failed (${response.status})`);
  if (!path.endsWith(".gz")) return response.json();
  const bytes = new Uint8Array(await response.arrayBuffer());
  // Pages can serve gzip files as bytes, or an intermediary may decode them.
  if (bytes[0] === 0x1f && bytes[1] === 0x8b) {
    const stream = new Blob([bytes]).stream().pipeThrough(
      new DecompressionStream("gzip"),
    );
    return new Response(stream).json();
  }
  return JSON.parse(new TextDecoder().decode(bytes));
}
export function chartPath(provider, index) {
  return runtime.mode === "static"
    ? `data/charts/${provider}-${index}.json.gz`
    : `api/chart?provider=${encodeURIComponent(provider)}&index=${
      encodeURIComponent(index)
    }`;
}
