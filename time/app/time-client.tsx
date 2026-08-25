"use client";

import { FormEvent, useEffect, useState } from "react";
import { Icon, type IconName } from "./icons";
import type { Appointment, Automation, BootstrapData, Customer, Service, Staff } from "../lib/types";
import { seedAppointments, seedAutomations, seedCustomers, seedFeedback, seedServices, seedStaff } from "../lib/seed";

type PageKey = "dashboard" | "appointments" | "customers" | "messages" | "reports" | "tools" | "management" | "profile";
type ModalKey = "appointment" | "customer" | "message" | "staff" | "service" | null;

const initialData: BootstrapData = {
  customers: seedCustomers,
  staff: seedStaff,
  services: seedServices,
  appointments: seedAppointments,
  messages: [],
  automations: seedAutomations,
  feedback: seedFeedback,
};

const navItems: { key: PageKey; label: string; icon: IconName }[] = [
  { key: "dashboard", label: "خانه", icon: "home" },
  { key: "appointments", label: "نوبت‌ها", icon: "calendar" },
  { key: "customers", label: "مشتریان", icon: "users" },
  { key: "messages", label: "پیام‌ها", icon: "message" },
  { key: "reports", label: "گزارش‌ها", icon: "chart" },
  { key: "tools", label: "امکانات", icon: "grid" },
];

const pageTitles: Record<PageKey, string> = {
  dashboard: "داشبورد کسب‌وکار",
  appointments: "مدیریت نوبت‌ها",
  customers: "باشگاه مشتریان",
  messages: "پیامک و ارتباط با مشتری",
  reports: "گزارش‌ها و تحلیل",
  tools: "امکانات هوشمند",
  management: "پرسنل و خدمات",
  profile: "پروفایل و تنظیمات",
};

const faNumber = new Intl.NumberFormat("fa-IR");
const faCompact = new Intl.NumberFormat("fa-IR", { notation: "compact", maximumFractionDigits: 1 });

function money(value: number) {
  return `${faNumber.format(value)} تومان`;
}

function isoToday(offset = 0) {
  const date = new Date();
  date.setHours(12, 0, 0, 0);
  date.setDate(date.getDate() + offset);
  return date.toISOString().slice(0, 10);
}

function formatDate(value: string, mode: "short" | "long" = "long") {
  const date = new Date(`${value}T12:00:00`);
  return new Intl.DateTimeFormat("fa-IR-u-ca-persian", mode === "short"
    ? { month: "short", day: "numeric" }
    : { weekday: "long", month: "long", day: "numeric" }).format(date);
}

function relativeDate(value: string | null) {
  if (!value) return "بدون مراجعه";
  const days = Math.max(0, Math.round((Date.now() - new Date(`${value}T12:00:00`).getTime()) / 86400000));
  if (days === 0) return "امروز";
  if (days < 30) return `${faNumber.format(days)} روز پیش`;
  return `${faNumber.format(Math.round(days / 30))} ماه پیش`;
}

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  const payload = (await response.json()) as T & { error?: string };
  if (!response.ok) throw new Error(payload.error || "ارتباط با سرور برقرار نشد.");
  return payload;
}

