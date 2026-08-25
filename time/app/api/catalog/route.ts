import { getDb } from "../../../db";
import { services, staff } from "../../../db/schema";
import { apiError } from "../../../lib/server-data";

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as Record<string, unknown>;
    const kind = String(body.kind ?? "");
    const name = String(body.name ?? "").trim();
    if (name.length < 2) return Response.json({ error: "نام را کامل وارد کنید." }, { status: 400 });
    const db = getDb();
    if (kind === "staff") {
      const [employee] = await db.insert(staff).values({
        id: crypto.randomUUID(),
        name,
        role: String(body.role ?? "متخصص خدمات"),
        phone: String(body.phone ?? ""),
        color: String(body.color ?? "#7c3aed"),
      }).returning();
      return Response.json({ employee }, { status: 201 });
    }
    if (kind === "service") {
      const [service] = await db.insert(services).values({
        id: crypto.randomUUID(),
        name,
        duration: Number(body.duration ?? 60),
        price: Number(body.price ?? 0),
        staffId: body.staffId ? String(body.staffId) : null,
        color: String(body.color ?? "#7c3aed"),
      }).returning();
      return Response.json({ service }, { status: 201 });
    }
    return Response.json({ error: "نوع داده معتبر نیست." }, { status: 400 });
  } catch (error) {
    return apiError(error, "ثبت اطلاعات با خطا روبه‌رو شد.");
  }
}
