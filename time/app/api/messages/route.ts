import { getDb } from "../../../db";
import { messageLog } from "../../../db/schema";
import { apiError } from "../../../lib/server-data";

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as Record<string, unknown>;
    const message = String(body.body ?? "").trim();
    if (!message) return Response.json({ error: "متن پیام خالی است." }, { status: 400 });
    const db = getDb();
    const [item] = await db.insert(messageLog).values({
      id: crypto.randomUUID(),
      kind: String(body.kind ?? "group"),
      audience: String(body.audience ?? "همه مشتریان"),
      body: message,
      recipients: Number(body.recipients ?? 0),
      status: "queued",
    }).returning();
    return Response.json({ message: item }, { status: 201 });
  } catch (error) {
    return apiError(error, "ثبت پیام با خطا روبه‌رو شد.");
  }
}