export default function TimeApp() {
  const [page, setPage] = useState<PageKey>("dashboard");
  const [data, setData] = useState<BootstrapData>(initialData);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [modal, setModal] = useState<ModalKey>(null);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [toast, setToast] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    let active = true;
    jsonRequest<BootstrapData>("/api/bootstrap")
      .then((result) => { if (active) { setData(result); setOffline(false); } })
      .catch(() => { if (active) setOffline(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 3600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function navigate(next: PageKey) {
    setPage(next);
    setSidebarOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function addCustomer(payload: Record<string, unknown>) {
    const result = await jsonRequest<{ customer: Customer }>("/api/customers", { method: "POST", body: JSON.stringify(payload) });
    setData((current) => ({ ...current, customers: [result.customer, ...current.customers] }));
    setModal(null);
    setToast("پرونده مشتری با موفقیت ساخته شد.");
  }

  async function addAppointment(payload: Record<string, unknown>) {
    const result = await jsonRequest<{ appointment: Appointment }>("/api/appointments", { method: "POST", body: JSON.stringify(payload) });
    setData((current) => ({ ...current, appointments: [...current.appointments, result.appointment].sort((a, b) => `${a.date}${a.time}`.localeCompare(`${b.date}${b.time}`)) }));
    setModal(null);
    setToast("نوبت جدید ثبت و در تقویم قرار گرفت.");
  }

  async function updateAppointment(id: string, status: Appointment["status"]) {
    const result = await jsonRequest<{ appointment: Appointment }>("/api/appointments", { method: "PATCH", body: JSON.stringify({ id, status }) });
    setData((current) => ({ ...current, appointments: current.appointments.map((item) => item.id === id ? result.appointment : item) }));
    setToast(status === "completed" ? "نوبت انجام‌شده ثبت شد." : "وضعیت نوبت تغییر کرد.");
  }

  async function sendMessage(payload: Record<string, unknown>) {
    const result = await jsonRequest<{ message: BootstrapData["messages"][number] }>("/api/messages", { method: "POST", body: JSON.stringify(payload) });
    setData((current) => ({ ...current, messages: [result.message, ...current.messages] }));
    setModal(null);
    setToast("پیام برای ارسال در صف قرار گرفت.");
  }

  async function toggleAutomation(item: Automation) {
    const result = await jsonRequest<{ automation: Automation }>("/api/automations", {
      method: "PATCH",
      body: JSON.stringify({ ...item, enabled: !item.enabled }),
    });
    setData((current) => ({ ...current, automations: current.automations.map((row) => row.id === item.id ? result.automation : row) }));
    setToast(result.automation.enabled ? "ارسال خودکار فعال شد." : "ارسال خودکار غیرفعال شد.");
  }

  async function addCatalog(kind: "staff" | "service", payload: Record<string, unknown>) {
    const result = await jsonRequest<{ employee?: Staff; service?: Service }>("/api/catalog", { method: "POST", body: JSON.stringify({ kind, ...payload }) });
    setData((current) => ({
      ...current,
      staff: result.employee ? [...current.staff, result.employee] : current.staff,
      services: result.service ? [...current.services, result.service] : current.services,
    }));
    setModal(null);
    setToast(kind === "staff" ? "عضو جدید به تیم اضافه شد." : "خدمت جدید اضافه شد.");
  }

  const content = (() => {
    switch (page) {
      case "dashboard": return <Dashboard data={data} onNavigate={navigate} onNewAppointment={() => setModal("appointment")} onNewCustomer={() => setModal("customer")} />;
      case "appointments": return <AppointmentsPage data={data} onNew={() => setModal("appointment")} onStatus={updateAppointment} />;
      case "customers": return <CustomersPage data={data} onNew={() => setModal("customer")} onSelect={setSelectedCustomer} />;
      case "messages": return <MessagesPage data={data} onCompose={() => setModal("message")} onToggle={toggleAutomation} />;
      case "reports": return <ReportsPage data={data} />;
      case "tools": return <ToolsPage data={data} onNavigate={navigate} onCompose={() => setModal("message")} />;
      case "management": return <ManagementPage data={data} onAddStaff={() => setModal("staff")} onAddService={() => setModal("service")} />;
      case "profile": return <ProfilePage />;
    }
  })();

  return (
    <div className="time-app">
      <aside className={`sidebar ${sidebarOpen ? "is-open" : ""}`}>
        <button className="sidebar-close" onClick={() => setSidebarOpen(false)} aria-label="بستن منو"><Icon name="close" /></button>
        <Brand />
        <div className="business-mini">
          <span className="avatar avatar-gradient">س</span>
          <div><b>مجموعه نمونه</b><small>پنل مدیریت</small></div>
          <span className="online-dot" />
        </div>
        <nav className="side-nav" aria-label="منوی اصلی">
          {navItems.map((item) => <button key={item.key} className={page === item.key ? "active" : ""} onClick={() => navigate(item.key)}><Icon name={item.icon} /><span>{item.label}</span>{item.key === "appointments" && <em>{faNumber.format(data.appointments.filter((a) => a.date === isoToday()).length)}</em>}</button>)}
        </nav>
        <div className="side-separator" />
        <button className={`side-secondary ${page === "management" ? "active" : ""}`} onClick={() => navigate("management")}><Icon name="briefcase" />پرسنل و خدمات</button>
        <button className={`side-secondary ${page === "profile" ? "active" : ""}`} onClick={() => navigate("profile")}><Icon name="settings" />تنظیمات حساب</button>
        <div className="plan-box"><div><Icon name="sparkles" /><b>اشتراک حرفه‌ای</b></div><p>۲۵ روز تا تمدید اشتراک</p><span><i style={{ width: "72%" }} /></span></div>
        <p className="version">TIME VER. 1.0</p>
      </aside>
      {sidebarOpen && <button className="scrim" onClick={() => setSidebarOpen(false)} aria-label="بستن منو" />}

      <main className="app-main">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="باز کردن منو"><Icon name="menu" /></button>
          <div className="title-wrap"><p>TIME / {pageTitles[page]}</p><h1>{pageTitles[page]}</h1></div>
          <div className="top-actions">
            <label className="top-search"><Icon name="search" /><input aria-label="جستجوی سریع" placeholder="جستجوی سریع..." /></label>
            <button className="icon-btn has-badge" aria-label="اعلان‌ها"><Icon name="bell" /><span /></button>
            <button className="profile-chip" onClick={() => navigate("profile")}><span className="avatar avatar-gradient">م</span><span><b>مدیر نمونه</b><small>مدیر مجموعه</small></span><Icon name="chevron" size={16} /></button>
          </div>
        </header>
        {offline && !loading && <div className="offline-banner"><Icon name="refresh" /> نسخه نمایشی نمایش داده می‌شود؛ برای ذخیره تغییرات اتصال را بررسی کنید.</div>}
        <div className="page-content">{content}</div>
      </main>

      <nav className="bottom-nav" aria-label="منوی موبایل">
        {navItems.slice(0, 5).map((item) => <button key={item.key} className={page === item.key ? "active" : ""} onClick={() => navigate(item.key)}><Icon name={item.icon} /><span>{item.label}</span></button>)}
        <button className={page === "tools" ? "active" : ""} onClick={() => navigate("tools")}><Icon name="grid" /><span>بیشتر</span></button>
      </nav>

      {modal === "appointment" && <AppointmentModal data={data} onClose={() => setModal(null)} onSubmit={addAppointment} />}
      {modal === "customer" && <CustomerModal onClose={() => setModal(null)} onSubmit={addCustomer} />}
      {modal === "message" && <MessageModal count={data.customers.length} onClose={() => setModal(null)} onSubmit={sendMessage} />}
      {modal === "staff" && <StaffModal onClose={() => setModal(null)} onSubmit={(payload) => addCatalog("staff", payload)} />}
      {modal === "service" && <ServiceModal staff={data.staff} onClose={() => setModal(null)} onSubmit={(payload) => addCatalog("service", payload)} />}
      {selectedCustomer && <CustomerDetail customer={selectedCustomer} data={data} onClose={() => setSelectedCustomer(null)} onNewAppointment={() => { setSelectedCustomer(null); setModal("appointment"); }} />}
      {toast && <div className="toast"><Icon name="check" />{toast}</div>}
    </div>
  );
}

function Brand() {
  return <div className="brand"><span className="brand-mark"><Icon name="check" size={26} /></span><div><strong>TIME</strong><small>BUSINESS PRIME</small></div></div>;
}

function Dashboard({ data, onNavigate, onNewAppointment, onNewCustomer }: { data: BootstrapData; onNavigate: (p: PageKey) => void; onNewAppointment: () => void; onNewCustomer: () => void }) {
  const today = data.appointments.filter((a) => a.date === isoToday() && a.status !== "cancelled");
  const upcoming = data.appointments.filter((a) => a.date >= isoToday() && a.status !== "cancelled").slice(0, 5);
  const income = data.appointments.filter((a) => a.status === "completed").reduce((sum, a) => sum + (data.services.find((s) => s.id === a.serviceId)?.price ?? 0), 0);
  const metrics = [
    { label: "نوبت‌های امروز", value: faNumber.format(today.length), icon: "calendar" as IconName, tone: "violet", detail: `${faNumber.format(today.filter((a) => a.status === "confirmed").length)} تأیید شده` },
    { label: "کل مشتریان", value: faNumber.format(data.customers.length), icon: "users" as IconName, tone: "cyan", detail: "+۱۲٪ نسبت به ماه قبل" },
    { label: "درآمد ثبت‌شده", value: faCompact.format(income), icon: "money" as IconName, tone: "green", detail: "تومان / این دوره" },
    { label: "رضایت مشتریان", value: "۴٫۹", icon: "smile" as IconName, tone: "pink", detail: `${faNumber.format(data.feedback.length)} نظر ثبت‌شده` },
  ];
  return <>
    <section className="welcome-panel">
      <div><span className="eyebrow"><i /> امروز {formatDate(isoToday())}</span><h2>سلام، روزت پربرکت ✦</h2><p>همه‌چیز برای مدیریت یک روز منظم آماده است.</p></div>
      <div className="quick-actions"><button className="btn btn-light" onClick={onNewCustomer}><Icon name="user" /> مشتری جدید</button><button className="btn btn-primary" onClick={onNewAppointment}><Icon name="plus" /> ثبت نوبت</button></div>
    </section>
    <section className="metric-grid">{metrics.map((m) => <article className={`metric-card ${m.tone}`} key={m.label}><span className="metric-icon"><Icon name={m.icon} /></span><div><small>{m.label}</small><strong>{m.value}</strong><p>{m.detail}</p></div><button onClick={() => onNavigate(m.label.includes("مشتری") || m.label.includes("رضایت") ? "customers" : m.label.includes("نوبت") ? "appointments" : "reports")} aria-label={`مشاهده ${m.label}`}><Icon name="chevron" /></button></article>)}</section>
    <section className="dashboard-grid">
      <div className="panel schedule-panel"><PanelTitle title="برنامه امروز" subtitle={`${faNumber.format(today.length)} نوبت برنامه‌ریزی شده`} action="مشاهده تقویم" onAction={() => onNavigate("appointments")} />
        <div className="timeline">{today.length ? today.map((a) => <AppointmentRow key={a.id} appointment={a} data={data} compact />) : <Empty icon="calendar" title="برای امروز نوبتی ثبت نشده" text="با ثبت نوبت جدید برنامه روزتان را بسازید." />}</div>
      </div>
      <div className="panel activity-panel"><PanelTitle title="عملکرد این هفته" subtitle="مقایسه تعداد نوبت‌های روزانه" action="گزارش کامل" onAction={() => onNavigate("reports")} /><MiniBars appointments={data.appointments} /><div className="chart-legend"><span><i className="purple" /> نوبت تأییدشده</span><span><i className="pink" /> انجام‌شده</span></div></div>
    </section>
    <section className="dashboard-grid lower">
      <div className="panel"><PanelTitle title="نوبت‌های پیش رو" subtitle="نزدیک‌ترین قرارهای ثبت‌شده" action="همه نوبت‌ها" onAction={() => onNavigate("appointments")} /><div className="upcoming-list">{upcoming.map((a) => <AppointmentRow key={a.id} appointment={a} data={data} compact />)}</div></div>
      <div className="panel smart-panel"><div className="smart-head"><span><Icon name="sparkles" /></span><div><h3>دستیار هوشمند Time</h3><p>سه پیشنهاد برای امروز</p></div></div><ul><li><Icon name="cake" /><span><b>۲ تولد نزدیک دارید</b><small>پیام تبریک را آماده کنید.</small></span></li><li><Icon name="refresh" /><span><b>۵ مشتری زمان بازگشت دارند</b><small>یادآوری خودکار غیرفعال است.</small></span></li><li><Icon name="clock" /><span><b>یک نوبت منتظر تأیید است</b><small>برای مشتری پیام ارسال کنید.</small></span></li></ul><button className="btn btn-soft" onClick={() => onNavigate("messages")}>مشاهده ابزارهای ارتباطی</button></div>
    </section>
  </>;
}

function AppointmentsPage({ data, onNew, onStatus }: { data: BootstrapData; onNew: () => void; onStatus: (id: string, status: Appointment["status"]) => Promise<void> }) {
  const [selectedDate, setSelectedDate] = useState(isoToday());
  const [view, setView] = useState<"week" | "month">("week");
  const days = Array.from({ length: view === "week" ? 7 : 14 }, (_, i) => isoToday(i - 2));
  const rows = data.appointments.filter((a) => a.date === selectedDate).sort((a, b) => a.time.localeCompare(b.time));
  return <>
    <PageIntro title="تقویم نوبت‌ها" text="زمان‌بندی روزانه، وضعیت حضور و یادآوری مشتریان را یک‌جا مدیریت کنید."><Segment value={view} onChange={(v) => setView(v as "week" | "month")} items={[{ value: "week", label: "هفته" }, { value: "month", label: "ماه" }]} /><button className="btn btn-primary" onClick={onNew}><Icon name="plus" /> ثبت نوبت جدید</button></PageIntro>
    <div className="calendar-summary"><div><span className="pulse-dot" /> امروز <b>{formatDate(isoToday())}</b></div><div><span><i className="dot confirmed" /> تأییدشده</span><span><i className="dot pending" /> منتظر تأیید</span><span><i className="dot completed" /> انجام‌شده</span></div></div>
    <div className="day-strip">{days.map((day) => { const count = data.appointments.filter((a) => a.date === day && a.status !== "cancelled").length; const date = new Date(`${day}T12:00:00`); return <button key={day} className={selectedDate === day ? "active" : ""} onClick={() => setSelectedDate(day)}><small>{new Intl.DateTimeFormat("fa-IR", { weekday: "short" }).format(date)}</small><strong>{new Intl.DateTimeFormat("fa-IR-u-ca-persian", { day: "numeric" }).format(date)}</strong><span>{count ? faNumber.format(count) : "—"}</span></button>; })}</div>
    <section className="appointment-layout">
      <div className="panel appointment-day"><PanelTitle title={formatDate(selectedDate)} subtitle={`${faNumber.format(rows.length)} نوبت در این روز`} />
        <div className="appointment-stack">{rows.length ? rows.map((a) => <AppointmentCard key={a.id} appointment={a} data={data} onStatus={onStatus} />) : <Empty icon="calendar" title="این روز هنوز خالی است" text="یک نوبت جدید ثبت کنید یا تاریخ دیگری را انتخاب کنید." action="ثبت نوبت" onAction={onNew} />}</div>
      </div>
      <aside className="day-sidebar">
        <div className="panel small-stats"><h3>خلاصه روز</h3><div><span><b>{faNumber.format(rows.length)}</b><small>کل نوبت</small></span><span><b>{faNumber.format(rows.filter((a) => a.status === "completed").length)}</b><small>انجام‌شده</small></span></div><hr/><p>درآمد بالقوه</p><strong>{money(rows.reduce((sum, a) => sum + (data.services.find((s) => s.id === a.serviceId)?.price ?? 0), 0))}</strong></div>
        <div className="panel availability"><h3>ساعات آزاد</h3><p>با توجه به نوبت‌های این روز</p><div>{["08:00", "11:30", "13:00", "18:45"].filter((time) => !rows.some((a) => a.time === time)).map((time) => <button key={time} onClick={onNew}><Icon name="plus" />{time}</button>)}</div></div>
      </aside>
    </section>
  </>;
}

function CustomersPage({ data, onNew, onSelect }: { data: BootstrapData; onNew: () => void; onSelect: (c: Customer) => void }) {
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("همه");
  const groups = ["همه", ...Array.from(new Set(data.customers.map((c) => c.groupName)))];
  const filtered = data.customers.filter((c) => (group === "همه" || c.groupName === group) && `${c.name} ${c.phone} ${c.occupation}`.includes(query));
  return <>
    <PageIntro title="مشتریان" text="پرونده کامل، سوابق مراجعه و ارتباطات هر مشتری را مدیریت کنید."><button className="btn btn-primary" onClick={onNew}><Icon name="plus" /> افزودن مشتری</button></PageIntro>
    <section className="customer-insights">
      <article><span className="ring">{faNumber.format(data.customers.length)}</span><div><small>کل مشتریان</small><strong>{faNumber.format(data.customers.length)}</strong><p>پرونده فعال</p></div></article>
      <article><Icon name="star" /><div><small>مشتریان وفادار</small><strong>{faNumber.format(data.customers.filter((c) => c.totalVisits >= 5).length)}</strong><p>بیش از ۵ مراجعه</p></div></article>
      <article><Icon name="refresh" /><div><small>زمان بازگشت</small><strong>{faNumber.format(data.customers.filter((c) => c.lastVisit && new Date(c.lastVisit) < new Date(isoToday(-30))).length)}</strong><p>نیازمند پیگیری</p></div></article>
      <article><Icon name="cake" /><div><small>تولدهای نزدیک</small><strong>۲</strong><p>تا ۳۰ روز آینده</p></div></article>
    </section>
    <div className="customer-toolbar"><label className="search-field"><Icon name="search" /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="جستجو با نام، شماره یا شغل..." /></label><div className="group-chips">{groups.map((item) => <button key={item} onClick={() => setGroup(item)} className={group === item ? "active" : ""}>{item}</button>)}</div><button className="filter-button"><Icon name="filter" /> مرتب‌سازی</button></div>
    <section className="customer-grid">{filtered.map((c) => <button className="customer-card" key={c.id} onClick={() => onSelect(c)}><div className="customer-card-head"><span className="avatar customer-avatar">{c.name[0]}</span><div><strong>{c.name}</strong><small>{c.phone}</small></div><span className={`customer-badge ${c.groupName.includes("VIP") ? "vip" : ""}`}>{c.groupName}</span></div><div className="customer-card-meta"><span><Icon name="briefcase" />{c.occupation || "ثبت نشده"}</span><span><Icon name="calendar" />{faNumber.format(c.totalVisits)} مراجعه</span><span><Icon name="money" />{faCompact.format(c.totalSpent)}</span></div><footer><span>آخرین مراجعه: <b>{relativeDate(c.lastVisit)}</b></span><Icon name="chevron" /></footer></button>)}</section>
    {!filtered.length && <Empty icon="users" title="مشتری پیدا نشد" text="عبارت جستجو یا گروه انتخابی را تغییر دهید." />}
  </>;
}

function MessagesPage({ data, onCompose, onToggle }: { data: BootstrapData; onCompose: () => void; onToggle: (a: Automation) => Promise<void> }) {
  const automatic = [
    { kind: "appointment-reminder", title: "یادآوری نوبت", text: "پیش از زمان مراجعه", icon: "bell" as IconName, color: "violet" },
    { kind: "birthday", title: "تبریک تولد", text: "پیام و هدیه خودکار", icon: "cake" as IconName, color: "pink" },
    { kind: "return", title: "بازگشت مشتری", text: "دعوت پس از وقفه", icon: "refresh" as IconName, color: "cyan" },
    { kind: "satisfaction", title: "رضایت‌سنجی", text: "پس از انجام خدمت", icon: "smile" as IconName, color: "green" },
  ];
  return <>
    <PageIntro title="مرکز پیام" text="پیام گروهی و ارتباط خودکار با مشتریان، بر اساس رویدادهای واقعی."><button className="btn btn-primary" onClick={onCompose}><Icon name="send" /> ارسال پیام گروهی</button></PageIntro>
    <section className="message-hero"><div className="message-balance"><span className="balance-ring"><b>۲۲۵</b><small>پیامک</small></span><div><small>بسته اشتراکی</small><strong>۲۲۵ پیام آماده ارسال</strong><p>بسته هدیه: صفر پیام</p></div></div><button className="btn btn-dark"><Icon name="plus" /> افزایش اعتبار</button></section>
    <h3 className="section-label">پیام‌های خودکار</h3>
    <section className="automation-grid">{automatic.map((card) => { const automation = data.automations.find((a) => a.kind === card.kind); return <article key={card.kind} className={`automation-card ${card.color}`}><span className="automation-icon"><Icon name={card.icon} /></span><div><h3>{card.title}</h3><p>{card.text}</p></div><button className={`switch ${automation?.enabled ? "on" : ""}`} onClick={() => automation && onToggle(automation)} aria-label={`تغییر وضعیت ${card.title}`}><i /></button><footer>{automation?.enabled ? "فعال و در حال اجرا" : "غیرفعال"}</footer></article>; })}</section>
    <section className="message-layout"><div className="panel"><PanelTitle title="تاریخچه پیام‌ها" subtitle="آخرین پیام‌های ارسال‌شده" action="ارسال جدید" onAction={onCompose} />{data.messages.length ? <div className="message-history">{data.messages.map((m) => <article key={m.id}><span><Icon name="message" /></span><div><b>{m.audience}</b><p>{m.body}</p><small>{faNumber.format(m.recipients)} گیرنده · در صف ارسال</small></div></article>)}</div> : <Empty icon="message" title="هنوز پیامی ارسال نشده" text="اولین پیام گروهی را بسازید و نتیجه را اینجا ببینید." action="نوشتن پیام" onAction={onCompose} />}</div>
      <div className="panel tip-panel"><span><Icon name="sparkles" /></span><h3>پیام مؤثرتر بسازید</h3><p>با نام مشتری شروع کنید، متن را کوتاه نگه دارید و یک اقدام مشخص پیشنهاد دهید.</p><ul><li>پیام‌های بیش از ۷۰ کاراکتر چندبخشی می‌شوند.</li><li>ارسال تبلیغاتی بین ساعت ۹ تا ۲۱ بهتر است.</li><li>مشتریان لغوشده از فهرست حذف می‌شوند.</li></ul></div></section>
  </>;
}

function ReportsPage({ data }: { data: BootstrapData }) {
  const completed = data.appointments.filter((a) => a.status === "completed");
  const revenue = completed.reduce((sum, a) => sum + (data.services.find((s) => s.id === a.serviceId)?.price ?? 0), 0);
  const groupCounts = Array.from(new Set(data.customers.map((c) => c.groupName))).map((name) => ({ name, value: data.customers.filter((c) => c.groupName === name).length }));
  const maxGroup = Math.max(1, ...groupCounts.map((g) => g.value));
  const serviceStats = data.services.map((service) => ({ ...service, count: data.appointments.filter((a) => a.serviceId === service.id).length })).sort((a, b) => b.count - a.count);
  const maxService = Math.max(1, ...serviceStats.map((s) => s.count));
  return <>
    <PageIntro title="گزارش‌ها" text="تصویر روشن از فروش، نوبت‌ها، رفتار مشتری و عملکرد خدمات."><select className="select-control" aria-label="بازه گزارش"><option>۳۰ روز اخیر</option><option>سه ماه اخیر</option><option>سال جاری</option></select></PageIntro>
    <section className="report-metrics"><article><span><Icon name="money" /></span><div><small>درآمد ثبت‌شده</small><strong>{money(revenue)}</strong><p className="up">↗ ۱۸٪ رشد</p></div></article><article><span><Icon name="calendar" /></span><div><small>نوبت تکمیل‌شده</small><strong>{faNumber.format(completed.length)}</strong><p>از {faNumber.format(data.appointments.length)} نوبت</p></div></article><article><span><Icon name="users" /></span><div><small>مشتری جدید</small><strong>{faNumber.format(data.customers.length)}</strong><p className="up">↗ ۱۲٪ رشد</p></div></article><article><span><Icon name="smile" /></span><div><small>میانگین رضایت</small><strong>۴٫۹ از ۵</strong><p>{faNumber.format(data.feedback.length)} بازخورد</p></div></article></section>
    <section className="report-grid"><div className="panel"><PanelTitle title="روند نوبت‌ها" subtitle="تعداد نوبت‌های ثبت‌شده در روز" /><MiniBars appointments={data.appointments} tall /></div><div className="panel"><PanelTitle title="خدمات پرفروش" subtitle="بر اساس تعداد رزرو" /><div className="rank-list">{serviceStats.map((s, i) => <div key={s.id}><span className="rank">{faNumber.format(i + 1)}</span><span className="rank-name"><b>{s.name}</b><i><em style={{ width: `${(s.count / maxService) * 100}%`, background: s.color }} /></i></span><strong>{faNumber.format(s.count)}</strong></div>)}</div></div></section>
    <section className="report-grid"><div className="panel"><PanelTitle title="گروه‌های مشتریان" subtitle="ترکیب باشگاه مشتریان" /><div className="group-report">{groupCounts.map((g, i) => <div key={g.name}><span style={{ background: ["#7c3aed", "#ec4899", "#06b6d4", "#f59e0b"][i % 4] }} /><p><b>{g.name}</b><i><em style={{ width: `${(g.value / maxGroup) * 100}%` }} /></i></p><strong>{faNumber.format(g.value)}</strong></div>)}</div></div><div className="panel feedback-panel"><PanelTitle title="رضایت مشتریان" subtitle="آخرین بازخوردها" />{data.feedback.slice(0, 3).map((f) => <article key={f.id}><span className="avatar">{data.customers.find((c) => c.id === f.customerId)?.name[0] ?? "م"}</span><div><b>{data.customers.find((c) => c.id === f.customerId)?.name ?? "مشتری"}</b><span className="stars">{"★".repeat(f.score)}</span><p>{f.comment}</p></div></article>)}</div></section>
  </>;
}

function ToolsPage({ data, onNavigate, onCompose }: { data: BootstrapData; onNavigate: (p: PageKey) => void; onCompose: () => void }) {
  const tools: { title: string; text: string; icon: IconName; color: string; badge?: string; action: () => void }[] = [
    { title: "پرسنل و خدمات", text: `${faNumber.format(data.staff.length)} پرسنل، ${faNumber.format(data.services.length)} خدمت`, icon: "briefcase", color: "violet", action: () => onNavigate("management") },
    { title: "رزرو آنلاین", text: "صفحه عمومی رزرو نوبت", icon: "globe", color: "green", badge: "فعال", action: () => onNavigate("appointments") },
    { title: "پیامک گروهی", text: "ارسال هدفمند به مشتریان", icon: "send", color: "cyan", action: onCompose },
    { title: "تبریک تولد", text: "هدیه و پیام خودکار", icon: "cake", color: "pink", badge: "۲ نزدیک", action: () => onNavigate("messages") },
    { title: "بازگشت مشتری", text: "یادآوری مراجعه مجدد", icon: "refresh", color: "orange", badge: "۵ نفر", action: () => onNavigate("messages") },
    { title: "رضایت‌سنجی", text: "فرم امتیازدهی مشتری", icon: "smile", color: "yellow", action: () => onNavigate("reports") },
    { title: "قرعه‌کشی", text: "انتخاب برنده از گروه مشتریان", icon: "gift", color: "violet", action: () => alert("قرعه‌کشی آزمایشی: مشتری نمونه ۴ برنده شد! 🎉") },
    { title: "شماره اختصاصی", text: "مدیریت خط ارسال پیامک", icon: "phone", color: "cyan", action: () => onNavigate("profile") },
    { title: "پیامک منطقه‌ای", text: "ارسال بر اساس شهر یا محدوده نقشه", icon: "globe", color: "violet", action: onCompose },
    { title: "دریافت پیام", text: "صندوق پیام‌های ورودی مشتریان", icon: "message", color: "green", action: () => onNavigate("messages") },
    { title: "وب‌سایت اختصاصی", text: "معرفی خدمات و رزرو آنلاین", icon: "book", color: "pink", action: () => onNavigate("management") },
    { title: "پشتیبانی", text: "راهنما و پاسخ به پرسش‌ها", icon: "headset", color: "green", action: () => alert("درخواست پشتیبانی شما ثبت شد.") },
  ];
  return <>
    <PageIntro title="امکانات" text="ابزارهای رشد، ارتباط و مدیریت کسب‌وکار شما." />
    <section className="feature-hero"><div><span className="eyebrow light">اشتراک حرفه‌ای</span><h2>همه ابزارهای رشد، در یک پنل</h2><p>اتوماسیون ارتباط با مشتری و گزارش‌های کاربردی همیشه کنار شماست.</p></div><span className="feature-orbit"><Icon name="sparkles" size={40} /></span></section>
    <section className="tools-grid">{tools.map((tool) => <button key={tool.title} onClick={tool.action} className="tool-card"><span className={`tool-icon ${tool.color}`}><Icon name={tool.icon} /></span><div><h3>{tool.title}</h3><p>{tool.text}</p></div>{tool.badge && <em>{tool.badge}</em>}<Icon name="chevron" /></button>)}</section>
  </>;
}

function ManagementPage({ data, onAddStaff, onAddService }: { data: BootstrapData; onAddStaff: () => void; onAddService: () => void }) {
  return <>
    <PageIntro title="پرسنل و خدمات" text="اعضای تیم، خدمات قابل رزرو، مدت و تعرفه هر خدمت را تنظیم کنید."><button className="btn btn-light" onClick={onAddStaff}><Icon name="user" /> افزودن پرسنل</button><button className="btn btn-primary" onClick={onAddService}><Icon name="plus" /> افزودن خدمت</button></PageIntro>
    <section className="management-grid"><div className="panel"><PanelTitle title="اعضای تیم" subtitle={`${faNumber.format(data.staff.length)} عضو فعال`} /> <div className="staff-list">{data.staff.map((employee) => <article key={employee.id}><span className="avatar" style={{ background: `${employee.color}18`, color: employee.color }}>{employee.name[0]}</span><div><b>{employee.name}</b><small>{employee.role}</small><p>{employee.phone}</p></div><span className="status-pill active">فعال</span><button className="row-action"><Icon name="edit" /></button></article>)}</div></div>
      <div className="panel"><PanelTitle title="خدمات" subtitle={`${faNumber.format(data.services.length)} خدمت قابل رزرو`} /><div className="service-list">{data.services.map((service) => <article key={service.id}><span className="service-color" style={{ background: service.color }} /><div><b>{service.name}</b><small><Icon name="clock" /> {faNumber.format(service.duration)} دقیقه</small></div><strong>{money(service.price)}</strong><button className="row-action"><Icon name="edit" /></button></article>)}</div></div></section>
    <section className="panel booking-config"><div><span><Icon name="globe" /></span><div><h3>صفحه رزرو آنلاین</h3><p>مشتری بدون تماس، خدمت و زمان خالی را انتخاب می‌کند.</p></div></div><label className="setting-row"><span><b>رزرو آنلاین فعال باشد</b><small>نمایش خدمات و وقت‌های خالی</small></span><button className="switch on"><i /></button></label><div className="booking-link"><input readOnly value="time.example.com/s/sara"/><button>کپی لینک</button></div></section>
  </>;
}

function ProfilePage() {
  const [nightSms, setNightSms] = useState(true);
  return <>
    <PageIntro title="پروفایل" text="اطلاعات کسب‌وکار، تنظیمات حساب و امنیت." />
    <section className="profile-layout"><div className="profile-card"><div className="profile-cover" /><span className="avatar avatar-gradient profile-avatar">م</span><h2>مدیر نمونه</h2><p>مدیر مجموعه نمونه</p><span className="pro-badge"><Icon name="sparkles" /> اشتراک PRO</span><button className="btn btn-soft"><Icon name="edit" /> ویرایش پروفایل</button></div><div className="settings-list panel">
      <Setting icon="user" title="اطلاعات حساب" text="نام، موبایل و اطلاعات کسب‌وکار" />
      <Setting icon="phone" title="دستگاه‌های متصل" text="یک دستگاه فعال" />
      <Setting icon="globe" title="به‌روزرسانی" text="آخرین نسخه نصب شده است" />
      <div className="setting-row"><span className="setting-icon"><Icon name="message" /></span><div><b>پیامک شبانه</b><small>یادآوری نوبت‌های فردا به‌صورت خودکار</small></div><button className={`switch ${nightSms ? "on" : ""}`} onClick={() => setNightSms(!nightSms)}><i /></button></div>
      <Setting icon="clock" title="ناحیه زمانی" text="Asia/Tehran · تقویم شمسی" />
      <Setting icon="logout" title="خروج از حساب" text="پایان نشست روی این دستگاه" danger />
    </div></section>
  </>;
}

function Setting({ icon, title, text, danger = false }: { icon: IconName; title: string; text: string; danger?: boolean }) { return <button className={`setting-row ${danger ? "danger" : ""}`}><span className="setting-icon"><Icon name={icon} /></span><div><b>{title}</b><small>{text}</small></div><Icon name="chevron" /></button>; }

function AppointmentRow({ appointment, data, compact = false }: { appointment: Appointment; data: BootstrapData; compact?: boolean }) {
  const customer = data.customers.find((c) => c.id === appointment.customerId);
  const service = data.services.find((s) => s.id === appointment.serviceId);
  const employee = data.staff.find((s) => s.id === appointment.staffId);
  return <article className={`appointment-row ${compact ? "compact" : ""}`}><time>{appointment.time}</time><span className="line-dot" style={{ background: service?.color }} /><div><b>{customer?.name ?? "مشتری"}</b><small>{service?.name} · {employee?.name}</small></div><Status status={appointment.status} /></article>;
}

function AppointmentCard({ appointment, data, onStatus }: { appointment: Appointment; data: BootstrapData; onStatus: (id: string, status: Appointment["status"]) => Promise<void> }) {
  const customer = data.customers.find((c) => c.id === appointment.customerId);
  const service = data.services.find((s) => s.id === appointment.serviceId);
  const employee = data.staff.find((s) => s.id === appointment.staffId);
  return <article className="appointment-card" style={{ borderRightColor: service?.color }}><div className="appointment-time"><strong>{appointment.time}</strong><small>{faNumber.format(service?.duration ?? 0)} دقیقه</small></div><div className="appointment-person"><span className="avatar">{customer?.name[0] ?? "م"}</span><div><b>{customer?.name}</b><small>{customer?.phone}</small></div></div><div className="appointment-service"><b>{service?.name}</b><small>{employee?.name}</small></div><Status status={appointment.status} /><div className="appointment-actions">{appointment.status !== "completed" && appointment.status !== "cancelled" && <button onClick={() => onStatus(appointment.id, "completed")}><Icon name="check" /> انجام شد</button>}<button><Icon name="phone" /></button><button><Icon name="edit" /></button></div></article>;
}

function Status({ status }: { status: Appointment["status"] }) {
  const labels = { confirmed: "تأییدشده", pending: "منتظر تأیید", completed: "انجام‌شده", cancelled: "لغوشده" };
  return <span className={`status-pill ${status}`}>{labels[status]}</span>;
}

function PanelTitle({ title, subtitle, action, onAction }: { title: string; subtitle?: string; action?: string; onAction?: () => void }) { return <header className="panel-title"><div><h3>{title}</h3>{subtitle && <p>{subtitle}</p>}</div>{action && <button onClick={onAction}>{action}<Icon name="chevron" size={15} /></button>}</header>; }

function PageIntro({ title, text, children }: { title: string; text: string; children?: React.ReactNode }) { return <section className="page-intro"><div><h2>{title}</h2><p>{text}</p></div>{children && <div className="page-actions">{children}</div>}</section>; }

function Segment({ value, onChange, items }: { value: string; onChange: (v: string) => void; items: { value: string; label: string }[] }) { return <div className="segment">{items.map((item) => <button key={item.value} className={value === item.value ? "active" : ""} onClick={() => onChange(item.value)}>{item.label}</button>)}</div>; }

function MiniBars({ appointments, tall = false }: { appointments: Appointment[]; tall?: boolean }) {
  const days = Array.from({ length: 7 }, (_, i) => isoToday(i - 6));
  const max = Math.max(1, ...days.map((day) => appointments.filter((a) => a.date === day).length));
  return <div className={`mini-bars ${tall ? "tall" : ""}`}>{days.map((day) => { const total = appointments.filter((a) => a.date === day).length; const done = appointments.filter((a) => a.date === day && a.status === "completed").length; return <div key={day}><span className="bar-track"><i style={{ height: `${Math.max(10, total / max * 100)}%` }}><em style={{ height: `${total ? done / total * 100 : 0}%` }} /></i></span><small>{new Intl.DateTimeFormat("fa-IR", { weekday: "narrow" }).format(new Date(`${day}T12:00:00`))}</small></div>; })}</div>;
}

function Empty({ icon, title, text, action, onAction }: { icon: IconName; title: string; text: string; action?: string; onAction?: () => void }) { return <div className="empty"><span><Icon name={icon} size={28} /></span><h3>{title}</h3><p>{text}</p>{action && <button className="btn btn-soft" onClick={onAction}><Icon name="plus" />{action}</button>}</div>; }

function CustomerDetail({ customer, data, onClose, onNewAppointment }: { customer: Customer; data: BootstrapData; onClose: () => void; onNewAppointment: () => void }) {
  const history = data.appointments.filter((a) => a.customerId === customer.id).sort((a, b) => b.date.localeCompare(a.date));
  return <div className="modal-layer"><button className="modal-backdrop" onClick={onClose} aria-label="بستن"/><aside className="detail-sheet"><header><button className="icon-btn" onClick={onClose}><Icon name="close" /></button><h2>پرونده مشتری</h2><button className="icon-btn"><Icon name="edit" /></button></header><div className="customer-profile-head"><span className="avatar customer-avatar large">{customer.name[0]}</span><h3>{customer.name}</h3><a href={`tel:${customer.phone}`}>{customer.phone}</a><span className="customer-badge vip">{customer.groupName}</span></div><div className="profile-numbers"><div><b>{faNumber.format(customer.totalVisits)}</b><small>تعداد مراجعه</small></div><div><b>{faCompact.format(customer.totalSpent)}</b><small>خرید کل</small></div><div><b>{relativeDate(customer.lastVisit)}</b><small>آخرین مراجعه</small></div></div><section className="record-card"><h4>مشخصات پرونده</h4><p><span>شغل</span><b>{customer.occupation || "ثبت نشده"}</b></p><p><span>نحوه آشنایی</span><b>{customer.referralSource}</b></p><p><span>تاریخ تولد</span><b>{customer.birthDate ? formatDate(customer.birthDate) : "ثبت نشده"}</b></p><p><span>توضیحات</span><b>{customer.notes || "توضیحی ثبت نشده"}</b></p></section><section className="record-card"><h4>سوابق نوبت</h4>{history.length ? history.map((a) => <AppointmentRow key={a.id} appointment={a} data={data} compact />) : <p className="muted">هنوز نوبتی ثبت نشده است.</p>}</section><div className="sticky-actions"><button className="btn btn-light"><Icon name="message" /> ارسال پیام</button><button className="btn btn-primary" onClick={onNewAppointment}><Icon name="plus" /> ثبت نوبت</button></div></aside></div>;
}

function ModalShell({ title, text, onClose, children }: { title: string; text?: string; onClose: () => void; children: React.ReactNode }) { return <div className="modal-layer"><button className="modal-backdrop" onClick={onClose} aria-label="بستن"/><section className="form-sheet"><header><div><h2>{title}</h2>{text && <p>{text}</p>}</div><button className="icon-btn" onClick={onClose}><Icon name="close" /></button></header>{children}</section></div>; }

function FormButton({ busy, label }: { busy: boolean; label: string }) { return <button className="btn btn-primary submit-button" type="submit" disabled={busy}>{busy ? <span className="spinner" /> : <Icon name="check" />}{busy ? "در حال ذخیره..." : label}</button>; }

function AppointmentModal({ data, onClose, onSubmit }: { data: BootstrapData; onClose: () => void; onSubmit: (p: Record<string, unknown>) => Promise<void> }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); setError(""); const form = new FormData(event.currentTarget); try { await onSubmit(Object.fromEntries(form.entries())); } catch (e) { setError(e instanceof Error ? e.message : "ثبت نوبت ممکن نشد."); setBusy(false); } }
  return <ModalShell title="ثبت نوبت جدید" text="مشخصات مشتری، خدمت و زمان نوبت را انتخاب کنید." onClose={onClose}><form className="app-form" onSubmit={submit}><label className="field full"><span>مشتری</span><select name="customerId" required defaultValue=""><option value="" disabled>انتخاب مشتری</option>{data.customers.map((c) => <option value={c.id} key={c.id}>{c.name} — {c.phone}</option>)}</select></label><label className="field"><span>خدمت</span><select name="serviceId" required defaultValue=""><option value="" disabled>انتخاب خدمت</option>{data.services.filter((s) => s.active).map((s) => <option value={s.id} key={s.id}>{s.name} · {money(s.price)}</option>)}</select></label><label className="field"><span>پرسنل</span><select name="staffId" required defaultValue=""><option value="" disabled>انتخاب پرسنل</option>{data.staff.filter((s) => s.active).map((s) => <option value={s.id} key={s.id}>{s.name}</option>)}</select></label><label className="field"><span>تاریخ</span><input name="date" type="date" required defaultValue={isoToday()} /></label><label className="field"><span>ساعت</span><input name="time" type="time" required defaultValue="10:00" /></label><label className="field full"><span>توضیحات</span><textarea name="notes" placeholder="توضیحات اختیاری درباره این نوبت..." /></label><div className="form-option full"><div><Icon name="bell" /><span><b>پیامک یادآوری نوبت</b><small>۲۴ ساعت قبل برای مشتری ارسال شود</small></span></div><input type="hidden" name="reminderHours" value="24"/><input name="reminderSms" type="checkbox" defaultChecked value="true" /></div>{error && <p className="form-error">{error}</p>}<FormButton busy={busy} label="ثبت نوبت" /></form></ModalShell>;
}

function CustomerModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (p: Record<string, unknown>) => Promise<void> }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); setError(""); try { await onSubmit(Object.fromEntries(new FormData(event.currentTarget).entries())); } catch (e) { setError(e instanceof Error ? e.message : "ثبت مشتری ممکن نشد."); setBusy(false); } }
  return <ModalShell title="افزودن مشتری" text="پرونده جدید در باشگاه مشتریان ساخته می‌شود." onClose={onClose}><form className="app-form" onSubmit={submit}><label className="field"><span>نام و نام خانوادگی</span><input name="name" required placeholder="مثلاً مشتری نمونه" /></label><label className="field"><span>شماره موبایل</span><input name="phone" required inputMode="tel" placeholder="09xxxxxxxxx" /></label><label className="field"><span>شغل</span><input name="occupation" placeholder="مثلاً طراح داخلی" /></label><label className="field"><span>جنسیت</span><select name="gender" defaultValue="زن"><option>زن</option><option>مرد</option><option>نامشخص</option></select></label><label className="field"><span>تاریخ تولد</span><input name="birthDate" type="date" /></label><label className="field"><span>گروه مشتری</span><select name="groupName"><option>مشتریان معمولی</option><option>مشتریان مهم</option><option>مشتریان VIP</option><option>کارکنان</option></select></label><label className="field full"><span>نحوه آشنایی</span><select name="referralSource"><option>معرفی دوستان</option><option>اینستاگرام</option><option>گوگل</option><option>وب‌سایت</option><option>تبلیغات پیامکی</option></select></label><label className="field full"><span>توضیحات پرونده</span><textarea name="notes" placeholder="حساسیت، علاقه‌مندی یا نکته مهم..." /></label>{error && <p className="form-error">{error}</p>}<FormButton busy={busy} label="ساخت پرونده مشتری" /></form></ModalShell>;
}

