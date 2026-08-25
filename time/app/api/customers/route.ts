import { eq } from "drizzle-orm";
import { getDb } from "../../../db";
import { customers } from "../../../db/schema";
import { apiError, ensureSeeded } from "../../../lib/server-data";

export async function POST(request: Request) {
  try {
    await ensureSeeded();
    const body = (await request.json()) as Record<string, unknown>;
    const name = String(body.name ?? "").trim();
    const phone = String(body.phone ?? "").replace(/\s/g, "");
    if (name.length < 2) return Response.json({ error: "نام مشتری را کامل وارد کنید." }, { status: 400 });
    if (!/^09\d{9}$/.test(phone)) return Response.json({ error: "شماره موبایل معتبر نیست." }, { status: 400 });

    const db = getDb();
    const duplicate = await db.select({ id: customers.id }).from(customers).where(eq(customers.phone, phone)).limit(1);
    if (duplicate[0]) return Response.json({ error: "این شماره قبلاً ثبت شده است." }, { status: 409 });

    const [customer] = await db.insert(customers).values({
      id: crypto.randomUUID(),
      name,
      phone,
      occupation: String(body.occupation ?? "").trim(),
      gender: String(body.gender ?? "نامشخص"),
      birthDate: body.birthDate ? String(body.birthDate) : null,
      groupName: String(body.groupName ?? "مشتریان معمولی"),
      referralSource: String(body.referralSource ?? "معرفی دوستان"),
      notes: String(body.notes ?? "").trim(),
    }).returning();
    return Response.json({ customer }, { status: 201 });
  } catch (error) {
    return apiError(error, "ثبت مشتری با خطا روبه‌رو شد.");
  }
}

export async function PATCH(request: Request) {
  try {
    const body = (await request.json()) as Record<string, unknown>;
    const id = String(body.id ?? "");
    if (!id) return Response.json({ error: "شناسه مشتری لازم است." }, { status: 400 });
    const db = getDb();
    const [customer] = await db.update(customers).set({
      name: String(body.name ?? "").trim(),
      occupation: String(body.occupation ?? "").trim(),
      gender: String(body.gender ?? "نامشخص"),
      birthDate: body.birthDate ? String(body.birthDate) : null,
      groupName: String(body.groupName ?? "مشتریان معمولی"),
      referralSource: String(body.referralSource ?? "معرفی دوستان"),
      notes: String(body.notes ?? "").trim(),
    }).where(eq(customers.id, id)).returning();
    return Response.json({ customer });
  } catch (error) {
    return apiError(error, "ویرایش مشتری با خطا روبه‌رو شد.");
  }
}
