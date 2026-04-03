import { redirect } from "next/navigation";

/** 默认落地：论文列表 */
export default function RootPage() {
  redirect("/papers");
}
