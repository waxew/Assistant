import type { SVGProps } from "react";

export type IconName =
  | "home" | "calendar" | "plus" | "users" | "message" | "chart" | "grid"
  | "search" | "bell" | "clock" | "money" | "gift" | "smile" | "send"
  | "settings" | "briefcase" | "sparkles" | "chevron" | "phone" | "edit"
  | "close" | "check" | "book" | "user" | "filter" | "wallet" | "cake"
  | "refresh" | "globe" | "headset" | "logout" | "star" | "trash" | "menu";

const paths: Record<IconName, React.ReactNode> = {
  home: <><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10M9 20v-6h6v6"/></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M8 3v4m8-4v4M3 10h18"/></>,
  plus: <path d="M12 5v14M5 12h14"/>,
  users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></>,
  message: <><path d="M21 15a4 4 0 0 1-4 4H8l-5 3v-7a4 4 0 0 1-1-2.6V7a4 4 0 0 1 4-4h11a4 4 0 0 1 4 4z"/><path d="M7 9h10M7 13h6"/></>,
  chart: <><path d="M4 19V9m6 10V5m6 14v-7m5 7H2"/></>,
  grid: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
  search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  money: <><rect x="3" y="5" width="18" height="14" rx="3"/><circle cx="12" cy="12" r="3"/><path d="M7 9H6m12 6h-1"/></>,
  gift: <><rect x="3" y="9" width="18" height="12" rx="2"/><path d="M12 9v12M3 13h18M7.5 9C4 9 4 4 7 4c2 0 5 5 5 5s3-5 5-5c3 0 3 5-.5 5"/></>,
  smile: <><circle cx="12" cy="12" r="9"/><path d="M8 14s1.5 2 4 2 4-2 4-2M9 9h.01M15 9h.01"/></>,
  send: <><path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a2 2 0 0 0 .4 2.2l.1.1-2.6 2.6-.1-.1a2 2 0 0 0-2.2-.4 2 2 0 0 0-1.2 1.8V21h-3.6v-.2A2 2 0 0 0 9 19a2 2 0 0 0-2.2.4l-.1.1-2.6-2.6.1-.1A2 2 0 0 0 4.6 15 2 2 0 0 0 2.8 13H2V9.4h.8A2 2 0 0 0 4.6 8a2 2 0 0 0-.4-2.2l-.1-.1 2.6-2.6.1.1A2 2 0 0 0 9 3.6a2 2 0 0 0 1.2-1.8V2h3.6v.2A2 2 0 0 0 15 4a2 2 0 0 0 2.2-.4l.1-.1 2.6 2.6-.1.1A2 2 0 0 0 19.4 8a2 2 0 0 0 1.8 1.2H22V13h-.8a2 2 0 0 0-1.8 2Z"/></>,
  briefcase: <><rect x="3" y="7" width="18" height="13" rx="3"/><path d="M9 7V5h6v2M3 12h18M10 12v2h4v-2"/></>,
  sparkles: <><path d="m12 3 1.3 3.7L17 8l-3.7 1.3L12 13l-1.3-3.7L7 8l3.7-1.3zM5 15l.8 2.2L8 18l-2.2.8L5 21l-.8-2.2L2 18l2.2-.8zM19 14l.6 1.4L21 16l-1.4.6L19 18l-.6-1.4L17 16l1.4-.6z"/></>,
  chevron: <path d="m9 18 6-6-6-6"/>,
  phone: <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 2 .7 2.9a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5 12.8 12.8 0 0 0 2.9.7 2 2 0 0 1 1.7 2Z"/>,
  edit: <><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/></>,
  close: <path d="m6 6 12 12M18 6 6 18"/>,
  check: <path d="m5 12 4 4L19 6"/>,
  book: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/><path d="M4 5.5v14"/></>,
  user: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
  filter: <path d="M4 5h16M7 12h10m-7 7h4"/>,
  wallet: <><path d="M3 7h16a2 2 0 0 1 2 2v10H5a2 2 0 0 1-2-2z"/><path d="M3 7V5a2 2 0 0 1 2-2h12v4m0 5h4"/></>,
  cake: <><path d="M4 13h16v8H4zM7 13V9h10v4M9 6V3m6 3V3"/><path d="M4 17c2 1 3 1 5 0 2 1 3 1 6 0 2 1 3 1 5 0"/></>,
  refresh: <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M7 7a7 7 0 0 1 11 2l2 3M4 12l2 3a7 7 0 0 0 11 2"/></>,
  globe: <><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/></>,
  headset: <><path d="M4 15v-3a8 8 0 0 1 16 0v3"/><path d="M4 15a3 3 0 0 0 3 3h1v-6H7a3 3 0 0 0-3 3Zm16 0a3 3 0 0 1-3 3h-1v-6h1a3 3 0 0 1 3 3ZM16 21h-4"/></>,
  logout: <><path d="M10 17l5-5-5-5M15 12H3"/><path d="M13 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/></>,
  star: <path d="m12 2 3 6 6.5 1-4.7 4.6 1.1 6.4-5.9-3.1L6.1 20l1.1-6.4L2.5 9 9 8z"/>,
  trash: <><path d="M3 6h18M8 6V4h8v2m3 0-1 15H6L5 6m5 4v7m4-7v7"/></>,
  menu: <path d="M4 6h16M4 12h16M4 18h16"/>,
};

export function Icon({ name, size = 20, ...props }: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name]}</svg>;
}
