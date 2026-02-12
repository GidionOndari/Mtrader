import { describe, it, expect } from 'vitest';
import { validateSchema, LoginResponseSchema } from '../../../frontend/src/validation/api-schemas';

describe('api schema', () => {
  it('validates login', () => {
    const out = validateSchema(LoginResponseSchema, { access_token: 'a', refresh_token: 'b' });
    expect(out.access_token).toBe('a');
  });
});
