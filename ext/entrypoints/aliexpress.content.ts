import { createApp } from 'vue';
import AliExpressOverlay from '@/components/AliExpressOverlay.vue';

export default defineContentScript({
  matches: [
    'https://www.aliexpress.us/*', 'https://*.aliexpress.us/*'
  ],
  async main(ctx) {
    console.log('Aliexpress Extension Loaded');

    const ui = await createIntegratedUi(ctx, {
      position: 'inline',
      anchor: 'body',
      append: 'last',
      onMount: (uiContainer) => {
        // Create a wrapper div to ensure styles are applied correctly if needed
        const app = createApp(AliExpressOverlay);
        app.mount(uiContainer);
        return app;
      },
      onRemove: (app) => {
        if (app) {
          app.unmount();
        }
      },
    });

    ui.mount();
  },
});
