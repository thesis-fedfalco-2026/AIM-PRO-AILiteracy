import { describe, expect, it } from 'vitest';

import { createAuthoringClient } from '../src/index';

describe('createAuthoringClient', () => {
  it('sends same-origin credentials and never caches API responses', async () => {
    const seen: Request[] = [];
    const client = createAuthoringClient({
      baseUrl: 'http://studio.test',
      fetch: async (request: Request) => {
        seen.push(request);
        return Response.json({ status: 'ok' });
      },
    });
    const { data } = await client.GET('/health');
    expect(data).toEqual({ status: 'ok' });
    expect(seen).toHaveLength(1);
    expect(seen[0]?.url).toBe('http://studio.test/health');
    expect(seen[0]?.credentials).toBe('same-origin');
    expect(seen[0]?.cache).toBe('no-store');
  });
});
