// Vitest configuration reference: https://vitest.dev/config/
import {defineConfig} from "vitest/config";

const configuredTimeout = Number(process.env.MYSTACK_FRONTEND_TEST_TIMEOUT_MS ?? "10000");
if (!Number.isFinite(configuredTimeout) || configuredTimeout <= 0) {
  throw new Error("MYSTACK_FRONTEND_TEST_TIMEOUT_MS must be a positive number");
}

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./ui/tests/setup.ts"],
    include: ["ui/tests/**/*.test.{ts,tsx}", "emr/ui/src/**/*.test.{ts,tsx}", "glue/ui/src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
    testTimeout: configuredTimeout,
    hookTimeout: configuredTimeout,
  },
});
