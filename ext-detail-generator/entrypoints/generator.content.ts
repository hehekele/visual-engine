import { createApp } from 'vue';
import VisualGenerator from '@/components/VisualGenerator.vue';

export default defineContentScript({
  matches: [
    '*://detail.1688.com/offer/*.html*',
    '*://*.1688.com/offer/*.html*'
  ],
  cssInjectionMode: 'ui',
  async main(ctx) {
    console.log('[Visual Generator] Content script loaded on:', window.location.href);

    const ui = await createShadowRootUi(ctx, {
      name: 'visual-generator-ui',
      position: 'overlay',
      anchor: 'body',
      append: 'last',
      onMount: (container) => {
        console.log('[Visual Generator] Mounting Vue app to shadow root');
        const app = createApp(VisualGenerator);
        app.mount(container);
        return app;
      },
      onRemove: (app) => {
        app?.unmount();
      },
    });

    ui.mount();
    console.log('[Visual Generator] UI mounted');
  },
});
