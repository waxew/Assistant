export type Customer = {
  id: string;
  name: string;
  phone: string;
  occupation: string;
  gender: string;
  birthDate: string | null;
  groupName: string;
  referralSource: string;
  notes: string;
  totalVisits: number;
  totalSpent: number;
  lastVisit: string | null;
  createdAt: string;
};

export type Staff = {
  id: string;
  name: string;
  role: string;
  phone: string;
  color: string;
  active: boolean;
  createdAt: string;
};

export type Service = {
  id: string;
  name: string;
  duration: number;
  price: number;
  staffId: string | null;
  color: string;
  active: boolean;
  createdAt: string;
};

export type Appointment = {
  id: string;
  customerId: string;
  staffId: string;
  serviceId: string;
  date: string;
  time: string;
  status: "confirmed" | "pending" | "completed" | "cancelled";
  notes: string;
  reminderSms: boolean;
  reminderHours: number;
  createdAt: string;
};

export type MessageItem = {
  id: string;
  kind: string;
  audience: string;
  body: string;
  recipients: number;
  status: string;
  createdAt: string;
};

export type Automation = {
  id: string;
  kind: string;
  enabled: boolean;
  message: string;
  offsetHours: number;
  updatedAt: string;
};

export type FeedbackItem = {
  id: string;
  customerId: string | null;
  score: number;
  comment: string;
  visible: boolean;
  createdAt: string;
};

export type BootstrapData = {
  customers: Customer[];
  staff: Staff[];
  services: Service[];
  appointments: Appointment[];
  messages: MessageItem[];
  automations: Automation[];
  feedback: FeedbackItem[];
};
