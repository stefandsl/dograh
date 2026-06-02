import { StackHandler } from "@stackframe/stack";
import { getTranslations } from "next-intl/server";

import { getAuthProvider } from "@/lib/auth/config";

import { BackButton } from "./BackButton";

export default async function Handler(props: unknown) {
  const t = await getTranslations("pages.handler");
  const authProvider = await getAuthProvider();

  if (authProvider === "local") {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <h1>{t("localAuthMode")}</h1>
        <p>{t("localAuthDisabled")}</p>
      </div>
    );
  }

  // Lazily import the real StackServerApp only when needed
  const { getStackServerApp } = await import("@/lib/auth/server");
  const app = await getStackServerApp();

  return (
    <div className="flex flex-col h-screen">
      <BackButton />
      <div className="flex-1 overflow-auto">
        <StackHandler
          fullPage
          app={app!}
          routeProps={props}
        />
      </div>
    </div>
  );
}
