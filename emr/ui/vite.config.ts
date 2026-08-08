// Official Vite React and Tailwind integrations:
// https://vite.dev/guide/ and https://tailwindcss.com/docs/installation/using-vite
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import {defineConfig} from "vite";

export default defineConfig({
  base: "/_mystack/ui/emr/",
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../src/mystack/emr/static/ui",
    emptyOutDir: true,
    sourcemap: true,
  },
});
