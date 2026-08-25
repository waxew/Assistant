import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://assistant-time.aczeeshan-4827.chatgpt.site"),
  title: "Time — مدیریت نوبت و مشتریان",
  description: "سامانه یکپارچه مدیریت نوبت، پرونده مشتری، پرسنل، پیامک و گزارش‌های کسب‌وکار",
  openGraph: {
    title: "Time — مدیریت نوبت و مشتریان",
    description: "سامانه یکپارچه مدیریت نوبت، پرونده مشتری، پرسنل و گزارش‌های کسب‌وکار",
    type: "website",
    locale: "fa_IR",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Time — مدیریت نوبت و مشتریان" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Time — مدیریت نوبت و مشتریان",
    description: "سامانه یکپارچه مدیریت نوبت، پرونده مشتری، پرسنل و گزارش‌های کسب‌وکار",
    images: ["/og.png"],
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fa" dir="rtl">
      <body className="antialiased">{children}</body>
    </html>
  );
}
