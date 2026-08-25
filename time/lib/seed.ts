import type { Appointment, Automation, Customer, FeedbackItem, Service, Staff } from "./types";

function isoDay(offset = 0) {
  const date = new Date();
  date.setHours(12, 0, 0, 0);
  date.setDate(date.getDate() + offset);
  return date.toISOString().slice(0, 10);
}

export const seedCustomers: Customer[] = [
  { id: "cus-1", name: "مشتری نمونه ۱", phone: "شماره آزمایشی ۱", occupation: "طراح", gender: "زن", birthDate: null, groupName: "مشتریان VIP", referralSource: "اینستاگرام", notes: "یادداشت نمونه برای نمایش پرونده.", totalVisits: 7, totalSpent: 0, lastVisit: isoDay(-12), createdAt: isoDay(-160) },
  { id: "cus-2", name: "مشتری نمونه ۲", phone: "شماره آزمایشی ۲", occupation: "آموزگار", gender: "زن", birthDate: null, groupName: "مشتریان مهم", referralSource: "معرفی دوستان", notes: "یادداشت نمونه برای نمایش پرونده.", totalVisits: 4, totalSpent: 0, lastVisit: isoDay(-28), createdAt: isoDay(-120) },
  { id: "cus-3", name: "مشتری نمونه ۳", phone: "شماره آزمایشی ۳", occupation: "مدیر", gender: "مرد", birthDate: null, groupName: "مشتریان معمولی", referralSource: "گوگل", notes: "", totalVisits: 2, totalSpent: 0, lastVisit: isoDay(-45), createdAt: isoDay(-82) },
  { id: "cus-4", name: "مشتری نمونه ۴", phone: "شماره آزمایشی ۴", occupation: "معمار", gender: "زن", birthDate: null, groupName: "مشتریان VIP", referralSource: "اینستاگرام", notes: "یادآوری نمونه ۴۸ ساعت قبل.", totalVisits: 9, totalSpent: 0, lastVisit: isoDay(-7), createdAt: isoDay(-230) },
  { id: "cus-5", name: "مشتری نمونه ۵", phone: "شماره آزمایشی ۵", occupation: "دانشجو", gender: "زن", birthDate: null, groupName: "کارکنان", referralSource: "معرفی دوستان", notes: "", totalVisits: 3, totalSpent: 0, lastVisit: isoDay(-19), createdAt: isoDay(-95) },
  { id: "cus-6", name: "مشتری نمونه ۶", phone: "شماره آزمایشی ۶", occupation: "کارشناس", gender: "زن", birthDate: null, groupName: "مشتریان مهم", referralSource: "وب‌سایت", notes: "یادداشت نمونه برای زمان مراجعه.", totalVisits: 6, totalSpent: 0, lastVisit: isoDay(-35), createdAt: isoDay(-190) },
];

export const seedStaff: Staff[] = [
  { id: "st-1", name: "مدیر نمونه", role: "مدیر مجموعه", phone: "شماره آزمایشی مدیر", color: "#7c3aed", active: true, createdAt: isoDay(-365) },
  { id: "st-2", name: "کارشناس نمونه الف", role: "متخصص خدمات", phone: "شماره آزمایشی الف", color: "#ec4899", active: true, createdAt: isoDay(-240) },
  { id: "st-3", name: "کارشناس نمونه ب", role: "متخصص خدمات", phone: "شماره آزمایشی ب", color: "#06b6d4", active: true, createdAt: isoDay(-180) },
];

export const seedServices: Service[] = [
  { id: "srv-1", name: "پلن تراپی", duration: 60, price: 1450000, staffId: "st-1", color: "#7c3aed", active: true, createdAt: isoDay(-300) },
  { id: "srv-2", name: "فیشال VIP", duration: 90, price: 2300000, staffId: "st-2", color: "#ec4899", active: true, createdAt: isoDay(-280) },
  { id: "srv-3", name: "آبرسانی", duration: 45, price: 980000, staffId: "st-2", color: "#06b6d4", active: true, createdAt: isoDay(-260) },
  { id: "srv-4", name: "ماساژ تخصصی", duration: 75, price: 1750000, staffId: "st-3", color: "#f59e0b", active: true, createdAt: isoDay(-220) },
];

export const seedAppointments: Appointment[] = [
  { id: "apt-1", customerId: "cus-1", staffId: "st-1", serviceId: "srv-1", date: isoDay(0), time: "10:00", status: "confirmed", notes: "جلسه پیگیری", reminderSms: true, reminderHours: 24, createdAt: isoDay(-4) },
  { id: "apt-2", customerId: "cus-2", staffId: "st-2", serviceId: "srv-2", date: isoDay(0), time: "14:30", status: "confirmed", notes: "", reminderSms: true, reminderHours: 24, createdAt: isoDay(-6) },
  { id: "apt-3", customerId: "cus-3", staffId: "st-3", serviceId: "srv-4", date: isoDay(0), time: "17:30", status: "pending", notes: "منتظر تأیید مشتری", reminderSms: false, reminderHours: 24, createdAt: isoDay(-1) },
  { id: "apt-4", customerId: "cus-4", staffId: "st-1", serviceId: "srv-1", date: isoDay(1), time: "09:15", status: "confirmed", notes: "", reminderSms: true, reminderHours: 48, createdAt: isoDay(-5) },
  { id: "apt-5", customerId: "cus-5", staffId: "st-2", serviceId: "srv-3", date: isoDay(2), time: "16:00", status: "confirmed", notes: "", reminderSms: true, reminderHours: 24, createdAt: isoDay(-8) },
  { id: "apt-6", customerId: "cus-6", staffId: "st-3", serviceId: "srv-4", date: isoDay(-1), time: "11:30", status: "completed", notes: "", reminderSms: true, reminderHours: 24, createdAt: isoDay(-10) },
];

export const seedAutomations: Automation[] = [
  { id: "auto-1", kind: "appointment-reminder", enabled: true, message: "یادآوری نوبت شما: {date} ساعت {time}", offsetHours: 24, updatedAt: isoDay(-2) },
  { id: "auto-2", kind: "birthday", enabled: true, message: "{name} عزیز، تولدت مبارک! هدیه ویژه‌ات منتظر توست.", offsetHours: 0, updatedAt: isoDay(-12) },
  { id: "auto-3", kind: "return", enabled: false, message: "دلمان برایتان تنگ شده؛ برای رزرو نوبت بعدی آماده‌ایم.", offsetHours: 720, updatedAt: isoDay(-20) },
  { id: "auto-4", kind: "satisfaction", enabled: true, message: "از تجربه امروزتان چقدر راضی بودید؟", offsetHours: 2, updatedAt: isoDay(-9) },
];

export const seedFeedback: FeedbackItem[] = [
  { id: "fb-1", customerId: "cus-1", score: 5, comment: "بازخورد نمونه: خدمات عالی بود.", visible: true, createdAt: isoDay(-10) },
  { id: "fb-2", customerId: "cus-4", score: 5, comment: "بازخورد نمونه: وقت‌شناسی عالی بود.", visible: true, createdAt: isoDay(-7) },
  { id: "fb-3", customerId: "cus-2", score: 4, comment: "بازخورد نمونه: رضایت داشتم.", visible: false, createdAt: isoDay(-22) },
];
