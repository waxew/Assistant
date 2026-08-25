import { apiError, readBootstrapData } from "../../../lib/server-data";

export async function GET() {
  try {
    return Response.json(await readBootstrapData());
  } catch (error) {
    return apiError(error, "دریافت اطلاعات با خطا روبه‌رو شد.");
  }
}
