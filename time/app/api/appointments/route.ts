import { eq } from "drizzle-orm";
import { getDb } from "../../../db";
import { appointments, customers, services, staff } from "../../../db/schema";
import { apiError, ensureSeeded, markAppointment } from "../../../lib/server-data";

export async function POST(request: Request) {
  try {
    await ensureSeeded();
    const body = (await request.json()) as Record<string, unknown>;
    const required = ["customerId", "staffId", "serviceId", "date", "time"];
    if (required.some((key) => !String(body[key] ?? "").trim())) {
      return Response.json({ error: "مشتری، خدمت، پرسنل، تاریخ و ساعت الزامی‌اند." }, { status: 400 });
    }
    const db = getDb();
    const [customer, employee, service] = await Promise.all([
      db.select({ id: customers.id }).from(customers).where(eq(customers.id, String(body.customerId))).limit(1),
      db.select({ id: staff.id }).from(staff).where(eq(staff.id, String(body.staffId))).limit(1),
      db.select({ id: services.id }).from(services).where(eq(services.id, String(body.serviceId))).limit(1),
    ]);
    if (!customer[0] || !employee[0] || !service[0]) {
      return Response.json({ error: "اطلاعات انتخاب‌شده معتبر نیست." }, { status: 400 });
    }
    const [appointment] = await db.insert(appointments).values({
      id: crypto.randomUUID(),
      customerId: String(body.customerId),
      staffId: String(body.staffId),
      serviceId: String(body.serviceId),
      date: String(body.date),
      time: String(body.time),
      status: "confirmed",
      notes: String(body.notes ?? "").trim(),
      reminderSms: body.reminderSms === true || body.reminderSms === "true",
      reminderHours: Number(body.reminderHours ?? 24),
    }).returning();
    return Response.json({ appointment }, { status: 201 });
  } catch (error) {
    return apiError(error, "ثبت نوبت با خطا روبه‌رو شد.");
  }
}

export async function PATCH(request: Request) {
  try {
    const body = (await request.json()) as Record<string, unknown>;
    const appointment = await markAppointment(String(body.id ?? ""), String(body.status ?? ""));
    if (!appointment) return Response.json({ error: "نوبت پیدا نشد." }, { status: 404 });
    return Response.json({ appointment });
  } catch (error) {
    return apiError(error, "تغییر وضعیت نوبت با خطا روبه‌رو شد.");
  }
}