function MessageModal({ count, onClose, onSubmit }: { count: number; onClose: () => void; onSubmit: (p: Record<string, unknown>) => Promise<void> }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [body, setBody] = useState(""); const [audience, setAudience] = useState("همه مشتریان");
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); try { await onSubmit({ body, audience, recipients: count, kind: "group" }); } catch (e) { setError(e instanceof Error ? e.message : "ارسال پیام ممکن نشد."); setBusy(false); } }
  return <ModalShell title="ارسال پیام گروهی" text="مخاطبان را انتخاب و پیام خود را آماده کنید." onClose={onClose}><form className="app-form" onSubmit={submit}><label className="field full"><span>گیرندگان</span><select value={audience} onChange={(e) => setAudience(e.target.value)}><option>همه مشتریان</option><option>مشتریان VIP</option><option>مشتریان مهم</option><option>مشتریان غیرفعال</option><option>تولدهای این ماه</option></select></label><label className="field full"><span>متن پیام</span><textarea className="message-textarea" value={body} onChange={(e) => setBody(e.target.value)} maxLength={320} required placeholder="سلام {name} عزیز..." /><small className="counter">{faNumber.format(body.length)} از ۳۲۰ کاراکتر</small></label><div className="recipient-estimate full"><span><Icon name="users" /></span><div><b>{faNumber.format(count)} گیرنده</b><small>هزینه تقریبی: {faNumber.format(count)} پیامک</small></div></div>{error && <p className="form-error">{error}</p>}<FormButton busy={busy} label="ثبت برای ارسال" /></form></ModalShell>;
}

function StaffModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (p: Record<string, unknown>) => Promise<void> }) { const [busy,setBusy]=useState(false); const [error,setError]=useState(""); async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();setBusy(true);try{await onSubmit(Object.fromEntries(new FormData(e.currentTarget).entries()));}catch(err){setError(err instanceof Error?err.message:"ثبت ممکن نشد.");setBusy(false);}} return <ModalShell title="افزودن پرسنل" onClose={onClose}><form className="app-form" onSubmit={submit}><label className="field"><span>نام و نام خانوادگی</span><input name="name" required /></label><label className="field"><span>شماره موبایل</span><input name="phone" inputMode="tel" /></label><label className="field full"><span>سمت</span><input name="role" defaultValue="متخصص خدمات" /></label><label className="field full"><span>رنگ نمایش در تقویم</span><input name="color" type="color" defaultValue="#7c3aed" /></label>{error&&<p className="form-error">{error}</p>}<FormButton busy={busy} label="افزودن به تیم" /></form></ModalShell>; }

function ServiceModal({ staff, onClose, onSubmit }: { staff: Staff[]; onClose: () => void; onSubmit: (p: Record<string, unknown>) => Promise<void> }) { const [busy,setBusy]=useState(false); const [error,setError]=useState(""); async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();setBusy(true);try{await onSubmit(Object.fromEntries(new FormData(e.currentTarget).entries()));}catch(err){setError(err instanceof Error?err.message:"ثبت ممکن نشد.");setBusy(false);}} return <ModalShell title="افزودن خدمت" onClose={onClose}><form className="app-form" onSubmit={submit}><label className="field full"><span>نام خدمت</span><input name="name" required /></label><label className="field"><span>مدت (دقیقه)</span><input name="duration" type="number" min="10" defaultValue="60" /></label><label className="field"><span>هزینه (تومان)</span><input name="price" type="number" min="0" step="10000" defaultValue="1000000" /></label><label className="field"><span>پرسنل پیش‌فرض</span><select name="staffId"><option value="">بدون انتخاب</option>{staff.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label className="field"><span>رنگ تقویم</span><input name="color" type="color" defaultValue="#ec4899" /></label>{error&&<p className="form-error">{error}</p>}<FormButton busy={busy} label="افزودن خدمت" /></form></ModalShell>; }
