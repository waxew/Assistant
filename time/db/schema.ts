import { sql } from "drizzle-orm";
import { index, integer, real, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const customers = sqliteTable(
  "customers",
  {
    id: text("id").primaryKey(),
    name: text("name").notNull(),
    phone: text("phone").notNull().unique(),
    occupation: text("occupation").notNull().default(""),
    gender: text("gender").notNull().default("نامشخص"),
    birthDate: text("birth_date"),
    groupName: text("group_name").notNull().default("مشتریان معمولی"),
    referralSource: text("referral_source").notNull().default("معرفی دوستان"),
    notes: text("notes").notNull().default(""),
    totalVisits: integer("total_visits").notNull().default(0),
    totalSpent: real("total_spent").notNull().default(0),
    lastVisit: text("last_visit"),
    createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
  },
  (table) => [
    index("customers_name_idx").on(table.name),
    index("customers_group_idx").on(table.groupName),
  ],
);

export const staff = sqliteTable("staff", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  role: text("role").notNull(),
  phone: text("phone").notNull().default(""),
  color: text("color").notNull().default("#7c3aed"),
  active: integer("active", { mode: "boolean" }).notNull().default(true),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});

export const services = sqliteTable("services", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  duration: integer("duration").notNull().default(60),
  price: real("price").notNull().default(0),
  staffId: text("staff_id").references(() => staff.id, { onDelete: "set null" }),
  color: text("color").notNull().default("#7c3aed"),
  active: integer("active", { mode: "boolean" }).notNull().default(true),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});

export const appointments = sqliteTable(
  "appointments",
  {
    id: text("id").primaryKey(),
    customerId: text("customer_id")
      .notNull()
      .references(() => customers.id, { onDelete: "cascade" }),
    staffId: text("staff_id")
      .notNull()
      .references(() => staff.id, { onDelete: "restrict" }),
    serviceId: text("service_id")
      .notNull()
      .references(() => services.id, { onDelete: "restrict" }),
    date: text("date").notNull(),
    time: text("time").notNull(),
    status: text("status").notNull().default("confirmed"),
    notes: text("notes").notNull().default(""),
    reminderSms: integer("reminder_sms", { mode: "boolean" }).notNull().default(true),
    reminderHours: integer("reminder_hours").notNull().default(24),
    createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
  },
  (table) => [
    index("appointments_date_idx").on(table.date),
    index("appointments_customer_idx").on(table.customerId),
  ],
);

export const messageLog = sqliteTable("message_log", {
  id: text("id").primaryKey(),
  kind: text("kind").notNull(),
  audience: text("audience").notNull(),
  body: text("body").notNull(),
  recipients: integer("recipients").notNull().default(0),
  status: text("status").notNull().default("queued"),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});

export const automations = sqliteTable("automations", {
  id: text("id").primaryKey(),
  kind: text("kind").notNull().unique(),
  enabled: integer("enabled", { mode: "boolean" }).notNull().default(false),
  message: text("message").notNull().default(""),
  offsetHours: integer("offset_hours").notNull().default(24),
  updatedAt: text("updated_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});

export const feedback = sqliteTable("feedback", {
  id: text("id").primaryKey(),
  customerId: text("customer_id").references(() => customers.id, { onDelete: "set null" }),
  score: integer("score").notNull(),
  comment: text("comment").notNull().default(""),
  visible: integer("visible", { mode: "boolean" }).notNull().default(false),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});
