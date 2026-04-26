const SNAKE_RE = /_[a-z]/g;

function toCamelKey(key: string): string {
  return key.replace(SNAKE_RE, (m) => m[1].toUpperCase());
}

function transformKeys(obj: unknown): unknown {
  if (obj === null || obj === undefined) return obj;
  if (Array.isArray(obj)) return obj.map(transformKeys);
  if (typeof obj === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      out[toCamelKey(k)] = transformKeys(v);
    }
    return out;
  }
  return obj;
}

export function toCamelCase<T>(data: unknown): T {
  if (data === null || data === undefined) {
    return data as T;
  }
  return transformKeys(data) as T;
}
