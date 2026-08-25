import { eq } from "drizzle-orm";
import { getDb } from "../../../db";
import { automations } from "../../../db/schema";
import { apiError } from "../../../lib/server-data";

export async function PATCH(request: Request) {
  try {
    const body = (await request.json()) as Record<string, unknown>;
    const kind = String(body.kind ?? "");
    const db = getDb();
    const [automation] = await db.update(automations).set({
      enabled: Boolean(body.enabled),
      message: String(body.message ?? ""),
      offsetHours: Number(body.offsetHours ?? 24),
      updatedAt: new Date().toISOString(),
    }).where(eq(automations.kind, kind)).returning();
    if (!automation) return Response.json({ error: "اتوماسیون پیدا نشد." }, { status: 404 });
    return Response.json({ automation });
  } catch (error) {
    return apiError(error, "ذخیره اتوماسیون با خطا روبه‌رو شد.");
  }
}
