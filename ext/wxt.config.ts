import { defineConfig } from 'wxt';

// See https://wxt.dev/api/config.html
export default defineConfig({
  modules: ['@wxt-dev/module-vue'],
  outDir: "output",
  manifest: {
    host_permissions: [
      "https://ixspy.com/*",
      "https://user.ixspy.com/*"
    ],
    permissions: ["storage"]
  }
});
