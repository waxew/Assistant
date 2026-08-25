CREATE TABLE `appointments` (
	`id` text PRIMARY KEY NOT NULL,
	`customer_id` text NOT NULL,
	`staff_id` text NOT NULL,
	`service_id` text NOT NULL,
	`date` text NOT NULL,
	`time` text NOT NULL,
	`status` text DEFAULT 'confirmed' NOT NULL,
	`notes` text DEFAULT '' NOT NULL,
	`reminder_sms` integer DEFAULT true NOT NULL,
	`reminder_hours` integer DEFAULT 24 NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	FOREIGN KEY (`customer_id`) REFERENCES `customers`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`staff_id`) REFERENCES `staff`(`id`) ON UPDATE no action ON DELETE restrict,
	FOREIGN KEY (`service_id`) REFERENCES `services`(`id`) ON UPDATE no action ON DELETE restrict
);
--> statement-breakpoint
CREATE INDEX `appointments_date_idx` ON `appointments` (`date`);--> statement-breakpoint
CREATE INDEX `appointments_customer_idx` ON `appointments` (`customer_id`);--> statement-breakpoint
CREATE TABLE `automations` (
	`id` text PRIMARY KEY NOT NULL,
	`kind` text NOT NULL,
	`enabled` integer DEFAULT false NOT NULL,
	`message` text DEFAULT '' NOT NULL,
	`offset_hours` integer DEFAULT 24 NOT NULL,
	`updated_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `automations_kind_unique` ON `automations` (`kind`);--> statement-breakpoint
CREATE TABLE `customers` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`phone` text NOT NULL,
	`occupation` text DEFAULT '' NOT NULL,
	`gender` text DEFAULT 'نامشخص' NOT NULL,
	`birth_date` text,
	`group_name` text DEFAULT 'مشتریان معمولی' NOT NULL,
	`referral_source` text DEFAULT 'معرفی دوستان' NOT NULL,
	`notes` text DEFAULT '' NOT NULL,
	`total_visits` integer DEFAULT 0 NOT NULL,
	`total_spent` real DEFAULT 0 NOT NULL,
	`last_visit` text,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `customers_phone_unique` ON `customers` (`phone`);--> statement-breakpoint
CREATE INDEX `customers_name_idx` ON `customers` (`name`);--> statement-breakpoint
CREATE INDEX `customers_group_idx` ON `customers` (`group_name`);--> statement-breakpoint
CREATE TABLE `feedback` (
	`id` text PRIMARY KEY NOT NULL,
	`customer_id` text,
	`score` integer NOT NULL,
	`comment` text DEFAULT '' NOT NULL,
	`visible` integer DEFAULT false NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	FOREIGN KEY (`customer_id`) REFERENCES `customers`(`id`) ON UPDATE no action ON DELETE set null
);
--> statement-breakpoint
CREATE TABLE `message_log` (
	`id` text PRIMARY KEY NOT NULL,
	`kind` text NOT NULL,
	`audience` text NOT NULL,
	`body` text NOT NULL,
	`recipients` integer DEFAULT 0 NOT NULL,
	`status` text DEFAULT 'queued' NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE TABLE `services` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`duration` integer DEFAULT 60 NOT NULL,
	`price` real DEFAULT 0 NOT NULL,
	`staff_id` text,
	`color` text DEFAULT '#7c3aed' NOT NULL,
	`active` integer DEFAULT true NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	FOREIGN KEY (`staff_id`) REFERENCES `staff`(`id`) ON UPDATE no action ON DELETE set null
);
--> statement-breakpoint
CREATE TABLE `staff` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`role` text NOT NULL,
	`phone` text DEFAULT '' NOT NULL,
	`color` text DEFAULT '#7c3aed' NOT NULL,
	`active` integer DEFAULT true NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
