import { redirect } from "next/navigation";

/** The alerts list lives at /compliance; /compliance/alerts (the parent of every alert page) goes there. */
export default function AlertsIndex() {
  redirect("/compliance");
}
