import { describe, expect, it } from 'vitest';
import { appRoutes } from '@/router';

describe('frontend scaffold', () => {
  it('registers the expected app routes', () => {
    const paths = appRoutes.flatMap((route) => {
      if (route.children?.length) {
        return route.children.map((child) => `/${String(child.path).replace(/^\//, '')}`);
      }

      return [route.path];
    });

    expect(paths).toContain('/login');
    expect(paths).toContain('/reset-password');
    expect(paths).toContain('/usage');
    expect(paths).toContain('/api-manage');
    expect(paths).toContain('/key-manage');
    expect(paths).toContain('/chat-history');
  });
});
