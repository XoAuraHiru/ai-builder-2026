import { redirect } from "next/navigation";

/** The leads list lives at /advisor; /advisor/leads (the parent of every lead page) goes there. */
export default function LeadsIndex() {
  redirect("/advisor");
}
