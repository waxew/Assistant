import { and, asc, count, desc, eq, sql } from "drizzle-orm";
import { getDb } from "../db";
import {
  appointments,
  automations,
  customers,
  feedback,
  messageLog,
  services,
  staff,
} from "../db/schema";
import {
  seedAppointments,
  seedAutomations,
  seedCustomers,
  seedFeedback,
  seedServices,
  seedStaff,
} from "./seed";

export async function ensureSeeded() {
  const db = getDb();
  const [{ value: customerCount }] = await db.select({ value: count() }).from(customers);
  if (customerCount === 0) await db.insert(customers).values(seedCustomers);

  const [{ value: staffCount }] = await db.select({ value: count() }).from(staff);
  if (staffCount === 0) await db.insert(staff).values(seedStaff);

  const [{ value: serviceCount }] = await db.select({ value: count() }).from(services);
  if (serviceCount === 0) await db.insert(services).values(seedServices);

  const [{ value: appointmentCount }] = await db.select({ value: count() }).from(appointments);
  if (appointmentCount === 0) await db.insert(appointments).values(seedAppointments);

  const [{ value: automationCount }] = await db.select({ value: count() }).from(automations);
  if (automationCount === 0) await db.insert(automations).values(seedAutomations);

  const [{ value: feedbackCount }] = await db.select({ value: count() }).from(feedback);
  if (feedbackCount === 0) await db.insert(feedback).values(seedFeedback);
}

export async function readBootstrapData() {
  await ensureSeeded();
  const db = getDb();
  const [customerRows, staffRows, serviceRows, appointmentRows, messageRows, automationRows, feedbackRows] = await Promise.all([
    db.select().from(customers).orderBy(desc(customers.createdAt)),
    db.select().from(staff).orderBy(asc(staff.name)),
    db.select().from(services).orderBy(asc(services.name)),
    db.select().from(appointments).orderBy(asc(appointments.date), asc(appointments.time)),
    db.select().from(messageLog).orderBy(desc(messageLog.createdAt)).limit(40),
    db.select().from(automations).orderBy(asc(automations.kind)),
    db.select().from(feedback).orderBy(desc(feedback.createdAt)).limit(40),
  ]);
  return {
    customers: customerRows,
    staff: staffRows,
    services: serviceRows,
    appointments: appointmentRows,
    messages: messageRows,
    automations: automationRows,
    feedback: feedbackRows,
  };
}

export async function markAppointment(id: string, status: string) {
  const db = getDb();
  const current = await db.select().from(appointments).where(eq(appointments.id, id)).limit(1);
  if (!current[0]) return null;

  const allowed = new Set(["confirmed", "pending", "completed", "cancelled"]);
  if (!allowed.has(status)) throw new Error("وضعیت نوبت معتبر نیست.");

  const [updated] = await db.update(appointments).set({ status }).where(eq(appointments.id, id)).returning();
  if (status === "completed" && current[0].status !== "completed") {
    const service = await db.select().from(services).where(eq(services.id, current[0].serviceId)).limit(1);
    await db
      .update(customers)
      .set({
        totalVisits: sql`${customers.totalVisits} + 1`,
        totalSpent: sql`${customers.totalSpent} + ${service[0]?.price ?? 0}`,
        lastVisit: current[0].date,
      })
      .where(and(eq(customers.id, current[0].customerId)));
  }
  return updated;
}

export function apiError(error: unknown, fallback = "خطایی رخ داد.") {
  const message = error instanceof Error ? error.message : fallback;
  return Response.json({ error: message }, { status: 500 });
}
