import { z } from 'zod';

export const LoginResponseSchema = z.object({ access_token: z.string(), refresh_token: z.string().optional(), token_type: z.string().optional() });
export const AccountInfoSchema = z.object({ balance: z.number(), equity: z.number(), margin: z.number(), free_margin: z.number(), margin_level: z.number().nullable().optional(), profit: z.number(), leverage: z.number(), currency: z.string() });
export const PositionSchema = z.object({ id: z.string(), symbol: z.string(), quantity: z.number(), entry_price: z.number(), current_price: z.number().optional(), pnl: z.number().optional(), pnl_pct: z.number().optional() });
export const PositionListSchema = z.array(PositionSchema);
export const OrderSubmissionSchema = z.object({ ok: z.boolean(), retcode: z.number().optional(), retcode_message: z.string().optional(), broker_order_id: z.number().optional() });
export const BacktestResultSchema = z.object({ total_return: z.number(), sharpe_ratio: z.number(), max_drawdown: z.number(), equity_curve: z.any(), drawdown_curve: z.any() });
export const ModelSchema = z.object({ id: z.string(), name: z.string(), version: z.number(), stage: z.string(), status: z.string().optional(), metrics: z.record(z.any()) });
export const ModelRegistrySchema = z.array(ModelSchema);

export function validateSchema<T>(schema: z.ZodSchema<T>, data: unknown): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    // @ts-ignore
    if (window.Sentry) {
      // @ts-ignore
      window.Sentry.captureMessage('API schema validation failed', { extra: { issues: result.error.issues } });
    }
    throw new Error('Invalid API response schema');
  }
  return result.data;
}
